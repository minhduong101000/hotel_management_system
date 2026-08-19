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


def test_no_early_surcharge_when_guest_checked_in_at_the_expected_hour(
    utc_container, client, seed_hotels, login_as, monkeypatch
):
    """Khách nhận đúng 14:00 VN, trả đúng 12:00 hôm sau = tròn 1 đêm.

    Trước khi sửa: check_in_actual (07:00 UTC) bị so với 14:00 VN ra 'sớm 7 giờ'
    -> phụ thu 100% giá đêm -> hóa đơn gấp đôi.
    """
    hotel, _, admin, _, br, _ = seed_hotels
    br.status = "checked_in"
    br.rental_type = "daily"
    br.check_in_expected = datetime(2026, 8, 19, 14, 0)     # VN
    br.check_out_expected = datetime(2026, 8, 20, 12, 0)    # VN
    br.check_in_actual = datetime(2026, 8, 19, 7, 0)        # UTC = 14:00 VN
    br.room.status = "occupied"
    db.session.commit()
    # "Bây giờ" = 12:00 VN ngày trả = 05:00 UTC
    monkeypatch.setattr(
        time_service, "utc_now", lambda: datetime(2026, 8, 20, 5, 0, tzinfo=timezone.utc)
    )
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/bookings/api/rooms/preview_checkout",
        json={"number": br.room.room_number},
    )

    assert response.status_code == 200, response.get_json()
    quote = response.get_json()["quote"]
    # 1 đêm x 500.000 (giá seed), không phụ thu
    assert float(quote["total"]) == 500000.0, quote


def test_check_in_after_midnight_vn_does_not_add_a_phantom_night(
    utc_container, client, seed_hotels, login_as, monkeypatch
):
    """Khách nhận 01:00 VN ngày 19: ngày UTC là 18 -> trước khi sửa bị tính thừa 1 đêm."""
    hotel, _, admin, _, br, _ = seed_hotels
    br.status = "checked_in"
    br.rental_type = "daily"
    br.check_in_expected = datetime(2026, 8, 19, 1, 0)      # VN
    br.check_out_expected = datetime(2026, 8, 19, 12, 0)    # VN
    br.check_in_actual = datetime(2026, 8, 18, 18, 0)       # UTC = 01:00 VN ngày 19
    br.room.status = "occupied"
    db.session.commit()
    monkeypatch.setattr(
        time_service, "utc_now", lambda: datetime(2026, 8, 19, 5, 0, tzinfo=timezone.utc)
    )
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/bookings/api/rooms/preview_checkout",
        json={"number": br.room.room_number},
    )

    quote = response.get_json()["quote"]
    # Nhận 01:00 VN và trả 12:00 VN đều nằm trong CÙNG một ngày nghiệp vụ
    # (2026-08-19), dù mốc UTC của giờ nhận phòng thuộc ngày 18/08. Bất biến
    # cần khoá: ranh giới ngày UTC không được phát sinh thêm một đêm ảo.
    # bill_start_date = bill_end_date = 2026-08-19 => 1 đêm x 500.000, không
    # phụ thu (check-in đúng giờ hẹn, check-out đúng giờ hẹn).
    assert float(quote["total"]) == 500000.0, quote
