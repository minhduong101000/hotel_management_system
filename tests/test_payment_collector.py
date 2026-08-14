from datetime import datetime, timedelta
from decimal import Decimal

from extensions import db
from models import Payment
from services import payment_service, refund_service


def test_refund_records_collector(app, seed_hotels):
    _, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        booking_room.status = "checked_out"
        booking_room.final_amount = Decimal("400000")
        db.session.flush()
        payment_service.record_deposit(
            booking_id=booking_room.booking_id, amount=500_000, note="Cọc", flush=True
        )
        payment = refund_service.create_refund(
            booking=booking_room.booking, base="total", amount=100_000,
            payment_method="cash", reason="Test truy vết",
            actor_user_id=user.id, client_key="collector-1",
        )
        assert payment.created_by == user.id


def test_create_booking_deposit_records_logged_in_collector(
    app, seed_hotels, client, login_as
):
    hotel, _, user, _, _, _ = seed_hotels
    with app.app_context():
        login_as(client, user)
        check_in = datetime(2026, 10, 1, 14, 0)
        response = client.post(
            f"/{hotel.slug}/timeline/api/bookings/create",
            json={
                "room_number": "101",
                "name": "Khách Cọc",
                "phone": "0905550001",
                "check_in": check_in.strftime("%Y-%m-%dT%H:%M"),
                "check_out": (check_in + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
                "status": "booked",
                "rental_type": "daily",
                "deposit": 250000,  # 50% cua 500k/dem
            },
        )
        assert response.status_code == 200, response.json
        deposit = Payment.query.filter_by(payment_type="deposit").one()
        assert deposit.created_by == user.id


def test_cashier_shows_collector_username(app, seed_hotels, client, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        payment_service.record_deposit(
            booking_id=booking_room.booking_id, amount=300_000,
            note="Cọc có người thu", created_by=user.id, flush=True,
        )
        db.session.commit()
        login_as(client, user)
        response = client.get(f"/{hotel.slug}/cashier/api/reports/cashier?period=today")
        assert response.status_code == 200
        record = response.json["data"]["records"][0]
        assert record["collected_by"] == user.username
