from flask import Blueprint, jsonify, request
from flask_login import login_required
from extensions import db
from datetime import datetime

# =======================================================
# IMPORT MODELS (Đúng cấu trúc)
# =======================================================
from models.room import Room
from models.service import Service
from models.booking_service import BookingService
from models.booking import Booking
from models.booking_room import BookingRoom
from models.customer import Customer

# Import Shared Logic
from controllers.pricing_service import calculate_complex_hotel_bill

booking_bp = Blueprint('booking', __name__)

# =======================================================
# 1. LẤY THÔNG TIN BOOKING SẮP TỚI (Dùng cho Timeline)
# =======================================================
@booking_bp.route('/api/bookings/upcoming/<int:room_id>')
@login_required
def get_upcoming_booking(room_id):
    # Tìm trong bảng BookingRoom thay vì Booking
    booking_room = BookingRoom.query.filter(
        BookingRoom.room_id == room_id,
        BookingRoom.status == 'booked' # Hoặc 'confirmed' tùy enum của bạn
    ).order_by(BookingRoom.check_in_expected.asc()).first()
    
    if booking_room:
        # Lấy thông tin Booking cha
        parent_booking = booking_room.booking
        customer_name = "Khách lẻ"
        if parent_booking and parent_booking.customer:
            customer_name = parent_booking.customer.name

        return jsonify({
            'has_booking': True,
            'booking_id': parent_booking.id if parent_booking else None,
            'customer_name': customer_name,
            'check_in_time': booking_room.check_in_expected.strftime('%H:%M %d/%m'),
            'rental_type': booking_room.rental_type
        })
    return jsonify({'has_booking': False})

# =======================================================
# 2. CHECK-IN 
# =======================================================
@booking_bp.route('/api/rooms/checkin', methods=['POST'])
@login_required
def checkin_room():
    req_data = request.get_json()
    room_number = req_data.get('number')
    # booking_id = req_data.get('booking_id') # Có thể dùng hoặc tìm tự động

    # 1. Kiểm tra phòng
    room = Room.query.filter(Room.room_number == room_number).first()
    if not room: 
        return jsonify({'success': False, 'msg': 'Phòng không tồn tại.'})
    
    if room.clean_status == 'dirty': 
        return jsonify({'success': False, 'msg': 'Phòng đang bẩn, hãy dọn trước!'})

    # 2. Tìm BookingRoom tương ứng (đang ở trạng thái chờ checkin)
    booking_room = BookingRoom.query.filter(
        BookingRoom.room_id == room.id,
        BookingRoom.status == 'booked'
    ).first()

    if booking_room:
        # Cập nhật trạng thái BookingRoom
        booking_room.status = 'checked_in'
        booking_room.check_in_actual = datetime.now() # GIỜ VÀO THỰC TẾ
        
        # Cập nhật trạng thái Phòng
        room.status = 'occupied'
        
        # Cập nhật trạng thái Booking cha (nếu cần logic checkin tất cả)
        if booking_room.booking:
             booking_room.booking.status = 'checked_in' # Hoặc giữ nguyên logic của bạn

        db.session.commit()
        
        customer_name = booking_room.booking.customer.name if (booking_room.booking and booking_room.booking.customer) else "Khách"
        return jsonify({'success': True, 'msg': f'Check-in thành công cho {customer_name}'})
    
    return jsonify({'success': False, 'msg': 'Không tìm thấy đơn đặt phòng hợp lệ cho phòng này.'})

