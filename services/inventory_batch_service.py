from datetime import date
from decimal import Decimal

from extensions import db
from models.inventory_batch import InventoryBatch
from models.inventory_movement import InventoryMovement


def _require_item_in_hotel(item, hotel_id):
    if item is None:
        raise ValueError('Vật tư không tồn tại.')
    if hotel_id is not None and item.hotel_id != hotel_id:
        raise ValueError('Vật tư không thuộc khách sạn hiện tại.')


def _next_batch_code(item, received_at):
    prefix = f'{item.code}-{received_at:%Y%m%d}'
    count = InventoryBatch.query.filter(
        InventoryBatch.hotel_id == item.hotel_id,
        InventoryBatch.batch_code.like(f'{prefix}-%'),
    ).count()
    return f'{prefix}-{count + 1:02d}'


def _validate_receipt(quantity, received_at, expires_at):
    if int(quantity or 0) <= 0:
        raise ValueError('Số lượng nhập phải lớn hơn 0.')
    if not received_at:
        raise ValueError('Cần có ngày nhập kho.')
    if expires_at and expires_at <= received_at:
        raise ValueError('Hạn dùng phải sau ngày nhập kho.')


def create_receipt_batch(
    *,
    item,
    quantity,
    received_at=None,
    expires_at=None,
    unit_cost=0,
    batch_code=None,
    expense_id=None,
    actor_user_id=None,
    hotel_id=None,
    reason='Nhập kho',
):
    """Create an inventory receipt batch and its immutable ledger entry."""
    _require_item_in_hotel(item, hotel_id)
    received_at = received_at or date.today()
    _validate_receipt(quantity, received_at, expires_at)
    quantity = int(quantity)

    batch = InventoryBatch(
        hotel_id=item.hotel_id,
        inventory_item_id=item.id,
        expense_id=expense_id,
        batch_code=batch_code or _next_batch_code(item, received_at),
        received_at=received_at,
        expires_at=expires_at,
        quantity_received=quantity,
        quantity_available=quantity,
        unit_cost=Decimal(str(unit_cost or 0)),
        status='active',
        created_by=actor_user_id,
    )
    db.session.add(batch)
    db.session.flush()

    item.quantity = int(item.quantity or 0) + quantity
    db.session.add(InventoryMovement(
        hotel_id=item.hotel_id,
        inventory_item_id=item.id,
        batch_id=batch.id,
        expense_id=expense_id,
        movement_type='receipt',
        quantity_delta=quantity,
        reason=reason,
        created_by=actor_user_id,
    ))
    return batch


def backfill_opening_batch(item, actor_user_id=None):
    """Create one non-expiring opening batch without changing legacy totals."""
    _require_item_in_hotel(item, item.hotel_id)
    quantity = int(item.quantity or 0)
    if quantity <= 0:
        raise ValueError('Chỉ có thể tạo lô tồn đầu cho vật tư còn tồn.')

    existing = InventoryBatch.query.filter_by(inventory_item_id=item.id).first()
    if existing:
        return existing

    received_at = date.today()
    batch = InventoryBatch(
        hotel_id=item.hotel_id,
        inventory_item_id=item.id,
        batch_code=f'TONDAU-{item.code}-{item.id}',
        received_at=received_at,
        quantity_received=quantity,
        quantity_available=quantity,
        unit_cost=Decimal(str(item.price or 0)),
        status='active',
        created_by=actor_user_id,
    )
    db.session.add(batch)
    db.session.flush()
    db.session.add(InventoryMovement(
        hotel_id=item.hotel_id,
        inventory_item_id=item.id,
        batch_id=batch.id,
        movement_type='receipt',
        quantity_delta=quantity,
        reason='Tồn đầu',
        created_by=actor_user_id,
    ))
    return batch


def available_quantity(item, on_date=None):
    on_date = on_date or date.today()
    batches = InventoryBatch.query.filter_by(inventory_item_id=item.id).all()
    if not batches:
        return int(item.quantity or 0)
    return sum(
        int(batch.quantity_available or 0)
        for batch in batches
        if batch.status == 'active' and (batch.expires_at is None or batch.expires_at >= on_date)
    )


def batches_for_consumption(item, on_date=None):
    on_date = on_date or date.today()
    batches = InventoryBatch.query.filter_by(inventory_item_id=item.id, status='active').all()
    return sorted(
        (batch for batch in batches if int(batch.quantity_available or 0) > 0 and (batch.expires_at is None or batch.expires_at >= on_date)),
        key=lambda batch: (batch.expires_at is None, batch.expires_at or date.max, batch.id),
    )


def dispose_batch(*, batch, quantity, reason, actor_user_id=None, hotel_id=None, note=None):
    if hotel_id is not None and batch.hotel_id != hotel_id:
        raise ValueError('Lô hàng không thuộc khách sạn hiện tại.')
    quantity = int(quantity or 0)
    if quantity <= 0:
        raise ValueError('Số lượng hủy phải lớn hơn 0.')
    if not (reason or '').strip():
        raise ValueError('Cần nhập lý do hủy hàng.')
    if quantity > int(batch.quantity_available or 0):
        raise ValueError('Số lượng hủy vượt quá tồn của lô.')
    batch.quantity_available -= quantity
    if batch.quantity_available == 0:
        batch.status = 'depleted'
    item = batch.item
    item.quantity = max(0, int(item.quantity or 0) - quantity)
    db.session.add(InventoryMovement(
        hotel_id=batch.hotel_id, inventory_item_id=item.id, batch_id=batch.id,
        movement_type='disposal', quantity_delta=-quantity, reason=reason.strip(), note=note,
        created_by=actor_user_id,
    ))
    return batch


def adjust_batch(*, batch, quantity_delta, reason, actor_user_id=None, hotel_id=None, note=None):
    if hotel_id is not None and batch.hotel_id != hotel_id:
        raise ValueError('Lô hàng không thuộc khách sạn hiện tại.')
    quantity_delta = int(quantity_delta or 0)
    if quantity_delta == 0:
        raise ValueError('Số lượng điều chỉnh phải khác 0.')
    if not (reason or '').strip():
        raise ValueError('Cần nhập lý do điều chỉnh.')
    if int(batch.quantity_available or 0) + quantity_delta < 0:
        raise ValueError('Điều chỉnh không được làm tồn kho âm.')
    batch.quantity_available += quantity_delta
    batch.status = 'active' if batch.quantity_available > 0 else 'depleted'
    item = batch.item
    item.quantity = int(item.quantity or 0) + quantity_delta
    db.session.add(InventoryMovement(
        hotel_id=batch.hotel_id, inventory_item_id=item.id, batch_id=batch.id,
        movement_type='adjustment_in' if quantity_delta > 0 else 'adjustment_out',
        quantity_delta=quantity_delta, reason=reason.strip(), note=note, created_by=actor_user_id,
    ))
    return batch
