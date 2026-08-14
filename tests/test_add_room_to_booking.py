from datetime import datetime, timedelta

from extensions import db
from models import AuditEvent, BookingRoom, Room, User


START = datetime(2026, 9, 1, 14, 0)
END = datetime(2026, 9, 4, 12, 0)


def _second_room(hotel, number="102"):
    room = Room(
        hotel_id=hotel.id, room_number=number, room_type="Deluxe",
        price_per_night=600000, price_initial_block=150000, initial_hours=2,
    )
    db.session.add(room)
    db.session.commit()
    return room


def _payload(booking_id, room_number="102"):
    return {
        "booking_id": booking_id,
        "room_number": room_number,
        "check_in": START.strftime("%Y-%m-%dT%H:%M"),
        "check_out": END.strftime("%Y-%m-%dT%H:%M"),
    }


def test_add_room_appends_to_existing_booking(app, seed_hotels, client, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        _second_room(hotel)
        booking = booking_room.booking
        login_as(client, user)

        response = client.post(
            f"/{hotel.slug}/timeline/api/bookings/add-room",
            json=_payload(booking.id),
        )
        assert response.status_code == 200, response.json
        assert response.json["success"] is True

        added = BookingRoom.query.filter(
            BookingRoom.booking_id == booking.id,
            BookingRoom.id != booking_room.id,
        ).one()
        assert added.status == "booked"
        assert added.rental_type == "daily"
        assert float(added.room_deposit_amount or 0) == 0
        # Snapshot giá đủ 3 đêm theo giá phòng mới
        assert len(added.price_breakdown_snapshot) == 3
        assert added.price_breakdown_snapshot[0]["amount"] == 600000.0

        event = AuditEvent.query.filter_by(action="add_room_to_booking").one()
        assert event.entity_id == added.id
        assert event.after_data["room_number"] == "102"


def test_add_room_rejects_conflict(app, seed_hotels, client, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        room2 = _second_room(hotel)
        # Phòng 102 đã có lịch trùng cửa sổ
        blocker = BookingRoom(
            hotel_id=hotel.id, booking_id=booking_room.booking_id, room_id=room2.id,
            rental_type="daily", status="booked",
            check_in_expected=START + timedelta(days=1),
            check_out_expected=END + timedelta(days=1),
        )
        db.session.add(blocker)
        db.session.commit()
        before = BookingRoom.query.count()
        login_as(client, user)

        response = client.post(
            f"/{hotel.slug}/timeline/api/bookings/add-room",
            json=_payload(booking_room.booking_id),
        )
        assert response.status_code == 409
        assert BookingRoom.query.count() == before


def test_add_room_rejects_finished_booking(app, seed_hotels, client, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        _second_room(hotel)
        booking_room.status = "cancelled"
        booking_room.booking.status = "cancelled"
        db.session.commit()
        login_as(client, user)

        response = client.post(
            f"/{hotel.slug}/timeline/api/bookings/add-room",
            json=_payload(booking_room.booking_id),
        )
        assert response.status_code == 409
        assert BookingRoom.query.filter_by(booking_id=booking_room.booking_id).count() == 1


def test_add_room_rejects_cross_tenant(app, seed_hotels, client, login_as):
    hotel_a, hotel_b, user_a, _, _, booking_room_b = seed_hotels
    with app.app_context():
        login_as(client, user_a)
        # Đơn của hotel B — user hotel A không thấy
        response = client.post(
            f"/{hotel_a.slug}/timeline/api/bookings/add-room",
            json=_payload(booking_room_b.booking_id, room_number="101"),
        )
        assert response.status_code == 404


def test_add_room_staff_allowed_and_unauth_gets_401(app, seed_hotels, client, login_as):
    hotel, _, _, _, booking_room, _ = seed_hotels
    with app.app_context():
        _second_room(hotel)
        # Chưa đăng nhập -> 401 JSON
        anon = client.post(
            f"/{hotel.slug}/timeline/api/bookings/add-room",
            json=_payload(booking_room.booking_id),
        )
        assert anon.status_code == 401

        staff = User(username="staff_addroom", role="staff", hotel_id=hotel.id)
        staff.set_password("correct-password")
        db.session.add(staff)
        db.session.commit()
        login_as(client, staff)
        response = client.post(
            f"/{hotel.slug}/timeline/api/bookings/add-room",
            json=_payload(booking_room.booking_id),
        )
        assert response.status_code == 200, response.json