# =======================================================
# 3. XEM TRƯỚC HÓA ĐƠN (Preview Checkout)
# =======================================================
@booking_bp.route('/api/rooms/preview_checkout', methods=['POST'])
@login_required
def preview_checkout():
    data = request.get_json()
    room_number = data.get('number')
    
    room = Room.query.filter(Room.room_number == room_number).first()
    if not room:
        return jsonify({'success': False, 'msg': 'Phòng không tồn tại!'})

    # --- KHẮC PHỤC LỖI ID ---
    # Tìm BookingRoom đang check-in
    booking_room = BookingRoom.query.filter_by(room_id=room.id, status='checked_in').first()

    if not booking_room:
        return jsonify({'success': False, 'msg': 'Phòng này chưa check-in hoặc không có khách.'})

    booking = booking_room.booking # Lấy Booking cha
    if not booking:
        return jsonify({'success': False, 'msg': 'Lỗi dữ liệu: Không tìm thấy thông tin Booking gốc.'})

    # --- TÍNH TOÁN TIỀN ---
    # Dùng check_in_actual của BookingRoom để tính tiền chính xác
    check_in = booking_room.check_in_actual if booking_room.check_in_actual else booking.booking_date
    check_out = datetime.now()
    expected_in= booking_room.check_in_expected
    expected_out= booking_room.check_out_expected
    rental_mode = booking_room.rental_type # Lấy loại thuê của phòng cụ thể

    # GỌI HÀM TÍNH TOÁN 
    room_fee, message = calculate_complex_hotel_bill(check_in, check_out, room, rental_type=rental_mode, expected_check_in=expected_in, expected_check_out=expected_out)
    
    # --- TÍNH TIỀN DỊCH VỤ ---
    # Lưu ý: Dịch vụ đang gắn với Booking cha. 
    # Nếu check-out 1 phòng trong đoàn, logic này đang hiển thị TOÀN BỘ dịch vụ của đoàn.
    # Bạn có thể cần sửa logic BookingService để có cột room_id nếu muốn tách riêng từng phòng.
    service_fee = 0.0
    service_details = []
    
    if booking.services:
        for item in booking.services:
            if item.service:
                price = float(item.price_at_booking or item.service.price)
                total_item = item.quantity * price
                service_fee += total_item
                
                service_details.append({
                    'service_id': item.service_id,
                    'name': item.service.name,
                    'quantity': item.quantity,
                    'price': price,
                    'total': total_item
                })

    total_bill = room_fee + service_fee
    
    # Tiền cọc: Cần xem xét cọc của cả đoàn hay cọc riêng. 
    # Ở đây lấy cọc tổng chia đều hoặc hiển thị hết tùy logic nghiệp vụ.
    # Tạm thời hiển thị cọc tổng của Booking.
    prepaid_amount = float(booking.prepaid_amount or 0)
    final_amount = total_bill - prepaid_amount

    return jsonify({
        'success': True,
        'booking_id': booking.id, 
        'booking_room_id': booking_room.id, # Trả về thêm ID phòng chi tiết
        'room_number': room.room_number,
        'rental_type': 'Thuê ngày' if rental_mode == 'daily' else 'Thuê giờ',
        'customer_name': booking.customer.name if booking.customer else 'Khách lẻ',
        'check_in': check_in.strftime('%H:%M %d/%m'),
        'check_out': check_out.strftime('%H:%M %d/%m'),
        'bill_details': message,
        'formatted_room_fee': "{:,.0f}".format(room_fee),
        'formatted_service_fee': "{:,.0f}".format(service_fee),
        'prepaid_amount': prepaid_amount,
        'formatted_prepaid_amount': "{:,.0f}".format(prepaid_amount),
        'formatted_total_bill': "{:,.0f}".format(total_bill),
        'total_bill': total_bill,
        'formatted_final_amount': "{:,.0f}".format(final_amount),
        'final_amount': final_amount,
        'services': service_details
    })

# =======================================================
# 4. CẬP NHẬT SỐ LƯỢNG DỊCH VỤ (+/-)
# =======================================================
@booking_bp.route('/api/bookings/update_service_quantity', methods=['POST'])
@login_required
def update_service_quantity():
    try:
        data = request.json
        booking_id = data.get('booking_id')
        service_id = data.get('service_id')
        change = int(data.get('change', 0))

        if not booking_id or not service_id:
            return jsonify({'success': False, 'msg': 'Thiếu thông tin.'})

        line_item = BookingService.query.filter_by(
            booking_id=booking_id,
            service_id=service_id
        ).first()

        if line_item:
            new_qty = line_item.quantity + change
            if new_qty <= 0:
                db.session.delete(line_item)
            else:
                line_item.quantity = new_qty
        else:
            if change > 0:
                service = Service.query.get(service_id)
                if service:
                    new_item = BookingService(
                        booking_id=booking_id,
                        service_id=service_id,
                        quantity=change,
                        price_at_booking=service.price
                    )
                    db.session.add(new_item)

        db.session.commit()
        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': str(e)})

