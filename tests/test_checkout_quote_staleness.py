from datetime import datetime

from extensions import db
from models import BookingService, BusinessOperation, Payment, Service


def test_stale_checkout_quote_returns_new_quote_without_mutation(
    client,
    seed_hotels,
    login_as,
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
    old_quote = preview.json["quote"]

    service = Service(hotel_id=hotel.id, name="Phát sinh", price=50000)
    db.session.add(service)
    db.session.flush()
    db.session.add(
        BookingService(
            hotel_id=hotel.id,
            booking_id=booking_room.booking_id,
            room_id=booking_room.room_id,
            service_id=service.id,
            quantity=1,
            price_at_booking=50000,
        )
    )
    db.session.commit()

    response = client.post(
        f"/{hotel.slug}/bookings/api/rooms/checkout",
        json={
            "number": booking_room.room.room_number,
            "booking_room_id": booking_room.id,
            "booking_id": booking_room.booking_id,
            "amount": 1,
            "quote_fingerprint": old_quote["fingerprint"],
            "quote_checkout_at": old_quote["checkout_at"],
        },
    )

    assert response.status_code == 409
    assert response.json["error_code"] == "quote_stale"
    assert response.json["quote"]["fingerprint"] != old_quote["fingerprint"]
    db.session.refresh(booking_room)
    assert booking_room.status == "checked_in"
    assert booking_room.room.status == "occupied"
    assert Payment.query.count() == 0
    assert BusinessOperation.query.count() == 0


def test_checkout_frontend_submits_quote_identity_and_refreshes_stale_quote():
    source = open("static/js/checkout.js", encoding="utf-8").read()

    assert "currentCheckoutQuote" in source
    assert "quote_fingerprint" in source
    assert "quote_checkout_at" in source
    assert "quote_stale" in source
    assert "checkout-status" in source
    assert "amount: amount" not in source
    assert "payment_method: 'cash'" in source
