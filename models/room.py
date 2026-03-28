from extensions import db

class Room(db.Model):
    __tablename__ = 'rooms'
    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    room_number = db.Column(db.String(10), nullable=False)
    room_type = db.Column(db.String(20), nullable=False) # Standard, Deluxe, Suite
    
    # Giá mặc định
    price_per_night = db.Column(db.Integer, nullable=False)
    price_initial_block = db.Column(db.Integer, nullable=False)
    initial_hours = db.Column(db.Integer, nullable=False)
    price_next_hour = db.Column(db.Numeric(10, 2), default=50000)
    
    status = db.Column(db.String(20), default='available') # available, occupied, maintenance
    clean_status = db.Column(db.String(20), default='cleaned') # cleaned, dirty

    # Quan hệ: Lịch sử đặt của phòng này
    booking_history = db.relationship('BookingRoom', back_populates='room', lazy=True)

    def to_dict(self):
            # Logic hiển thị: Nếu đang available mà chưa dọn -> coi như là dirty
            display_status = self.status
            if self.status == 'available' and self.clean_status == 'dirty':
                display_status = 'dirty'

            return {
                'id': self.id,
                'room_number': self.room_number,
                'room_type': self.room_type,
                'price_per_night': float(self.price_per_night),
                'status': display_status,          # Trạng thái hiển thị (gộp)
                'real_status': self.status,        # Trạng thái gốc (available/occupied)
                'clean_status': self.clean_status, # Trạng thái dọn dẹp
                'booking_count': len(self.booking_history) if self.booking_history else 0
            }