# =======================================================
# 5. XÁC NHẬN TRẢ PHÒNG (CHECKOUT CONFIRM)
# =======================================================
@booking_bp.route('/api/rooms/checkout', methods=['POST'])
@login_required
def checkout_room():
    data = request.get_json()
    room_number = data.get('number')
    booking_room_id = data.get('booking_room_id') # Nên gửi kèm ID này từ preview
    amount_raw = data.get('amount', '0')
    
    payment_received = float(str(amount_raw).replace(',', ''))

    room = Room.query.filter(Room.room_number == room_number).first()
    if not room:
         return jsonify({'success': False, 'msg': 'Phòng không tồn tại.'})

    # Tìm BookingRoom
    booking_room = None
    if booking_room_id:
        booking_room = BookingRoom.query.get(booking_room_id)
    else:
        # Fallback tìm thủ công
        booking_room = BookingRoom.query.filter_by(room_id=room.id, status='checked_in').first()

    if booking_room:
        # 1. Chốt BookingRoom
        booking_room.status = 'checked_out'
        booking_room.check_out_actual = datetime.now()
        booking_room.price = payment_received # Lưu tiền phòng thực tế vào detail
        
        # 2. Giải phóng phòng
        room.status = 'available'
        room.clean_status = 'dirty'
        
        # 3. Kiểm tra xem Booking cha đã xong hết chưa (Optional)
        # parent_booking = booking_room.booking
        # check_remaining = BookingRoom.query.filter_by(booking_id=parent_booking.id, status='checked_in').count()
        # if check_remaining == 0:
        #     parent_booking.status = 'completed'

        db.session.commit()
        return jsonify({'success': True, 'msg': 'Trả phòng thành công!'})
        
    return jsonify({'success': False, 'msg': 'Không tìm thấy đơn để thanh toán.'})

# =======================================================
# 6. THÊM ORDER DỊCH VỤ
# =======================================================
@booking_bp.route('/api/orders/add', methods=['POST'])
@login_required
def add_order():
    try:
        data = request.json
        room_number = data.get('room_number')
        items = data.get('items') 

        # 1. Tìm phòng từ số phòng
        room = Room.query.filter_by(room_number=room_number).first()
        if not room: return jsonify({'success': False, 'msg': 'Phòng lỗi.'})

        # 2. Tìm BookingRoom đang check-in của phòng này
        br = BookingRoom.query.filter_by(room_id=room.id, status='checked_in').first()
        if not br: return jsonify({'success': False, 'msg': 'Phòng chưa check-in.'})

        booking_id = br.booking_id

        for item in items:
            s_id = item['id']
            qty = int(item['qty'])
            
            # Logic cộng dồn nếu đã có dịch vụ này rồi (trong cùng booking và cùng phòng)
            existing = BookingService.query.filter_by(
                booking_id=booking_id, 
                service_id=s_id,
                room_id=room.id  # <--- QUAN TRỌNG: Phải check cả room_id để tránh cộng nhầm sang phòng khác trong đoàn
            ).first()

            if existing:
                existing.quantity += qty
            else:
                svc = Service.query.get(s_id)
                if svc:
                    new_bs = BookingService(
                        booking_id=booking_id,
                        room_id=room.id,   # <--- BỔ SUNG DÒNG NÀY (Fix lỗi null)
                        service_id=s_id,
                        quantity=qty,
                        price_at_booking=svc.price
                    )
                    db.session.add(new_bs)
        
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Đã thêm dịch vụ.'})
    except Exception as e:
        db.session.rollback()
        # In lỗi ra console để debug dễ hơn
        print(f"Lỗi thêm dịch vụ: {e}")
        return jsonify({'success': False, 'msg': str(e)})

