"""Một nguồn chân lý cho 'phòng có bận không'.

Trước đây có ba cách kiểm tra khác nhau: đường đặt lẻ xét cả giờ thực tế và
khách overstay, còn đường đặt đoàn và tìm phòng trống chỉ so giờ dự kiến.
"""

from datetime import datetime, timezone

import pytest

from extensions import db
from services import room_availability_service, time_service


@pytest.fixture()
def frozen_noon(monkeypatch):
    """13:00 VN ngày 19-08 = 06:00 UTC."""
    monkeypatch.setattr(
        time_service, "utc_now", lambda: datetime(2026, 8, 19, 6, 0, tzinfo=timezone.utc)
    )


def test_overstaying_guest_still_holds_the_room(app, seed_hotels, frozen_noon):
    hotel, _, _, _, br, _ = seed_hotels
    br.status = "checked_in"
    br.check_in_expected = datetime(2026, 8, 18, 14, 0)
    br.check_out_expected = datetime(2026, 8, 19, 12, 0)   # đã quá hẹn 1 tiếng
    db.session.commit()

    with app.test_request_context(f"/{hotel.slug}/"):
        from flask import g

        g.hotel_id = hotel.id
        busy = room_availability_service.has_room_conflict(
            room_id=br.room_id,
            start_dt=datetime(2026, 8, 19, 13, 0),
            end_dt=datetime(2026, 8, 19, 15, 0),
        )

    assert busy is True


def test_checked_in_row_without_an_end_is_busy(app, seed_hotels, frozen_noon):
    hotel, _, _, _, br, _ = seed_hotels
    br.status = "checked_in"
    br.check_in_expected = datetime(2026, 8, 18, 14, 0)
    br.check_out_expected = None
    db.session.commit()

    with app.test_request_context(f"/{hotel.slug}/"):
        from flask import g

        g.hotel_id = hotel.id
        busy = room_availability_service.has_room_conflict(
            room_id=br.room_id,
            start_dt=datetime(2026, 8, 25, 14, 0),
            end_dt=datetime(2026, 8, 26, 12, 0),
        )

    assert busy is True


def test_free_window_after_checkout_is_not_a_conflict(app, seed_hotels, frozen_noon):
    hotel, _, _, _, br, _ = seed_hotels
    br.status = "booked"
    br.check_in_expected = datetime(2026, 8, 19, 14, 0)
    br.check_out_expected = datetime(2026, 8, 20, 12, 0)
    db.session.commit()

    with app.test_request_context(f"/{hotel.slug}/"):
        from flask import g

        g.hotel_id = hotel.id
        busy = room_availability_service.has_room_conflict(
            room_id=br.room_id,
            start_dt=datetime(2026, 8, 20, 14, 0),
            end_dt=datetime(2026, 8, 21, 12, 0),
        )

    assert busy is False


def test_excluded_row_does_not_conflict_with_itself(app, seed_hotels, frozen_noon):
    hotel, _, _, _, br, _ = seed_hotels
    br.status = "booked"
    br.check_in_expected = datetime(2026, 8, 19, 14, 0)
    br.check_out_expected = datetime(2026, 8, 20, 12, 0)
    db.session.commit()

    with app.test_request_context(f"/{hotel.slug}/"):
        from flask import g

        g.hotel_id = hotel.id
        busy = room_availability_service.has_room_conflict(
            room_id=br.room_id,
            start_dt=datetime(2026, 8, 19, 14, 0),
            end_dt=datetime(2026, 8, 20, 12, 0),
            exclude_booking_room_id=br.id,
        )

    assert busy is False


def test_future_booking_is_allowed_while_guest_is_still_within_expected_stay(
    app, seed_hotels, frozen_noon
):
    """Khách đang ở, dự kiến trả trưa mai (CHƯA quá hẹn) -> tuần sau vẫn phải
    đặt được phòng này. Một khách đang ở không được khoá cứng mọi ngày tương
    lai; chỉ có khách quá hẹn mới chiếm phòng vượt quá giờ dự kiến."""
    hotel, _, _, _, br, _ = seed_hotels
    br.status = "checked_in"
    br.check_in_expected = datetime(2026, 8, 18, 14, 0)
    br.check_out_expected = datetime(2026, 8, 20, 12, 0)  # trả trưa mai, chưa quá hẹn (now = 19/8 13:00)
    db.session.commit()

    with app.test_request_context(f"/{hotel.slug}/"):
        from flask import g

        g.hotel_id = hotel.id
        busy = room_availability_service.has_room_conflict(
            room_id=br.room_id,
            start_dt=datetime(2026, 8, 26, 14, 0),
            end_dt=datetime(2026, 8, 27, 12, 0),
        )

    assert busy is False


def test_overdue_guest_still_blocks_a_booking_starting_around_right_now(
    app, seed_hotels, frozen_noon
):
    """Khách đang ở đã quá giờ trả dự kiến (hẹn 12:00, giờ là 13:00) -> một đặt
    phòng mà cửa sổ bao trùm "bây giờ" (bắt đầu từ trước bây giờ) vẫn phải bị
    chặn, vì khách vẫn đang chiếm phòng thật ngay lúc này."""
    hotel, _, _, _, br, _ = seed_hotels
    br.status = "checked_in"
    br.check_in_expected = datetime(2026, 8, 18, 14, 0)
    br.check_out_expected = datetime(2026, 8, 19, 12, 0)  # hẹn 12:00, giờ 13:00 -> quá hẹn 1 tiếng
    db.session.commit()

    with app.test_request_context(f"/{hotel.slug}/"):
        from flask import g

        g.hotel_id = hotel.id
        busy = room_availability_service.has_room_conflict(
            room_id=br.room_id,
            start_dt=datetime(2026, 8, 19, 12, 30),  # trước "bây giờ" (13:00)
            end_dt=datetime(2026, 8, 19, 13, 30),     # trùm qua "bây giờ"
        )

    assert busy is True


def test_occupied_room_ids_includes_the_overstaying_room(app, seed_hotels, frozen_noon):
    hotel, _, _, _, br, _ = seed_hotels
    br.status = "checked_in"
    br.check_in_expected = datetime(2026, 8, 18, 14, 0)
    br.check_out_expected = datetime(2026, 8, 19, 12, 0)
    db.session.commit()

    with app.test_request_context(f"/{hotel.slug}/"):
        from flask import g

        g.hotel_id = hotel.id
        busy_ids = room_availability_service.occupied_room_ids(
            start_dt=datetime(2026, 8, 19, 13, 0),
            end_dt=datetime(2026, 8, 19, 15, 0),
        )

    assert br.room_id in busy_ids
