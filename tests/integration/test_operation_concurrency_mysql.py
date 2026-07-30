from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
import time

import pytest
from flask_migrate import upgrade
from sqlalchemy import inspect

from app import create_app
from extensions import db
from models import Booking, BusinessOperation, Customer, Hotel, Payment
from services import business_operation_service, payment_service


pytestmark = pytest.mark.mysql
MIGRATIONS_DIRECTORY = str(
    Path(__file__).resolve().parents[2] / "migrations"
)


def _mysql_app(database_url):
    return create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": database_url,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "mysql-operation-test-secret",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "pool_pre_ping": True,
                "pool_recycle": 60,
            },
        }
    )


def test_operation_payment_migration_matches_metadata(mysql_database_url):
    app = _mysql_app(mysql_database_url)
    with app.app_context():
        upgrade(directory=MIGRATIONS_DIRECTORY)
        operation_columns = {
            column["name"]
            for column in inspect(db.engine).get_columns("business_operations")
        }
        payment_columns = {
            column["name"]
            for column in inspect(db.engine).get_columns("payments")
        }
        payment_constraints = {
            constraint["name"]: tuple(constraint["column_names"])
            for constraint in inspect(db.engine).get_unique_constraints("payments")
        }
        payment_indexes = {
            index["name"]: tuple(index["column_names"])
            for index in inspect(db.engine).get_indexes("payments")
        }

        assert {"request_fingerprint", "result_snapshot"} <= operation_columns
        assert {"business_operation_id", "component_key"} <= payment_columns
        assert payment_constraints["uq_payments_operation_component"] == (
            "hotel_id",
            "business_operation_id",
            "component_key",
        )
        assert payment_indexes["ix_payments_hotel_booking"] == (
            "hotel_id",
            "booking_id",
        )
        db.engine.dispose()


def test_same_operation_key_concurrently_creates_one_operation_and_payment(
    mysql_database_url,
):
    app = _mysql_app(mysql_database_url)
    with app.app_context():
        db.create_all()
        hotel = Hotel(name="Concurrency Hotel", slug="concurrency")
        db.session.add(hotel)
        db.session.flush()
        customer = Customer(hotel_id=hotel.id, name="Concurrent Guest")
        db.session.add(customer)
        db.session.flush()
        booking = Booking(
            hotel_id=hotel.id,
            code="CONCURRENT-BOOKING",
            customer_id=customer.id,
        )
        db.session.add(booking)
        db.session.commit()
        hotel_id = hotel.id
        booking_id = booking.id

    def execute_once():
        with app.app_context():
            def handler(operation):
                payment_service.record_room_payment(
                    booking_id=booking_id,
                    amount=Decimal("100000.00"),
                    note="Concurrent payment",
                    business_operation=operation,
                    component_key="settlement",
                )
                time.sleep(0.15)
                return {"success": True, "amount": "100000.00"}

            result = business_operation_service.execute_operation(
                hotel_id=hotel_id,
                operation_key="checkout:concurrent",
                action="checkout",
                entity_type="booking",
                entity_id=booking_id,
                request_payload={"amount": "100000.00"},
                handler=handler,
            )
            db.session.remove()
            return result

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _index: execute_once(), range(2)))

    with app.app_context():
        assert [replayed for _result, replayed in outcomes].count(False) == 1
        assert [replayed for _result, replayed in outcomes].count(True) == 1
        assert outcomes[0][0] == outcomes[1][0]
        assert BusinessOperation.query.count() == 1
        assert Payment.query.count() == 1
        db.engine.dispose()
