from datetime import date

from extensions import db
from models.inventory_item import InventoryItem
from services import inventory_batch_service


def test_adjustment_updates_batch_and_records_reason(app, seed_hotels):
    hotel, _, _, _, _, _ = seed_hotels
    with app.app_context():
        item = InventoryItem(hotel_id=hotel.id, code='ADJUST', name='Vật tư điều chỉnh', quantity=0)
        db.session.add(item)
        db.session.flush()
        batch = inventory_batch_service.create_receipt_batch(item=item, quantity=5, received_at=date.today())
        db.session.flush()

        inventory_batch_service.adjust_batch(batch=batch, quantity_delta=-2, reason='Kiểm kê cuối ca', hotel_id=hotel.id)

        assert batch.quantity_available == 3
        assert item.quantity == 3


def test_adjustment_requires_reason_and_never_makes_stock_negative(app, seed_hotels):
    hotel, _, _, _, _, _ = seed_hotels
    with app.app_context():
        item = InventoryItem(hotel_id=hotel.id, code='ADJUST-2', name='Vật tư điều chỉnh', quantity=0)
        db.session.add(item)
        db.session.flush()
        batch = inventory_batch_service.create_receipt_batch(item=item, quantity=1, received_at=date.today())

        import pytest
        with pytest.raises(ValueError, match='lý do'):
            inventory_batch_service.adjust_batch(batch=batch, quantity_delta=1, reason='', hotel_id=hotel.id)
        with pytest.raises(ValueError, match='âm'):
            inventory_batch_service.adjust_batch(batch=batch, quantity_delta=-2, reason='Kiểm kê', hotel_id=hotel.id)
