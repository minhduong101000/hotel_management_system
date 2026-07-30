from datetime import datetime, timedelta

from extensions import db
from models import Booking

def test_checkin_changes_only_requested_booking_room(client, booked_room, login_as):
    hotel, user, first_booking_room, second_booking_room = booked_room
    login_as(client, user)
    response = client.post(
        f"/{hotel.slug}/bookings/api/rooms/checkin",
        json={"booking_room_id": second_booking_room.id},
    )
    assert response.status_code == 200
    db.session.refresh(first_booking_room)
    db.session.refresh(second_booking_room)
    assert first_booking_room.status == "booked"
    assert second_booking_room.status == "checked_in"
    assert second_booking_room.room.status == "occupied"
    assert second_booking_room.booking.status == "checked_in"

def test_checkin_rejects_booking_room_from_another_hotel(client, seed_hotels, login_as):
    hotel_a, hotel_b, user_a, _, booking_room_a, booking_room_b = seed_hotels
    login_as(client, user_a)
    response = client.post(
        f"/{hotel_a.slug}/bookings/api/rooms/checkin",
        json={"booking_room_id": booking_room_b.id},
    )
    assert response.status_code == 404


def test_create_checked_in_booking_aggregates_parent_state(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, user, _, existing_room, _ = seed_hotels
    existing_room.status = "cancelled"
    now = datetime.now().replace(second=0, microsecond=0)
    db.session.commit()
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/create",
        json={
            "room_number": existing_room.room.room_number,
            "check_in": now.strftime("%Y-%m-%dT%H:%M"),
            "check_out": (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "rental_type": "daily",
            "status": "checked_in",
            "deposit": 250000,
            "name": "Khách nhận ngay",
        },
    )

    assert response.status_code == 200
    created_booking = Booking.query.filter_by(code=response.json["code"]).one()
    assert created_booking.status == "checked_in"
    assert created_booking.rooms[0].status == "checked_in"
    assert created_booking.rooms[0].room.status == "occupied"
