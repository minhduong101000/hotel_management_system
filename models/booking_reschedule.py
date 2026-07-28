from extensions import db


class BookingReschedule(db.Model):
    __tablename__ = 'booking_reschedules'

    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    booking_room_id = db.Column(db.Integer, db.ForeignKey('booking_rooms.id'), nullable=False)
    old_room_id = db.Column(db.Integer, nullable=False)
    new_room_id = db.Column(db.Integer, nullable=False)
    old_check_in = db.Column(db.DateTime, nullable=False)
    old_check_out = db.Column(db.DateTime, nullable=False)
    new_check_in = db.Column(db.DateTime, nullable=False)
    new_check_out = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    price_mode = db.Column(db.String(20), nullable=False)
    actor_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
