from .base import db
from datetime import datetime

class Invoice(db.Model):
    __tablename__ = 'Invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('Bookings.id'), unique=True)
    
    total_amount = db.Column(db.Numeric(10, 2))
    tax_rate = db.Column(db.Numeric(5, 2), default=0.08) # 8%
    discount = db.Column(db.Numeric(10, 2), default=0)
    
    payment_method = db.Column(db.Enum('cash', 'card', 'transfer'), default='cash')
    paid = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Quan hệ 1-1 với Booking
    booking = db.relationship('Booking', backref=db.backref('invoice', uselist=False))