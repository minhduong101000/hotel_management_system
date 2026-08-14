from extensions import db

class Booking(db.Model):
    __tablename__ = 'bookings' # Lưu ý: SQL bạn để là bookings (số nhiều)

    __table_args__ = (
        db.Index('ix_bookings_hotel_status', 'hotel_id', 'status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    code = db.Column(db.String(20), nullable=False)
    
    # Khóa ngoại: Khách hàng
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    
    total_amount = db.Column(db.Numeric(15, 2), default=0)
    prepaid_amount = db.Column(db.Numeric(15, 2), default=0)
    
    # Enum trạng thái
    payment_status = db.Column(db.String(20), default='partial') # unpaid, partial, paid, refunded
    status = db.Column(db.String(20), default='pending') # pending, confirmed, checked_in...
    
    note = db.Column(db.String(1000), nullable=True)
    source = db.Column(db.String(50), default='walk_in')
    
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    # Mốc hoàn tất nghiệp vụ (UTC-naive); chỉ booking_state_service được set
    completed_at = db.Column(db.DateTime, nullable=True)

    # --- RELATIONSHIPS (ĐỊNH NGHĨA RÕ RÀNG) ---
    customer = db.relationship('Customer', back_populates='bookings')
    
    # Một Booking có nhiều BookingRoom
    rooms = db.relationship('BookingRoom', back_populates='booking', cascade="all, delete-orphan", lazy=True)
    
    # Một Booking có nhiều Dịch vụ
    services = db.relationship('BookingService', back_populates='booking', cascade="all, delete-orphan", lazy=True)
    
    # Một Booking có nhiều Giao dịch thanh toán
    payments = db.relationship('Payment', back_populates='booking', cascade="all, delete-orphan", lazy=True)

    def to_dict(self):
        # Hàm hỗ trợ trả về JSON
        return {
            'id': self.id,
            'code': self.code,
            'customer_name': self.customer.name if self.customer else 'Unknown',
            'status': self.status,
            'total_amount': float(self.total_amount or 0),
            'prepaid_amount': float(self.prepaid_amount or 0),
            'balance': float(self.total_amount or 0) - float(self.prepaid_amount or 0),
            'rooms': [r.to_dict() for r in self.rooms],
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')
        }