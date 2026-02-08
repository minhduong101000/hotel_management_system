from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from extensions import db
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta
from sqlalchemy import and_, or_

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
from controllers.pricing_service import get_effective_room_prices

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

@room_bp.route('/api/rooms')
@login_required
def get_rooms():
    """
    API cung cấp dữ liệu cho Sơ đồ phòng (Dashboard).
    Bao gồm: Trạng thái, Giá, Thông tin khách (Full info).
    """
    try:
        # 1. Lấy tất cả phòng
        rooms = Room.query.all()
        
        now = datetime.now()
        limit_time = now + timedelta(hours=24) 

        # 2. Lấy danh sách phòng ĐANG CÓ KHÁCH (Status = 'checked_in')
        # --- TỐI ƯU QUERY: Load luôn Booking VÀ Customer để tránh N+1 ---
        active_booking_rooms = BookingRoom.query.options(
            joinedload(BookingRoom.booking).joinedload(Booking.customer) 
        ).filter(
            BookingRoom.status == 'checked_in' 
        ).all()
        
        active_map = {br.room_id: br for br in active_booking_rooms}

        # 3. Lấy danh sách phòng SẮP CÓ KHÁCH (Booked)
        # Cũng nên load customer để hiển thị ai sắp đến
        upcoming_booking_rooms = BookingRoom.query.options(
             joinedload(BookingRoom.booking).joinedload(Booking.customer)
        ).filter(
            BookingRoom.status == 'booked', 
            BookingRoom.check_in_expected >= now,
            BookingRoom.check_in_expected <= limit_time
        ).all()
        
        upcoming_map = {}
        for br in upcoming_booking_rooms:
            if br.room_id not in upcoming_map:
                upcoming_map[br.room_id] = br

        # 4. Tổng hợp dữ liệu
        rooms_list = []
        count_occupied = 0
        count_dirty = 0
        
        for r in rooms:
            # Gọi service tính giá (giữ nguyên logic cũ)
            current_prices = get_effective_room_prices(r, now)

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
                
                room_data['rental_type'] = br.rental_type
                
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

            # --- CASE B: Sắp có khách ---
            elif r.status == 'available':
                if r.id in upcoming_map:
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
    
    room = Room.query.filter(Room.room_number == room_number_val).first()
    
    if room:
        room.clean_status = 'cleaned' 
        
        # Chỉ chuyển sang 'available' nếu KHÔNG có khách đang ở
        is_occupied = db.session.query(BookingRoom).filter(
            BookingRoom.room_id == room.id,
            BookingRoom.status == 'checked_in' 
        ).first()

        if not is_occupied and room.status != 'maintenance':
            room.status = 'available'
            
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
        available_rooms = Room.query.filter(
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