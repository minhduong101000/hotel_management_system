from extensions import db

class BookingRoom(db.Model):
    __tablename__ = 'booking_rooms'

    __table_args__ = (
        db.Index('ix_booking_rooms_hotel_status', 'hotel_id', 'status'),
        db.Index('ix_booking_rooms_hotel_booking_status', 'hotel_id', 'booking_id', 'status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    
    # Khóa ngoại
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    
    # Thời gian
    check_in_expected = db.Column(db.DateTime, nullable=True)
    check_out_expected = db.Column(db.DateTime, nullable=True)
    check_in_actual = db.Column(db.DateTime, nullable=True)
    check_out_actual = db.Column(db.DateTime, nullable=True)
    
    rental_type = db.Column(db.String(20), default='daily') # daily, hourly
    
    # Tài chính
    price_snapshot = db.Column(db.Numeric(15, 2), default=0)
    price_breakdown_snapshot = db.Column(db.JSON, nullable=True)
    hourly_price_snapshot = db.Column(db.JSON, nullable=True)
    room_deposit_amount = db.Column(db.Numeric(15, 2), default=0)
    room_deposit_original = db.Column(db.Numeric(15, 2), default=0)
    cancellation_refund_percent = db.Column(db.Numeric(5, 2), default=0)
    cancellation_fee_percent = db.Column(db.Numeric(5, 2), default=0)
    cancellation_refund_amount = db.Column(db.Numeric(15, 2), default=0)
    
    final_amount = db.Column(db.Numeric(15, 2), default=0)
    status = db.Column(db.String(20), default='booked')

    # Relationship ngược lại
    booking = db.relationship('Booking', back_populates='rooms')
    room = db.relationship('Room', back_populates='booking_history')

    def to_dict(self):
        return {
            'id': self.id,
            'booking': self.booking_id,
            'room_number': self.room.room_number if self.room else 'N/A',
            'status': self.status,
            'room_deposit_amount': float(self.room_deposit_amount or 0),
            'room_deposit_original': float(self.room_deposit_original or 0),
            'cancellation_refund_percent': float(self.cancellation_refund_percent or 0),
            'cancellation_fee_percent': float(self.cancellation_fee_percent or 0),
            'cancellation_refund_amount': float(self.cancellation_refund_amount or 0),
            'final_amount': float(self.final_amount or 0),
            'price_snapshot': float(self.price_snapshot or 0)    # Thêm vào luôn cho đầy đủ
        }
