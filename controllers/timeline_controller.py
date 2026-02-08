from flask import Blueprint, jsonify, request
from flask_login import login_required
from sqlalchemy.orm import joinedload
from extensions import db
from models.room import Room
from models.booking import Booking
from models.booking_room import BookingRoom
from models.customer import Customer
from datetime import datetime, timedelta
import random
import string

timeline_bp = Blueprint('timeline', __name__)

# --- HÀM HELPER: TẠO MÃ BOOKING ---
def generate_booking_code():
    date_str = datetime.now().strftime('%y%m%d')
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    random_str = ''.join(random.choices(chars, k=4))
    return f"BK-{date_str}-{random_str}"

# =======================================================
# 1. LẤY DỮ LIỆU TIMELINE (Cho Vis.js)
# =======================================================
@timeline_bp.route('/api/bookings/timeline', methods=['GET'])
@login_required
def get_timeline():
    # A. GROUP: Danh sách phòng
    rooms = Room.query.all()
    groups = []
    for r in rooms:
        # Hiển thị số phòng và loại phòng bên cột trái
        content = f'<strong>{r.room_number}</strong> <br><span style="color:#888; font-size:11px">{r.room_type}</span>'
        groups.append({'id': r.id, 'content': content, 'room_number': r.room_number})

    # B. ITEMS: Danh sách BookingRoom (Chi tiết xếp phòng)
    # Load kèm Booking và Customer để lấy tên hiển thị
    booking_rooms = BookingRoom.query.options(
        joinedload(BookingRoom.booking).joinedload(Booking.customer)
    ).all()
    
    items = []
    now = datetime.now() 

    for br in booking_rooms:
        b = br.booking # Object Booking cha
        if not b: continue

        # 1. XÁC ĐỊNH THỜI GIAN START / END
        # Nếu đã check-in thì dùng giờ thực tế, chưa thì dùng giờ dự kiến
        start = br.check_in_actual if br.check_in_actual else br.check_in_expected
        end = br.check_out_actual if br.check_out_actual else br.check_out_expected

        # Fallback nếu dữ liệu lỗi
        if not start: start = now
        if not end: end = start + timedelta(hours=1)

        # Logic hiển thị: Nếu đang ở (checked_in), kéo dài thanh timeline đến hiện tại
        # để lễ tân thấy khách đang ở quá giờ hay chưa
        if br.status == 'checked_in':
            if end < now:
                end = now 
        
        # 2. XỬ LÝ MÀU SẮC & GIAO DIỆN
        style = ''
        content = ''
        cus_name = b.customer.name if (b.customer) else "Khách lẻ"
        
        # --- CASE 1: ĐÃ HỦY ---
        if br.status == 'cancelled':
            style = 'background: repeating-linear-gradient(45deg, #e74c3c, #e74c3c 10px, #c0392b 10px, #c0392b 20px); color: white; opacity: 0.6; text-decoration: line-through;'
            content = f'<i class="fas fa-ban"></i> {cus_name}'
        
        # --- CASE 2: ĐÃ TRẢ PHÒNG (Lịch sử) ---
        elif br.status == 'checked_out':
            style = 'background: #bdc3c7; border-color: #95a5a6; color: #555;'
            content = f'<i class="fas fa-check"></i> {cus_name}'
            
        # --- CASE 3: ĐANG Ở HOẶC SẮP ĐẾN ---
        else:
            # A. KHÁCH THEO GIỜ (HOURLY) -> Tông màu TÍM
            if br.rental_type == 'hourly':
                if br.status == 'checked_in':
                    style = 'background: #9b59b6; border: 2px solid #8e44ad; color: white;' # Đang ở
                    icon = '<i class="fas fa-clock"></i>'
                else: 
                    style = 'background: #d7bde2; border: 1px dashed #8e44ad; color: #4a235a;' # Đặt trước
                    icon = '<i class="far fa-clock"></i>'

            # B. KHÁCH THEO NGÀY (DAILY) -> Tông màu XANH / CAM
            else: 
                if br.status == 'checked_in':
                    style = 'background: #e67e22; border: 2px solid #d35400; color: white;' # Đang ở
                    icon = '<i class="fas fa-bed"></i>'
                else:
                    style = 'background: #3498db; border: 1px solid #2980b9; color: white;' # Đặt trước
                    icon = '<i class="far fa-calendar-check"></i>'

            # Cảnh báo quá giờ (Chỉ áp dụng khi khách đang ở)
            is_overstay = False
            if br.status == 'checked_in' and br.check_out_expected and br.check_out_expected < now:
                is_overstay = True
                style += ' box-shadow: 0 0 8px red; border: 2px solid red;'
                content = f'{icon} <strong>{cus_name}</strong> <span class="badge bg-danger">Quá giờ</span>'
            else:
                content = f'{icon} {cus_name}'

        # Tooltip hiển thị khi rê chuột
        money_info = f"Giá: {br.price_snapshot:,.0f}"
        
        items.append({
            'id': br.id,          # ID này là ID của BookingRoom
            'group': br.room_id,  # Thuộc dòng của phòng nào
            'start': start.isoformat(),
            'end': end.isoformat(),
            'content': content,
            'style': f'{style} border-radius: 4px; font-size: 12px;',
            'title': f"Khách: {cus_name}",
            'editable': (br.status != 'checked_out' and br.status != 'cancelled') 
        })

    return jsonify({'groups': groups, 'items': items})


