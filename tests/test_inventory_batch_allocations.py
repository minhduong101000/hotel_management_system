from datetime import date

from extensions import db
from models.booking_service import BookingService
from models.booking_service_batch_allocation import BookingServiceBatchAllocation
from models.inventory_item import InventoryItem
from models.service import Service
from services import inventory_batch_service, inventory_service


def test_consumption_and_restore_use_the_same_batches(app, seed_hotels):
    hotel, _, _, _, booking_room, _ = seed_hotels
    with app.app_context():
        service = Service(hotel_id=hotel.id, name='Nước đóng chai', price=10000)
        item = InventoryItem(hotel_id=hotel.id, code='WATER-LOT', name='Nước', quantity=0, service=service)
        db.session.add_all([service, item])
        db.session.flush()
        early = inventory_batch_service.create_receipt_batch(item=item, quantity=2, received_at=date(2026, 1, 1), expires_at=date(2026, 8, 1))
        later = inventory_batch_service.create_receipt_batch(item=item, quantity=3, received_at=date(2026, 1, 1), expires_at=date(2026, 9, 1))
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
