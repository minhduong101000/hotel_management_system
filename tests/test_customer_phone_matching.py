from extensions import db
from models import Customer


def test_booking_rejects_ambiguous_customer_phone_without_explicit_selection(
    client, seed_hotels, login_as
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    db.session.add(Customer(hotel_id=hotel.id, name="Người thứ hai", phone="0900000000"))
    booking_room.booking.customer.phone = "0900000000"
    db.session.commit()
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/create",
        json={
            "room_number": booking_room.room.room_number,
            "check_in": "2030-01-01T14:00",
            "check_out": "2030-01-02T12:00",
            "rental_type": "daily",
            "deposit": 250000,
            "name": "Khách mới",
            "phone": "0900000000",
        },
    )

    assert response.status_code == 409
    assert response.json["code"] == "customer_phone_ambiguous"
    assert len(response.json["candidates"]) == 2
