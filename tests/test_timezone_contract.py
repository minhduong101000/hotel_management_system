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


def test_overstay_is_flagged_as_soon_as_the_expected_hour_passes(
    utc_container, client, seed_hotels, login_as, monkeypatch
):
    hotel, _, admin, _, br, _ = seed_hotels
    br.status = "checked_in"
    br.check_in_expected = datetime(2026, 8, 18, 14, 0)
    br.check_out_expected = datetime(2026, 8, 19, 12, 0)   # VN
    br.check_in_actual = datetime(2026, 8, 18, 7, 0)
    db.session.commit()
    # 12:30 VN = 05:30 UTC — đã quá hẹn 30 phút
    monkeypatch.setattr(
        time_service, "utc_now", lambda: datetime(2026, 8, 19, 5, 30, tzinfo=timezone.utc)
    )
    login_as(client, admin)

    payload = client.get(f"/{hotel.slug}/timeline/api/bookings/timeline").get_json()

    item = next(i for i in payload["items"] if i["id"] == br.id)
    assert item["is_overstay"] is True


def test_timeline_serializes_every_moment_in_business_time(
    utc_container, client, seed_hotels, login_as, monkeypatch
):
    """Bar không được nhảy lùi 7 tiếng lúc khách check-in."""
    hotel, _, admin, _, br, _ = seed_hotels
    br.status = "checked_in"
    br.check_in_expected = datetime(2026, 8, 19, 14, 0)
    br.check_out_expected = datetime(2026, 8, 20, 12, 0)
    br.check_in_actual = datetime(2026, 8, 19, 7, 0)       # UTC = 14:00 VN
    db.session.commit()
    monkeypatch.setattr(
        time_service, "utc_now", lambda: datetime(2026, 8, 19, 8, 0, tzinfo=timezone.utc)
    )
    login_as(client, admin)

    payload = client.get(f"/{hotel.slug}/timeline/api/bookings/timeline").get_json()

    item = next(i for i in payload["items"] if i["id"] == br.id)
    assert item["start"].startswith("2026-08-19T14:00"), item["start"]


def test_room_map_marks_overdue_using_business_time(
    utc_container, client, seed_hotels, login_as, monkeypatch
):
    hotel, _, admin, _, br, _ = seed_hotels
    br.status = "checked_in"
    br.check_in_actual = datetime(2026, 8, 18, 7, 0)
    br.check_out_expected = datetime(2026, 8, 19, 12, 0)   # VN
    br.room.status = "occupied"
    db.session.commit()
    monkeypatch.setattr(
        time_service, "utc_now", lambda: datetime(2026, 8, 19, 5, 30, tzinfo=timezone.utc)
    )
    login_as(client, admin)

    response = client.get(f"/{hotel.slug}/rooms/api/rooms")

    payload = response.get_json()
    rooms = payload.get("rooms") if isinstance(payload, dict) else payload
    target = next(r for r in rooms if r.get("booking_id") == br.booking_id)
    assert target["is_overdue"] is True


def test_preview_checkout_displays_check_in_and_check_out_in_business_time(
    utc_container, client, seed_hotels, login_as, monkeypatch
):
    """preview_checkout_room không được in giờ UTC thẳng ra màn hình lễ tân.

    check_in_actual lưu UTC; lễ tân phải thấy giờ VN trên bảng xem trước
    thanh toán, không phải mốc UTC lệch 7 tiếng.
    """
    hotel, _, admin, _, br, _ = seed_hotels
    br.status = "checked_in"
    br.rental_type = "daily"
    br.check_in_expected = datetime(2026, 8, 19, 14, 0)     # VN
    br.check_out_expected = datetime(2026, 8, 20, 12, 0)    # VN
    br.check_in_actual = datetime(2026, 8, 19, 7, 0)        # UTC = 14:00 VN 19/08
    br.room.status = "occupied"
    db.session.commit()
    # "Bây giờ" = 12:00 VN 20/08 = 05:00 UTC
    monkeypatch.setattr(
        time_service, "utc_now", lambda: datetime(2026, 8, 20, 5, 0, tzinfo=timezone.utc)
    )
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/bookings/api/rooms/preview_checkout",
        json={"number": br.room.room_number},
    )

    payload = response.get_json()
    assert payload["success"] is True, payload
    assert payload["check_in"] == "14:00 19/08/2026", payload["check_in"]
    assert payload["check_out"] == "12:00 20/08/2026", payload["check_out"]


