def test_cancel_booking_room_marks_only_requested_room_cancelled(
    client, booked_room, login_as
):
    hotel, user, booking_room_a, booking_room_b = booked_room
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/cancel",
        json={"booking_room_id": booking_room_a.id, "refund_percent": 0},
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    assert booking_room_a.status == "cancelled"
    assert booking_room_b.status == "booked"


def test_cancel_booking_room_rejects_another_hotels_room(client, seed_hotels, login_as):
    hotel_a, _, user_a, _, booking_room_a, booking_room_b = seed_hotels
    login_as(client, user_a)

    response = client.post(
        f"/{hotel_a.slug}/timeline/api/bookings/cancel",
        json={"booking_room_id": booking_room_b.id, "refund_percent": 0},
    )

    assert response.status_code == 404
    assert response.json["success"] is False
    assert booking_room_a.status == "booked"
    assert booking_room_b.status == "booked"


def test_cancel_booking_by_booking_id_cancels_all_active_rooms(client, booked_room, login_as):
    hotel, user, booking_room_a, booking_room_b = booked_room
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/cancel",
        json={"booking_id": booking_room_a.booking_id, "refund_percent": 0},
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    assert booking_room_a.status == "cancelled"
    assert booking_room_b.status == "cancelled"


def test_cancel_booking_rejects_invalid_id_and_checked_out_room(
    client, seed_hotels, login_as
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    login_as(client, user)

    invalid_response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/cancel",
        json={"booking_room_id": "not-a-number", "refund_percent": 0},
    )
    booking_room.status = "checked_out"
    checked_out_response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/cancel",
        json={"booking_room_id": booking_room.id, "refund_percent": 0},
    )

    assert invalid_response.status_code == 400
    assert invalid_response.json["success"] is False
    assert checked_out_response.status_code == 409
    assert checked_out_response.json["success"] is False
    assert booking_room.status == "checked_out"


def test_cancel_booking_rejects_checked_in_room(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.status = "checked_in"
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/cancel",
        json={"booking_room_id": booking_room.id, "refund_percent": 0},
    )

    assert response.status_code == 409
    assert response.json["success"] is False
    assert booking_room.status == "checked_in"
