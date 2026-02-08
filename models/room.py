from .base import db

class Room(db.Model):
    __tablename__ = 'Rooms'
    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(10), unique=True)
    room_type = db.Column(db.String(50))
    price_per_night = db.Column(db.Integer)
    status = db.Column(db.String(20)) # available/occupied