from extensions import db

class BookingRoom(db.Model):
    __tablename__ = 'booking_rooms'

    id = db.Column(db.Integer, primary_key=True)
    
    # Khóa ngoại
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False) # Bổ sung FK cho rooms
    
    # Thời gian
    check_in_expected = db.Column(db.DateTime, nullable=True)
    check_out_expected = db.Column(db.DateTime, nullable=True)
    check_in_actual = db.Column(db.DateTime, nullable=True)
    check_out_actual = db.Column(db.DateTime, nullable=True)
    
    rental_type = db.Column(db.String(20), default='daily') # daily, hourly
    
    # Tài chính
    price_snapshot = db.Column(db.Numeric(15, 2), default=0)
    final_amount = db.Column(db.Numeric(15, 2), default=0)
    status = db.Column(db.String(20), default='booked')

    # Relationship ngược lại
    booking = db.relationship('Booking', back_populates='rooms')
    room = db.relationship('Room', back_populates='booking_history')

    def to_dict(self):
        return {
            'id': self.id,
            'room_number': self.room.room_number if self.room else 'N/A',
            'status': self.status,
            'final_amount': float(self.final_amount or 0)
        }