from services.tenant_service import current_hotel_id, tenant_get_or_404, tenant_query
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from extensions import db
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
from sqlalchemy import and_, func, or_

# ====================================================
# 1. IMPORT MODELS (Đúng cấu trúc tách file)
# ====================================================
from models.room import Room
from models.booking import Booking
from models.booking_room import BookingRoom
# from models.customer import Customer # Import nếu cần dùng trực tiếp đối tượng Customer

# ====================================================
# 2. IMPORT SERVICE (Logic tính giá)
# ====================================================
from services.pricing_service import get_effective_room_prices_bulk
from services import audit_service, booking_quote_service
from services.room_configuration_service import (
    RoomConfigurationValidationError,
    room_audit_snapshot,
    serialize_room_settings,
    validate_room_update_payload,
    validate_room_create_payload,
)
from decorators import room_structure_required

room_bp = Blueprint('room', __name__)

# --- VIEW ROUTES ---
@room_bp.route('/dashboard/room-map')
@login_required
def map_view():
    return render_template('rooms/map.html')

@room_bp.route('/timeline-view')
@login_required
def timeline_view():
    return render_template('rooms/timeline.html')

# --- API ROUTES ---

@room_bp.route('/api/settings')
@login_required
def get_room_settings():
    active_booking_counts = db.session.query(
        BookingRoom.room_id.label('room_id'),
        func.count(BookingRoom.id).label('active_booking_count'),
    ).filter(
        BookingRoom.hotel_id == current_hotel_id(),
        BookingRoom.status.in_(['booked', 'checked_in']),
    ).group_by(
        BookingRoom.room_id,
    ).subquery()

    room_rows = tenant_query(Room).outerjoin(
        active_booking_counts,
        active_booking_counts.c.room_id == Room.id,
    ).add_columns(
        active_booking_counts.c.active_booking_count,
    ).order_by(
        Room.room_number.asc(),
    ).all()

    rooms = [
        serialize_room_settings(room, active_booking_count)
        for room, active_booking_count in room_rows
    ]

    return jsonify({
        'rooms': rooms,
        'room_types': sorted({room['room_type'] for room in rooms}),
    })


@room_bp.route('/api/settings', methods=['POST'])
@login_required
@room_structure_required
def create_room_setting():
    try:
        values = validate_room_create_payload(request.get_json(silent=True))
    except RoomConfigurationValidationError as exc:
        return jsonify({
            'success': False,
            'error_code': 'validation_error',
            'errors': exc.errors,
        }), 400

    try:
        room = Room(
            hotel_id=current_hotel_id(),
            room_number=values['room_number'],
            room_type=values['room_type'],
            price_per_night=values['price_per_night'],
            price_initial_block=values['price_initial_block'],
            initial_hours=values['initial_hours'],
            price_next_hour=values['price_next_hour'],
            status='maintenance' if values['maintenance'] else 'available',
            clean_status='cleaned',
        )
        db.session.add(room)
        db.session.flush()
        audit_service.record_event(
            hotel_id=room.hotel_id,
            actor_user_id=current_user.id,
            action='create_room',
            entity_type='room',
            entity_id=room.id,
            after_data=room_audit_snapshot(room),
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error_code': 'room_number_conflict',
            'msg': 'Số phòng đã tồn tại trong khách sạn này.',
        }), 409
    except Exception:
        db.session.rollback()
        raise

    return jsonify({
        'success': True,
        'room': serialize_room_settings(room),
    }), 201


def _active_booking_count(room_id):
    return tenant_query(BookingRoom).filter(
        BookingRoom.room_id == room_id,
        BookingRoom.status.in_(['booked', 'checked_in']),
    ).count()


@room_bp.route('/api/settings/<int:room_id>', methods=['PUT'])
@login_required
@room_structure_required
def update_room_setting(room_id):
    room = tenant_get_or_404(Room, room_id)
    try:
        values = validate_room_update_payload(request.get_json(silent=True))
    except RoomConfigurationValidationError as exc:
        return jsonify({
            'success': False,
            'error_code': 'validation_error',
            'errors': exc.errors,
        }), 400

    before_data = room_audit_snapshot(room)
    try:
        room.room_number = values['room_number']
        room.room_type = values['room_type']
        room.price_per_night = values['price_per_night']
        room.price_initial_block = values['price_initial_block']
        room.initial_hours = values['initial_hours']
        room.price_next_hour = values['price_next_hour']
        db.session.flush()
        audit_service.record_event(
            hotel_id=room.hotel_id,
            actor_user_id=current_user.id,
            action='update_room',
            entity_type='room',
            entity_id=room.id,
            before_data=before_data,
            after_data=room_audit_snapshot(room),
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error_code': 'room_number_conflict',
            'msg': 'Số phòng đã tồn tại trong khách sạn này.',
        }), 409
    except Exception:
        db.session.rollback()
        raise

    return jsonify({
        'success': True,
        'room': serialize_room_settings(room, _active_booking_count(room.id)),
    })


