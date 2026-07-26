from __future__ import annotations

from collections import defaultdict

from models.inventory_item import InventoryItem


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

        available = sum(max(0, int(item.quantity or 0)) for item in items)
        if available < quantity:
            raise InsufficientInventoryError(
                f"Dịch vụ {service_id} không đủ tồn kho (còn {available}, cần {quantity})."
            )


def deduct_inventory(hotel_id: int, service_id: int, quantity: int) -> None:
    """Deduct already-validated stock for one service within one hotel."""
    quantity = int(quantity or 0)
    if quantity <= 0:
        return

    items = _items_for_service(hotel_id, service_id)
    if not items:
        return

    remaining = quantity
    for item in items:
        deducted = min(max(0, int(item.quantity or 0)), remaining)
        item.quantity = int(item.quantity or 0) - deducted
        remaining -= deducted
        if remaining == 0:
            return

    raise InsufficientInventoryError("Tồn kho đã thay đổi trước khi ghi nhận dịch vụ.")


def restore_inventory(hotel_id: int, service_id: int, quantity: int) -> None:
    """Restore stock when a bill quantity is reduced; no-op if unmanaged."""
    quantity = int(quantity or 0)
    if quantity <= 0:
        return

    items = _items_for_service(hotel_id, service_id)
    if items:
        items[0].quantity = int(items[0].quantity or 0) + quantity


def aggregate_quantities(items):
    """Return service_id -> quantity totals from validated order data."""
    totals = defaultdict(int)
    for service_id, quantity in items:
        totals[int(service_id)] += int(quantity)
    return dict(totals)
