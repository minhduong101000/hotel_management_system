import json
from pathlib import Path

import pytest
from flask_migrate import upgrade

from app import create_app
from extensions import db
from models import Booking, BookingRoom, Customer, Hotel, Room


pytestmark = pytest.mark.mysql
MIGRATIONS_DIRECTORY = str(
    Path(__file__).resolve().parents[2] / "migrations"
)


def test_reconciliation_apply_commits_atomically_on_migrated_mysql(
    mysql_database_url,
):
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": mysql_database_url,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "mysql-reconciliation-test-secret",
        }
    )
    with app.app_context():
        upgrade(directory=MIGRATIONS_DIRECTORY)
        hotel = Hotel(name="Reconciliation Hotel", slug="reconciliation")
        db.session.add(hotel)
        db.session.flush()
        customer = Customer(hotel_id=hotel.id, name="Reconciliation Guest")
        room = Room(
            hotel_id=hotel.id,
            room_number="101",
            room_type="Standard",
            price_per_night=500000,
            price_initial_block=300000,
            initial_hours=2,
            status="occupied",
        )
        db.session.add_all([customer, room])
        db.session.flush()
        booking = Booking(
            hotel_id=hotel.id,
            code="RECONCILE-001",
            customer_id=customer.id,
            status="cancelled",
            total_amount=123456,
        )
        db.session.add(booking)
        db.session.flush()
        booking_room = BookingRoom(
            hotel_id=hotel.id,
            booking_id=booking.id,
            room_id=room.id,
            status="booked",
            rental_type="daily",
            price_breakdown_snapshot=[
                {"business_date": "2026-07-30", "amount": 500000}
            ],
        )
        db.session.add(booking_room)
        db.session.commit()
        booking_id = booking.id
        room_id = room.id

    result = app.test_cli_runner().invoke(
        args=[
            "reconcile-business-data",
            "--hotel-slug",
            "reconciliation",
            "--apply",
            "--confirm-apply",
            "--backup-acknowledged",
        ]
    )

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["summary"]["applied_count"] == 2
    with app.app_context():
        assert db.session.get(Booking, booking_id).status == "confirmed"
        assert db.session.get(Booking, booking_id).total_amount == 123456
        assert db.session.get(Room, room_id).status == "available"