@room_bp.route('/api/rooms')
@login_required
def get_rooms():
    """
    API cung cấp dữ liệu cho Sơ đồ phòng (Dashboard).
    Bao gồm: Trạng thái, Giá, Thông tin khách (Full info).
    """
    try:
        # 1. Lấy tất cả phòng
        rooms = tenant_query(Room).all()
        
        now = datetime.now()
        limit_time = now + timedelta(hours=24) 

        # 2. Lấy danh sách phòng ĐANG CÓ KHÁCH (Status = 'checked_in')
        # --- TỐI ƯU QUERY: Load luôn Booking VÀ Customer để tránh N+1 ---
        group_counts_subquery = db.session.query(
            BookingRoom.booking_id.label('booking_id'),
            func.count(BookingRoom.id).label('room_count'),
        ).filter(
            BookingRoom.hotel_id == current_hotel_id(),
        ).group_by(
            BookingRoom.booking_id,
        ).subquery()

        active_booking_rows = tenant_query(BookingRoom).outerjoin(
            group_counts_subquery,
            group_counts_subquery.c.booking_id == BookingRoom.booking_id,
        ).add_columns(
            group_counts_subquery.c.room_count,
        ).options(
            joinedload(BookingRoom.booking).joinedload(Booking.customer) 
        ).filter(
            BookingRoom.status == 'checked_in' 
        ).all()

        active_booking_rooms = [row[0] for row in active_booking_rows]
        group_room_counts = {
            row[0].booking_id: int(row[1] or 1)
            for row in active_booking_rows
        }
        
        active_map = {br.room_id: br for br in active_booking_rooms}

        # 3. Lấy danh sách phòng SẮP CÓ KHÁCH (Booked)
        upcoming_booking_rooms = tenant_query(BookingRoom).options(
             joinedload(BookingRoom.booking).joinedload(Booking.customer)
        ).filter(
            BookingRoom.status == 'booked', 
            BookingRoom.check_in_expected <= limit_time
        ).order_by(BookingRoom.check_in_expected.asc()).all()
        
        upcoming_map = {}
        waiting_map = {} # Những phòng đã quá giờ check-in mà chưa đến
        notices_map = {}
        
        for br in upcoming_booking_rooms:
            if br.room_id not in notices_map:
                notices_map[br.room_id] = []
                
            notice_type = "waiting" if br.check_in_expected < now else "upcoming"
            customer_name = br.booking.customer.name if br.booking and br.booking.customer else "Khách"
            customer_phone = br.booking.customer.phone if br.booking and br.booking.customer else ""
            
            notices_map[br.room_id].append({
                "booking_room_id": br.id,
                "type": notice_type,
                "status": br.status,
                "guest_name": customer_name,
                "guest_phone": customer_phone,
                "check_in_expected": br.check_in_expected.strftime('%Y-%m-%dT%H:%M') if br.check_in_expected else "",
                "check_out_expected": br.check_out_expected.strftime('%Y-%m-%dT%H:%M') if br.check_out_expected else "",
                "deposit": float(br.room_deposit_amount or 0)
            })
            
            if br.check_in_expected < now:
                # Quá giờ check-in dự kiến -> Chờ nhận phòng
                if br.room_id not in waiting_map:
                    waiting_map[br.room_id] = br
            else:
                # Sắp đến (trong vòng 24h)
                if br.room_id not in upcoming_map:
                    upcoming_map[br.room_id] = br

        room_prices = get_effective_room_prices_bulk(rooms, now)

        # 4. Tổng hợp dữ liệu
        rooms_list = []
        count_occupied = 0
        count_dirty = 0
        
        for r in rooms:
            # Gọi service tính giá (giữ nguyên logic cũ)
            current_prices = room_prices[r.id]

            room_data = {
                'id': r.id,
                'number': r.room_number,
                'type': r.room_type,
                'price': current_prices['p_night'], 
                'is_special_price': current_prices['is_special'],
                'formatted_price': "{:,.0f}".format(current_prices['p_night']).replace(",", "."),
                'clean_status': r.clean_status, 
                'status': r.status,
                
                # Default values
                'check_in_time': '',
                'rental_type': None,
                'upcoming': None,
                'waiting': None,  # Mới: Chờ nhận phòng (phòng trống nhưng có khách đặt đã quá giờ)
                'notices': notices_map.get(r.id, []),
                
                # --- THÊM DATA KHÁCH HÀNG ---
                'customer': None,      # Object chứa full info (để popup)
                'customer_name': ''    # String đơn giản (để hiện ngay trên ô)
            }

            # --- CASE A: Đang có khách ---
            if r.id in active_map:
                br = active_map[r.id]
                room_data['status'] = 'occupied' 
                
                if br.check_in_actual:
                    room_data['check_in_time'] = br.check_in_actual.strftime('%H:%M %d/%m')

                if br.check_out_expected:
                    room_data['check_out_expected'] = br.check_out_expected.strftime('%H:%M %d/%m')
                    room_data['is_overdue'] = datetime.now() > br.check_out_expected
                else:
                    room_data['is_overdue'] = False
                
                room_data['rental_type'] = br.rental_type
                room_data['booking_id'] = br.booking_id
                
                # Kiểm tra đoàn: booking có nhiều hơn 1 phòng
                room_count = group_room_counts.get(br.booking_id, 1)
                room_data['is_group'] = room_count > 1
                
                # LẤY INFO KHÁCH HÀNG
                if br.booking and br.booking.customer:
                    cust = br.booking.customer
                    room_data['customer_name'] = cust.name
                    room_data['customer'] = {
                        'id': cust.id,
                        'name': cust.name,
                        'phone': cust.phone or "Trống",
                        'email': cust.email or ""
                    }
                else:
                    room_data['customer_name'] = "Khách vãng lai"
                
                count_occupied += 1

            # --- CASE B: Sắp có khách hoặc Chờ nhận phòng ---
            elif r.status == 'available':
                if r.id in waiting_map:
                    br = waiting_map[r.id]
                    room_data['waiting'] = br.check_in_expected.strftime('%H:%M %d/%m')
                    if br.booking and br.booking.customer:
                         room_data['customer_name'] = f"Chờ: {br.booking.customer.name}"
                
                elif r.id in upcoming_map:
                    br = upcoming_map[r.id]
                    if br.check_in_expected:
                        room_data['upcoming'] = br.check_in_expected.strftime('%H:%M')
                        
                    # Nếu muốn hiện tên khách sắp đến luôn:
                    if br.booking and br.booking.customer:
                         room_data['customer_name'] = f"Sắp đến: {br.booking.customer.name}"

            # --- CASE C: Phòng bẩn ---
            if r.clean_status == 'dirty' and room_data['status'] != 'occupied':
                room_data['status'] = 'dirty'
                count_dirty += 1
            
            rooms_list.append(room_data)

        stats = {
            'total': len(rooms),
            'occupied': count_occupied,
            'dirty': count_dirty,
            'available': max(0, len(rooms) - count_occupied - count_dirty)
        }

        return jsonify({'rooms': rooms_list, 'stats': stats})

    except Exception as e:
        print(f"Lỗi API Get Rooms: {e}")
        return jsonify({'rooms': [], 'stats': {}, 'error': str(e)})
    

