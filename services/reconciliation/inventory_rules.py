from models import BookingService
from models.inventory_item import InventoryItem
from services.reconciliation.common import issue


def reconcile_inventory_totals(hotel_id, *, apply):
    issues = []
    items = (
        InventoryItem.query.filter_by(hotel_id=hotel_id)
        .order_by(InventoryItem.id)
        .all()
    )
    for item in items:
        batches = list(item.batches)
        if not batches:
            continue
        expected_quantity = sum(
            int(batch.quantity_available or 0)
            for batch in batches
            if batch.hotel_id == hotel_id
        )
        if int(item.quantity or 0) != expected_quantity:
            current_quantity = int(item.quantity or 0)
            if apply:
                item.quantity = expected_quantity
            issues.append(
                issue(
                    rule="inventory_total",
                    entity_type="inventory_item",
                    entity_id=item.id,
                    current=current_quantity,
                    expected=expected_quantity,
                    can_apply=True,
                    applied=apply,
                )
            )
    return issues


def reconcile_service_allocations(hotel_id, *, apply):
    del apply
    issues = []
    lines = (
        BookingService.query.filter_by(hotel_id=hotel_id)
        .order_by(BookingService.id)
        .all()
    )
    for line in lines:
        stock_items = [
            item
            for item in line.service.inventory_items
            if item.hotel_id == hotel_id and item.batches
        ]
        if not stock_items:
            continue
        allocated = sum(
            int(allocation.quantity or 0)
            for allocation in line.batch_allocations
            if allocation.hotel_id == hotel_id
        )
        expected = int(line.quantity or 0)
        if allocated != expected:
            issues.append(
                issue(
                    rule="service_allocation",
                    entity_type="booking_service",
                    entity_id=line.id,
                    current=allocated,
                    expected=expected,
                    note="Không tự phân bổ lại lô khi thiếu lịch sử movement.",
                )
            )
    return issues
