from datetime import datetime, timedelta
from decimal import Decimal

from extensions import db
from models import Payment, User
from services import payment_service


START = datetime(2026, 8, 10, 14, 0)


def _prep_booking(booking_room, funded=500_000):
    booking_room.rental_type = "daily"
    booking_room.status = "checked_out"
    booking_room.check_in_actual = START
    booking_room.check_out_actual = START + timedelta(days=1)
    booking_room.price_snapshot = Decimal("400000")
    booking_room.price_breakdown_snapshot = [
        {"business_date": "2026-08-10", "amount": 400000.0},
    ]
    db.session.flush()
    payment_service.record_deposit(
        booking_id=booking_room.booking_id, amount=funded, note="Cọc", flush=True
    )
    db.session.commit()
    return booking_room.booking


def test_preview_returns_server_numbers(app, seed_hotels, client, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        booking = _prep_booking(booking_room)
        login_as(client, user)

        response = client.post(
            f"/{hotel.slug}/api/refunds/preview",
            json={"booking_id": booking.id, "base": "total", "percent": 50},
        )
        assert response.status_code == 200
        data = response.json["data"]
        assert data["base_value"] == 400000.0
        assert data["refund_amount"] == 200000.0
        assert data["cap"] == 500000.0
        assert data["already_refunded"] == 0.0


def test_create_refund_over_cap_returns_error_code(app, seed_hotels, client, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        booking = _prep_booking(booking_room, funded=100_000)
        login_as(client, user)

        response = client.post(
            f"/{hotel.slug}/api/refunds",
            json={
                "booking_id": booking.id,
                "base": "total",
                "amount": 999_999,
                "payment_method": "cash",
                "reason": "Thử vượt trần qua API",
                "client_key": "over-cap",
            },
        )
        assert response.status_code == 400
        assert response.json["error_code"] == "refund_exceeds_cap"
        assert Payment.query.filter_by(payment_type="refund").count() == 0


def test_staff_can_create_and_reverse_refund(app, seed_hotels, client, login_as):
    hotel, _, _, _, booking_room, _ = seed_hotels
    with app.app_context():
        booking = _prep_booking(booking_room)
        staff = User(username="staff_refund", role="staff", hotel_id=hotel.id)
        staff.set_password("correct-password")
        db.session.add(staff)
        db.session.commit()
        login_as(client, staff)

        created = client.post(
            f"/{hotel.slug}/api/refunds",
            json={
                "booking_id": booking.id,
                "base": "total",
                "amount": 150_000,
                "payment_method": "cash",
                "reason": "Khách yêu cầu, staff xử lý",
                "client_key": "staff-1",
            },
        )
        assert created.status_code == 200, created.json
        payment_id = created.json["data"]["payment_id"]
        assert Payment.query.get(payment_id).amount == Decimal("-150000.00")

        reversed_resp = client.post(
            f"/{hotel.slug}/api/refunds/{payment_id}/reverse",
            json={"reason": "Nhập nhầm", "client_key": "staff-1-fix"},
        )
        assert reversed_resp.status_code == 200, reversed_resp.json
        again = client.post(
            f"/{hotel.slug}/api/refunds/{payment_id}/reverse",
            json={"reason": "Đảo lần nữa", "client_key": "staff-1-fix2"},
        )
        assert again.status_code == 400


def test_refund_api_tenant_isolation(app, seed_hotels, client, login_as):
    hotel_a, _, user_a, _, _, booking_room_b = seed_hotels
    with app.app_context():
        booking_b = _prep_booking(booking_room_b)
        login_as(client, user_a)

        preview = client.post(
            f"/{hotel_a.slug}/api/refunds/preview",
            json={"booking_id": booking_b.id, "base": "total", "percent": 10},
        )
        create = client.post(
            f"/{hotel_a.slug}/api/refunds",
            json={
                "booking_id": booking_b.id,
                "base": "total",
                "amount": 10_000,
                "payment_method": "cash",
                "reason": "Sai tenant",
                "client_key": "cross",
            },
        )
        assert preview.status_code == 404
        assert create.status_code == 404
        assert Payment.query.filter_by(payment_type="refund").count() == 0


def test_refund_requires_login_as_json(app, seed_hotels, client):
    hotel, _, _, _, booking_room, _ = seed_hotels
    with app.app_context():
        booking = _prep_booking(booking_room)
        response = client.post(
            f"/{hotel.slug}/api/refunds",
            json={"booking_id": booking.id},
        )
        # API chưa đăng nhập: chấp nhận redirect login hiện hành (302) — sẽ
        # chuẩn hóa 401 JSON toàn cục ở đợt riêng; không được là 200/500.
        assert response.status_code in (302, 401, 403)
        assert Payment.query.filter_by(payment_type="refund").count() == 0
