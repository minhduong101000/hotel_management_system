from extensions import db
from services.time_service import utc_now_naive
from services.time_service import format_business as _format_business


class BookingService(db.Model):
    __tablename__ = 'booking_services'

    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    
    # Khóa ngoại
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    
    quantity = db.Column(db.Integer, default=1)
    price_at_booking = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now_naive)

    # Relationship
    booking = db.relationship('Booking', back_populates='services')
    room = db.relationship('Room') # Link đơn giản để biết phòng nào gọi
    service = db.relationship('Service') # Link để lấy tên dịch vụ
    batch_allocations = db.relationship('BookingServiceBatchAllocation', back_populates='booking_service')

    def to_dict(self):
        return {
            'id': self.id,
            'service_name': self.service.name if self.service else 'Unknown Service',
            'room_number': self.room.room_number if self.room else 'Chung',
            
            'quantity': self.quantity,
            'price': float(self.price_at_booking or 0),
            'total': float(self.price_at_booking or 0) * (self.quantity or 0),
            
            'created_at': _format_business(self.created_at, '%H:%M %d/%m')
        }
