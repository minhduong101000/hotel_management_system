from decimal import Decimal

import pytest

from extensions import db
from models.business_operation import BusinessOperation
from models.payment import Payment
from services import payment_service


def _operation(hotel_id, booking_room, key):
    operation = BusinessOperation(
        hotel_id=hotel_id,
        operation_key=key,
        action="checkout",
        entity_type="booking_room",
        entity_id=booking_room.id,
        request_fingerprint="fingerprint",
    )
    db.session.add(operation)
    db.session.flush()
    return operation


def test_payment_uses_decimal_and_links_to_operation_component(seed_hotels):
    hotel, _, _, _, booking_room, _ = seed_hotels
    operation = _operation(hotel.id, booking_room, "checkout:payment-link")

    payment = payment_service.record_room_payment(
        booking_id=booking_room.booking_id,
        amount="123456.78",
        note="Thanh toán tiền phòng",
        business_operation=operation,
        component_key="room:101",
        flush=True,
    )

    assert payment.hotel_id == hotel.id
    assert payment.amount == Decimal("123456.78")
    assert payment.business_operation_id == operation.id
    assert payment.component_key == "room:101"


def test_payment_rejects_operation_from_another_tenant(seed_hotels):
    hotel_a, hotel_b, _, _, booking_room_a, booking_room_b = seed_hotels
    operation = _operation(
        hotel_b.id,
        booking_room_b,
        "checkout:wrong-tenant",
    )

    with pytest.raises(ValueError, match="khác khách sạn"):
        payment_service.record_room_payment(
            booking_id=booking_room_a.booking_id,
            amount="100000",
            note="Không hợp lệ",
            business_operation=operation,
            component_key="room:101",
        )

    assert hotel_a.id != hotel_b.id
    assert Payment.query.count() == 0


def test_payment_component_constraint_is_named_and_tenant_scoped():
    constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in Payment.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }

    assert constraints["uq_payments_operation_component"] == (
        "hotel_id",
        "business_operation_id",
        "component_key",
    )
