from datetime import datetime, timedelta
from decimal import Decimal

from extensions import db
from models import (
    AuditEvent,
    BookingRoom,
    BookingService,
    BusinessOperation,
    Payment,
    Room,
    Service,
)
from services import payment_service, time_service


def _add_room(
    *,
    hotel,
    booking,
    room_number,
    status,
    nightly_amount,
    final_amount=0,
):
    # check_in_expected/check_out_expected: giờ nghiệp vụ (business_now_naive).
    # check_in_actual/check_out_actual: UTC-naive (utc_now_naive) — đây là các
    # cột hệ thống mà booking_quote_service quy đổi ngược qua to_business_naive().
    business_now = time_service.business_now_naive().replace(microsecond=0)
    actual_now = time_service.utc_now_naive().replace(microsecond=0)
    room = Room(
        hotel_id=hotel.id,
        room_number=room_number,
        room_type="Standard",
        price_per_night=nightly_amount,
        price_initial_block=nightly_amount,
        initial_hours=2,
        status="occupied" if status == "checked_in" else "available",
    )
    db.session.add(room)
    db.session.flush()
    booking_room = BookingRoom(
        hotel_id=hotel.id,
        booking_id=booking.id,
        room_id=room.id,
        status=status,
        rental_type="daily",
        check_in_expected=business_now - timedelta(days=1),
        check_out_expected=business_now,
        check_in_actual=(
            actual_now - timedelta(days=1)
            if status in ("checked_in", "checked_out")
            else None
        ),
        check_out_actual=actual_now if status == "checked_out" else None,
        final_amount=final_amount,
        price_breakdown_snapshot=[
            {
                "business_date": (business_now - timedelta(days=1)).date().isoformat(),
                "amount": float(nightly_amount),
            }
        ],
    )
    db.session.add(booking_room)
    db.session.flush()
    return booking_room


def _group_quote(client, hotel, booking_id, include_tax=False):
    response = client.get(
        f"/{hotel.slug}/bookings/api/bookings/{booking_id}/group_billing",
        query_string={"include_tax": str(include_tax).lower()},
    )
    assert response.status_code == 200
    quote = response.json["data"]["quote"]
    return quote, {
        "include_tax": include_tax,
        "payment_method": "cash",
        "quote_fingerprint": quote["fingerprint"],
        "quote_checkout_at": quote["checkout_at"],
    }


