from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from flask_migrate import upgrade
from sqlalchemy import inspect

from app import create_app
from extensions import db
from models import (
    Booking,
    BookingRoom,
    BookingService,
    BookingServiceBatchAllocation,
    Customer,
    Hotel,
    InventoryBatch,
    InventoryMovement,
    Room,
    Service,
    User,
)
from models.inventory_item import InventoryItem
from services import inventory_batch_service


pytestmark = pytest.mark.mysql
MIGRATIONS_DIRECTORY = str(
    Path(__file__).resolve().parents[2] / "migrations"
)


def test_allocation_migration_merges_duplicates_before_unique_constraint(
    mysql_database_url,
):
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": mysql_database_url,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "mysql-inventory-migration-secret",
        }
    )
    with app.app_context():
        upgrade(revision="f1a2b3c4d5e6", directory=MIGRATIONS_DIRECTORY)
        hotel = Hotel(name="Migration Hotel", slug="inventory-migration")
        db.session.add(hotel)
        db.session.flush()
        customer = Customer(hotel_id=hotel.id, name="Migration Guest")
        service = Service(hotel_id=hotel.id, name="Migration service", price=1)
        room = Room(
            hotel_id=hotel.id,
            room_number="101",
            room_type="Standard",
            price_per_night=1,
            price_initial_block=1,
            initial_hours=1,
        )
        item = InventoryItem(
            hotel_id=hotel.id,
            code="MIGRATE",
            name="Migration item",
            quantity=5,
            service=service,
        )
        db.session.add_all([customer, service, room, item])
        db.session.flush()
        booking = Booking(
            hotel_id=hotel.id,
            code="MIGRATION",
            customer_id=customer.id,
        )
        db.session.add(booking)
        db.session.flush()
        line = BookingService(
            hotel_id=hotel.id,
            booking_id=booking.id,
            room_id=room.id,
            service_id=service.id,
            quantity=3,
            price_at_booking=1,
        )
        batch = InventoryBatch(
            hotel_id=hotel.id,
            inventory_item_id=item.id,
            batch_code="MIGRATE-01",
            received_at=date.today(),
            quantity_received=5,
            quantity_available=2,
            unit_cost=1,
        )
        db.session.add_all([line, batch])
        db.session.flush()
        db.session.add_all([
            BookingServiceBatchAllocation(
                hotel_id=hotel.id,
                booking_service_id=line.id,
                batch_id=batch.id,
                quantity=1,
            ),
            BookingServiceBatchAllocation(
                hotel_id=hotel.id,
                booking_service_id=line.id,
                batch_id=batch.id,
                quantity=2,
            ),
        ])
        db.session.commit()

        upgrade(directory=MIGRATIONS_DIRECTORY)

        allocation = BookingServiceBatchAllocation.query.one()
        assert allocation.quantity == 3
        constraints = {
            constraint["name"]: tuple(constraint["column_names"])
            for constraint in inspect(db.engine).get_unique_constraints(
                "booking_service_batch_allocations"
            )
        }
        assert constraints["uq_booking_service_batch_allocation"] == (
            "hotel_id",
            "booking_service_id",
            "batch_id",
        )
        db.engine.dispose()


def test_concurrent_orders_cannot_consume_the_same_last_unit(
    mysql_database_url,
):
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": mysql_database_url,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "mysql-inventory-concurrency-secret",
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_pre_ping": True},
        }
    )
    with app.app_context():
        db.create_all()
        hotel = Hotel(name="Inventory Hotel", slug="inventory-concurrency")
        db.session.add(hotel)
        db.session.flush()
        user = User(username="inventory_admin", role="admin", hotel_id=hotel.id)
        user.set_password("correct-password")
        customer = Customer(hotel_id=hotel.id, name="Inventory Guest")
        service = Service(hotel_id=hotel.id, name="Last unit", price=10000)
        room = Room(
            hotel_id=hotel.id,
            room_number="101",
            room_type="Standard",
            price_per_night=500000,
            price_initial_block=300000,
            initial_hours=2,
            status="occupied",
        )
        db.session.add_all([user, customer, service, room])
        db.session.flush()
        booking = Booking(
            hotel_id=hotel.id,
            code="INVENTORY-CONCURRENT",
            customer_id=customer.id,
            status="checked_in",
        )
        item = InventoryItem(
            hotel_id=hotel.id,
            code="LAST",
            name="Last unit",
            quantity=0,
            service_id=service.id,
        )
        db.session.add_all([booking, item])
        db.session.flush()
        now = datetime.now()
        booking_room = BookingRoom(
            hotel_id=hotel.id,
            booking_id=booking.id,
            room_id=room.id,
            status="checked_in",
            check_in_actual=now,
            check_in_expected=now,
            check_out_expected=now + timedelta(days=1),
        )
        db.session.add(booking_room)
        db.session.flush()
        inventory_batch_service.create_receipt_batch(
            item=item,
            quantity=1,
            received_at=date.today(),
            expires_at=date.today() + timedelta(days=30),
        )
        db.session.commit()
        hotel_slug = hotel.slug
        booking_room_id = booking_room.id
        service_id = service.id

    clients = [app.test_client(), app.test_client()]
    for client in clients:
        login = client.post(
            f"/{hotel_slug}/login",
            data={
                "username": "inventory_admin",
                "password": "correct-password",
            },
        )
        assert login.status_code == 302

    payload = {
        "room_number": "101",
        "booking_room_id": booking_room_id,
        "items": [{"id": service_id, "qty": 1}],
    }

    def order(client):
        response = client.post(
            f"/{hotel_slug}/bookings/api/orders/add",
            json=payload,
        )
        return response.status_code, response.json

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(order, clients))

    assert sorted(status for status, _body in outcomes) == [200, 409]
    with app.app_context():
        item = InventoryItem.query.one()
        batch = InventoryBatch.query.one()
        assert item.quantity == 0
        assert batch.quantity_available == 0
        assert BookingService.query.one().quantity == 1
        assert BookingServiceBatchAllocation.query.one().quantity == 1
        assert InventoryMovement.query.filter_by(
            movement_type="consumption"
        ).count() == 1
        db.engine.dispose()
