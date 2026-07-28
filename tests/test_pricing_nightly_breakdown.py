from datetime import datetime

from extensions import db
from models import PriceRule
from services.pricing_service import calculate_complex_hotel_bill, get_billable_night_dates, get_nightly_price_breakdown


def test_billable_nights_use_the_start_date_of_each_night():
    nights = get_billable_night_dates(
        datetime(2026, 9, 2, 14, 0),
        datetime(2026, 9, 3, 12, 0),
    )

    assert nights == [datetime(2026, 9, 2).date()]


def test_billable_nights_span_each_business_date():
    nights = get_billable_night_dates(
        datetime(2026, 4, 30, 14, 0),
        datetime(2026, 5, 2, 12, 0),
    )

    assert nights == [datetime(2026, 4, 30).date(), datetime(2026, 5, 1).date()]


def test_nightly_breakdown_uses_each_nights_effective_price(app, seed_hotels):
    hotel, _, _, _, booking_room, _ = seed_hotels
    db.session.add(PriceRule(hotel_id=hotel.id, name='Lễ', room_type=booking_room.room.room_type,
        start_date=datetime(2026, 4, 30).date(), end_date=datetime(2026, 4, 30).date(), price_daily=1000000, priority=10, is_active=True))
    db.session.commit()
    with app.app_context():
        breakdown = get_nightly_price_breakdown(booking_room.room, datetime(2026, 4, 30, 14), datetime(2026, 5, 2, 12))
    assert [line['amount'] for line in breakdown] == [1000000.0, 500000.0]


def test_daily_bill_sums_each_nights_price_rule(app, seed_hotels):
    hotel, _, _, _, booking_room, _ = seed_hotels
    db.session.add(PriceRule(hotel_id=hotel.id, name='Lễ', room_type=booking_room.room.room_type,
        start_date=datetime(2026, 4, 30).date(), end_date=datetime(2026, 4, 30).date(), price_daily=1000000, priority=10, is_active=True))
    db.session.commit()
    with app.app_context():
        total, _ = calculate_complex_hotel_bill(datetime(2026, 4, 30, 14), datetime(2026, 5, 2, 12), booking_room.room, rental_type='daily')
    assert total == 1500000.0
