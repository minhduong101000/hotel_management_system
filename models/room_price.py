from .base import db

class RoomPrice(db.Model):
    __tablename__ = 'Room_Prices'
    id = db.Column(db.Integer, primary_key=True)
    room_type = db.Column(db.String(50))
    day_of_week = db.Column(db.String(20))
    specific_date = db.Column(db.Date)
    price = db.Column(db.Integer)