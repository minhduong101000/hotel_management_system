from extensions import db
from services.time_service import utc_now_naive

class Hotel(db.Model):
    __tablename__ = 'hotels'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)  # vd: 'hotel-a'
    address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    logo_url = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utc_now_naive)

    # Quan hệ
    users = db.relationship('User', backref='hotel', lazy=True)
    rooms = db.relationship('Room', backref='hotel', lazy=True)
