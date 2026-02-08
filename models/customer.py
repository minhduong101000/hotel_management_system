from .base import db

class Customer(db.Model):
    __tablename__ = 'Customers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    
    # Quan hệ: 1 Khách hàng có nhiều đơn đặt phòng
    bookings = db.relationship('Booking', backref='customer', lazy=True)