@room_bp.route('/api/rooms/clean', methods=['POST'])
@login_required
def clean_room():
    """API xác nhận đã dọn phòng"""
    req_data = request.get_json()
    room_number_val = req_data.get('number')
    
    room = tenant_query(Room).filter(Room.room_number == room_number_val).first()
    
    if room:
        before_data = {'status': room.status, 'clean_status': room.clean_status}
        room.clean_status = 'cleaned' 
        
        # Chỉ chuyển sang 'available' nếu KHÔNG có khách đang ở
        is_occupied = tenant_query(BookingRoom).filter(
            BookingRoom.room_id == room.id,
            BookingRoom.status == 'checked_in' 
        ).first()

        if not is_occupied and room.status != 'maintenance':
            room.status = 'available'

        audit_service.record_event(
            hotel_id=room.hotel_id,
            actor_user_id=current_user.id,
            action='clean_room',
            entity_type='room',
            entity_id=room.id,
            before_data=before_data,
            after_data={'status': room.status, 'clean_status': room.clean_status},
        )
        db.session.commit()
        return jsonify({'success': True, 'msg': f'Phòng {room_number_val} đã dọn sạch!'})
        
    return jsonify({'success': False, 'msg': 'Không tìm thấy phòng.'})


@room_bp.route('/api/rooms/search', methods=['POST'])
@login_required
def search_available_rooms():
    """
    API tìm phòng trống theo khoảng thời gian.
    Trả về giá đã tính toán (theo Rule) cho từng loại phòng.
    """
    try:
        data = request.json
        check_in_str = data.get('check_in')
        check_out_str = data.get('check_out')

        if not check_in_str or not check_out_str:
            return jsonify({'success': False, 'msg': 'Vui lòng chọn đầy đủ ngày!'})

        try:
            # Parse ngày giờ từ frontend
            check_in_date = datetime.strptime(check_in_str[0:10], '%Y-%m-%d')
            check_out_date = datetime.strptime(check_out_str[0:10], '%Y-%m-%d')

            # Giờ mặc định cho search ngày đêm: 14h checkin, 12h checkout
            check_in = check_in_date.replace(hour=14, minute=0, second=0)
            check_out = check_out_date.replace(hour=12, minute=0, second=0)
            
        except ValueError:
            return jsonify({'success': False, 'msg': 'Lỗi định dạng ngày tháng!'})

        if check_in >= check_out:
            return jsonify({'success': False, 'msg': 'Ngày Trả phòng phải sau ngày Nhận phòng!'})

        # --- 1. LỌC PHÒNG BẬN ---
        # Tìm các phòng có booking dính dáng tới khoảng thời gian này
        occupied_room_ids = db.session.query(BookingRoom.room_id).filter(
            BookingRoom.status.in_(['booked', 'checked_in']),
            # Logic trùng lịch: (StartA < EndB) AND (EndA > StartB)
            BookingRoom.check_in_expected < check_out,
            BookingRoom.check_out_expected > check_in
        ).distinct()

        # --- 2. LẤY PHÒNG TRỐNG ---
        available_rooms = tenant_query(Room).filter(
            Room.id.notin_(occupied_room_ids),
            Room.status != 'maintenance'
        ).all()

        # --- 3. GOM NHÓM & TÍNH GIÁ ---
        grouped_data = {}
        for room in available_rooms:
            r_type = room.room_type 
            
            # Gọi Service để xem ngày check-in có giá đặc biệt không
            effective_prices = get_effective_room_prices(room, check_in)
            
            if r_type not in grouped_data:
                grouped_data[r_type] = []
            
            grouped_data[r_type].append({
                'id': room.id,
                'number': room.room_number,
                # Hiển thị giá đã tính toán
                'price': "{:,.0f}".format(effective_prices['p_night']), 
                'status': room.status,
                'is_special': effective_prices['is_special'],
                'rule_name': effective_prices['rule_name']
            })

        return jsonify({'success': True, 'data': grouped_data})

    except Exception as e:
        print(f"Lỗi tìm phòng: {e}")
        return jsonify({'success': False, 'msg': 'Lỗi Server: ' + str(e)})
    
