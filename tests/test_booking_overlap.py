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
