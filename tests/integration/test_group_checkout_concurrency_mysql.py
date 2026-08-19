from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

import pytest

from app import create_app
from extensions import db
from models import (
    AuditEvent,
    Booking,
    BookingRoom,
    BusinessOperation,
    Customer,
    Hotel,
    Payment,
    Room,
    User,
)
from services import time_service


pytestmark = pytest.mark.mysql


def test_concurrent_group_checkout_mutates_once(mysql_database_url):
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": mysql_database_url,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "mysql-group-checkout-test-secret",
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_pre_ping": True},
        }
    )
    with app.app_context():
        db.create_all()
        hotel = Hotel(name="Group Checkout Hotel", slug="group-concurrency")
        db.session.add(hotel)
        db.session.flush()
        user = User(username="group_admin", role="admin", hotel_id=hotel.id)
        user.set_password("correct-password")
        customer = Customer(hotel_id=hotel.id, name="Concurrent Group")
        db.session.add_all([user, customer])
        db.session.flush()
        booking = Booking(
            hotel_id=hotel.id,
            code="GROUP-CONCURRENT",
            customer_id=customer.id,
            status="checked_in",
            prepaid_amount=100000,
        )
        db.session.add(booking)
        db.session.flush()
        # check_in_expected/check_out_expected và business_date của snapshot
        # là giờ nghiệp vụ; check_in_actual là timestamp hệ thống (UTC-naive).
        # Một biến now() duy nhất cho cả hai từng lệch nhau đúng offset múi
        # giờ dưới TZ=UTC, làm phụ thu/thiếu một đêm trong tổng group checkout.
        business_now = time_service.business_now_naive().replace(microsecond=0)
        actual_now = time_service.utc_now_naive().replace(microsecond=0)
        for index, price in enumerate((500000, 600000), start=1):
            room = Room(
                hotel_id=hotel.id,
                room_number=str(100 + index),
                room_type="Standard",
                price_per_night=price,
                price_initial_block=price,
                initial_hours=2,
                status="occupied",
            )
            db.session.add(room)
            db.session.flush()
            db.session.add(
                BookingRoom(
                    hotel_id=hotel.id,
                    booking_id=booking.id,
                    room_id=room.id,
                    status="checked_in",
                    rental_type="daily",
                    check_in_actual=actual_now - timedelta(days=1),
                    check_in_expected=business_now - timedelta(days=1),
                    check_out_expected=business_now,
                    price_breakdown_snapshot=[
                        {
                            "business_date": (
                                business_now - timedelta(days=1)
                            ).date().isoformat(),
                            "amount": float(price),
                        }
                    ],
                )
            )
        db.session.commit()
        hotel_slug = hotel.slug
        booking_id = booking.id

    clients = [app.test_client(), app.test_client()]
    for client in clients:
        login = client.post(
            f"/{hotel_slug}/login",
            data={"username": "group_admin", "password": "correct-password"},
        )
        assert login.status_code == 302

    preview = clients[0].get(
        f"/{hotel_slug}/bookings/api/bookings/{booking_id}/group_billing"
    )
    quote = preview.json["data"]["quote"]
    payload = {
        "include_tax": False,
        "payment_method": "cash",
        "quote_fingerprint": quote["fingerprint"],
        "quote_checkout_at": quote["checkout_at"],
    }

    def confirm(client):
        response = client.post(
            f"/{hotel_slug}/bookings/api/bookings/{booking_id}/group_checkout",
            json=payload,
        )
        return response.status_code, response.json

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(confirm, clients))

    assert [status for status, _body in outcomes] == [200, 200]
    assert outcomes[0][1] == outcomes[1][1]
    with app.app_context():
        assert BusinessOperation.query.count() == 1
        assert sum(
            (payment.amount for payment in Payment.query.all()),
            Decimal("0"),
        ) == Decimal("1000000.00")
        assert BookingRoom.query.filter_by(status="checked_out").count() == 2
        assert Booking.query.one().total_amount == Decimal("1100000.00")
        assert AuditEvent.query.filter_by(action="group_checkout").count() == 1
        db.engine.dispose()