def test_room_conflict_check_does_not_flag_a_window_before_the_real_check_in(
    utc_container, client, seed_hotels, login_as
):
    """Chống trùng phòng không được so UTC thô của check_in_actual với cửa sổ
    giờ nghiệp vụ của khách mới.

    Khách đang ở nhận phòng thật lúc 14:00 VN (check_in_actual = 07:00 UTC).
    Trước khi sửa, code so trực tiếp 07:00 (bị hiểu lầm là giờ nghiệp vụ) với
    cửa sổ giờ nghiệp vụ 10:00-13:00 VN của khách mới -> tưởng chồng lấn (07:00
    < 13:00) -> chặn oan một khoảng thời gian hoàn toàn TRƯỚC giờ nhận phòng
    thật của khách đang ở.
    """
    hotel, _, admin, _, br, _ = seed_hotels
    br.status = "checked_in"
    br.check_in_expected = datetime(2026, 8, 19, 14, 0)     # VN
    br.check_out_expected = datetime(2026, 8, 20, 12, 0)    # VN
    br.check_in_actual = datetime(2026, 8, 19, 7, 0)        # UTC = 14:00 VN
    db.session.commit()
    room_number = br.room.room_number
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/create",
        json={
            "room_number": room_number,
            "status": "booked",
            "rental_type": "daily",
            "customer_name": "Khach Truoc Gio Nhan",
            "customer_phone": "0900000002",
            "check_in": "2026-08-19T10:00",
            "check_out": "2026-08-19T13:00",
            "deposit": 500000,
            "source": "walk_in",
        },
    )

    assert response.status_code == 200, response.get_json()
    assert response.get_json()["success"] is True, response.get_json()


def test_room_map_shows_check_in_time_in_business_time(
    utc_container, client, seed_hotels, login_as, monkeypatch
):
    """Sơ đồ phòng không được in giờ UTC thô của check_in_actual."""
    hotel, _, admin, _, br, _ = seed_hotels
    br.status = "checked_in"
    br.check_in_actual = datetime(2026, 8, 19, 7, 0)   # UTC = 14:00 VN
    br.check_out_expected = datetime(2026, 8, 20, 12, 0)
    br.room.status = "occupied"
    db.session.commit()
    monkeypatch.setattr(
        time_service, "utc_now", lambda: datetime(2026, 8, 19, 8, 0, tzinfo=timezone.utc)
    )
    login_as(client, admin)

    response = client.get(f"/{hotel.slug}/rooms/api/rooms")

    payload = response.get_json()
    rooms = payload.get("rooms") if isinstance(payload, dict) else payload
    target = next(r for r in rooms if r.get("booking_id") == br.booking_id)
    assert target["check_in_time"] == "14:00 19/08", target["check_in_time"]


def test_booking_code_uses_the_business_day_not_the_utc_day(
    utc_container, client, seed_hotels, login_as, monkeypatch
):
    """01:00 VN ngày 19 là 18:00 UTC ngày 18 — mã không được in ngày 18."""
    from models import Booking

    monkeypatch.setattr(
        time_service, "utc_now", lambda: datetime(2026, 8, 18, 18, 0, tzinfo=timezone.utc)
    )
    hotel, _, admin, _, br, _ = seed_hotels
    login_as(client, admin)
    room_number = br.room.room_number
    br.status = "cancelled"
    db.session.commit()

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/create",
        json={
            "room_number": room_number,
            "status": "booked",
            "rental_type": "daily",
            "customer_name": "Khach Dem",
            "customer_phone": "0900000002",
            "check_in": "2026-08-19T14:00",
            "check_out": "2026-08-20T12:00",
            "deposit": 500000,
            "source": "walk_in",
        },
    )
    assert response.get_json()["success"] is True, response.get_json()

    code = Booking.query.order_by(Booking.id.desc()).first().code
    assert "260819" in code, code


def test_price_rule_lookup_defaults_to_the_business_day(app, monkeypatch):
    """Giá ngày lễ bắt đầu 'hôm nay' phải có hiệu lực từ 00:00 VN, không phải 07:00."""
    from services import pricing_service

    monkeypatch.setattr(
        time_service, "utc_now", lambda: datetime(2026, 8, 18, 18, 0, tzinfo=timezone.utc)
    )
    with app.app_context():
        assert pricing_service._default_price_date() == datetime(2026, 8, 19, 1, 0)


def test_deposit_payment_created_at_is_utc_even_on_a_vn_clock_host(
    client, seed_hotels, login_as, monkeypatch
):
    """KHÔNG dùng utc_container: giả lập máy chạy giờ VN (dev, hoặc ai đó set TZ).

    created_at phải bám time_service chứ không bám đồng hồ máy, nếu không phiếu
    thu buổi tối rơi sang ngày nghiệp vụ hôm sau trong sổ quỹ.
    """
    import os
    import time as _time

    from models import Payment

    original = os.environ.get("TZ")
    os.environ["TZ"] = "Asia/Ho_Chi_Minh"
    _time.tzset()
    try:
        monkeypatch.setattr(
            time_service, "utc_now", lambda: datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
        )
        hotel, _, admin, _, br, _ = seed_hotels
        login_as(client, admin)

        response = client.post(
            f"/{hotel.slug}/timeline/api/bookings/update",
            json={
                "booking_id": br.booking_id,
                "booking_room_id": br.id,
                "room_id": br.room_id,
                "status": br.status,
                "check_in": "2026-08-19T14:00",
                "check_out": "2026-08-20T12:00",
                "deposit": 200000,
            },
        )
        assert response.get_json()["success"] is True, response.get_json()

        payment = Payment.query.order_by(Payment.id.desc()).first()
        assert payment.created_at == datetime(2026, 8, 19, 12, 0)
    finally:
        if original is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original
        _time.tzset()
