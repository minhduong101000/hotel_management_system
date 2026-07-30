from decimal import Decimal

import pytest

from extensions import db
from models.business_operation import BusinessOperation
from models.inventory_item import InventoryItem
from models.payment import Payment
from services import business_operation_service, payment_service


def test_completed_operation_replays_stored_result_without_running_handler_again(
    seed_hotels,
):
    hotel, _, _, _, booking_room, _ = seed_hotels
    booking_id = booking_room.booking_id
    hotel_id = hotel.id
    booking_room_id = booking_room.id
    db.session.rollback()
    calls = []

    def handler(operation):
        calls.append(operation.operation_key)
        payment_service.record_room_payment(
            booking_id=booking_id,
            amount=Decimal("100000.25"),
            note="Thanh toán test",
            business_operation=operation,
            component_key="room:101",
        )
        return {"success": True, "amount": "100000.25"}

    first_result, first_replayed = business_operation_service.execute_operation(
        hotel_id=hotel_id,
        operation_key="checkout:test-result",
        action="checkout",
        entity_type="booking_room",
        entity_id=booking_room_id,
        request_payload={"amount": "100000.25"},
        handler=handler,
    )
    second_result, second_replayed = business_operation_service.execute_operation(
        hotel_id=hotel_id,
        operation_key="checkout:test-result",
        action="checkout",
        entity_type="booking_room",
        entity_id=booking_room_id,
        request_payload={"amount": "100000.25"},
        handler=handler,
    )

    assert first_replayed is False
    assert second_replayed is True
    assert second_result == first_result == {
        "success": True,
        "amount": "100000.25",
    }
    assert calls == ["checkout:test-result"]
    operation = BusinessOperation.query.one()
    assert operation.status == "completed"
    assert operation.request_fingerprint
    assert operation.result_snapshot == first_result
    assert Payment.query.one().business_operation_id == operation.id


def test_retry_with_changed_request_is_rejected(seed_hotels):
    hotel, _, _, _, booking_room, _ = seed_hotels
    hotel_id = hotel.id
    booking_room_id = booking_room.id
    db.session.rollback()

    business_operation_service.execute_operation(
        hotel_id=hotel_id,
        operation_key="checkout:fingerprint",
        action="checkout",
        entity_type="booking_room",
        entity_id=booking_room_id,
        request_payload={"amount": "100000"},
        handler=lambda _operation: {"success": True},
    )

    with pytest.raises(
        business_operation_service.OperationRequestConflict,
        match="không khớp",
    ):
        business_operation_service.execute_operation(
            hotel_id=hotel_id,
            operation_key="checkout:fingerprint",
            action="checkout",
            entity_type="booking_room",
            entity_id=booking_room_id,
            request_payload={"amount": "200000"},
            handler=lambda _operation: {"success": True},
        )


def test_operation_exception_rolls_back_state_payment_and_operation(seed_hotels):
    hotel, _, _, _, booking_room, _ = seed_hotels
    inventory_item = InventoryItem(
        hotel_id=hotel.id,
        code="ROLLBACK",
        name="Vật tư rollback",
        quantity=10,
    )
    db.session.add(inventory_item)
    db.session.commit()

    booking_id = booking_room.booking_id
    original_status = booking_room.status
    hotel_id = hotel.id
    booking_room_id = booking_room.id
    inventory_item_id = inventory_item.id
    db.session.rollback()

    def failing_handler(operation):
        booking_room.status = "checked_out"
        db.session.get(InventoryItem, inventory_item_id).quantity = 5
        payment_service.record_room_payment(
            booking_id=booking_id,
            amount=Decimal("50000"),
            note="Phải rollback",
            business_operation=operation,
            component_key="room:rollback",
        )
        raise RuntimeError("forced failure")

    with pytest.raises(RuntimeError, match="forced failure"):
        business_operation_service.execute_operation(
            hotel_id=hotel_id,
            operation_key="checkout:rollback",
            action="checkout",
            entity_type="booking_room",
            entity_id=booking_room_id,
            request_payload={"amount": "50000"},
            handler=failing_handler,
        )

    db.session.expire_all()
    assert booking_room.status == original_status
    assert db.session.get(InventoryItem, inventory_item_id).quantity == 10
    assert BusinessOperation.query.count() == 0
    assert Payment.query.count() == 0