# =======================================================
# 2. LẤY CHI TIẾT 1 BOOKING ROOM (Cho Modal Edit)
# =======================================================
@timeline_bp.route('/api/bookings/<int:id>', methods=['GET'])
@login_required
def get_booking_detail(id):
    # ID ở đây là id của BookingRoom (item trên timeline)
    br = BookingRoom.query.get_or_404(id)
    
    # Trả về dữ liệu gộp từ BookingRoom + Booking cha + Customer
    customer = br.booking.customer
    
    data = {
        'id': br.id, # BookingRoom ID
        'booking_id': br.booking_id,
        'room_id': br.room_id,
        'booking_code': br.booking.code,
        'customer_name': customer.name if customer else "Khách lẻ",
        'customer_phone': customer.phone if customer else "",
        'status': br.status,
        'rental_type': br.rental_type,
        
        # Format ngày giờ cho input datetime-local của HTML (YYYY-MM-DDTHH:MM)
        'check_in': (br.check_in_actual or br.check_in_expected).strftime('%Y-%m-%dT%H:%M'),
        'check_out': (br.check_out_actual or br.check_out_expected).strftime('%Y-%m-%dT%H:%M'),
        
        'price': float(br.price_snapshot or 0),
        'deposit': float(br.booking.prepaid_amount or 0),
        'note': br.booking.note
    }
    return jsonify(data)


# =======================================================
# 3. TẠO BOOKING MỚI (Từ Modal Tạo trên Timeline)
# =======================================================
@timeline_bp.route('/api/bookings/create', methods=['POST'])
@login_required
def create_booking():
    try:
        data = request.get_json()
        # 1. Validate Phòng
        room_number = int(data.get('room_number'))
        room = Room.query.filter_by(room_number=room_number).first()
        if not room: return jsonify({'success': False, 'msg': 'Phòng không tồn tại'})

        # 2. Xử lý Khách hàng
        phone = data.get('phone')
        name = data.get('name')
        customer = Customer.query.filter_by(phone=phone).first()
        if not customer and phone:
            customer = Customer(name=name, phone=phone)
            db.session.add(customer)
            db.session.flush() # Lấy ID
            
        customer_id = customer.id if customer else None

        # 3. Tạo Booking (Đơn tổng)
        code = generate_booking_code()
        new_booking = Booking(
            code=code,
            customer_id=customer_id,
            total_amount=0, # Sẽ tính sau
            prepaid_amount=int(data.get('deposit') or 0),
            note=data.get('note'),
            created_at=datetime.now()
        )
        db.session.add(new_booking)
        db.session.flush() # Lấy booking_id

        # 4. Tạo BookingRoom (Chi tiết phòng)
        check_in_dt = datetime.strptime(data.get('check_in'), '%Y-%m-%dT%H:%M')
        check_out_dt = datetime.strptime(data.get('check_out'), '%Y-%m-%dT%H:%M')
        status = data.get('status') # 'booked' hoặc 'checked_in'
        r_type = data.get('rental_type') or 'daily'
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
            rental_type=data.get('rental_type'),
            price_snapshot=0, # Cần có logic tính giá ở đây nếu muốn
            status=status,
            check_in_expected=check_in_dt,
            check_out_expected=check_out_dt
        )

        # Nếu check-in ngay
        if status == 'checked_in':
            new_br.check_in_actual = datetime.now()
            room.status = 'occupied'
            # (Có thể thêm logic tạo BookingService mặc định ở đây nếu cần)

        db.session.add(new_br)
        db.session.commit()
        
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

        br = BookingRoom.query.get(br_id)
        if not br: return jsonify({'success': False, 'msg': 'Không tìm thấy booking'})

        # 1. Xử lý đổi phòng (Nếu user kéo sang dòng khác)
        if new_room_id and int(new_room_id) != br.room_id:
            old_room = Room.query.get(br.room_id)
            new_room = Room.query.get(new_room_id)
            
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
            new_start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            # Nếu đang active thì update check_in_actual, chưa thì update expected
            if br.status == 'checked_in':
                br.check_in_actual = new_start
            else:
                br.check_in_expected = new_start

        if end_str:
            new_end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            if br.status == 'checked_out':
                br.check_out_actual = new_end
            else:
                br.check_out_expected = new_end

        db.session.commit()
        return jsonify({'success': True, 'msg': 'Cập nhật thành công'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': str(e)})