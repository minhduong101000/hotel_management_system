from extensions import db
from datetime import datetime

class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    # created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # Bật nếu cần track nhân viên
    
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    payment_method = db.Column(db.String(50), default='cash')
    payment_type = db.Column(db.String(50), default='settlement') # deposit, settlement
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    # Relationship
    booking = db.relationship('Booking', back_populates='payments')

    def to_dict(self):
        return {
            'id': self.id,
            'amount': float(self.amount or 0),
            'method': self.payment_method, # cash, banking...
            'type': self.payment_type,     # deposit, settlement...
            'time': self.created_at.strftime('%d/%m/%Y %H:%M'),
            'note': self.note
        }