def test_group_checkout_blocks_all_rooms_when_one_is_still_booked(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, user, _, checked_in_room, _ = seed_hotels
    booking = checked_in_room.booking
    checked_in_room.status = "checked_in"
    checked_in_room.check_in_actual = datetime.now() - timedelta(days=1)
    checked_in_room.room.status = "occupied"
    booked_room = _add_room(
        hotel=hotel,
        booking=booking,
        room_number="102",
        status="booked",
        nightly_amount=600000,
    )
    db.session.commit()
    login_as(client, user)
    quote, payload = _group_quote(client, hotel, booking.id)

    assert quote["state_groups"]["booked"] == ["102"]
    response = client.post(
        f"/{hotel.slug}/bookings/api/bookings/{booking.id}/group_checkout",
        json=payload,
    )

    assert response.status_code == 409
    assert response.json["error_code"] == "rooms_not_checked_in"
    assert response.json["room_numbers"] == ["102"]
    db.session.refresh(checked_in_room)
    db.session.refresh(booked_room)
    assert checked_in_room.status == "checked_in"
    assert booked_room.status == "booked"
    assert Payment.query.count() == 0
    assert BusinessOperation.query.count() == 0
    assert AuditEvent.query.count() == 0


def test_group_checkout_without_checked_in_room_preserves_existing_total(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking = booking_room.booking
    booking_room.status = "checked_out"
    booking_room.final_amount = Decimal("400000")
    booking.total_amount = Decimal("400000")
    booking.status = "completed"
    booking.payment_status = "paid"
    db.session.commit()
    login_as(client, user)
    quote, payload = _group_quote(client, hotel, booking.id)

    response = client.post(
        f"/{hotel.slug}/bookings/api/bookings/{booking.id}/group_checkout",
        json=payload,
    )

    assert response.status_code == 409
    assert response.json["error_code"] == "no_rooms_checked_in"
    db.session.refresh(booking)
    assert booking.total_amount == Decimal("400000")
    assert booking.status == "completed"
    assert booking.payment_status == "paid"
    assert Payment.query.count() == 0
    assert BusinessOperation.query.count() == 0
    assert AuditEvent.query.count() == 0


def test_group_checkout_keeps_finalized_rooms_and_replays_without_duplicates(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, user, _, finalized_room, _ = seed_hotels
    booking = finalized_room.booking
    finalized_room.status = "checked_out"
    finalized_room.final_amount = Decimal("400000")
    finalized_room.room.status = "available"
    booking.prepaid_amount = Decimal("100000")
    active_room = _add_room(
        hotel=hotel,
        booking=booking,
        room_number="102",
        status="checked_in",
        nightly_amount=600000,
    )
    service = Service(hotel_id=hotel.id, name="Giặt ủi", price=10000)
    db.session.add(service)
    db.session.flush()
    db.session.add(
        BookingService(
            hotel_id=hotel.id,
            booking_id=booking.id,
            room_id=active_room.room_id,
            service_id=service.id,
            quantity=2,
            price_at_booking=10000,
        )
    )
    db.session.commit()
    login_as(client, user)
    quote, payload = _group_quote(client, hotel, booking.id, include_tax=True)

    assert Decimal(quote["settlement_total"]) == Decimal("669600.00")
    assert Decimal(quote["booking_total"]) == Decimal("1069600.00")
    assert Decimal(quote["balance"]) == Decimal("569600.00")
    first = client.post(
        f"/{hotel.slug}/bookings/api/bookings/{booking.id}/group_checkout",
        json=payload,
    )
    retry = client.post(
        f"/{hotel.slug}/bookings/api/bookings/{booking.id}/group_checkout",
        json={**payload, "amount": -999999999},
    )

    assert first.status_code == 200
    assert retry.status_code == 200
    assert retry.json == first.json
    db.session.expire_all()
    assert finalized_room.status == "checked_out"
    assert finalized_room.final_amount == Decimal("400000")
    assert active_room.status == "checked_out"
    assert active_room.final_amount == Decimal("669600.00")
    assert booking.total_amount == Decimal("1069600.00")
    assert booking.prepaid_amount == 0
    assert booking.status == "completed"
    assert booking.payment_status == "paid"
    assert sum(
        (payment.amount for payment in Payment.query.all()),
        Decimal("0"),
    ) == Decimal("569600.00")
    assert Payment.query.filter_by(payment_type="tax_payment").count() == 1
    operation = BusinessOperation.query.one()
    assert operation.operation_key == f"checkout_group:booking:{booking.id}"
    assert all(
        payment.business_operation_id == operation.id
        for payment in Payment.query.all()
    )
    assert AuditEvent.query.filter_by(action="group_checkout").count() == 1


def test_group_checkout_excess_deposit_returns_credit_without_refund(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking = booking_room.booking
    booking_room.status = "checked_in"
    booking_room.check_in_actual = datetime.now() - timedelta(days=1)
    booking_room.room.status = "occupied"
    db.session.commit()
    login_as(client, user)

    # Chống phụ thuộc giờ chạy: lấy hóa đơn thật rồi đặt cọc = hóa đơn + 100k
    # -> balance luôn đúng -100k dù test chạy lúc mấy giờ.
    base_quote, _ = _group_quote(client, hotel, booking.id)
    booking.prepaid_amount = Decimal(str(base_quote["settlement_total"])) + Decimal("100000")
    booking_room.room_deposit_amount = booking.prepaid_amount
    db.session.commit()
    quote, payload = _group_quote(client, hotel, booking.id)

    assert Decimal(quote["balance"]) == Decimal("-100000.00")
    response = client.post(
        f"/{hotel.slug}/bookings/api/bookings/{booking.id}/group_checkout",
        json=payload,
    )

    assert response.status_code == 200
    data = response.json["data"]
    assert Decimal(str(data["unrefunded_credit"])) == Decimal("100000.00")
    assert Payment.query.filter_by(payment_type="refund").count() == 0
    assert Payment.query.count() == 0
    assert booking_room.status == "checked_out"


def test_group_checkout_failure_rolls_back_every_room(
    client,
    seed_hotels,
    login_as,
    monkeypatch,
):
    hotel, _, user, _, first_room, _ = seed_hotels
    booking = first_room.booking
    first_room.status = "checked_in"
    first_room.check_in_actual = datetime.now() - timedelta(days=1)
    first_room.room.status = "occupied"
    second_room = _add_room(
        hotel=hotel,
        booking=booking,
        room_number="102",
        status="checked_in",
        nightly_amount=600000,
    )
    db.session.commit()
    login_as(client, user)
    quote, payload = _group_quote(client, hotel, booking.id)

    def fail_payment(*_args, **_kwargs):
        raise RuntimeError("forced group checkout failure")

    monkeypatch.setattr(payment_service, "record_room_payment", fail_payment)
    response = client.post(
        f"/{hotel.slug}/bookings/api/bookings/{booking.id}/group_checkout",
        json=payload,
    )

    assert response.status_code == 500
    assert response.json["error_code"] == "group_checkout_failed"
    db.session.expire_all()
    assert first_room.status == "checked_in"
    assert second_room.status == "checked_in"
    assert first_room.room.status == "occupied"
    assert second_room.room.status == "occupied"
    assert Payment.query.count() == 0
    assert BusinessOperation.query.count() == 0
    assert AuditEvent.query.count() == 0


def test_group_checkout_frontend_uses_quote_and_accessible_state_feedback():
    source = open("static/js/checkout.js", encoding="utf-8").read()
    modal = open(
        "templates/rooms/_group_checkout_modal.html",
        encoding="utf-8",
    ).read()

    assert "currentGroupCheckoutQuote" in source
    assert "quote_fingerprint" in source
    assert "rooms_not_checked_in" in source
    assert "groupCheckoutSubmitting" in source
    assert 'id="gc-checkout-status"' in modal
    assert 'aria-live="polite"' in modal
    assert 'aria-busy="false"' in modal
    assert 'aria-labelledby="groupCheckoutModalLabel"' in modal
