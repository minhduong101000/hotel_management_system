from extensions import db

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
    # created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # Bật nếu cần track nhân viên
    
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
            'time': self.created_at.strftime('%d/%m/%Y %H:%M'),
            'note': self.note,
            'business_operation_id': self.business_operation_id,
            'component_key': self.component_key,
        }
