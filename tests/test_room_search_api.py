"""Bug 15-08 (lộ khi nghiệm thu redesign): /api/rooms/search NameError.

room_controller chỉ import get_effective_room_prices_bulk nhưng endpoint
search gọi get_effective_room_prices — đặt đoàn không tìm được phòng trống.
"""


def test_room_search_returns_available_rooms_with_prices(client, seed_hotels, login_as):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/rooms/api/rooms/search",
        json={"check_in": "2026-09-10T14:00:00", "check_out": "2026-09-12T12:00:00"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True, payload
    grouped = payload["data"]
    assert "Standard" in grouped
    rooms = grouped["Standard"]
    assert any(r["number"] == "101" for r in rooms)
    assert all(r["price"] for r in rooms)
