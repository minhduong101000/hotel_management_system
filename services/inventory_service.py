from __future__ import annotations

from collections import defaultdict

from models.inventory_item import InventoryItem
from models.inventory_movement import InventoryMovement
from models.booking_service_batch_allocation import BookingServiceBatchAllocation
from services import inventory_batch_service
from extensions import db


class InsufficientInventoryError(ValueError):
    """Raised before an order would make a hotel's inventory negative."""


def _items_for_service(hotel_id: int, service_id: int):
    return InventoryItem.query.filter_by(
        hotel_id=hotel_id,
        service_id=service_id,
    ).order_by(InventoryItem.id.asc()).all()


def validate_inventory(hotel_id: int, requirements: dict[int, int]) -> None:
    """Validate all positive deductions before mutating any inventory record.

    Services without an InventoryItem remain billable because they are not
    stock-managed. When stock-managed, the sum of linked items is the
    available quantity and cannot become negative.
    """
    for service_id, requested in requirements.items():
        quantity = int(requested or 0)
        if quantity <= 0:
            continue

        items = _items_for_service(hotel_id, service_id)
        if not items:
            continue

        available = sum(inventory_batch_service.available_quantity(item) for item in items)
        if available < quantity:
            raise InsufficientInventoryError(
                f"Dịch vụ {service_id} không đủ tồn kho (còn {available}, cần {quantity})."
            )


def deduct_inventory(hotel_id: int, service_id: int, quantity: int, booking_service=None) -> None:
    """Deduct already-validated stock for one service within one hotel."""
    quantity = int(quantity or 0)
    if quantity <= 0:
        return

    items = _items_for_service(hotel_id, service_id)
    if not items:
        return

    remaining = quantity
    for item in items:
        if not item.batches:
            deducted = min(max(0, int(item.quantity or 0)), remaining)
            item.quantity = int(item.quantity or 0) - deducted
            remaining -= deducted
            if remaining == 0:
                return
            continue
        for batch in inventory_batch_service.batches_for_consumption(item):
            deducted = min(int(batch.quantity_available or 0), remaining)
            if deducted <= 0:
                continue
            batch.quantity_available -= deducted
            if batch.quantity_available == 0:
                batch.status = 'depleted'
            item.quantity = int(item.quantity or 0) - deducted
            db.session.add(InventoryMovement(
                hotel_id=hotel_id, inventory_item_id=item.id, batch_id=batch.id,
                movement_type='consumption', quantity_delta=-deducted, reason='Dùng dịch vụ',
            ))
            if booking_service is not None:
                db.session.add(BookingServiceBatchAllocation(
                    hotel_id=hotel_id, booking_service_id=booking_service.id,
                    batch_id=batch.id, quantity=deducted,
                ))
            remaining -= deducted
            if remaining == 0:
                return

    raise InsufficientInventoryError("Tồn kho đã thay đổi trước khi ghi nhận dịch vụ.")


def restore_inventory(hotel_id: int, service_id: int, quantity: int, booking_service=None) -> None:
    """Restore stock when a bill quantity is reduced; no-op if unmanaged."""
    quantity = int(quantity or 0)
    if quantity <= 0:
        return

    items = _items_for_service(hotel_id, service_id)
    if items:
        item = items[0]
        if not item.batches:
            item.quantity = int(item.quantity or 0) + quantity
            return
        allocations = list(booking_service.batch_allocations) if booking_service is not None else []
        remaining = quantity
        for allocation in reversed(allocations):
            restored = min(allocation.quantity, remaining)
            allocation.batch.quantity_available += restored
            allocation.batch.status = 'active'
            item.quantity = int(item.quantity or 0) + restored
            allocation.quantity -= restored
            if allocation.quantity == 0:
                db.session.delete(allocation)
            db.session.add(InventoryMovement(hotel_id=hotel_id, inventory_item_id=item.id, batch_id=allocation.batch_id, movement_type='adjustment_in', quantity_delta=restored, reason='Hoàn dịch vụ'))
            remaining -= restored
            if remaining == 0:
                return
        if remaining:
            batches = inventory_batch_service.batches_for_consumption(item)
            if batches:
                batch = batches[0]
                batch.quantity_available += remaining
                item.quantity = int(item.quantity or 0) + remaining


def aggregate_quantities(items):
    """Return service_id -> quantity totals from validated order data."""
    totals = defaultdict(int)
    for service_id, quantity in items:
        totals[int(service_id)] += int(quantity)
    return dict(totals)
