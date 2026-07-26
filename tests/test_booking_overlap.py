def test_create_booking_rejects_overlapping_active_room_with_conflict_status(
    client, seed_hotels, login_as
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/create",
        json={
            "room_number": booking_room.room.room_number,
            "check_in": booking_room.check_in_expected.strftime("%Y-%m-%dT%H:%M"),
            "check_out": booking_room.check_out_expected.strftime("%Y-%m-%dT%H:%M"),
            "rental_type": "daily",
            "deposit": 250000,
            "name": "Khách mới",
        },
    )

    assert response.status_code == 409
    assert response.json["success"] is False


def test_create_booking_allows_a_stay_starting_at_previous_checkout(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    start = datetime(2030, 1, 1, 14, 0)
    end = start + timedelta(days=1)
    booking_room.check_in_expected = start
    booking_room.check_out_expected = end
    db.session.commit()
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/create",
        json={
            "room_number": booking_room.room.room_number,
            "check_in": end.strftime("%Y-%m-%dT%H:%M"),
            "check_out": (end + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "rental_type": "daily",
            "deposit": 250000,
            "name": "Khách nối tiếp",
        },
    )

    assert response.status_code == 200
    assert response.json["success"] is True
from datetime import datetime, timedelta

from extensions import db
