from extensions import db
from services.time_service import format_business as _format_business

class Payment(db.Model):
    __tablename__ = 'payments'

    __table_args__ = (
        db.Index('ix_payments_hotel_booking', 'hotel_id', 'booking_id'),
        db.UniqueConstraint(
            'hotel_id',
            'business_operation_id',
            'component_key',
            name='uq_payments_operation_component',
        ),
        # Một dòng refund chỉ được đảo đúng một lần
        db.UniqueConstraint('reverses_payment_id', name='uq_payments_reverses_once'),
    )

    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    business_operation_id = db.Column(
        db.Integer,
        db.ForeignKey('business_operations.id'),
        nullable=True,
    )
    component_key = db.Column(db.String(120), nullable=True)
    # Bút toán đảo: dòng refund_reversal trỏ về dòng refund bị đảo
    reverses_payment_id = db.Column(
        db.Integer,
        db.ForeignKey('payments.id'),
        nullable=True,
    )
    # Nhân viên thao tác dòng tiền (truy vết + đối soát theo ca)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    payment_method = db.Column(db.String(50), default='cash')
    payment_type = db.Column(db.String(50), default='settlement') # deposit, settlement
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())

    # Relationship
    booking = db.relationship('Booking', back_populates='payments')
    business_operation = db.relationship(
        'BusinessOperation',
        back_populates='payments',
    )

    def to_dict(self):
        return {
            'id': self.id,
            'amount': float(self.amount or 0),
            'method': self.payment_method, # cash, banking...
            'type': self.payment_type,     # deposit, settlement...
            'time': _format_business(self.created_at, '%d/%m/%Y %H:%M'),
            'note': self.note,
            'business_operation_id': self.business_operation_id,
            'created_by': self.created_by,
            'component_key': self.component_key,
        }
