from datetime import datetime
from decimal import Decimal

from extensions import db
from models import BusinessOperation, Payment


def _prepare_checkout(client, hotel, user, booking_room, login_as):
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
    payload = {
        "number": booking_room.room.room_number,
        "booking_room_id": booking_room.id,
        "booking_id": booking_room.booking_id,
        "include_tax": False,
        "payment_method": "cash",
        "quote_fingerprint": quote["fingerprint"],
        "quote_checkout_at": quote["checkout_at"],
    }
    return quote, payload


def test_checkout_ignores_client_amount_and_settles_server_quote(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    quote, payload = _prepare_checkout(
        client,
        hotel,
        user,
        booking_room,
        login_as,
    )
    payload["amount"] = 1

    response = client.post(
        f"/{hotel.slug}/bookings/api/rooms/checkout",
        json=payload,
    )

    assert response.status_code == 200
    payments = Payment.query.order_by(Payment.id).all()
    assert sum((payment.amount for payment in payments), Decimal("0")) == Decimal(
        quote["balance"]
    )
    assert all(payment.amount > 0 for payment in payments)
    assert booking_room.final_amount == Decimal(quote["total"])
    assert booking_room.status == "checked_out"
    assert booking_room.room.status == "available"
    assert booking_room.room.clean_status == "dirty"
    assert booking_room.booking.status == "completed"
    assert booking_room.booking.payment_status == "paid"
    assert booking_room.booking.prepaid_amount == 0


def test_excess_deposit_creates_refund_instead_of_negative_room_payment(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.booking.prepaid_amount = 600000
    booking_room.room_deposit_amount = 600000
    quote, payload = _prepare_checkout(
        client,
        hotel,
        user,
        booking_room,
        login_as,
    )

    assert Decimal(quote["balance"]) == Decimal("-100000.00")
    response = client.post(
        f"/{hotel.slug}/bookings/api/rooms/checkout",
        json=payload,
    )

    assert response.status_code == 200
    payment = Payment.query.one()
    assert payment.payment_type == "refund"
    assert payment.component_key == "refund"
    assert payment.amount == Decimal("-100000.00")
    assert Payment.query.filter_by(payment_type="room_payment").count() == 0
    assert booking_room.booking.payment_status == "paid"


def test_deposit_equal_to_total_completes_without_new_cash_payment(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.booking.prepaid_amount = 500000
    booking_room.room_deposit_amount = 500000
    quote, payload = _prepare_checkout(
        client,
        hotel,
        user,
        booking_room,
        login_as,
    )

    assert Decimal(quote["balance"]) == Decimal("0.00")
    response = client.post(
        f"/{hotel.slug}/bookings/api/rooms/checkout",
        json=payload,
    )

    assert response.status_code == 200
    assert Payment.query.count() == 0
    assert BusinessOperation.query.one().status == "completed"
    assert booking_room.booking.payment_status == "paid"
