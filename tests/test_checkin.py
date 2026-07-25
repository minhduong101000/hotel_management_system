from extensions import db

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

def test_checkin_rejects_booking_room_from_another_hotel(client, seed_hotels, login_as):
    hotel_a, hotel_b, user_a, _, booking_room_a, booking_room_b = seed_hotels
    login_as(client, user_a)
    response = client.post(
        f"/{hotel_a.slug}/bookings/api/rooms/checkin",
        json={"booking_room_id": booking_room_b.id},
    )
    assert response.status_code == 404
