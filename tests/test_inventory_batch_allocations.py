from datetime import date, timedelta

from extensions import db
from models.booking_service import BookingService
from models.booking_service_batch_allocation import BookingServiceBatchAllocation
from models.inventory_item import InventoryItem
from models.inventory_movement import InventoryMovement
from models.service import Service
from services import inventory_batch_service, inventory_service


def test_consumption_and_restore_use_the_same_batches(app, seed_hotels):
    hotel, _, _, _, booking_room, _ = seed_hotels
    with app.app_context():
        service = Service(hotel_id=hotel.id, name='Nước đóng chai', price=10000)
        item = InventoryItem(hotel_id=hotel.id, code='WATER-LOT', name='Nước', quantity=0, service=service)
        db.session.add_all([service, item])
        db.session.flush()
        # Đồng hồ nghiệp vụ inject được -> ngày cố định, chạy đúng ở MỌI ngày thực
        as_of = date(2026, 7, 1)
        early = inventory_batch_service.create_receipt_batch(item=item, quantity=2, received_at=date(2026, 1, 1), expires_at=date(2026, 8, 1))
        later = inventory_batch_service.create_receipt_batch(item=item, quantity=3, received_at=date(2026, 1, 1), expires_at=date(2026, 9, 1))
        line = BookingService(hotel_id=hotel.id, booking_id=booking_room.booking_id, room_id=booking_room.room_id, service_id=service.id, quantity=3, price_at_booking=10000)
        db.session.add(line)
        db.session.flush()

        inventory_service.deduct_inventory(hotel.id, service.id, 3, booking_service=line, as_of_date=as_of)
        db.session.flush()
        allocations = BookingServiceBatchAllocation.query.order_by(BookingServiceBatchAllocation.batch_id).all()
        assert [(allocation.batch_id, allocation.quantity) for allocation in allocations] == [(early.id, 2), (later.id, 1)]

        inventory_service.restore_inventory(hotel.id, service.id, 2, booking_service=line)
        db.session.flush()
        assert early.quantity_available == 1
        assert later.quantity_available == 3
        allocations = BookingServiceBatchAllocation.query.order_by(
            BookingServiceBatchAllocation.batch_id
        ).all()
        assert [
            (allocation.batch_id, allocation.quantity)
            for allocation in allocations
        ] == [(early.id, 1), (later.id, 0)]
        assert all(
            movement.booking_service_id == line.id
            for movement in InventoryMovement.query.filter(
                InventoryMovement.movement_type.in_(
                    ["consumption", "adjustment_in"]
                )
            ).all()
        )
        assert item.quantity == sum(
            batch.quantity_available for batch in item.batches
        )


def test_incremental_consumption_merges_allocation_for_the_same_batch(
    app,
    seed_hotels,
):
    hotel, _, _, _, booking_room, _ = seed_hotels
    with app.app_context():
        service = Service(hotel_id=hotel.id, name="Nước lon", price=12000)
        item = InventoryItem(
            hotel_id=hotel.id,
            code="CAN-LOT",
            name="Nước lon",
            quantity=0,
            service=service,
        )
        db.session.add_all([service, item])
        db.session.flush()
        batch = inventory_batch_service.create_receipt_batch(
            item=item,
            quantity=5,
            received_at=date(2026, 1, 1),
            expires_at=date(2026, 12, 1),
        )
        line = BookingService(
            hotel_id=hotel.id,
            booking_id=booking_room.booking_id,
            room_id=booking_room.room_id,
            service_id=service.id,
            quantity=2,
            price_at_booking=service.price,
        )
        db.session.add(line)
        db.session.flush()

        inventory_service.deduct_inventory(
            hotel.id, service.id, 1, booking_service=line, as_of_date=date(2026, 7, 1),
        )
        inventory_service.deduct_inventory(
            hotel.id, service.id, 1, booking_service=line, as_of_date=date(2026, 7, 1),
        )
        db.session.flush()

        allocation = BookingServiceBatchAllocation.query.one()
        assert allocation.batch_id == batch.id
        assert allocation.quantity == 2
        assert batch.quantity_available == 3
        assert item.quantity == 3
        assert InventoryMovement.query.filter_by(
            movement_type="consumption",
            booking_service_id=line.id,
        ).count() == 2