@room_bp.route('/api/bookings/calculate-price', methods=['POST'])
@login_required
def api_calculate_price():
    """
    API Tính nhanh tổng tiền phòng dựa vào ngày giờ và loại hình thuê.
    Dùng để gọi từ giao diện và tự động tính tiền cọc.
    """
    try:
        data = request.json
        room_id = data.get('room_id')
        room_ids = data.get('room_ids') or ([room_id] if room_id else [])
        check_in_str = data.get('check_in')
        check_out_str = data.get('check_out')
        rental_type = data.get('rental_type') # 'daily' hoặc 'hourly'

        if not all([room_ids, check_in_str, check_out_str]):
            return jsonify({'success': False, 'msg': 'Thiếu thông tin tính giá!'})

        # 1. Lấy thông tin phòng từ DB
        normalized_room_ids = [int(value) for value in room_ids]
        rooms = tenant_query(Room).filter(
            Room.id.in_(normalized_room_ids)
        ).order_by(Room.id.asc()).all()
        if len(rooms) != len(set(normalized_room_ids)):
            return jsonify({'success': False, 'msg': 'Không tìm thấy phòng!'})

        # 2. Parse ngày giờ từ frontend (Input type="datetime-local" có dạng YYYY-MM-DDTHH:MM)
        check_in = datetime.strptime(check_in_str[0:16].replace('T', ' '), '%Y-%m-%d %H:%M')
        check_out = datetime.strptime(check_out_str[0:16].replace('T', ' '), '%Y-%m-%d %H:%M')

        if check_in >= check_out:
            return jsonify({'success': False, 'msg': 'Giờ trả phòng phải sau giờ nhận phòng!'})

        if rental_type not in ('daily', 'hourly'):
            return jsonify({'success': False, 'msg': 'Loại thuê không hợp lệ!'})

        quote = booking_quote_service.build_new_booking_quote(
            rooms,
            check_in=check_in,
            check_out=check_out,
            rental_type=rental_type,
        )

        return jsonify({
            'success': True,
            'total_amount': int(booking_quote_service.money(quote['total'])),
            'quote': quote,
            'msg': 'Tính giá thành công'
        })

    except Exception as e:
        print(f"Lỗi API Calculate Price: {e}")
        return jsonify({'success': False, 'msg': f'Lỗi server: {str(e)}'})
