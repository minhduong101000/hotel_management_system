from datetime import datetime, timedelta
from decimal import Decimal

from extensions import db


def test_billing_list_uses_business_day_window(app, seed_hotels, client, login_as):
    """Checkout 00:30 giờ VN ngày 14-08 (17:30 UTC 13-08) phải hiện khi lọc ngày 14-08."""
    hotel, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        booking_room.status = "checked_out"
        booking_room.check_in_actual = datetime(2026, 8, 13, 10, 0)
        booking_room.check_out_actual = datetime(2026, 8, 13, 17, 30)  # UTC-naive
        booking_room.final_amount = Decimal("400000")
        db.session.commit()
        login_as(client, user)

        inside = client.get(
            f"/{hotel.slug}/billing/api/billing/list?start=2026-08-14&end=2026-08-14"
        )
        outside = client.get(
            f"/{hotel.slug}/billing/api/billing/list?start=2026-08-13&end=2026-08-13"
        )
        assert inside.status_code == 200
        assert len(inside.json["data"]) == 1, "00:30 VN 14-08 phải thuộc ngày 14-08"
        assert len(outside.json["data"]) == 0, "không được lẫn về ngày 13-08"


def test_create_booking_accepts_source(app, seed_hotels, client, login_as):
    from models import Booking, Room

    hotel, _, user, _, _, _ = seed_hotels
    with app.app_context():
        login_as(client, user)
        check_in = datetime(2026, 10, 5, 14, 0)
        response = client.post(
            f"/{hotel.slug}/timeline/api/bookings/create",
            json={
                "room_number": "101",
                "name": "Khách OTA",
                "phone": "0905550002",
                "check_in": check_in.strftime("%Y-%m-%dT%H:%M"),
                "check_out": (check_in + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
                "status": "booked",
                "rental_type": "daily",
                "deposit": 250000,
                "source": "ota",
            },
        )
        assert response.status_code == 200, response.json
        booking = Booking.query.filter_by(code=response.json["code"]).one()
        assert booking.source == "ota"

        # Nguồn lạ rơi về walk_in, không lỗi
        response2 = client.post(
            f"/{hotel.slug}/timeline/api/bookings/create",
            json={
                "room_number": "101",
                "name": "Khách Lạ",
                "phone": "0905550003",
                "check_in": (check_in + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M"),
                "check_out": (check_in + timedelta(days=4)).strftime("%Y-%m-%dT%H:%M"),
                "status": "booked",
                "rental_type": "daily",
                "deposit": 250000,
                "source": "tiktok??",
            },
        )
        assert response2.status_code == 200, response2.json
        booking2 = Booking.query.filter_by(code=response2.json["code"]).one()
        assert booking2.source == "walk_in"
