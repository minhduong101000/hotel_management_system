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


def test_back_to_back_checkout_and_checkin_at_same_time_is_not_a_conflict(
    app, seed_hotels, frozen_noon
):
    """Khách A hẹn trả 12:00 (chưa quá hẹn) -> khách B đặt bắt đầu ĐÚNG 12:00
    cùng ngày không được coi là trùng. Đây là ca xoay phòng hàng ngày ở khách
    sạn; cửa sổ bận phải nửa-mở [start, end) ở nhánh 'bounded' để trả 12:00 và
    nhận 12:00 không đụng nhau."""
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
            start_dt=datetime(2026, 8, 20, 12, 0),  # đúng giờ khách A trả
            end_dt=datetime(2026, 8, 21, 12, 0),
        )

    assert busy is False


def test_active_row_missing_expected_dates_fails_safe_as_busy(app, seed_hotels, frozen_noon, caplog):
    """Một booking đang active (booked) nhưng thiếu check_in_expected (cột
    cho phép NULL, dữ liệu bất thường có thật) phải được coi là BẬN
    (fail-safe), không phải trống (fail-open) — trong cơ chế chống trùng
    phòng, đoán sai theo hướng an toàn (lễ tân kiểm tra lại thủ công) còn hơn
    đoán sai theo hướng mở (hai khách vào cùng một phòng)."""
    hotel, _, _, _, br, _ = seed_hotels
    br.status = "booked"
    br.check_in_expected = None
    br.check_out_expected = datetime(2026, 8, 20, 12, 0)
    db.session.commit()

    with app.test_request_context(f"/{hotel.slug}/"):
        from flask import g

        g.hotel_id = hotel.id
        with caplog.at_level("WARNING"):
            busy = room_availability_service.has_room_conflict(
                room_id=br.room_id,
                start_dt=datetime(2026, 8, 19, 14, 0),
                end_dt=datetime(2026, 8, 20, 18, 0),
            )

    assert busy is True
    assert any("thiếu mốc thời gian" in message for message in caplog.messages)


@pytest.fixture()
def frozen_4pm(monkeypatch):
    """16:00 VN ngày 19-08 = 09:00 UTC.

    Khác `frozen_noon` (13:00): mốc này nằm SAU giờ bắt đầu (14:00) của cửa sổ
    tìm kiếm/đặt phòng mới bên dưới, nên mới phân biệt được code cũ (chỉ so
    giờ dự kiến) với service mới (chốt cửa sổ bận của khách quá hẹn tại "bây
    giờ"). Xem phần "Phát hiện chặn" trong task-13-report.md để biết vì sao
    `frozen_noon` (13:00, TRƯỚC 14:00) không đo được gì ở đây.
    """
    monkeypatch.setattr(
        time_service, "utc_now", lambda: datetime(2026, 8, 19, 9, 0, tzinfo=timezone.utc)
    )


def test_search_does_not_offer_a_room_with_an_overstaying_guest(
    client, seed_hotels, login_as, frozen_4pm
):
    hotel, _, admin, _, br, _ = seed_hotels
    br.status = "checked_in"
    br.check_in_expected = datetime(2026, 8, 18, 14, 0)
    br.check_out_expected = datetime(2026, 8, 19, 12, 0)   # quá hẹn 4 tiếng (now = 16:00)
    br.check_in_actual = datetime(2026, 8, 18, 7, 0)        # UTC, = 14:00 VN 18-08
    db.session.commit()
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/rooms/api/rooms/search",
        json={"check_in": "2026-08-19", "check_out": "2026-08-20"},
    )

    grouped = response.get_json()["data"]
    offered = [r["number"] for rooms in grouped.values() for r in rooms]
    assert br.room.room_number not in offered


def test_group_booking_refuses_a_room_with_an_overstaying_guest(
    client, seed_hotels, login_as, frozen_4pm
):
    hotel, _, admin, _, br, _ = seed_hotels
    br.status = "checked_in"
    br.check_in_expected = datetime(2026, 8, 18, 14, 0)
    br.check_out_expected = datetime(2026, 8, 19, 12, 0)   # quá hẹn 4 tiếng (now = 16:00)
    br.check_in_actual = datetime(2026, 8, 18, 7, 0)        # UTC, = 14:00 VN 18-08
    db.session.commit()
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/bookings/api/bookings/group_create",
        json={
            "check_in": "2026-08-19",
            "check_out": "2026-08-20",
            "room_ids": [br.room_id],
            "customer": {"phone": "0900000003", "name": "Doan Test"},
            # Cọc phải đúng 50% hoặc 100% tổng dự kiến (1 đêm x 500.000),
            # nếu không request bị chặn TRƯỚC khi tới bước kiểm tra trùng phòng.
            "deposit": 500000,
        },
    )

    body = response.get_json()
    assert body["success"] is False, body
    assert "trùng lịch hết" in body["msg"]


def test_update_without_status_still_checks_for_overlap(client, seed_hotels, login_as):
    """Gọi thẳng API mà bỏ trường status: trước đây vừa bỏ qua kiểm tra trùng
    lịch, vừa ghi status = None."""
    from models import BookingRoom

    hotel, _, admin, _, br, _ = seed_hotels
    br.status = "booked"
    br.check_in_expected = datetime(2026, 8, 19, 14, 0)
    br.check_out_expected = datetime(2026, 8, 20, 12, 0)
    other = BookingRoom(
        hotel_id=hotel.id,
        booking_id=br.booking_id,
        room_id=br.room_id,
        status="booked",
        check_in_expected=datetime(2026, 8, 22, 14, 0),
        check_out_expected=datetime(2026, 8, 23, 12, 0),
    )
    db.session.add(other)
    db.session.commit()
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json={
            "booking_id": br.booking_id,
            "booking_room_id": other.id,
            "room_id": br.room_id,
            # cố tình KHÔNG gửi status
            "check_in": "2026-08-19T18:00",   # đè lên br
            "check_out": "2026-08-20T10:00",
        },
    )

    assert response.get_json()["success"] is False
    db.session.refresh(other)
    assert other.status == "booked"                              # không bị ghi None
    assert other.check_in_expected == datetime(2026, 8, 22, 14, 0)  # không bị đổi giờ
