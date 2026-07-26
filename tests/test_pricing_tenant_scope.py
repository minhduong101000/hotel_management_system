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
