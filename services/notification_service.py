from flask import render_template, current_app
from flask_mail import Message
from extensions import mail
import threading

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            print(f"Error sending email: {e}")

def send_booking_notification(booking, hotel):
    """
    Gửi email thông báo cho chủ khách sạn khi có booking mới.
    Chạy trong thread riêng để không block request chính.
    """
    if not hotel.email:
        print(f"Hotel {hotel.name} has no email configured. Skipping notification.")
        return

    subject = f"🔔 [HOTEL] Booking mới: {hotel.name} - #{booking.id}"
    
    # Render template đơn giản (nếu chưa có file template, dùng chuỗi text)
    # Vì chưa tạo file template .html riêng, ta sẽ dùng body text thuần cho nhanh và ổn định
    body = f"""
    Xin chào chủ khách sạn {hotel.name},

    Bạn vừa có một yêu cầu đặt phòng mới từ hệ thống:

    - Mã đặt phòng: #{booking.id}
    - Khách hàng: {booking.customer.name if booking.customer else 'Khách lẻ'}
    - Loại thuê: {'Theo ngày' if booking.rental_type == 'daily' else 'Theo giờ'}
    - Thời gian vào: {booking.check_in_time.strftime('%H:%M %d/%m/%Y')}
    - Thời gian ra (dự kiến): {booking.check_out_expected.strftime('%H:%M %d/%m/%Y') if booking.check_out_expected else 'Chưa xác định'}
    - Tiền cọc: {booking.deposit_amount:,.0f} VNĐ

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
