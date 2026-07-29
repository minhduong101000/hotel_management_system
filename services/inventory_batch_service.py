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
