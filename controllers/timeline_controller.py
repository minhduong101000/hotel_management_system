from services.tenant_service import tenant_query, tenant_get_or_404
from flask import Blueprint, jsonify, request, g
from models.hotel import Hotel
from services.notification_service import send_booking_notification
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from extensions import db
from models.room import Room
from models.booking import Booking
from models.booking_room import BookingRoom
from models.booking_service import BookingService
from models.customer import Customer
from models.service import Service
from models.business_operation import BusinessOperation
from models.booking_reschedule import BookingReschedule
from datetime import datetime, timedelta
import random
import string
from services.pricing_service import get_effective_room_prices, calculate_raw_hourly_fee, get_nightly_price_breakdown
from services import payment_service, audit_service

timeline_bp = Blueprint('timeline', __name__)


def _normalize_dt(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    # Frontend/vis.js may send timezone-aware ISO; DB values are typically naive.
    return dt.replace(tzinfo=None) if getattr(dt, 'tzinfo', None) is not None else dt


def _effective_range(br: BookingRoom) -> tuple[datetime | None, datetime | None]:
    start = br.check_in_actual or br.check_in_expected
    end = br.check_out_actual or br.check_out_expected
    return _normalize_dt(start), _normalize_dt(end)


def _has_room_time_conflict(
    *,
    room_id: int,
    start_dt: datetime,
    end_dt: datetime,
    exclude_booking_room_id: int | None = None,
) -> bool:
    """Return True if another active booking overlaps [start_dt, end_dt) in the same room."""
    start_dt = _normalize_dt(start_dt)
    end_dt = _normalize_dt(end_dt)

    if not start_dt or not end_dt:
        return False

    q = tenant_query(BookingRoom).filter(
        BookingRoom.room_id == room_id,
        BookingRoom.status.in_(['booked', 'checked_in']),
    )
    if exclude_booking_room_id is not None:
        q = q.filter(BookingRoom.id != int(exclude_booking_room_id))

    candidates = q.all()
    now = datetime.now()

    for row in candidates:
        row_start, row_end = _effective_range(row)

        if row.status == 'checked_in' and not row_end:
            # A checked-in row with no end is treated as occupying the room.
            return True

        if not row_start or not row_end:
            continue

        if row.status == 'checked_in' and row_end < now:
            # Overstay: treat end as now.
            row_end = now

        # Standard overlap test: [a,b) overlaps [c,d) iff a < d and b > c
        if row_start < end_dt and row_end > start_dt:
            return True

    return False

# --- HÀM HELPER: TẠO MÃ BOOKING ---
def generate_booking_code():
    date_str = datetime.now().strftime('%y%m%d')
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    random_str = ''.join(random.choices(chars, k=4))
    return f"BK-{date_str}-{random_str}"


def _has_active_booking_conflict(room_id, check_in_dt, check_out_dt):
    """Trả về True nếu phòng có booking active bị giao thời gian."""
    active_rows = tenant_query(BookingRoom).filter(
        BookingRoom.room_id == room_id,
        BookingRoom.status.in_(['booked', 'checked_in'])
    ).all()

    now = datetime.now()
    for row in active_rows:
        row_start = row.check_in_actual or row.check_in_expected
        row_end = row.check_out_actual or row.check_out_expected

        # Nếu phòng đang check-in mà thiếu mốc end thì coi như đang bận.
        if row.status == 'checked_in' and not row_end:
            return True

        if not row_start or not row_end:
            continue

        if row.status == 'checked_in' and row_end < now:
            # Trường hợp khách ở quá giờ dự kiến: vẫn coi là bận đến hiện tại.
            row_end = now

        if row_start < check_out_dt and row_end > check_in_dt:
            return True

    return False


def _estimate_booking_amount(room, rental_type, check_in_dt, check_out_dt):
    """Ước tính tiền phòng tại thời điểm tạo booking để kiểm tra tỷ lệ cọc."""
    prices = get_effective_room_prices(room, check_in_dt)

    if rental_type == 'hourly':
        hourly_total, _, _ = calculate_raw_hourly_fee(check_in_dt, check_out_dt, prices)
        return min(hourly_total, prices['p_night'])

    nights = (check_out_dt.date() - check_in_dt.date()).days
    if nights < 1:
        nights = 1
    return nights * prices['p_night']


def _is_valid_deposit_by_ratio(deposit_amount, estimated_amount):
    """Cọc hợp lệ khi đúng 50% hoặc 100% tổng tiền ước tính."""
    if estimated_amount <= 0:
        return False

    expected_50 = round(float(estimated_amount) * 0.5, 2)
    expected_100 = round(float(estimated_amount), 2)
    dep = round(float(deposit_amount), 2)
    return abs(dep - expected_50) <= 1 or abs(dep - expected_100) <= 1

# =======================================================
# 1. LẤY DỮ LIỆU TIMELINE (Cho Vis.js)
# =======================================================
@timeline_bp.route('/api/bookings/timeline', methods=['GET'])
@login_required
def get_timeline():
    # A. GROUP: Danh sách phòng
    rooms = tenant_query(Room).all()
    groups = []
    for r in rooms:
        # Hiển thị số phòng và loại phòng bên cột trái
        content = f'<strong>{r.room_number}</strong> <br><span style="color:#888; font-size:11px">{r.room_type}</span>'
        groups.append({'id': r.id, 'content': content, 'room_number': r.room_number})

    # B. ITEMS: Danh sách BookingRoom (Chi tiết xếp phòng)
    # Load kèm Booking và Customer để lấy tên hiển thị
    booking_rooms = tenant_query(BookingRoom).options(
        joinedload(BookingRoom.booking).joinedload(Booking.customer)
    ).all()
    
    # PRE-COMPUTE: Đếm số phòng của từng Booking để xác định đoàn/lẻ
    from sqlalchemy import func
    booking_room_counts = dict(
        db.session.query(BookingRoom.booking_id, func.count(BookingRoom.id))
        .group_by(BookingRoom.booking_id).all()
    )
    
    items = []
    now = datetime.now() 

    for br in booking_rooms:
        b = br.booking # Object Booking cha
        if not b: continue

        is_finalized = (br.status in ['checked_out', 'cancelled']) or (b.status in ['completed', 'cancelled'])
        if is_finalized:
            # Ẩn booking đã hoàn tất/hủy khỏi timeline theo yêu cầu vận hành.
            continue

        # Xác định khách đoàn hay khách lẻ
        room_count = booking_room_counts.get(br.booking_id, 1)
        is_group = room_count > 1

        # 1. XÁC ĐỊNH THỜI GIAN START / END
        start = br.check_in_actual if br.check_in_actual else br.check_in_expected
        end = br.check_out_actual if br.check_out_actual else br.check_out_expected

        if not start: start = now
        if not end: end = start + timedelta(hours=1)

        if br.status == 'checked_in':
            if end < now:
                end = now 
        
        # 2. XỬ LÝ MÀU SẮC & GIAO DIỆN (Bảng màu mới - Hài hòa)
        style = ''
        content = ''
        css_class = ''
        cus_name = b.customer.name if (b.customer) else "Khách lẻ"
        group_badge = f'<span class="tl-group-badge" title="Đoàn {room_count} phòng"><i class="fas fa-users"></i></span> ' if is_group else ''
        
        # --- CASE 1: ĐÃ HỦY ---
        if br.status == 'cancelled':
            css_class = 'tl-cancelled'
            content = f'{group_badge}<i class="fas fa-ban"></i> <span class="tl-name">{cus_name}</span>'
        
        # --- CASE 2: ĐÃ TRẢ PHÒNG (Lịch sử) ---
        elif br.status == 'checked_out':
            css_class = 'tl-checked-out'
            content = f'{group_badge}<i class="fas fa-check-circle"></i> <span class="tl-name">{cus_name}</span>'
            
        # --- CASE 3: ĐANG Ở HOẶC SẮP ĐẾN ---
        else:
            # A. KHÁCH THEO GIỜ (HOURLY)
            if br.rental_type == 'hourly':
                if br.status == 'checked_in':
                    css_class = 'tl-hourly-active'
                    icon = '<i class="fas fa-clock"></i>'
                else: 
                    css_class = 'tl-hourly-booked'
                    icon = '<i class="far fa-clock"></i>'

            # B. KHÁCH THEO NGÀY (DAILY)
            else: 
                if br.status == 'checked_in':
                    css_class = 'tl-daily-active'
                    icon = '<i class="fas fa-bed"></i>'
                else:
                    css_class = 'tl-daily-booked'
                    icon = '<i class="far fa-calendar-check"></i>'

            # Cảnh báo quá giờ
            is_overstay = False
            if br.status == 'checked_in' and br.check_out_expected and br.check_out_expected < now:
                is_overstay = True
                css_class += ' tl-overstay'
                content = f'{group_badge}{icon} <strong class="tl-name">{cus_name}</strong> <span class="tl-badge-danger">Quá giờ!</span>'
            else:
                content = f'{group_badge}{icon} <span class="tl-name">{cus_name}</span>'

        # Tooltip chi tiết khi rê chuột
        tooltip_type = "Đoàn" if is_group else "Lẻ"
        tooltip_rooms = f" ({room_count} phòng)" if is_group else ""
        money_info = f"Giá: {br.price_snapshot:,.0f}" if br.price_snapshot else ""
        tooltip = f"Khách: {cus_name}\nLoại: {tooltip_type}{tooltip_rooms}\nMã: {b.code}"
        if money_info:
            tooltip += f"\n{money_info}"
        if br.status == 'cancelled' and b.note:
            note_upper = b.note.upper()
            if 'HOÀN' in note_upper and '%' in b.note:
                tooltip += "\n" + b.note[-160:]
        
        items.append({
            'id': br.id,
            'booking_id': br.booking_id,
            'group': br.room_id,
            'start': start.isoformat(),
            'end': end.isoformat(),
            'content': content,
            'className': css_class,
            'title': tooltip,
            'editable': (not is_finalized),
            'is_group': is_group,
            'status': br.status,
            'booking_status': b.status,
            'is_finalized': is_finalized
        })

    return jsonify({'groups': groups, 'items': items})


# =======================================================
# 2. LẤY CHI TIẾT 1 BOOKING ROOM (Cho Modal Edit)
# =======================================================
@timeline_bp.route('/api/bookings/<int:id>', methods=['GET'])
@login_required
def get_booking_detail(id):
    # ID ở đây là id của BookingRoom (item trên timeline)
    br = tenant_get_or_404(BookingRoom, id)

    if br.status in ['checked_out', 'cancelled'] or (br.booking and br.booking.status in ['completed', 'cancelled']):
        return jsonify({
            'success': False,
            'locked': True,
            'msg': 'Booking này đã hoàn tất/hủy và đã khóa chỉnh sửa trên timeline.'
        }), 409
    
    # =========================================================
    # LOGIC MỚI: Đếm số phòng của Booking này để xác định đoàn/lẻ
    room_count = tenant_query(BookingRoom).filter_by(booking_id=br.booking_id).count()
    is_group = True if room_count > 1 else False
    # =========================================================

    # Trả về dữ liệu gộp từ BookingRoom + Booking cha + Customer
    customer = br.booking.customer
    booking = br.booking

    room_services = tenant_query(BookingService).filter_by(
        booking_id=br.booking_id,
        room_id=br.room_id
    ).all()

    services_payload = []
    for item in room_services:
        unit_price = float(item.price_at_booking or (item.service.price if item.service else 0))
        qty = int(item.quantity or 0)
        services_payload.append({
            'service_id': item.service_id,
            'name': item.service.name if item.service else 'Dich vu',
            'quantity': qty,
            'price': unit_price,
            'total': unit_price * qty
        })

    room_lines = []
    for room_row in booking.rooms:
        room_lines.append({
            'booking_room_id': room_row.id,
            'room_id': room_row.room_id,
            'room_number': room_row.room.room_number if room_row.room else room_row.room_id,
            'status': room_row.status,
            'check_in': (room_row.check_in_actual or room_row.check_in_expected).strftime('%Y-%m-%d %H:%M') if (room_row.check_in_actual or room_row.check_in_expected) else '',
            'check_out': (room_row.check_out_actual or room_row.check_out_expected).strftime('%Y-%m-%d %H:%M') if (room_row.check_out_actual or room_row.check_out_expected) else '',
            'deposit': float(room_row.room_deposit_amount or 0),
        })
    
    data = {
        'id': br.id, # BookingRoom ID
        'booking_id': br.booking_id,
        'booking_code': br.booking.code,
        'booking_status': booking.status,
        'payment_status': booking.payment_status,
        'room_id': br.room_id,
        'room_number': br.room.room_number if br.room else '',
        'customer_name': customer.name if customer else "Khách lẻ",
        'customer_phone': customer.phone if customer else "",
        'customer_cccd': customer.cccd if customer else "",
        'customer_address': customer.address if customer else "",
        'status': br.status,
        'rental_type': br.rental_type,
        
        # Format ngày giờ cho input datetime-local của HTML (YYYY-MM-DDTHH:MM)
        'check_in': (br.check_in_actual or br.check_in_expected).strftime('%Y-%m-%dT%H:%M'),
        'check_out': (br.check_out_actual or br.check_out_expected).strftime('%Y-%m-%dT%H:%M'),
        
        'price': float(br.price_snapshot or 0),
        'deposit': float(br.room_deposit_amount or 0),
        'booking_total_amount': float(booking.total_amount or 0),
        'booking_prepaid_amount': float(booking.prepaid_amount or 0),
        'note': booking.note,
        'created_at': booking.created_at.strftime('%d/%m/%Y %H:%M') if booking.created_at else '',

        'room_services': services_payload,
        'rooms': room_lines,

        # --- DỮ LIỆU ĐỂ BẬT TẮT NÚT Ở FRONTEND ---
        'is_group': is_group,
        'room_count': room_count
    }
    return jsonify(data)


@timeline_bp.route('/api/bookings/services-catalog', methods=['GET'])
@login_required
def get_services_catalog_for_booking():
    services = tenant_query(Service).order_by(Service.name.asc()).all()
    return jsonify([
        {
            'id': s.id,
            'name': s.name,
            'price': float(s.price or 0),
        }
        for s in services
    ])


# =======================================================
# 3. TẠO BOOKING MỚI (Từ Modal Tạo trên Timeline)
# =======================================================
@timeline_bp.route('/api/bookings/create', methods=['POST'])
@login_required
def create_booking():
    try:
        data = request.get_json()
        # 1. Validate Phòng
        room_number = str(data.get('room_number', '')).strip()
        if not room_number:
            return jsonify({'success': False, 'msg': 'Thiếu số phòng.'})

        # Lock the room row on databases that support SELECT ... FOR UPDATE.
        # SQLite ignores this clause, while MySQL serializes competing booking requests.
        room = tenant_query(Room).filter_by(room_number=room_number).with_for_update().first()
        if not room: return jsonify({'success': False, 'msg': 'Phòng không tồn tại'})

        check_in_dt = datetime.strptime(data.get('check_in'), '%Y-%m-%dT%H:%M')
        check_out_dt = datetime.strptime(data.get('check_out'), '%Y-%m-%dT%H:%M')
        if check_in_dt >= check_out_dt:
            return jsonify({'success': False, 'msg': 'Giờ check-out phải sau giờ check-in.'})

        # Phòng bảo trì thì luôn không cho tạo booking.
        if room.status == 'maintenance':
            return jsonify({'success': False, 'msg': f'Phòng {room.room_number} đang bảo trì, không thể tạo booking.'})

        # Chặn trùng lịch với booking active (booked/checked_in).
        if _has_active_booking_conflict(room.id, check_in_dt, check_out_dt):
            return jsonify({'success': False, 'msg': f'Phòng {room.room_number} đã có lịch trong khoảng thời gian này.'}), 409

        status = (data.get('status') or 'booked').strip()
        if status not in ['booked', 'checked_in']:
            return jsonify({'success': False, 'msg': 'Trạng thái booking không hợp lệ.'})

        r_type = (data.get('rental_type') or 'daily').strip()
        if r_type not in ['daily', 'hourly']:
            return jsonify({'success': False, 'msg': 'Loại thuê không hợp lệ.'})

        now = datetime.now()
        if status == 'checked_in':
            max_early = check_in_dt - timedelta(hours=3)
            if now < max_early:
                return jsonify({'success': False, 'msg': 'Chỉ được vào ở ngay sớm tối đa 3 giờ trước giờ booking.'})

            # Chặn cứng theo dữ liệu active dù trạng thái phòng có thể lệch.
            occupied_row = tenant_query(BookingRoom).filter(
                BookingRoom.room_id == room.id,
                BookingRoom.status == 'checked_in'
            ).first()
            if occupied_row:
                return jsonify({'success': False, 'msg': f'Phòng {room.room_number} đang có khách, không thể vào ở ngay.'})

        estimated_amount = _estimate_booking_amount(room, r_type, check_in_dt, check_out_dt)
        deposit_amount = float(data.get('deposit') or 0)
        if not _is_valid_deposit_by_ratio(deposit_amount, estimated_amount):
            return jsonify({'success': False, 'msg': 'Tiền cọc bắt buộc phải đúng 50% hoặc 100% tổng tiền phòng dự kiến.'})

        # 2. Xử lý Khách hàng
        phone = str(data.get('phone', '')).strip()
        name = str(data.get('name', '')).strip()
        cccd = str(data.get('cccd', '')).strip() or None
        address = str(data.get('address', '')).strip() or None
        
        customer = None
        if phone:
            matching_customers = tenant_query(Customer).filter_by(phone=phone).all()
            selected_customer_id = data.get('customer_id')
            if selected_customer_id:
                customer = next(
                    (candidate for candidate in matching_customers if candidate.id == int(selected_customer_id)),
                    None,
                )
                if not customer:
                    return jsonify({'success': False, 'msg': 'Khách được chọn không hợp lệ.'}), 404
            elif len(matching_customers) == 1:
                customer = matching_customers[0]
            elif len(matching_customers) > 1:
                return jsonify({
                    'success': False,
                    'code': 'customer_phone_ambiguous',
                    'msg': 'Có nhiều khách dùng cùng SĐT; cần chọn đúng khách.',
                    'candidates': [
                        {'id': candidate.id, 'name': candidate.name, 'phone': candidate.phone, 'cccd': candidate.cccd}
                        for candidate in matching_customers
                    ],
                }), 409

            if not customer:
                customer = Customer(name=name or "Khách lẻ", phone=phone, cccd=cccd, address=address)
                db.session.add(customer)
                db.session.flush()
            else:
                if cccd and not customer.cccd: customer.cccd = cccd
                if address and not customer.address: customer.address = address
                if name and customer.name in ["", "Khách lẻ"]: customer.name = name
                db.session.flush()
        else:
            customer = Customer(name=name or "Khách lẻ", phone=None, cccd=cccd, address=address)
            db.session.add(customer)
            db.session.flush()
            
        customer_id = customer.id if customer else None

        # 3. Tạo Booking (Đơn tổng)
        code = generate_booking_code()
        new_booking = Booking(
            code=code,
            customer_id=customer_id,
            total_amount=0, # Sẽ tính sau
            prepaid_amount=deposit_amount,
            note=data.get('note'),
            created_at=datetime.now()
        )
        db.session.add(new_booking)
        db.session.flush() # Lấy booking_id
        
        # --- GHI NHẬN TIỀN CỌC VÀO SỔ QUỸ TỰ ĐỘNG ---
        if deposit_amount > 0:
            payment_service.record_deposit(
                booking_id=new_booking.id,
                amount=deposit_amount,
                payment_method='cash',
                note=f"Tiền cọc đặt phòng {room.room_number}",
                created_at=datetime.now(),
                flush=True,
            )

        # 4. Tạo BookingRoom (Chi tiết phòng)
        price_snapshot = 0
        if r_type == 'hourly':
            # Nếu thuê giờ: Lấy giá giờ đầu
            price_snapshot = room.price_initial_block or 0
        else:
            # Nếu thuê ngày (hoặc đêm): Lấy giá ngày
            price_snapshot = room.price_per_night or 0

        new_br = BookingRoom(
            booking_id=new_booking.id,
            room_id=room.id,
            rental_type=r_type,
            price_snapshot=price_snapshot,
            room_deposit_amount=deposit_amount,
            room_deposit_original=deposit_amount,
            status=status,
            check_in_expected=check_in_dt,
            check_out_expected=check_out_dt
        )
        if r_type == 'daily':
            new_br.price_breakdown_snapshot = [
                {'business_date': line['business_date'].isoformat(), 'amount': float(line['amount'])}
                for line in get_nightly_price_breakdown(room, check_in_dt, check_out_dt)
            ]
        else:
            new_br.hourly_price_snapshot = {
                'initial_hours': int(room.initial_hours or 2),
                'price_initial': float(room.price_initial_block or 0),
                'price_next': float(room.price_next_hour or 0),
                'price_night': float(room.price_per_night or 0),
            }

        # Nếu check-in ngay
        if status == 'checked_in':
            new_br.check_in_actual = datetime.now()
            room.status = 'occupied'
            # (Có thể thêm logic tạo BookingService mặc định ở đây nếu cần)

        db.session.add(new_br)
        db.session.flush()
        audit_service.record_event(
            hotel_id=g.hotel_id,
            actor_user_id=current_user.id,
            action='create_booking',
            entity_type='booking_room',
            entity_id=new_br.id,
            after_data={
                'booking_code': new_booking.code,
                'room_number': room.room_number,
                'status': new_br.status,
                'check_in_expected': new_br.check_in_expected.isoformat(),
                'check_out_expected': new_br.check_out_expected.isoformat(),
                'deposit_amount': float(new_br.room_deposit_amount or 0),
            },
        )
        db.session.commit()

        # --- GỬI EMAIL THÔNG BÁO CHO CHỦ KHÁCH SẠN ---
        try:
            hotel = db.session.get(Hotel, g.hotel_id)
            if hotel:
                send_booking_notification(new_booking, hotel)
        except Exception as mail_err:
            print(f"Error triggering email notification: {mail_err}")
        
        return jsonify({'success': True, 'msg': 'Tạo booking thành công!', 'code': code})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error create booking: {e}")
        return jsonify({'success': False, 'msg': str(e)})


# =======================================================
# 4. CẬP NHẬT (Kéo thả trên Timeline hoặc Sửa Modal)
# =======================================================
@timeline_bp.route('/api/bookings/update_timeline', methods=['POST'])
@login_required
def update_booking_timeline():
    """
    API này dùng khi:
    1. Kéo thả (Drag & Drop) để đổi phòng.
    2. Kéo dãn (Resize) để đổi giờ.
    """
    try:
        data = request.get_json()
        br_id = data.get('id') # ID của item (BookingRoom)
        new_room_id = data.get('group') # ID của group (Room)
        start_str = data.get('start')
        end_str = data.get('end')

        br = tenant_query(BookingRoom).filter_by(id=br_id).first()
        if not br: return jsonify({'success': False, 'msg': 'Không tìm thấy booking'})
        if br.status in ['checked_out', 'cancelled'] or (br.booking and br.booking.status in ['completed', 'cancelled']):
            return jsonify({'success': False, 'msg': 'Booking đã hoàn tất/hủy, không thể chỉnh sửa timeline.'})

        booking = br.booking
        before_data = {
            'room_id': br.room_id,
            'room_number': br.room.room_number,
            'check_in_expected': br.check_in_expected.isoformat() if br.check_in_expected else None,
            'check_out_expected': br.check_out_expected.isoformat() if br.check_out_expected else None,
            'status': br.status,
        }

        # Pre-compute target room/time to validate overlap before mutating.
        target_room_id = int(new_room_id) if new_room_id else int(br.room_id)
        cur_start, cur_end = _effective_range(br)
        target_start = cur_start
        target_end = cur_end

        # 1. Xử lý đổi phòng (Nếu user kéo sang dòng khác)
        if new_room_id and int(new_room_id) != br.room_id:
            old_room = tenant_query(Room).filter_by(id=br.room_id).first()
            new_room = tenant_query(Room).filter_by(id=new_room_id).first()
            
            # Chỉ cho đổi nếu phòng mới còn trống (Logic đơn giản check status hiện tại)
            # (Nâng cao: Cần check trùng lịch trong khoảng thời gian đó)
            if br.status == 'checked_in' and new_room.status == 'occupied':
                 return jsonify({'success': False, 'msg': 'Phòng mới đang có khách!'})

            # Update ID phòng
            br.room_id = new_room_id
            
            # Nếu đang check-in -> Đổi status 2 phòng
            if br.status == 'checked_in':
                old_room.status = 'available'
                new_room.status = 'occupied'

        # 2. Xử lý đổi giờ (Check-in / Check-out)
        # Vis.js gửi format ISO, cần parse cẩn thận
        if start_str:
            # Cắt chuỗi để bỏ timezone nếu cần, hoặc dùng dateutil
            # Ví dụ đơn giản: lấy 19 ký tự đầu (YYYY-MM-DDTHH:MM:SS)
            new_start = _normalize_dt(datetime.fromisoformat(start_str.replace("Z", "+00:00")))
            # Nếu đang active thì update check_in_actual, chưa thì update expected
            if br.status == 'checked_in':
                br.check_in_actual = new_start
            else:
                br.check_in_expected = new_start
            target_start = new_start

        if end_str:
            new_end = _normalize_dt(datetime.fromisoformat(end_str.replace("Z", "+00:00")))
            if br.status == 'checked_out':
                br.check_out_actual = new_end
            else:
                br.check_out_expected = new_end
            target_end = new_end

        if target_start and target_end and target_end <= target_start:
            return jsonify({'success': False, 'msg': 'Giờ check-out phải sau giờ check-in.'})

        # Validate no overlap for active bookings.
        if br.status in ['booked', 'checked_in'] and target_start and target_end:
            if _has_room_time_conflict(
                room_id=target_room_id,
                start_dt=target_start,
                end_dt=target_end,
                exclude_booking_room_id=br.id,
            ):
                return jsonify({'success': False, 'msg': 'Trùng lịch: Phòng đã có booking trong khoảng thời gian này.'})

        # Cập nhật thông tin khách hàng nếu có
        customer = tenant_query(Customer).filter_by(id=booking.customer_id).first()
        if customer:
            new_name = data.get('customer_name', '').strip()
            new_cccd = data.get('customer_cccd', '').strip() or None
            new_addr = data.get('customer_address', '').strip() or None
            
            if new_name and customer.name in ["", "Khách lẻ"]: customer.name = new_name
            if new_cccd and not customer.cccd: customer.cccd = new_cccd
            if new_addr and not customer.address: customer.address = new_addr
        
        audit_service.record_event(
            hotel_id=g.hotel_id,
            actor_user_id=current_user.id,
            action='update_booking_timeline',
            entity_type='booking_room',
            entity_id=br.id,
            before_data=before_data,
            after_data={
                'room_id': br.room_id,
                'room_number': br.room.room_number,
                'check_in_expected': br.check_in_expected.isoformat() if br.check_in_expected else None,
                'check_out_expected': br.check_out_expected.isoformat() if br.check_out_expected else None,
                'status': br.status,
            },
        )
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Cập nhật thành công'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': str(e)})
    
