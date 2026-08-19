"""Hành vi dưới TZ=UTC — đúng môi trường container production.

Các test này xanh giả trên máy dev múi VN nếu thiếu fixture utc_container:
datetime.now() khi đó tình cờ trùng giờ nghiệp vụ.
"""

from datetime import datetime, timezone

import pytest

from extensions import db
from services import time_service


@pytest.fixture()
def frozen_2pm_vn(monkeypatch):
    """Đóng băng đồng hồ: 07:00 UTC = 14:00 giờ VN."""
    monkeypatch.setattr(
        time_service, "utc_now", lambda: datetime(2026, 8, 19, 7, 0, tzinfo=timezone.utc)
    )
    return datetime(2026, 8, 19, 7, 0)


def test_checkin_succeeds_when_guest_arrives_at_the_expected_hour(
    utc_container, frozen_2pm_vn, client, seed_hotels, login_as
):
    hotel, _, admin, _, br, _ = seed_hotels
    br.status = "booked"
    br.check_in_expected = datetime(2026, 8, 19, 14, 0)   # giờ VN
    br.check_out_expected = datetime(2026, 8, 20, 12, 0)
    br.room.status = "available"
    br.room.clean_status = "cleaned"
    db.session.commit()
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/bookings/api/rooms/checkin",
        json={"booking_room_id": br.id},
    )

    assert response.status_code == 200, response.get_json()
    assert response.get_json()["success"] is True


def test_checkin_still_blocked_when_guest_is_genuinely_too_early(
    utc_container, frozen_2pm_vn, client, seed_hotels, login_as
):
    """Luật 'sớm tối đa 3 giờ' phải còn nguyên: hẹn 20:00 mà đến 14:00 thì chặn."""
    hotel, _, admin, _, br, _ = seed_hotels
    br.status = "booked"
    br.check_in_expected = datetime(2026, 8, 19, 20, 0)
    br.check_out_expected = datetime(2026, 8, 20, 12, 0)
    br.room.status = "available"
    br.room.clean_status = "cleaned"
    db.session.commit()
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/bookings/api/rooms/checkin",
        json={"booking_room_id": br.id},
    )

    assert response.status_code == 400
    assert "3 giờ" in response.get_json()["msg"]


def test_checkin_stores_check_in_actual_in_utc(
    utc_container, frozen_2pm_vn, client, seed_hotels, login_as
):
    """Sửa vế so sánh không được làm hỏng vế lưu trữ: *_actual vẫn là UTC."""
    hotel, _, admin, _, br, _ = seed_hotels
    br.status = "booked"
    br.check_in_expected = datetime(2026, 8, 19, 14, 0)
    br.check_out_expected = datetime(2026, 8, 20, 12, 0)
    br.room.status = "available"
    br.room.clean_status = "cleaned"
    db.session.commit()
    login_as(client, admin)

    client.post(
        f"/{hotel.slug}/bookings/api/rooms/checkin",
        json={"booking_room_id": br.id},
    )

    db.session.refresh(br)
    assert br.check_in_actual == datetime(2026, 8, 19, 7, 0)   # UTC, không phải 14:00


def test_walk_in_check_in_now_is_accepted(
    utc_container, frozen_2pm_vn, client, seed_hotels, login_as
):
    hotel, _, admin, _, br, _ = seed_hotels
    login_as(client, admin)
    room_number = br.room.room_number
    # Dọn phòng seed để không vướng guard 'phòng đang có khách'
    br.status = "cancelled"
    db.session.commit()

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/create",
        json={
            "room_number": room_number,
            "status": "checked_in",
            "rental_type": "daily",
            "customer_name": "Khach Vang Lai",
            "customer_phone": "0900000001",
            "check_in": "2026-08-19T14:00",
            "check_out": "2026-08-20T12:00",
            "deposit": 500000,
            "source": "walk_in",
        },
    )

    assert response.status_code == 200, response.get_json()
    assert response.get_json()["success"] is True, response.get_json()
