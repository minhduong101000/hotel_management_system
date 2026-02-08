from .base import db

class Service(db.Model):
    __tablename__ = 'Services'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)

class BookingService(db.Model):
    __tablename__ = 'Booking_Services'
    
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('Bookings.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('Services.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    
    # Quan trọng: Lưu giá tại thời điểm dùng dịch vụ
    price_at_booking = db.Column(db.Numeric(10, 2), nullable=False)

    # Quan hệ để truy xuất ngược
    service = db.relationship('Service')
    # Quan hệ với Booking đã được khai báo ở models/booking.py (backref='services')