# ========================================================
# 5. DỜI LỊCH BOOKING
# ========================================================
@timeline_bp.route('/api/bookings/reschedule', methods=['POST'])
@login_required
def reschedule_booking():
    data = request.get_json(silent=True) or {}
    reason = str(data.get('reason') or '').strip()
    if not reason:
        return jsonify({'success': False, 'msg': 'Cần nhập lý do dời lịch.'}), 400
    try:
        br = tenant_query(BookingRoom).filter_by(id=int(data.get('booking_room_id'))).with_for_update().first()
        room = tenant_query(Room).filter_by(id=int(data.get('room_id'))).with_for_update().first()
        check_in = _normalize_dt(datetime.fromisoformat(str(data.get('check_in')).replace('Z', '+00:00')))
        check_out = _normalize_dt(datetime.fromisoformat(str(data.get('check_out')).replace('Z', '+00:00')))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'msg': 'Dữ liệu dời lịch không hợp lệ.'}), 400
    if not br or not room:
        return jsonify({'success': False, 'msg': 'Không tìm thấy booking hoặc phòng.'}), 404
    if br.status != 'booked' or check_out <= check_in or room.status == 'maintenance':
        return jsonify({'success': False, 'msg': 'Booking hoặc phòng không phù hợp để dời lịch.'}), 409
    if _has_room_time_conflict(room_id=room.id, start_dt=check_in, end_dt=check_out, exclude_booking_room_id=br.id):
        return jsonify({'success': False, 'msg': 'Phòng mới đã có lịch trong khoảng thời gian này.'}), 409
    price_mode = data.get('price_mode', 'keep')
    if price_mode not in ('keep', 'reprice'):
        return jsonify({'success': False, 'msg': 'Chế độ giá không hợp lệ.'}), 400
    before = {'room_id': br.room_id, 'check_in': br.check_in_expected.isoformat(), 'check_out': br.check_out_expected.isoformat()}
    history = BookingReschedule(hotel_id=br.hotel_id, booking_room_id=br.id, old_room_id=br.room_id, new_room_id=room.id, old_check_in=br.check_in_expected, old_check_out=br.check_out_expected, new_check_in=check_in, new_check_out=check_out, reason=reason, price_mode=price_mode, actor_user_id=current_user.id)
    br.room_id, br.check_in_expected, br.check_out_expected = room.id, check_in, check_out
    if price_mode == 'reprice':
        if br.rental_type == 'daily':
            br.price_breakdown_snapshot = [{'business_date': x['business_date'].isoformat(), 'amount': float(x['amount'])} for x in get_nightly_price_breakdown(room, check_in, check_out)]
        elif br.rental_type == 'hourly':
            current_prices = get_effective_room_prices(room, check_in)
            br.hourly_price_snapshot = {
                'initial_hours': current_prices['initial_hours'],
                'price_initial': current_prices['p_initial'],
                'price_next': current_prices['p_next'],
                'price_night': current_prices['p_night'],
            }
    db.session.add(history)
    audit_service.record_event(hotel_id=br.hotel_id, actor_user_id=current_user.id, action='reschedule_booking_keep_price' if price_mode == 'keep' else 'reschedule_booking_reprice', entity_type='booking_room', entity_id=br.id, before_data=before, after_data={'room_id': room.id, 'check_in': check_in.isoformat(), 'check_out': check_out.isoformat(), 'reason': reason, 'price_mode': price_mode})
    db.session.commit()
    return jsonify({'success': True, 'msg': 'Đã dời lịch booking.'})

