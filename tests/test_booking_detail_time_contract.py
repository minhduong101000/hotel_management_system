"""Modal chi tiết booking không được trộn UTC vào ô giờ nghiệp vụ.

Vòng ghi ngược: GET /api/bookings/<id> đổ `check_in` vào ô datetime-local
`edit-checkin`; lễ tân bấm Lưu thì đúng chuỗi đó được POST sang
/api/bookings/update và ghi thẳng vào check_in_expected (cột GIỜ NGHIỆP VỤ).
Nếu API trả về giá trị UTC của check_in_actual thì mỗi lần Lưu sẽ lùi cột
nghiệp vụ 7 tiếng — khách nhận phòng 02:00 sáng bị tính thêm một đêm.
"""

from datetime import datetime

from extensions import db
from services import time_service


# 19:00 UTC 14-08 = 02:00 sáng 15-08 giờ VN — đúng ca qua nửa đêm gây thu oan.
CHECK_IN_UTC = datetime(2026, 8, 14, 19, 0)
CHECK_IN_BUSINESS = datetime(2026, 8, 15, 2, 0)
CHECK_OUT_BUSINESS = datetime(2026, 8, 16, 12, 0)


def _checked_in_guest(br):
    br.status = "checked_in"
    br.check_in_expected = CHECK_IN_BUSINESS
    br.check_out_expected = CHECK_OUT_BUSINESS
    br.check_in_actual = CHECK_IN_UTC
    db.session.commit()


def test_detail_returns_business_time_for_an_actual_check_in(
    client, seed_hotels, login_as
):
    hotel, _, admin, _, br, _ = seed_hotels
    _checked_in_guest(br)
    login_as(client, admin)

    detail = client.get(f"/{hotel.slug}/timeline/api/bookings/{br.id}").get_json()

    assert detail["check_in"] == "2026-08-15T02:00", (
        "ô datetime-local phải nhận GIỜ NGHIỆP VỤ; "
        f"nhận được {detail['check_in']!r} (giờ UTC của check_in_actual)"
    )


def test_saving_the_detail_modal_does_not_rewind_the_business_columns(
    client, seed_hotels, login_as
):
    """Vòng khép kín: giá trị API trả ra, POST ngược lại, cột phải đứng yên."""
    hotel, _, admin, _, br, _ = seed_hotels
    _checked_in_guest(br)
    login_as(client, admin)

    detail = client.get(f"/{hotel.slug}/timeline/api/bookings/{br.id}").get_json()

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json={
            "booking_id": br.booking_id,
            "booking_room_id": br.id,
            "room_id": br.room_id,
            "check_in": detail["check_in"],
            "check_out": detail["check_out"],
            "deposit": 200000,
        },
    )
    assert response.get_json()["success"] is True, response.get_json()

    db.session.refresh(br)
    assert br.check_in_expected == CHECK_IN_BUSINESS, (
        "check_in_expected là cột giờ nghiệp vụ; lưu modal không được lùi nó "
        f"về UTC (thành {br.check_in_expected})"
    )
    assert br.check_in_actual == CHECK_IN_UTC, "check_in_actual vẫn phải là UTC"


def test_room_list_and_created_at_are_shown_in_business_time(
    client, seed_hotels, login_as
):
    """Các mốc chỉ để đọc cũng phải là giờ nghiệp vụ, không phải UTC thô."""
    hotel, _, admin, _, br, _ = seed_hotels
    _checked_in_guest(br)
    br.booking.created_at = CHECK_IN_UTC
    db.session.commit()
    login_as(client, admin)

    detail = client.get(f"/{hotel.slug}/timeline/api/bookings/{br.id}").get_json()

    assert detail["created_at"] == "15/08/2026 02:00"
    room_row = next(r for r in detail["rooms"] if r["booking_room_id"] == br.id)
    assert room_row["check_in"] == "2026-08-15 02:00"


def test_business_helpers_agree_with_the_fixture(app):
    """Chốt giả định múi giờ của bộ test này (UTC+7), không phụ thuộc TZ máy."""
    with app.app_context():
        assert time_service.to_business_naive(CHECK_IN_UTC) == CHECK_IN_BUSINESS
