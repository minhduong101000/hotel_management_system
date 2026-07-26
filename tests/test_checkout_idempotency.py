from datetime import datetime

from extensions import db
from models.business_operation import BusinessOperation
from models.payment import Payment


def test_repeated_checkout_returns_conflict_without_duplicate_payment(
    client, seed_hotels, login_as
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.status = "checked_in"
    booking_room.check_in_actual = datetime.now()
    booking_room.room.status = "occupied"
    db.session.commit()
    login_as(client, user)

    payload = {
        "number": booking_room.room.room_number,
        "booking_room_id": booking_room.id,
        "booking_id": booking_room.booking_id,
        "amount": 100000,
    }
    first_response = client.post(f"/{hotel.slug}/bookings/api/rooms/checkout", json=payload)
    second_response = client.post(f"/{hotel.slug}/bookings/api/rooms/checkout", json=payload)

    assert first_response.status_code == 200
    assert first_response.json["success"] is True
    assert second_response.status_code == 409
    assert second_response.json == {
        "success": False,
        "msg": "Phòng này đã checkout.",
        "operation_key": f"checkout:{booking_room.id}",
    }
    assert Payment.query.filter_by(booking_id=booking_room.booking_id).count() == 1
    operation = BusinessOperation.query.one()
    assert operation.hotel_id == hotel.id
    assert operation.operation_key == f"checkout:{booking_room.id}"
    assert operation.status == "completed"
