from __future__ import annotations

from extensions import db
from models.inventory_item import InventoryItem


def deduct_inventory(service_id: int, quantity: int) -> None:
    """Deduct inventory quantity for a service.

    Preserves legacy semantics in controllers:
    - Quantity <= 0 is treated as no-op (or delegated to restore when negative).
    - Inventory is clamped to >= 0.

    This function only mutates ORM objects; commit/rollback is the caller's responsibility.
    """
    if quantity is None:
        return

    qty = int(quantity)
    if qty < 0:
        restore_inventory(service_id, -qty)
        return
    if qty == 0:
        return

    inv_items = InventoryItem.query.filter_by(service_id=service_id).all()
    for inv in inv_items:
        inv.quantity = max(0, int(inv.quantity or 0) - qty)


def restore_inventory(service_id: int, quantity: int) -> None:
    """Restore inventory quantity for a service.

    This function only mutates ORM objects; commit/rollback is the caller's responsibility.
    """
    if quantity is None:
        return

    qty = int(quantity)
    if qty < 0:
        deduct_inventory(service_id, -qty)
        return
    if qty == 0:
        return

    inv_items = InventoryItem.query.filter_by(service_id=service_id).all()
    for inv in inv_items:
        inv.quantity = int(inv.quantity or 0) + qty
