from flask import render_template, current_app
from flask_mail import Message
from extensions import mail
import threading

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception:
            app.logger.exception("Error sending booking notification email")

def send_booking_notification(booking, hotel):
    """
    Gửi email thông báo cho chủ khách sạn khi có booking mới.
    Chạy trong thread riêng để không block request chính.
    """
    if not hotel.email:
        current_app.logger.info(
            "Hotel %s has no email configured. Skipping notification.", hotel.name
        )
        return

    subject = f"🔔 [HOTEL] Booking mới: {hotel.name} - {booking.code}"

    # Thời gian/loại thuê là thuộc tính TỪNG PHÒNG (BookingRoom), không nằm
    # trên Booking — liệt kê theo phòng để đơn đoàn cũng hiển thị đúng.
    active_rooms = [r for r in booking.rooms if r.status != 'cancelled'] or list(booking.rooms)
    room_lines = []
    for br in active_rooms:
        room_number = br.room.room_number if br.room else 'N/A'
        rental_label = 'Theo ngày' if br.rental_type == 'daily' else 'Theo giờ'
        check_in = br.check_in_expected.strftime('%H:%M %d/%m/%Y') if br.check_in_expected else 'Chưa xác định'
        check_out = br.check_out_expected.strftime('%H:%M %d/%m/%Y') if br.check_out_expected else 'Chưa xác định'
        room_lines.append(
            f"    - Phòng {room_number} ({rental_label}): vào {check_in}, ra dự kiến {check_out}"
        )

    body = f"""
    Xin chào chủ khách sạn {hotel.name},

    Bạn vừa có một yêu cầu đặt phòng mới từ hệ thống:

    - Mã đặt phòng: {booking.code}
    - Khách hàng: {booking.customer.name if booking.customer else 'Khách lẻ'}
    - Số phòng trong đơn: {len(active_rooms)}
{chr(10).join(room_lines)}
    - Tiền cọc: {float(booking.prepaid_amount or 0):,.0f} VNĐ

    Vui lòng truy cập hệ thống quản lý để xem chi tiết.

    ---
    Hotel POS Pro System
    """

    msg = Message(
        subject=subject,
        recipients=[hotel.email],
        body=body
    )

    # Lấy app object hiện tại để truyền vào thread (context safety)
    app = current_app._get_current_object()
    thread = threading.Thread(target=send_async_email, args=(app, msg))
    thread.start()