def test_expired_batch_never_consumed_or_allocated(app, seed_hotels):
    hotel, _, _, _, booking_room, _ = seed_hotels
    with app.app_context():
        service = Service(hotel_id=hotel.id, name="Sữa hộp", price=15000)
        item = InventoryItem(hotel_id=hotel.id, code="MILK-LOT", name="Sữa", quantity=0, service=service)
        db.session.add_all([service, item])
        db.session.flush()
        expired = inventory_batch_service.create_receipt_batch(
            item=item, quantity=5, received_at=date(2026, 1, 1), expires_at=date(2026, 6, 1),
        )
        fresh = inventory_batch_service.create_receipt_batch(
            item=item, quantity=5, received_at=date(2026, 1, 1), expires_at=date(2026, 12, 1),
        )
        line = BookingService(
            hotel_id=hotel.id, booking_id=booking_room.booking_id,
            room_id=booking_room.room_id, service_id=service.id,
            quantity=2, price_at_booking=15000,
        )
        db.session.add(line)
        db.session.flush()

        # as_of 01-07: lô expired (hết hạn 01-06) tuyệt đối không được đụng
        inventory_service.deduct_inventory(
            hotel.id, service.id, 2, booking_service=line, as_of_date=date(2026, 7, 1),
        )
        db.session.flush()
        assert expired.quantity_available == 5
        assert fresh.quantity_available == 3
        assert not InventoryMovement.query.filter_by(
            batch_id=expired.id, movement_type="consumption"
        ).count()
        assert not BookingServiceBatchAllocation.query.filter_by(batch_id=expired.id).count()


def test_no_expiry_batch_consumed_after_dated_batches(app, seed_hotels):
    hotel, _, _, _, booking_room, _ = seed_hotels
    with app.app_context():
        service = Service(hotel_id=hotel.id, name="Bia lon", price=25000)
        item = InventoryItem(hotel_id=hotel.id, code="BEER-LOT", name="Bia", quantity=0, service=service)
        db.session.add_all([service, item])
        db.session.flush()
        no_expiry = inventory_batch_service.create_receipt_batch(
            item=item, quantity=5, received_at=date(2026, 1, 1),
        )
        dated = inventory_batch_service.create_receipt_batch(
            item=item, quantity=2, received_at=date(2026, 2, 1), expires_at=date(2026, 12, 1),
        )
        line = BookingService(
            hotel_id=hotel.id, booking_id=booking_room.booking_id,
            room_id=booking_room.room_id, service_id=service.id,
            quantity=3, price_at_booking=25000,
        )
        db.session.add(line)
        db.session.flush()

        inventory_service.deduct_inventory(
            hotel.id, service.id, 3, booking_service=line, as_of_date=date(2026, 7, 1),
        )
        db.session.flush()
        # Lô có hạn xuất trước (FEFO), lô không hạn chỉ bù phần thiếu
        assert dated.quantity_available == 0
        assert no_expiry.quantity_available == 4


def test_insufficient_stock_writes_no_partial_movement(app, seed_hotels):
    import pytest as _pytest

    hotel, _, _, _, booking_room, _ = seed_hotels
    with app.app_context():
        service = Service(hotel_id=hotel.id, name="Snack", price=20000)
        item = InventoryItem(hotel_id=hotel.id, code="SNACK-LOT", name="Snack", quantity=0, service=service)
        db.session.add_all([service, item])
        db.session.flush()
        batch = inventory_batch_service.create_receipt_batch(
            item=item, quantity=2, received_at=date(2026, 1, 1), expires_at=date(2026, 12, 1),
        )
        line = BookingService(
            hotel_id=hotel.id, booking_id=booking_room.booking_id,
            room_id=booking_room.room_id, service_id=service.id,
            quantity=5, price_at_booking=20000,
        )
        db.session.add(line)
        db.session.flush()
        movements_before = InventoryMovement.query.count()

        with _pytest.raises(inventory_service.InsufficientInventoryError):
            inventory_service.deduct_inventory(
                hotel.id, service.id, 5, booking_service=line, as_of_date=date(2026, 7, 1),
            )

        # Thiếu tồn: không được ghi partial — mọi con số giữ nguyên
        assert batch.quantity_available == 2
        assert item.quantity == 2
        assert InventoryMovement.query.count() == movements_before
        assert BookingServiceBatchAllocation.query.count() == 0
