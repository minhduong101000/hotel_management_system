from extensions import db

class Customer(db.Model):
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True)
    cccd = db.Column(db.String(12), unique=True) # Căn cước công dân
    address = db.Column(db.String(255))
    
    # Quan hệ: Một khách có nhiều đơn đặt phòng
    bookings = db.relationship('Booking', back_populates='customer', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'email': self.email or '',
            'cccd': self.cccd or '',
            'address': self.address or ''
        }