# ========================================================
# 6. API HỦY PHÒNG (CANCEL) & HOÀN TIỀN
# ========================================================
@timeline_bp.route('/api/bookings/cancel', methods=['POST'])
@login_required
def cancel_booking():
    try:
        data = request.get_json(silent=True) or {}
        booking_id_raw = data.get('booking_id')
        booking_room_id_raw = data.get('booking_room_id')
        is_force_majeure = data.get('is_force_majeure', False)
        cancellation_reason = str(data.get('reason', '')).strip()
        if not cancellation_reason:
            return jsonify({'success': False, 'msg': 'Cần nhập lý do hủy/hoàn tiền.'}), 400
        try:
            refund_percent_input = float(data.get('refund_percent', 0))
        except (TypeError, ValueError):
            return jsonify({'success': False, 'msg': 'Tỷ lệ hoàn tiền không hợp lệ.'}), 400

        # 1. Tìm đơn tương ứng (ưu tiên chi tiết phòng nếu có)
        booking = None
        target_br = None
        
        if booking_room_id_raw:
            try:
                booking_room_id = int(booking_room_id_raw)
            except (TypeError, ValueError):
                return jsonify({'success': False, 'msg': 'Mã phòng đặt không hợp lệ.'}), 400
            target_br = tenant_query(BookingRoom).filter_by(id=booking_room_id).first()
            if target_br:
                booking = target_br.booking
        elif booking_id_raw:
            try:
                booking_id = int(booking_id_raw)
            except (TypeError, ValueError):
                return jsonify({'success': False, 'msg': 'Mã đơn đặt không hợp lệ.'}), 400
            booking = tenant_query(Booking).filter_by(id=booking_id).first()
        else:
            return jsonify({'success': False, 'msg': 'Cần chọn đơn đặt hoặc phòng đặt để hủy.'}), 400

        if not booking:
            return jsonify({'success': False, 'msg': 'Không tìm thấy thông tin đơn đặt phòng.'}), 404

        operation_entity_id = target_br.id if target_br else booking.id
        operation_key = f'cancel:{operation_entity_id}'
        existing_operation = tenant_query(BusinessOperation).filter_by(operation_key=operation_key).first()
        if existing_operation:
            return jsonify({'success': False, 'msg': 'Yêu cầu hủy đã được xử lý.', 'operation_key': operation_key}), 409
        operation = BusinessOperation(
            hotel_id=booking.hotel_id,
            operation_key=operation_key,
            action='cancel_booking',
            entity_type='booking_room' if target_br else 'booking',
            entity_id=operation_entity_id,
        )
        db.session.add(operation)
        db.session.flush()

        # 2. Xác định danh sách phòng cần hủy
        # Nếu gửi booking_room_id -> Chỉ hủy 1 phòng đó
        # Nếu chỉ gửi booking_id -> Hủy toàn bộ phòng trong đơn
        rooms_to_cancel = [target_br] if target_br else tenant_query(BookingRoom).filter_by(booking_id=booking.id).all()
        if any(room.status == 'checked_out' for room in rooms_to_cancel if room):
            return jsonify({'success': False, 'msg': 'Không thể hủy phòng đã trả.'}), 409
        if any(room.status == 'checked_in' for room in rooms_to_cancel if room):
            return jsonify({'success': False, 'msg': 'Phòng đã nhận chỉ có thể checkout.'}), 409
        rooms_to_cancel = [r for r in rooms_to_cancel if r and r.status != 'cancelled']

        if not rooms_to_cancel:
            return jsonify({'success': False, 'msg': 'Các phòng đã ở trạng thái hủy trước đó.'}), 409
        
        # Kiểm tra xem có phải là hủy nốt phòng cuối cùng của đơn không (để xử lý cọc)
        total_non_cancelled = tenant_query(BookingRoom).filter(
            BookingRoom.booking_id == booking.id,
            BookingRoom.status != 'cancelled'
        ).count()
        
        cancelling_count = len(rooms_to_cancel)
        is_final_cancellation = (total_non_cancelled <= cancelling_count)

        # 3. Tính toán tiền hoàn lại dựa trên cọc của từng phòng đang hủy
        deposit = float(booking.prepaid_amount or 0)  # Cọc còn lại của đơn tại thời điểm hủy
        refund_amount = 0
        reason = ""
        refund_percent_effective = 0.0
        fee_percent_effective = 0.0

        active_rooms_before = tenant_query(BookingRoom).filter(
            BookingRoom.booking_id == booking.id,
            BookingRoom.status != 'cancelled'
        ).all()

        def _room_weight(room_item):
            price = float(room_item.price_snapshot or 0)
            return price if price > 0 else 1.0

        total_weight = sum(_room_weight(r) for r in active_rooms_before)
        cancel_weight = sum(_room_weight(r) for r in rooms_to_cancel)

        if total_weight <= 0:
            total_weight = float(len(active_rooms_before) or 1)
        if cancel_weight <= 0:
            cancel_weight = float(len(rooms_to_cancel) or 1)

        # Ưu tiên dùng cọc theo từng phòng. Nếu dữ liệu cũ chưa có thì fallback theo tỷ trọng giá phòng.
        room_deposit_pool = sum(float(r.room_deposit_amount or 0) for r in active_rooms_before)
        allocated_by_room = {}

        for br in rooms_to_cancel:
            current_room_deposit = float(br.room_deposit_amount or 0)
            if current_room_deposit > 0:
                allocated_by_room[br.id] = round(current_room_deposit, 2)
            else:
                base_pool = room_deposit_pool if room_deposit_pool > 0 else deposit
                if base_pool > 0 and total_weight > 0:
                    allocated_by_room[br.id] = round(base_pool * (_room_weight(br) / total_weight), 2)
                else:
                    allocated_by_room[br.id] = 0.0

        allocated_deposit = round(sum(allocated_by_room.values()), 2)

        if allocated_deposit > 0:
            if is_force_majeure:
                refund_percent_effective = 100.0
                reason = "Hủy phòng (Bất khả kháng - Hoàn 100% cọc phân bổ)"
            else:
                refund_percent_effective = max(0.0, min(100.0, refund_percent_input))
                reason = f"Hủy {cancelling_count} phòng (Hoàn {refund_percent_effective:.0f}% cọc phân bổ theo giá phòng)"

            refund_amount = round(allocated_deposit * (refund_percent_effective / 100), 2)
            fee_percent_effective = max(0.0, 100.0 - refund_percent_effective)
        else:
            reason = f"Hủy {cancelling_count} phòng (Không có cọc để xử lý)"

        cancellation_fee = round(max(0.0, allocated_deposit - refund_amount), 2)
        room_labels = ', '.join([r.room.room_number if r.room else str(r.room_id) for r in rooms_to_cancel])

        # 4. Thực hiện cập nhật trạng thái
        for br in rooms_to_cancel:
            br.status = 'cancelled'
            br.check_out_actual = datetime.now()
            if br.final_amount is None:
                br.final_amount = 0

            room_allocated_deposit = float(allocated_by_room.get(br.id, 0) or 0)
            room_refund_share = round(room_allocated_deposit * (refund_percent_effective / 100), 2)
            room_fee_share = round(max(0.0, room_allocated_deposit - room_refund_share), 2)

            br.final_amount = room_fee_share
            br.room_deposit_original = room_allocated_deposit
            br.cancellation_refund_percent = refund_percent_effective
            br.cancellation_fee_percent = fee_percent_effective
            br.cancellation_refund_amount = room_refund_share
            br.room_deposit_amount = 0

            # Trả lại trạng thái cho phòng vật lý
            room = tenant_query(Room).filter_by(id=br.room_id).first()
            if room:
                room.status = 'available'

        # 5. Ghi log và Xử lý Tiền (Refund/Fee)
        current_note = booking.note or ""
        refund_str = "{:,.0f}".format(refund_amount).replace(',', '.')
        allocated_str = "{:,.0f}".format(allocated_deposit).replace(',', '.')
        if allocated_deposit > 0:
            cancel_detail = (
                f"{reason}. Phòng: {room_labels}. Cọc phân bổ: {allocated_str} đ. "
                f"Hoàn tiền: {refund_str} đ ({refund_percent_effective:.0f}%), "
                f"Phí hủy: {fee_percent_effective:.0f}%"
            )
        else:
            cancel_detail = f"{reason}. Hoàn tiền: {refund_str} đ"

        new_note_content = f"{current_note} | [HỦY: {cancel_detail}]".strip()
        booking.note = new_note_content[:990] # Cắt bớt để tránh lỗi DataTooLong (Database limit)

        # --- LOGIC MỚI: Ghi nhận vào Sổ Quỹ ---
        # 1. Nếu có HOÀN TIỀN thực tế -> Ghi một dòng âm vào Payment
        if refund_amount > 0:
            payment_service.record_refund(
                booking_id=booking.id,
                refund_amount=refund_amount,
                payment_method='cash',
                note=(
                    f"Hoàn cọc khi hủy phòng {room_labels} đơn {booking.code} "
                    f"(Cọc phân bổ {allocated_str} đ, hoàn {refund_percent_effective:.0f}%)"
                ),
                created_at=datetime.now(),
            )

        # 2. Nếu có GIỮ LẠI một phần tiền cọc (Phí hủy)
        if cancellation_fee > 0:
            payment_service.record_cancellation_fee(
                booking_id=booking.id,
                amount=0,
                payment_method='cash',
                note=(
                    f"Ghi nhận phí hủy phòng {room_labels}: {cancellation_fee:,.0f} đ "
                    f"({fee_percent_effective:.0f}% cọc phân bổ, trích từ tiền cọc)"
                ),
                created_at=datetime.now(),
            )

        # Đã xử lý xong nhóm phòng hủy -> cọc còn lại = tổng cọc của các phòng chưa hủy.
        remaining_room_deposit = db.session.query(db.func.coalesce(db.func.sum(BookingRoom.room_deposit_amount), 0)).filter(
            BookingRoom.booking_id == booking.id,
            BookingRoom.status != 'cancelled'
        ).scalar()
        booking.prepaid_amount = max(0.0, round(float(remaining_room_deposit or 0), 2))

        # Cập nhật tổng doanh thu booking theo toàn bộ phòng đã finalize.
        all_rooms = tenant_query(BookingRoom).filter_by(booking_id=booking.id).all()
        booking.total_amount = sum(float(r.final_amount or 0) for r in all_rooms)
        booking.updated_at = datetime.now()

        # Nếu là lần hủy cuối cùng, đánh dấu đơn là 'cancelled' để phân biệt với 'completed' (đã trả phòng)
        if is_final_cancellation:
            booking.status = 'cancelled'

        operation.status = 'completed'
        operation.completed_at = datetime.now()

        for cancelled_room in rooms_to_cancel:
            audit_service.record_event(
                hotel_id=booking.hotel_id,
                actor_user_id=current_user.id,
                action='cancel_booking',
                entity_type='booking_room',
                entity_id=cancelled_room.id,
                operation_key=f'cancel:{cancelled_room.id}',
                before_data={'status': 'booked'},
                after_data={
                    'status': 'cancelled',
                    'reason': cancellation_reason,
                    'refund_percent': refund_percent_effective,
                    'refund_amount': float(cancelled_room.cancellation_refund_amount or 0),
                },
            )

        db.session.commit()

        return jsonify({
            'success': True, 
            'msg': (
                f'Hủy phòng thành công.\n'
                f'Lý do: {reason}\n'
                f'Cọc phân bổ cho phòng hủy: {allocated_str} đ\n'
                f'Tỷ lệ hoàn: {refund_percent_effective:.0f}%\n'
                f'Tỷ lệ phí hủy: {fee_percent_effective:.0f}%\n'
                f'Hoàn cọc: {refund_str} đ'
            ),
            'data': {
                'refund_percent': refund_percent_effective,
                'fee_percent': fee_percent_effective,
                'refund_amount': refund_amount,
                'allocated_deposit': allocated_deposit,
                'deposit': deposit,
                'is_final_cancellation': is_final_cancellation
            }
        })

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'msg': f'Lỗi hệ thống: {str(e)}'})

