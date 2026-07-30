from datetime import datetime

from extensions import db
from models import BusinessOperation, Payment
from services import audit_service, payment_service


def test_booked_room_cannot_be_checked_out(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.status = "booked"
    booking_room.room.status = "available"
    db.session.commit()
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/bookings/api/rooms/checkout",
        json={
            "number": booking_room.room.room_number,
            "booking_room_id": booking_room.id,
            "booking_id": booking_room.booking_id,
            "quote_fingerprint": "not-applicable",
            "quote_checkout_at": datetime.now().isoformat(),
        },
    )

    assert response.status_code == 409
    assert response.json["error_code"] == "invalid_checkout_state"
    assert booking_room.status == "booked"
    assert Payment.query.count() == 0
    assert BusinessOperation.query.count() == 0


def test_checkout_failure_rolls_back_all_state(
    client,
    seed_hotels,
    login_as,
    monkeypatch,
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.status = "checked_in"
    booking_room.check_in_actual = datetime.now()
    booking_room.room.status = "occupied"
    db.session.commit()
    login_as(client, user)
    preview = client.post(
        f"/{hotel.slug}/bookings/api/rooms/preview_checkout",
        json={"number": booking_room.room.room_number},
    )
    quote = preview.json["quote"]

    def fail_payment(*_args, **_kwargs):
        raise RuntimeError("forced checkout failure")

    monkeypatch.setattr(payment_service, "record_room_payment", fail_payment)
    response = client.post(
        f"/{hotel.slug}/bookings/api/rooms/checkout",
        json={
            "number": booking_room.room.room_number,
            "booking_room_id": booking_room.id,
            "booking_id": booking_room.booking_id,
            "quote_fingerprint": quote["fingerprint"],
            "quote_checkout_at": quote["checkout_at"],
        },
    )

    assert response.status_code == 500
    assert response.json["error_code"] == "checkout_failed"
    db.session.expire_all()
    assert booking_room.status == "checked_in"
    assert booking_room.room.status == "occupied"
    assert Payment.query.count() == 0
    assert BusinessOperation.query.count() == 0
    assert audit_service is not None
