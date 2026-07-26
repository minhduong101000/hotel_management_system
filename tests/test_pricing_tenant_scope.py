from datetime import datetime

from extensions import db
from models import PriceRule
from services.pricing_service import get_effective_room_prices


def test_special_price_rule_cannot_cross_hotel_boundary(app, seed_hotels):
    hotel_a, hotel_b, _, _, booking_room_a, _ = seed_hotels
    check_date = datetime(2026, 7, 26, 14, 0)
    rule_b = PriceRule(
        hotel_id=hotel_b.id,
        name="Giá khách sạn B",
        room_type=booking_room_a.room.room_type,
        start_date=check_date.date(),
        end_date=check_date.date(),
        price_daily=990000,
        priority=10,
        is_active=True,
    )
    db.session.add(rule_b)
    db.session.commit()

    with app.app_context():
        prices = get_effective_room_prices(booking_room_a.room, check_date)

    assert prices["p_night"] == 500000
    assert prices["is_special"] is False


def test_special_price_rule_applies_only_to_its_hotel_and_keeps_hourly_price(app, seed_hotels):
    hotel_a, _, _, _, booking_room_a, _ = seed_hotels
    check_date = datetime(2026, 7, 26, 14, 0)
    rule_a = PriceRule(
        hotel_id=hotel_a.id,
        name="Cuối tuần A",
        room_type=booking_room_a.room.room_type,
        start_date=check_date.date(),
        end_date=check_date.date(),
        price_daily=750000,
        priority=10,
        is_active=True,
    )
    db.session.add(rule_a)
    db.session.commit()

    with app.app_context():
        prices = get_effective_room_prices(booking_room_a.room, check_date)

    assert prices["p_night"] == 750000
    assert prices["p_initial"] == 300000
    assert prices["rule_name"] == "Cuối tuần A"


def test_open_ended_price_rule_applies_without_dates(app, seed_hotels):
    hotel, _, _, _, booking_room, _ = seed_hotels
    rule = PriceRule(
        hotel_id=hotel.id,
        name="Giá quanh năm",
        room_type=booking_room.room.room_type,
        start_date=None,
        end_date=None,
        price_daily=680000,
        priority=10,
        is_active=True,
    )
    db.session.add(rule)
    db.session.commit()

    with app.app_context():
        prices = get_effective_room_prices(booking_room.room, datetime(2026, 12, 31, 14, 0))

    assert prices["p_night"] == 680000
    assert prices["rule_name"] == "Giá quanh năm"


def test_price_rule_rejects_invalid_date_range(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    login_as(client, user)

    response = client.post(f'/{hotel.slug}/prices/api/prices/save-rule', json={
        'name': 'Sai ngày', 'room_type': booking_room.room.room_type, 'priority': 1,
        'start_date': '2026-09-03', 'end_date': '2026-09-02', 'price_daily': 500000,
    })

    assert response.json['success'] is False
