from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app import create_app
from extensions import db
from models import (
    Booking,
    BookingRoom,
    BusinessOperation,
    Customer,
    Hotel,
    Payment,
    Room,
    User,
)


pytestmark = pytest.mark.mysql


def test_concurrent_checkout_mutates_once(mysql_database_url):
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": mysql_database_url,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "mysql-checkout-test-secret",
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_pre_ping": True},
        }
    )
    with app.app_context():
        db.create_all()
        hotel = Hotel(name="Checkout Hotel", slug="checkout-concurrency")
        db.session.add(hotel)
        db.session.flush()
        user = User(username="checkout_admin", role="admin", hotel_id=hotel.id)
        user.set_password("correct-password")
        customer = Customer(hotel_id=hotel.id, name="Concurrent Guest")
        room = Room(
            hotel_id=hotel.id,
            room_number="101",
            room_type="Standard",
            price_per_night=500000,
            price_initial_block=300000,
            initial_hours=2,
            status="occupied",
        )
        db.session.add_all([user, customer, room])
        db.session.flush()
        booking = Booking(
            hotel_id=hotel.id,
            code="CONCURRENT-CHECKOUT",
            customer_id=customer.id,
            status="checked_in",
        )
        db.session.add(booking)
        db.session.flush()
        now = datetime.now().replace(microsecond=0)
        booking_room = BookingRoom(
            hotel_id=hotel.id,
            booking_id=booking.id,
            room_id=room.id,
            status="checked_in",
            rental_type="daily",
            check_in_actual=now - timedelta(days=1),
            check_in_expected=now - timedelta(days=1),
            check_out_expected=now,
            price_breakdown_snapshot=[
                {
                    "business_date": (now - timedelta(days=1)).date().isoformat(),
                    "amount": 500000.0,
                }
            ],
        )
        db.session.add(booking_room)
        db.session.commit()
        hotel_slug = hotel.slug
        booking_id = booking.id
        booking_room_id = booking_room.id

    clients = [app.test_client(), app.test_client()]
    for client in clients:
        login = client.post(
            f"/{hotel_slug}/login",
            data={
                "username": "checkout_admin",
                "password": "correct-password",
            },
        )
        assert login.status_code == 302

    preview = clients[0].post(
        f"/{hotel_slug}/bookings/api/rooms/preview_checkout",
        json={"number": "101"},
    )
    quote = preview.json["quote"]
    payload = {
        "number": "101",
        "booking_id": booking_id,
        "booking_room_id": booking_room_id,
        "quote_fingerprint": quote["fingerprint"],
        "quote_checkout_at": quote["checkout_at"],
        "payment_method": "cash",
    }

    def confirm(client):
        response = client.post(
            f"/{hotel_slug}/bookings/api/rooms/checkout",
            json=payload,
        )
        return response.status_code, response.json

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(confirm, clients))

    assert [status for status, _body in outcomes] == [200, 200]
    assert outcomes[0][1] == outcomes[1][1]
    with app.app_context():
        assert BusinessOperation.query.count() == 1
        assert Payment.query.count() == 1
        assert Payment.query.one().amount == Decimal("500000.00")
        assert BookingRoom.query.one().status == "checked_out"
        db.engine.dispose()
