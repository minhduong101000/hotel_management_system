from datetime import datetime, timezone
from decimal import Decimal

from extensions import db
from services import booking_state_service, payment_service, time_service


def _complete_booking(booking_room, checkout_utc_naive):
    booking_room.status = "checked_out"
    booking_room.check_in_actual = checkout_utc_naive.replace(hour=7)
    booking_room.check_out_actual = checkout_utc_naive
    booking_room.final_amount = Decimal("400000")
    booking_state_service.aggregate_booking_state(booking_room.booking)
    db.session.commit()
    return booking_room.booking


def _freeze_utc(monkeypatch, fake_now_naive):
    fake_aware = fake_now_naive.replace(tzinfo=timezone.utc)
    monkeypatch.setattr(time_service, "utc_now", lambda: fake_aware)


def test_completed_at_set_once_by_state_service(app, seed_hotels, monkeypatch):
    _, _, _, _, booking_room, _ = seed_hotels
    with app.app_context():
        _freeze_utc(monkeypatch, datetime(2026, 8, 13, 17, 5))
        booking = _complete_booking(booking_room, datetime(2026, 8, 13, 17, 5))
        assert booking.status == "completed"
        first_completed_at = booking.completed_at
        assert first_completed_at is not None

        # Sửa metadata rồi aggregate lại ở thời điểm khác: mốc không được trôi
        _freeze_utc(monkeypatch, datetime(2026, 8, 20, 9, 0))
        booking.note = "chỉnh sửa ghi chú sau này"
        booking_state_service.aggregate_booking_state(booking)
        db.session.commit()
        assert booking.completed_at == first_completed_at


def test_period_today_at_0030_bangkok_includes_late_utc_yesterday(
    app, seed_hotels, client, login_as, monkeypatch
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        # 00:30 Bangkok 14-08 = 17:30 UTC 13-08
        _freeze_utc(monkeypatch, datetime(2026, 8, 13, 17, 30))
        booking = _complete_booking(booking_room, datetime(2026, 8, 13, 17, 5))
        payment_service.record_deposit(
            booking_id=booking.id,
            amount=400_000,
            note="Thu 23:05 giờ VN (17:05 UTC hôm trước theo lịch UTC... vẫn là hôm nay VN)",
            created_at=datetime(2026, 8, 13, 17, 5),
        )
        db.session.commit()
        login_as(client, user)

        response = client.get(f"/{hotel.slug}/reports/api/reports/revenue?period=today")
        assert response.status_code == 200, response.json
        data = response.json["data"]
        assert data["completed_bookings"] == 1
        assert data["room_revenue"] == 400000.0
        assert data["total_net_payment"] == 400000.0


def test_period_today_at_2330_bangkok_excludes_next_business_day(
    app, seed_hotels, client, login_as, monkeypatch
):
    hotel, _, user, _, booking_room, _ = seed_hotels
    with app.app_context():
        # Hoàn tất 23:59 Bangkok ĐÊM QUA (13-08) = 16:59 UTC 13-08
        _freeze_utc(monkeypatch, datetime(2026, 8, 13, 16, 59))
        _complete_booking(booking_room, datetime(2026, 8, 13, 16, 59))
        db.session.commit()
        # Xem báo cáo 12:00 trưa nay (14-08 Bangkok) = 05:00 UTC 14-08
        _freeze_utc(monkeypatch, datetime(2026, 8, 14, 5, 0))
        login_as(client, user)

        response = client.get(f"/{hotel.slug}/reports/api/reports/revenue?period=today")
        assert response.status_code == 200, response.json
        assert response.json["data"]["completed_bookings"] == 0


def test_chart_groups_by_bangkok_date(app, booked_room, client, login_as, monkeypatch):
    hotel, user, room_a, room_b = booked_room
    with app.app_context():
        # 12:00 Bangkok 14-08 = 05:00 UTC 14-08
        _freeze_utc(monkeypatch, datetime(2026, 8, 14, 5, 0))
        # Hai lần checkout: 00:30 và 09:00 giờ VN ngày 14 — khác ngày UTC (13 vs 14)
        for booking_room, checkout in (
            (room_a, datetime(2026, 8, 13, 17, 30)),
            (room_b, datetime(2026, 8, 14, 2, 0)),
        ):
            booking_room.status = "checked_out"
            booking_room.check_in_actual = checkout.replace(hour=1)
            booking_room.check_out_actual = checkout
            booking_room.final_amount = Decimal("500000")
        booking_state_service.aggregate_booking_state(room_a.booking)
        db.session.commit()
        login_as(client, user)

        response = client.get(f"/{hotel.slug}/reports/api/reports/revenue?period=today")
        assert response.status_code == 200, response.json
        chart = response.json["data"]["chart"]
        assert len(chart) == 1
        assert chart[0]["date"] == "14/08"
        assert chart[0]["revenue"] == 1000000.0
