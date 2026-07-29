from datetime import date, timedelta

import pytest

from extensions import db
from models import InventoryBatch, InventoryMovement
from models.inventory_item import InventoryItem
from services import inventory_batch_service


def _create_item(hotel, code='WATER'):
    item = InventoryItem(hotel_id=hotel.id, code=code, name='Nước suối', quantity=0, price=10000)
    db.session.add(item)
    db.session.commit()
    return item


def test_create_receipt_batch_updates_item_and_records_movement(app, seed_hotels):
    hotel, _, _, _, _, _ = seed_hotels
    with app.app_context():
        item = _create_item(hotel)

        batch = inventory_batch_service.create_receipt_batch(
            item=item,
            quantity=200,
            received_at=date(2026, 7, 29),
            expires_at=date(2026, 12, 31),
            unit_cost=10000,
            batch_code='NUOC-20260729-01',
        )
        db.session.commit()

        assert batch.hotel_id == hotel.id
        assert batch.quantity_received == 200
        assert batch.quantity_available == 200
        assert item.quantity == 200
        movement = InventoryMovement.query.one()
        assert movement.batch_id == batch.id
        assert movement.movement_type == 'receipt'
        assert movement.quantity_delta == 200


def test_receipt_batch_rejects_item_from_another_hotel(app, seed_hotels):
    hotel_a, hotel_b, _, _, _, _ = seed_hotels
    with app.app_context():
        foreign_item = InventoryItem(hotel_id=hotel_b.id, code='B-WATER', name='Nước B', quantity=0)
        db.session.add(foreign_item)
        db.session.commit()

        with pytest.raises(ValueError, match='khách sạn'):
            inventory_batch_service.create_receipt_batch(
                item=foreign_item,
                hotel_id=hotel_a.id,
                quantity=10,
                received_at=date.today(),
            )


def test_expiry_date_must_be_after_receipt_date(app, seed_hotels):
    hotel, _, _, _, _, _ = seed_hotels
    with app.app_context():
        item = _create_item(hotel)
        with pytest.raises(ValueError, match='Hạn dùng'):
            inventory_batch_service.create_receipt_batch(
                item=item,
                quantity=10,
                received_at=date.today(),
                expires_at=date.today(),
            )

        no_expiry_batch = inventory_batch_service.create_receipt_batch(
            item=item,
            quantity=10,
            received_at=date.today(),
        )
        assert no_expiry_batch.expires_at is None


def test_backfill_creates_opening_batch_without_changing_total(app, seed_hotels):
    hotel, _, _, _, _, _ = seed_hotels
    with app.app_context():
        item = _create_item(hotel)
        item.quantity = 17
        db.session.commit()

        batch = inventory_batch_service.backfill_opening_batch(item)
        db.session.commit()

        assert batch.quantity_received == 17
        assert batch.quantity_available == 17
        assert batch.expires_at is None
        assert item.quantity == 17
        assert InventoryMovement.query.filter_by(movement_type='receipt').count() == 1


def test_receipt_batch_rejects_non_positive_quantity(app, seed_hotels):
    hotel, _, _, _, _, _ = seed_hotels
    with app.app_context():
        item = _create_item(hotel)
        with pytest.raises(ValueError, match='Số lượng'):
            inventory_batch_service.create_receipt_batch(
                item=item,
                quantity=0,
                received_at=date.today() + timedelta(days=1),
            )