# ========================================================
# 6. API CẬP NHẬT THÔNG TIN (UPDATE)
# ========================================================
@timeline_bp.route('/api/bookings/update', methods=['POST'])
@login_required
def update_booking():
    try:
        data = request.get_json()
        
        # 1. Lấy tham số quan trọng
        booking_room_id = data.get('booking_room_id') # <--- QUAN TRỌNG: ID của dòng chi tiết
        booking_id = data.get('booking_id')           # ID của đơn tổng
        
        # Lấy dữ liệu cần sửa
        new_room_id = int(data.get('room_id'))
        new_status = data.get('status')
        new_deposit = data.get('deposit')
        
        check_in_str = data.get('check_in')
        check_out_str = data.get('check_out')

        # ---------------------------------------------------------
        # BƯỚC 1: CẬP NHẬT ĐƠN TỔNG (Booking)
        # (Cập nhật tiền cọc chung cho cả đoàn nếu có thay đổi)
        # ---------------------------------------------------------
        if booking_id:
            booking = tenant_query(Booking).filter_by(id=booking_id).first()

        # ---------------------------------------------------------
        # BƯỚC 2: CẬP NHẬT CHI TIẾT PHÒNG (BookingRoom)
        # ---------------------------------------------------------
        br = None
        
        # Ưu tiên tìm đích danh dòng BookingRoom cần sửa
        if booking_room_id:
            br = tenant_query(BookingRoom).filter_by(id=booking_room_id).first()
        
        # Fallback: Nếu frontend cũ không gửi booking_room_id thì mới tìm theo booking_id
        elif booking_id:
            br = tenant_query(BookingRoom).filter_by(booking_id=booking_id).first()

        if not br:
            return jsonify({'success': False, 'msg': 'Không tìm thấy thông tin phòng cần sửa.'})
        if br.status in ['checked_out', 'cancelled'] or (br.booking and br.booking.status in ['completed', 'cancelled']):
            return jsonify({'success': False, 'msg': 'Booking đã hoàn tất/hủy, không thể chỉnh sửa.'})

        if new_deposit is not None:
            room_deposit = max(0.0, float(new_deposit))
            old_deposit = float(br.room_deposit_amount or 0)
            
            # --- LOGIC MỚI: Ghi nhận nộp thêm cọc vào sổ quỹ ---
            if room_deposit > old_deposit:
                diff = room_deposit - old_deposit
                payment_service.record_deposit(
                    booking_id=br.booking_id,
                    amount=diff,
                    payment_method='cash',
                    note=f"Nộp thêm cọc cho phòng {br.room.room_number if br.room else br.room_id} (Cập nhật đơn)",
                    created_at=datetime.now(),
                )

            br.room_deposit_amount = room_deposit
            if br.status not in ['cancelled', 'checked_out']:
                br.room_deposit_original = room_deposit

        # -- Logic đổi phòng --
        old_room_id = br.room_id
        
        # Parse ngày giờ (Cần format chuẩn từ Frontend gửi lên: YYYY-MM-DDTHH:mm)
        parsed_check_in = None
        parsed_check_out = None
        if check_in_str:
            clean_in = check_in_str.split('.')[0]
            parsed_check_in = datetime.strptime(clean_in, '%Y-%m-%dT%H:%M')

        if check_out_str:
            clean_out = check_out_str.split('.')[0]
            parsed_check_out = datetime.strptime(clean_out, '%Y-%m-%dT%H:%M')

        # Validate overlap BEFORE applying room/time changes.
        if new_status in ['booked', 'checked_in']:
            candidate_start = parsed_check_in if parsed_check_in else (br.check_in_actual or br.check_in_expected)
            candidate_end = parsed_check_out if parsed_check_out else (br.check_out_actual or br.check_out_expected)
            candidate_start = _normalize_dt(candidate_start)
            candidate_end = _normalize_dt(candidate_end)

            if candidate_start and candidate_end and candidate_end <= candidate_start:
                return jsonify({'success': False, 'msg': 'Giờ check-out phải sau giờ check-in.'})

            if candidate_start and candidate_end:
                if _has_room_time_conflict(
                    room_id=new_room_id,
                    start_dt=candidate_start,
                    end_dt=candidate_end,
                    exclude_booking_room_id=br.id,
                ):
                    return jsonify({'success': False, 'msg': 'Trùng lịch: Phòng đã có booking trong khoảng thời gian này.'})

        # Cập nhật thông tin mới
        br.room_id = new_room_id
        br.status = new_status

        if parsed_check_in:
            br.check_in_expected = parsed_check_in
        if parsed_check_out:
            br.check_out_expected = parsed_check_out

        # ---------------------------------------------------------
        # BƯỚC 3: XỬ LÝ TRẠNG THÁI PHÒNG (Room Status)
        # ---------------------------------------------------------
        
        # A. Nếu thay đổi phòng (VD: Đổi từ phòng 101 -> 102)
        if old_room_id != new_room_id:
            # 1. Trả phòng cũ về 'available' (nếu nó đang occupied bởi đơn này)
            room_old = tenant_query(Room).filter_by(id=old_room_id).first()
            if room_old and room_old.status == 'occupied':
                # Chỉ set available nếu đơn này đang chiếm giữ
                # (Logic kỹ hơn là check xem có booking nào khác đang check-in không, nhưng tạm làm đơn giản)
                room_old.status = 'available'
            
            # 2. Set phòng mới thành status tương ứng
            room_new = tenant_query(Room).filter_by(id=new_room_id).first()
            if room_new:
                if new_status == 'checked_in':
                    room_new.status = 'occupied'
                # Nếu chỉ là booked thì không đổi status room (vẫn để available cho khách khác book giờ khác)

        # B. Nếu không đổi phòng, chỉ đổi trạng thái (VD: Check-in)
        else:
            room_current = tenant_query(Room).filter_by(id=new_room_id).first()
            if room_current:
                if new_status == 'checked_in':
                    room_current.status = 'occupied'
                    # Cập nhật giờ check-in thực tế nếu chưa có
                    if not br.check_in_actual:
                        br.check_in_actual = datetime.now()
                
                elif new_status == 'cancelled' or new_status == 'checked_out':
                    room_current.status = 'available'

        # Đồng bộ cọc booking theo tổng cọc các phòng chưa hủy.
        booking_scope_id = booking_id if booking_id else br.booking_id
        if booking_scope_id:
            booking_scope = tenant_query(Booking).filter_by(id=booking_scope_id).first()
            if booking_scope:
                remain_deposit = db.session.query(db.func.coalesce(db.func.sum(BookingRoom.room_deposit_amount), 0)).filter(
                    BookingRoom.booking_id == booking_scope.id,
                    BookingRoom.status != 'cancelled'
                ).scalar()
                booking_scope.prepaid_amount = float(remain_deposit or 0)

        db.session.commit()
        return jsonify({'success': True, 'msg': 'Cập nhật thành công!'})

    except Exception as e:
        db.session.rollback()
        print(f"Error updating: {e}")
        import traceback
        traceback.print_exc() # In lỗi chi tiết ra terminal để debug
        return jsonify({'success': False, 'msg': f'Lỗi server: {str(e)}'})
