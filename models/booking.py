from .base import db
from datetime import datetime

class Booking(db.Model):
    __tablename__ = 'Bookings'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('Customers.id'), nullable=False)
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='pending')
    
    rooms = db.relationship('BookingRoom', backref='booking', lazy=True)

class BookingRoom(db.Model):
    __tablename__ = 'Booking_Rooms'
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('Bookings.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('Rooms.id'), nullable=False)
    check_in = db.Column(db.Date, nullable=False)
    check_out = db.Column(db.Date, nullable=False)
    price_at_booking = db.Column(db.Integer, nullable=False)