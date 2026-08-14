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
        # Ngày tương đối để test không tự đỏ khi lịch vượt qua một mốc hardcode:
        # lô "early" hết hạn trước lô "later", cả hai còn hạn tại thời điểm chạy.
        received = date.today() - timedelta(days=30)
        early = inventory_batch_service.create_receipt_batch(item=item, quantity=2, received_at=received, expires_at=date.today() + timedelta(days=30))
        later = inventory_batch_service.create_receipt_batch(item=item, quantity=3, received_at=received, expires_at=date.today() + timedelta(days=60))
        line = BookingService(hotel_id=hotel.id, booking_id=booking_room.booking_id, room_id=booking_room.room_id, service_id=service.id, quantity=3, price_at_booking=10000)
        db.session.add(line)
        db.session.flush()

        inventory_service.deduct_inventory(hotel.id, service.id, 3, booking_service=line)
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
            received_at=date.today() - timedelta(days=30),
            expires_at=date.today() + timedelta(days=120),
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
            hotel.id,
            service.id,
            1,
            booking_service=line,
        )
        inventory_service.deduct_inventory(
            hotel.id,
            service.id,
            1,
            booking_service=line,
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
