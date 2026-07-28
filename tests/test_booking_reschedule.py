from datetime import datetime
from extensions import db
from models import Room
from models.booking_reschedule import BookingReschedule


def test_reschedule_moves_room_keeps_price_and_records_history(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    target = Room(hotel_id=hotel.id, room_number='102', room_type='Standard', price_per_night=900000, price_initial_block=300000, initial_hours=2)
    booking_room.price_breakdown_snapshot = [{'business_date': '2030-01-01', 'amount': 500000.0}]
    db.session.add(target); db.session.commit(); login_as(client, user)
    response = client.post(f'/{hotel.slug}/timeline/api/bookings/reschedule', json={'booking_room_id': booking_room.id, 'room_id': target.id, 'check_in': '2030-02-01T14:00', 'check_out': '2030-02-02T12:00', 'reason': 'Khách đổi lịch', 'price_mode': 'keep'})
    assert response.status_code == 200
    db.session.refresh(booking_room)
    assert booking_room.room_id == target.id
    assert booking_room.price_breakdown_snapshot == [{'business_date': '2030-01-01', 'amount': 500000.0}]
    assert BookingReschedule.query.one().reason == 'Khách đổi lịch'


def test_reschedule_can_apply_new_price(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.price_breakdown_snapshot = [{'business_date': '2030-01-01', 'amount': 400000.0}]
    db.session.commit(); login_as(client, user)
    response = client.post(f'/{hotel.slug}/timeline/api/bookings/reschedule', json={'booking_room_id': booking_room.id, 'room_id': booking_room.room_id, 'check_in': '2030-02-01T14:00', 'check_out': '2030-02-02T12:00', 'reason': 'Đổi giá', 'price_mode': 'reprice'})
    assert response.status_code == 200
    db.session.refresh(booking_room)
    assert booking_room.price_breakdown_snapshot == [{'business_date': '2030-02-01', 'amount': 500000.0}]
