from datetime import datetime

from extensions import db
from models import PriceRule
from models.booking_room import BookingRoom
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


def test_timeline_booking_stores_nightly_price_snapshot(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.check_in_expected = datetime(2030, 1, 1, 14)
    booking_room.check_out_expected = datetime(2030, 1, 2, 12)
    db.session.commit(); login_as(client, user)
    response = client.post(f'/{hotel.slug}/timeline/api/bookings/create', json={
        'room_number': booking_room.room.room_number, 'check_in': '2030-01-02T12:00',
        'check_out': '2030-01-03T12:00', 'rental_type': 'daily', 'deposit': 250000, 'name': 'Snapshot',
    })
    assert response.status_code == 200
    assert response.json['success'] is True
    created = BookingRoom.query.order_by(BookingRoom.id.desc()).first()
    assert created.price_breakdown_snapshot == [{'business_date': '2030-01-02', 'amount': 500000.0}]


def test_daily_bill_uses_existing_snapshot_over_current_rules(app, seed_hotels):
    _, _, _, _, booking_room, _ = seed_hotels
    with app.app_context():
        total, _ = calculate_complex_hotel_bill(datetime(2030, 1, 1, 14), datetime(2030, 1, 2, 12), booking_room.room, rental_type='daily', price_breakdown_snapshot=[{'business_date': '2030-01-01', 'amount': 420000.0}])
    assert total == 420000.0


def test_group_booking_stores_nightly_price_snapshot(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    login_as(client, user)
    response = client.post(f'/{hotel.slug}/bookings/api/bookings/group_create', json={
        'room_ids': [booking_room.room_id], 'check_in': '2031-01-02', 'check_out': '2031-01-03', 'deposit': 250000,
        'customer': {'name': 'Đoàn', 'phone': '0901234567'},
    })
    assert response.status_code == 200
    created = BookingRoom.query.order_by(BookingRoom.id.desc()).first()
    assert created.price_breakdown_snapshot == [{'business_date': '2031-01-02', 'amount': 500000.0}]


def test_hourly_booking_stores_hourly_price_snapshot(client, seed_hotels, login_as):
    hotel, _, user, _, booking_room, _ = seed_hotels
    booking_room.check_in_expected = datetime(2030, 1, 1, 14); booking_room.check_out_expected = datetime(2030, 1, 2, 12)
    db.session.commit(); login_as(client, user)
    response = client.post(f'/{hotel.slug}/timeline/api/bookings/create', json={
        'room_number': booking_room.room.room_number, 'check_in': '2030-01-02T12:00', 'check_out': '2030-01-02T15:00',
        'rental_type': 'hourly', 'deposit': 175000, 'name': 'Giờ',
    })
    assert response.status_code == 200
    assert response.json['success'] is True
    created = BookingRoom.query.order_by(BookingRoom.id.desc()).first()
    assert created.hourly_price_snapshot == {'initial_hours': 2, 'price_initial': 300000.0, 'price_next': 50000.0, 'price_night': 500000.0}


def test_hourly_bill_uses_the_stored_hourly_price_snapshot(app, seed_hotels):
    _, _, _, _, booking_room, _ = seed_hotels
    booking_room.room.price_initial_block = 700000
    booking_room.room.price_next_hour = 150000
    booking_room.room.price_per_night = 1200000
    with app.app_context():
        total, _ = calculate_complex_hotel_bill(
            datetime(2030, 1, 1, 14), datetime(2030, 1, 1, 17), booking_room.room,
            rental_type='hourly',
            hourly_price_snapshot={'initial_hours': 2, 'price_initial': 300000.0, 'price_next': 50000.0, 'price_night': 500000.0},
        )
    assert total == 350000.0


def test_hourly_snapshot_controls_the_overnight_fallback(app, seed_hotels):
    _, _, _, _, booking_room, _ = seed_hotels
    booking_room.room.price_initial_block = 700000
    booking_room.room.price_next_hour = 150000
    booking_room.room.price_per_night = 1200000
    with app.app_context():
        total, _ = calculate_complex_hotel_bill(
            datetime(2030, 1, 1, 14), datetime(2030, 1, 1, 22), booking_room.room,
            rental_type='hourly',
            hourly_price_snapshot={'initial_hours': 2, 'price_initial': 300000.0, 'price_next': 50000.0, 'price_night': 500000.0},
        )
    assert total == 500000.0
