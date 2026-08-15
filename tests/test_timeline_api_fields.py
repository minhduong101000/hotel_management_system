"""Lưới timeline tự vẽ (spec 15-08-2026) cần field cấu trúc thay vì parse HTML.

API /api/bookings/timeline phải trả thêm: groups.room_type; items.customer_name,
rental_type, room_count, is_overstay. content/className giữ nguyên (tương thích).
"""

from datetime import datetime, timedelta


def _get_timeline(client, hotel):
    response = client.get(f"/{hotel.slug}/timeline/api/bookings/timeline")
    assert response.status_code == 200
    return response.get_json()


def test_timeline_groups_include_room_type(client, seed_hotels, login_as):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    data = _get_timeline(client, hotel)

    assert data["groups"], "seed phải có ít nhất 1 phòng"
    group = data["groups"][0]
    assert group["room_number"] == "101"
    assert group["room_type"] == "Standard"


def test_timeline_items_include_structured_fields(client, seed_hotels, login_as):
    hotel, _, admin, _, br_a, _ = seed_hotels
    login_as(client, admin)

    data = _get_timeline(client, hotel)

    items = [i for i in data["items"] if i["id"] == br_a.id]
    assert items, "booking seed phải xuất hiện trên timeline"
    item = items[0]
    assert item["customer_name"] == "Nguyen Van A"
    assert item["rental_type"] == "daily"
    assert item["room_count"] == 1
    assert item["is_overstay"] is False
    # tương thích ngược cho phần hiển thị cũ
    assert "content" in item and "className" in item


def test_timeline_flags_overstay_items(client, seed_hotels, login_as):
    from extensions import db
    from models import BookingRoom

    hotel, _, admin, _, br_a, _ = seed_hotels
    br_a.status = "checked_in"
    br_a.check_in_actual = datetime.now() - timedelta(days=2)
    br_a.check_out_expected = datetime.now() - timedelta(hours=3)
    db.session.commit()
    login_as(client, admin)

    data = _get_timeline(client, hotel)

    item = next(i for i in data["items"] if i["id"] == br_a.id)
    assert item["is_overstay"] is True
