from __future__ import annotations

from collections import defaultdict

from models.inventory_batch import InventoryBatch
from models.inventory_item import InventoryItem
from models.inventory_movement import InventoryMovement
from models.booking_service_batch_allocation import BookingServiceBatchAllocation
from services import inventory_batch_service
from extensions import db


class InsufficientInventoryError(ValueError):
    """Raised before an order would make a hotel's inventory negative."""


def _items_for_service(hotel_id: int, service_id: int, lock=False):
    query = InventoryItem.query.filter_by(
        hotel_id=hotel_id,
        service_id=service_id,
    ).order_by(InventoryItem.id.asc())
    if lock:
        query = query.with_for_update()
    return query.all()


def validate_inventory(hotel_id: int, requirements: dict[int, int], as_of_date=None) -> None:
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

        available = sum(
            inventory_batch_service.available_quantity(item, on_date=as_of_date)
            for item in items
        )
        if available < quantity:
            raise InsufficientInventoryError(
                f"Dịch vụ {service_id} không đủ tồn kho (còn {available}, cần {quantity})."
            )


def deduct_inventory(
    hotel_id: int,
    service_id: int,
    quantity: int,
    booking_service=None,
    as_of_date=None,
) -> None:
    """Deduct already-validated stock for one service within one hotel.

    as_of_date: ngày nghiệp vụ dùng để loại lô hết hạn (FEFO); mặc định
    lấy từ time_service. Thiếu tồn -> raise TRƯỚC khi ghi bất kỳ thứ gì,
    không bao giờ để lại partial movement/allocation.
    """
    quantity = int(quantity or 0)
    if quantity <= 0:
        return

    items = _items_for_service(hotel_id, service_id, lock=True)
    if not items:
        return

    # Validate đủ tồn còn dùng được TRƯỚC khi mutate (no partial write)
    total_available = 0
    for item in items:
        if not item.batches:
            total_available += max(0, int(item.quantity or 0))
        else:
            total_available += sum(
                int(batch.quantity_available or 0)
                for batch in inventory_batch_service.batches_for_consumption(
                    item, on_date=as_of_date
                )
            )
    if total_available < quantity:
        raise InsufficientInventoryError(
            "Tồn kho đã thay đổi trước khi ghi nhận dịch vụ."
        )

    remaining = quantity
    for item in items:
        if not item.batches:
            deducted = min(max(0, int(item.quantity or 0)), remaining)
            item.quantity = int(item.quantity or 0) - deducted
            remaining -= deducted
            if remaining == 0:
                return
            continue
        for batch in inventory_batch_service.batches_for_consumption(
            item,
            on_date=as_of_date,
            lock=True,
        ):
            deducted = min(int(batch.quantity_available or 0), remaining)
            if deducted <= 0:
                continue
            batch.quantity_available -= deducted
            if batch.quantity_available == 0:
                batch.status = 'depleted'
            item.quantity = int(item.quantity or 0) - deducted
            db.session.add(InventoryMovement(
                hotel_id=hotel_id, inventory_item_id=item.id, batch_id=batch.id,
                booking_service_id=(
                    booking_service.id
                    if booking_service is not None
                    else None
                ),
                movement_type='consumption', quantity_delta=-deducted,
                reason='Dùng dịch vụ',
            ))
            if booking_service is not None:
                allocation = BookingServiceBatchAllocation.query.filter_by(
                    hotel_id=hotel_id,
                    booking_service_id=booking_service.id,
                    batch_id=batch.id,
                ).with_for_update().first()
                if allocation is None:
                    allocation = BookingServiceBatchAllocation(
                        hotel_id=hotel_id,
                        booking_service_id=booking_service.id,
                        batch_id=batch.id,
                        quantity=0,
                    )
                    db.session.add(allocation)
                allocation.quantity = int(allocation.quantity or 0) + deducted
            remaining -= deducted
            if remaining == 0:
                return

    raise InsufficientInventoryError("Tồn kho đã thay đổi trước khi ghi nhận dịch vụ.")


def restore_inventory(hotel_id: int, service_id: int, quantity: int, booking_service=None) -> None:
    """Restore stock when a bill quantity is reduced; no-op if unmanaged."""
    quantity = int(quantity or 0)
    if quantity <= 0:
        return

    items = _items_for_service(hotel_id, service_id, lock=True)
    if items:
        if not any(item.batches for item in items):
            items[0].quantity = int(items[0].quantity or 0) + quantity
            return
        if booking_service is None:
            raise ValueError(
                "Cần booking_service để hoàn tồn kho theo đúng lô gốc."
            )
        allocations = BookingServiceBatchAllocation.query.filter_by(
            hotel_id=hotel_id,
            booking_service_id=booking_service.id,
        ).order_by(
            BookingServiceBatchAllocation.id.desc()
        ).with_for_update().all()
        remaining = quantity
        for allocation in allocations:
            allocated_quantity = int(allocation.quantity or 0)
            if allocated_quantity <= 0:
                continue
            batch = InventoryBatch.query.filter_by(
                id=allocation.batch_id,
                hotel_id=hotel_id,
            ).with_for_update().one()
            restored = min(allocated_quantity, remaining)
            batch.quantity_available += restored
            batch.status = 'active'
            item = batch.item
            item.quantity = int(item.quantity or 0) + restored
            allocation.quantity -= restored
            db.session.add(InventoryMovement(
                hotel_id=hotel_id,
                inventory_item_id=item.id,
                batch_id=allocation.batch_id,
                booking_service_id=booking_service.id,
                movement_type='adjustment_in',
                quantity_delta=restored,
                reason='Hoàn dịch vụ',
            ))
            remaining -= restored
            if remaining == 0:
                return
        if remaining:
            raise ValueError(
                "Số lượng hoàn vượt quá phân bổ lô của dịch vụ."
            )


def aggregate_quantities(items):
    """Return service_id -> quantity totals from validated order data."""
    totals = defaultdict(int)
    for service_id, quantity in items:
        totals[int(service_id)] += int(quantity)
    return dict(totals)
