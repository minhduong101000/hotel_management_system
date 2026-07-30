from datetime import datetime

from extensions import db
from models import PriceRule


def test_calculate_price_returns_server_quote_and_hourly_deposit_options(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/rooms/api/bookings/calculate-price",
        json={
            "room_id": booking_room.room_id,
            "check_in": "2030-01-01T14:00",
            "check_out": "2030-01-01T17:00",
            "rental_type": "hourly",
        },
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    assert response.json["total_amount"] == 350000
    assert response.json["quote"]["total"] == "350000.00"
    assert response.json["quote"]["deposit_options"] == {
        "suggested_50": "175000.00",
        "maximum_100": "350000.00",
    }


def test_group_booking_deposit_uses_each_nights_server_price(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    db.session.add(
        PriceRule(
            hotel_id=hotel.id,
            name="Đêm đầu cao điểm",
            room_type=booking_room.room.room_type,
            start_date=datetime(2032, 4, 30).date(),
            end_date=datetime(2032, 4, 30).date(),
            price_daily=1_000_000,
            priority=10,
            is_active=True,
        )
    )
    db.session.commit()
    login_as(client, user)

    response = client.post(
        f"/{hotel.slug}/bookings/api/bookings/group_create",
        json={
            "room_ids": [booking_room.room_id],
            "check_in": "2032-04-30",
            "check_out": "2032-05-02",
            "deposit": 750000,
            "customer": {
                "name": "Đoàn theo quote",
                "phone": "0901234568",
            },
        },
    )

    assert response.status_code == 200
    assert response.json["success"] is True


def test_group_booking_frontend_uses_server_quote_for_deposit():
    source = open("static/js/group_booking.js", encoding="utf-8").read()

    assert "room_ids" in source
    assert "/api/bookings/calculate-price" in source
    assert "deposit_options" in source
    assert "totalSelectedPricePerNight" not in source
