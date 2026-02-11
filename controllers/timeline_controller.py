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
            'booking_id': br.booking_id,
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
    
# ========================================================
# 5. API HỦY PHÒNG (CANCEL) & HOÀN TIỀN
# ========================================================
@timeline_bp.route('/api/bookings/cancel', methods=['POST'])
@login_required
def cancel_booking():
    try:
        data = request.get_json()
        booking_id = data.get('booking_id')
        is_force_majeure = data.get('is_force_majeure', False)
        
        # --- THÊM DÒNG NÀY: Lấy % hoàn tiền từ client gửi lên ---
        # Nếu không gửi thì mặc định là 0
        refund_percent_input = float(data.get('refund_percent', 0)) 
        
        # 1. Tìm Booking
        booking = Booking.query.get(booking_id)
        if not booking:
            return jsonify({'success': False, 'msg': 'Không tìm thấy đơn đặt phòng.'})

        booking_rooms = BookingRoom.query.filter_by(booking_id=booking.id).all()

        # 2. Tính toán tiền hoàn lại (Refund Logic - ĐÃ SỬA)
        deposit = float(booking.prepaid_amount or 0)
        refund_amount = 0
        final_percent = 0

        if deposit > 0:
            if is_force_majeure:
                final_percent = 100
                refund_amount = deposit
                reason = "Hủy do bất khả kháng (Hoàn 100% cọc)"
            else:
                # Dùng số % từ frontend gửi lên
                final_percent = refund_percent_input
                refund_amount = deposit * (final_percent / 100)
                reason = f"Hủy thường (Hoàn {final_percent}% cọc)"
        else:
            reason = "Hủy phòng (Không có cọc)"

        # 3. Cập nhật Database
        
        # A. Cập nhật trạng thái BookingRoom -> cancelled
        for br in booking_rooms:
            # Chỉ hủy những phòng chưa check-in hoặc đang book
            if br.status != 'cancelled': 
                br.status = 'cancelled'
                
                # B. Trả lại trạng thái "Sẵn sàng" cho Room thực tế
                room = Room.query.get(br.room_id)
                if room:
                    room.status = 'available'

        # C. Cập nhật Note
        refund_str = "{:,.0f}".format(refund_amount).replace(',', '.')
        current_note = booking.note or ""
        
        # Ghi log rõ ràng hơn
        booking.note = f"{current_note} | [ĐÃ HỦY: {reason}. Hoàn tiền: {refund_str} đ]".strip()

        db.session.commit()

        return jsonify({
            'success': True, 
            'msg': f'Đã hủy phòng thành công.\nLý do: {reason}\nSố tiền cần hoàn trả khách: {refund_str} đ'
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error canceling: {e}")
        return jsonify({'success': False, 'msg': str(e)})

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
            booking = Booking.query.get(booking_id)
            if booking and new_deposit is not None:
                booking.prepaid_amount = float(new_deposit)
                # db.session.add(booking) # (SQLAlchemy tự track, không cần add lại nếu chỉ sửa)

        # ---------------------------------------------------------
        # BƯỚC 2: CẬP NHẬT CHI TIẾT PHÒNG (BookingRoom)
        # ---------------------------------------------------------
        br = None
        
        # Ưu tiên tìm đích danh dòng BookingRoom cần sửa
        if booking_room_id:
            br = BookingRoom.query.get(booking_room_id)
        
        # Fallback: Nếu frontend cũ không gửi booking_room_id thì mới tìm theo booking_id
        elif booking_id:
            br = BookingRoom.query.filter_by(booking_id=booking_id).first()

        if not br:
            return jsonify({'success': False, 'msg': 'Không tìm thấy thông tin phòng cần sửa.'})

        # -- Logic đổi phòng --
        old_room_id = br.room_id
        
        # Cập nhật thông tin mới
        br.room_id = new_room_id
        br.status = new_status
        
        # Parse ngày giờ (Cần format chuẩn từ Frontend gửi lên: YYYY-MM-DDTHH:mm)
        if check_in_str:
            # Cắt chuỗi nếu frontend gửi dư giây (VD: 2023-10-10T14:00:00.000Z)
            clean_in = check_in_str.split('.')[0] 
            br.check_in_expected = datetime.strptime(clean_in, '%Y-%m-%dT%H:%M')
            
        if check_out_str:
            clean_out = check_out_str.split('.')[0]
            br.check_out_expected = datetime.strptime(clean_out, '%Y-%m-%dT%H:%M')

        # ---------------------------------------------------------
        # BƯỚC 3: XỬ LÝ TRẠNG THÁI PHÒNG (Room Status)
        # ---------------------------------------------------------
        
        # A. Nếu thay đổi phòng (VD: Đổi từ phòng 101 -> 102)
        if old_room_id != new_room_id:
            # 1. Trả phòng cũ về 'available' (nếu nó đang occupied bởi đơn này)
            room_old = Room.query.get(old_room_id)
            if room_old and room_old.status == 'occupied':
                # Chỉ set available nếu đơn này đang chiếm giữ
                # (Logic kỹ hơn là check xem có booking nào khác đang check-in không, nhưng tạm làm đơn giản)
                room_old.status = 'available'
            
            # 2. Set phòng mới thành status tương ứng
            room_new = Room.query.get(new_room_id)
            if room_new:
                if new_status == 'checked_in':
                    room_new.status = 'occupied'
                # Nếu chỉ là booked thì không đổi status room (vẫn để available cho khách khác book giờ khác)

        # B. Nếu không đổi phòng, chỉ đổi trạng thái (VD: Check-in)
        else:
            room_current = Room.query.get(new_room_id)
            if room_current:
                if new_status == 'checked_in':
                    room_current.status = 'occupied'
                    # Cập nhật giờ check-in thực tế nếu chưa có
                    if not br.check_in_actual:
                        br.check_in_actual = datetime.now()
                
                elif new_status == 'cancelled' or new_status == 'checked_out':
                    room_current.status = 'available'

        db.session.commit()
        return jsonify({'success': True, 'msg': 'Cập nhật thành công!'})

    except Exception as e:
        db.session.rollback()
        print(f"Error updating: {e}")
        import traceback
        traceback.print_exc() # In lỗi chi tiết ra terminal để debug
        return jsonify({'success': False, 'msg': f'Lỗi server: {str(e)}'})