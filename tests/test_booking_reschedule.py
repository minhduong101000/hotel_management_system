from datetime import datetime
from extensions import db
from models import Room, User
from models.audit_event import AuditEvent
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


def test_reschedule_reprices_hourly_booking_snapshot(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.rental_type = 'hourly'
    booking_room.hourly_price_snapshot = {'initial_hours': 2, 'price_initial': 300000.0, 'price_next': 50000.0, 'price_night': 500000.0}
    booking_room.room.price_initial_block = 450000
    booking_room.room.price_next_hour = 90000
    booking_room.room.price_per_night = 800000
    db.session.commit(); login_as(client, user)
    response = client.post(f'/{hotel.slug}/timeline/api/bookings/reschedule', json={'booking_room_id': booking_room.id, 'room_id': booking_room.room_id, 'check_in': '2030-02-01T14:00', 'check_out': '2030-02-01T17:00', 'reason': 'Đổi giá giờ', 'price_mode': 'reprice'})
    assert response.status_code == 200
    db.session.refresh(booking_room)
    assert booking_room.hourly_price_snapshot == {'initial_hours': 2, 'price_initial': 450000.0, 'price_next': 90000.0, 'price_night': 800000.0}


def test_reschedule_availability_returns_price_comparison(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.price_breakdown_snapshot = [{'business_date': '2030-01-01', 'amount': 400000.0}]
    db.session.commit(); login_as(client, user)

    response = client.post(f'/{hotel.slug}/timeline/api/bookings/reschedule/availability', json={
        'booking_room_id': booking_room.id, 'room_id': booking_room.room_id,
        'check_in': '2030-02-01T14:00', 'check_out': '2030-02-02T12:00',
    })

    assert response.status_code == 200
    assert response.json['available'] is True
    assert response.json['locked_amount'] == 400000.0
    assert response.json['current_amount'] == 500000.0
    assert response.json['difference'] == 100000.0


def test_booking_detail_includes_reschedule_history(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    db.session.commit(); login_as(client, user)
    client.post(f'/{hotel.slug}/timeline/api/bookings/reschedule', json={
        'booking_room_id': booking_room.id, 'room_id': booking_room.room_id,
        'check_in': '2030-02-01T14:00', 'check_out': '2030-02-02T12:00',
        'reason': 'Khách đổi lịch', 'price_mode': 'keep',
    })

    response = client.get(f'/{hotel.slug}/timeline/api/bookings/{booking_room.id}')

    assert response.status_code == 200
    assert response.json['reschedules'][0]['reason'] == 'Khách đổi lịch'


def test_staff_cannot_check_or_confirm_reschedule(
    client, seed_hotels, login_as
):
    hotel, _, _, _, booking_room, _ = seed_hotels
    staff = User(username="reschedule_staff", role="staff", hotel_id=hotel.id)
    staff.set_password("correct-password")
    db.session.add(staff)
    db.session.commit()
    login_as(client, staff)
    availability_payload = {
        "booking_room_id": booking_room.id,
        "room_id": booking_room.room_id,
        "check_in": "2030-02-01T14:00",
        "check_out": "2030-02-02T12:00",
    }

    availability = client.post(
        f"/{hotel.slug}/timeline/api/bookings/reschedule/availability",
        json=availability_payload,
    )
    confirmation = client.post(
        f"/{hotel.slug}/timeline/api/bookings/reschedule",
        json={
            **availability_payload,
            "reason": "Staff không được dời",
            "price_mode": "keep",
        },
    )

    assert availability.status_code == 403
    assert confirmation.status_code == 403
    assert confirmation.get_json()["error_code"] == "forbidden"
    assert BookingReschedule.query.count() == 0


def test_generic_timeline_update_cannot_change_booked_room_schedule(
    client, seed_hotels, login_as
):
    hotel, _, admin, _, booking_room, _ = seed_hotels
    original_start = datetime(2030, 1, 1, 14, 0)
    original_end = datetime(2030, 1, 2, 12, 0)
    booking_room.check_in_expected = original_start
    booking_room.check_out_expected = original_end
    db.session.commit()
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/update_timeline",
        json={
            "id": booking_room.id,
            "start": "2030-01-01T15:00:00",
            "end": "2030-01-02T13:00:00",
        },
    )

    assert response.status_code == 409
    db.session.refresh(booking_room)
    assert booking_room.check_in_expected == original_start
    assert booking_room.check_out_expected == original_end
    assert AuditEvent.query.count() == 0


def test_generic_timeline_update_cannot_change_checked_in_actual_time_or_room(
    client, seed_hotels, login_as
):
    hotel, _, admin, _, booking_room, _ = seed_hotels
    target_room = Room(
        hotel_id=hotel.id,
        room_number="102",
        room_type="Standard",
        price_per_night=500_000,
        price_initial_block=300_000,
        initial_hours=2,
    )
    original_check_in = datetime(2030, 1, 1, 14, 0)
    booking_room.status = "checked_in"
    booking_room.check_in_actual = original_check_in
    db.session.add(target_room)
    db.session.commit()
    original_room_id = booking_room.room_id
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/update_timeline",
        json={
            "id": booking_room.id,
            "group": target_room.id,
            "start": "2030-01-01T15:00:00",
        },
    )

    assert response.status_code == 409
    db.session.refresh(booking_room)
    assert booking_room.room_id == original_room_id
    assert booking_room.check_in_actual == original_check_in