# =======================================================
# 7. TẠO BOOKING (Đoàn/Lẻ) - Logic mới
# =======================================================
@booking_bp.route('/api/bookings/group_create', methods=['POST'])
@login_required
def create_group_booking():
    try:
        data = request.json
        customer_info = data.get('customer', {})
        room_ids = data.get('room_ids', [])
        check_in_str = data.get('check_in')
        check_out_str = data.get('check_out')
        total_deposit = float(data.get('deposit', 0))
        note = data.get('note', '')

        if not room_ids or not customer_info.get('phone'):
            return jsonify({'success': False, 'msg': 'Thiếu thông tin phòng hoặc khách hàng!'})

        # Parse ngày
        try:
            c_in_date = datetime.strptime(check_in_str[0:10], '%Y-%m-%d')
            c_out_date = datetime.strptime(check_out_str[0:10], '%Y-%m-%d')
            check_in = c_in_date.replace(hour=14, minute=0, second=0)
            check_out = c_out_date.replace(hour=12, minute=0, second=0)
        except ValueError:
             return jsonify({'success': False, 'msg': 'Lỗi định dạng ngày!'})

        # 1. Tạo/Lấy Customer
        customer = Customer.query.filter_by(phone=customer_info['phone']).first()
        if not customer:
            customer = Customer(name=customer_info['name'], phone=customer_info['phone'])
            db.session.add(customer)
            db.session.flush() # Để lấy ID

        # 2. Tạo Booking Header (Một đơn chung cho cả nhóm)
        new_booking = Booking(
            customer_id=customer.id,
            booking_date=datetime.now(),
            status='confirmed', # Trạng thái chung
            deposit=total_deposit,
            note=f"{note} (Đoàn: {len(room_ids)} phòng)",
            # rental_type logic: Tạm để daily, hoặc lấy từ FE
            rental_type='daily' 
        )
        db.session.add(new_booking)
        db.session.flush() # Lấy new_booking.id

        # 3. Tạo BookingRoom (Chi tiết từng phòng)
        success_count = 0
        errors = []

        for r_id in room_ids:
            # Check trùng lịch cho từng phòng
            is_taken = BookingRoom.query.filter(
                BookingRoom.room_id == r_id,
                BookingRoom.status.in_(['booked', 'checked_in']),
                BookingRoom.check_in_expected < check_out,
                BookingRoom.check_out_expected > check_in
            ).first()

            if is_taken:
                errors.append(f"Phòng {r_id} đã có lịch.")
                continue

            new_br = BookingRoom(
                booking_id=new_booking.id,
                room_id=r_id,
                check_in_expected=check_in,
                check_out_expected=check_out,
                status='booked',
                rental_type='daily',
                price=0 # Giá sẽ tính khi checkout hoặc lấy từ settings
            )
            db.session.add(new_br)
            success_count += 1

        if success_count > 0:
            db.session.commit()
            msg = f"Đã đặt {success_count} phòng."
            if errors:
                msg += f" (Bỏ qua {len(errors)} phòng do trùng)."
            return jsonify({'success': True, 'msg': msg})
        else:
            db.session.rollback()
            return jsonify({'success': False, 'msg': 'Không đặt được phòng nào (trùng lịch hết)!'})

    except Exception as e:
        db.session.rollback()
        print(f"Lỗi Booking: {e}")
        return jsonify({'success': False, 'msg': 'Lỗi hệ thống: ' + str(e)})

# =======================================================
# 8. UPDATE SERVICES (Trước checkout)
# =======================================================
@booking_bp.route('/api/bookings/update_services', methods=['POST'])
@login_required
def update_services_before_checkout():
    data = request.get_json()
    room_number = data.get('number')
    new_services = data.get('services', [])

    room = Room.query.filter(Room.room_number == room_number).first()
    if not room: return jsonify({'success': False, 'msg': 'Lỗi phòng.'})

    booking_room = BookingRoom.query.filter_by(room_id=room.id, status='checked_in').first()
    if not booking_room: return jsonify({'success': False, 'msg': 'Phòng chưa checkin.'})
    
    booking = booking_room.booking

    try:
        # Xóa cũ thay mới (hoặc logic update diff tùy bạn)
        BookingService.query.filter_by(booking_id=booking.id).delete()
        
        for item in new_services:
            qty = int(item['quantity'])
            s_id = int(item['service_id']) # Lưu ý key từ frontend
            
            if qty > 0:
                service_obj = Service.query.get(s_id)
                if service_obj:
                    new_bs = BookingService(
                        booking_id=booking.id,
                        service_id=s_id,
                        quantity=qty,
                        price_at_booking=service_obj.price 
                    )
                    db.session.add(new_bs)
        
        db.session.commit()
        return jsonify({'success': True, 'msg': 'Đã cập nhật dịch vụ!'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': str(e)})