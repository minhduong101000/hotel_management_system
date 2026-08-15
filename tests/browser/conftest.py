"""Harness smoke trình duyệt (spec CI-hardening 15-08-2026).

Chạy với stack thật: BROWSER_BASE_URL=http://127.0.0.1:8000 \
BROWSER_ADMIN_PASSWORD=... venv/bin/python -m pytest -m browser -q
Thiếu biến môi trường -> skip toàn bộ (bộ test thường không chậm đi).
"""

import itertools
import json
import os
import time

import pytest

_seed_counter = itertools.count()

BASE = os.environ.get("BROWSER_BASE_URL", "").rstrip("/")
SLUG = os.environ.get("BROWSER_HOTEL_SLUG", "central")


@pytest.fixture(scope="session")
def base():
    if not BASE:
        pytest.skip("Cần BROWSER_BASE_URL trỏ tới stack compose đang chạy.")
    return BASE


@pytest.fixture
def guarded_page(page, base):
    """Hai bất biến toàn cục: không lỗi console, không request /api|.js >= 400.

    Đây là lưới bắt 'nút chết im lặng' — lớp bug đã lọt 2 lần ngày 14-08.
    """
    console_errors = []
    bad_responses = []
    page.on(
        "console",
        lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
    )

    def _on_response(response):
        if response.status >= 400 and (
            "/api/" in response.url or response.url.endswith(".js")
        ):
            bad_responses.append(f"{response.status} {response.url}")

    page.on("response", _on_response)
    yield page
    assert not console_errors, f"Lỗi console trong phiên: {console_errors}"
    assert not bad_responses, f"Request lỗi trong phiên: {bad_responses}"


@pytest.fixture
def admin_page(guarded_page, base):
    password = os.environ.get("BROWSER_ADMIN_PASSWORD")
    if not password:
        pytest.skip("Cần BROWSER_ADMIN_PASSWORD (xem .env của stack).")
    page = guarded_page
    page.goto(f"{base}/{SLUG}/login")
    page.fill('input[name="username"]', os.environ.get("BROWSER_ADMIN_USER", "admin"))
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_url("**/rooms/dashboard/room-map", timeout=15_000)
    return page


class _JsResponse:
    """Bọc kết quả fetch trong trang cho giống APIResponse tối thiểu."""

    def __init__(self, raw):
        self.status = raw["status"]
        self._body = raw["body"]

    @property
    def ok(self):
        return 200 <= self.status < 300

    def json(self):
        return json.loads(self._body)

    def text(self):
        return self._body


def api_post(page, base, path, payload):
    """POST qua fetch TRONG trang — đi đúng cơ chế CSRF wrap của app."""
    raw = page.evaluate(
        """async ([path, payload]) => {
            const res = await fetch(path, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload),
            });
            return {status: res.status, body: await res.text()};
        }""",
        [path, payload],
    )
    return _JsResponse(raw)


SMOKE_PHONE = "0909000111"
SMOKE_NAME = "Khach Smoke"
ROOM_A, ROOM_B = "701", "702"


@pytest.fixture
def seeded(admin_page, base):
    """Phòng 701/702 + khách + một booking tươi trên cửa sổ ngày duy nhất."""
    page = admin_page

    def api_get(path):
        return json.loads(page.evaluate(
            "async (p) => await (await fetch(p)).text()", path,
        ))

    # Seed theo lối query-trước-tạo-sau: KHÔNG tự gây 4xx nào
    # (guard console/response của chính suite này sẽ bắt 4xx làm fail test).
    timeline_now = api_get(f"/{SLUG}/timeline/api/bookings/timeline")
    existing_rooms = {g.get("room_number") for g in timeline_now["groups"]}
    for number in (ROOM_A, ROOM_B):
        if number in existing_rooms:
            continue
        response = api_post(page, base, f"/{SLUG}/rooms/api/settings", {
            "room_number": number,
            "room_type": "Standard",
            "price_per_night": 500000,
            "price_initial_block": 100000,
            "initial_hours": 2,
            "price_next_hour": 50000,
        })
        assert response.status == 201, response.text()

    matches = [
        c for c in api_get(f"/{SLUG}/customers/api/customers?q={SMOKE_PHONE}")
        if c.get("phone") == SMOKE_PHONE
    ]
    if matches:
        customer_id = matches[0]["id"]
    else:
        response = api_post(page, base, f"/{SLUG}/customers/api/customers", {
            "name": SMOKE_NAME,
            "phone": SMOKE_PHONE,
        })
        assert response.ok, response.text()
        customer_id = next(
            c["id"]
            for c in api_get(f"/{SLUG}/customers/api/customers?q={SMOKE_PHONE}")
            if c.get("phone") == SMOKE_PHONE
        )

    # Mỗi lượt seed một NGÀY riêng (counter trong phiên + giây hệ thống),
    # kèm retry dịch ngày — chạy lặp bao nhiêu lần cũng không đụng lịch cũ.
    uniq = int(time.time())
    body = None
    for attempt in range(5):
        offset_days = 60 + ((uniq * 13 + next(_seed_counter) * 131) % 3000)
        check_in = time.strftime(
            "%Y-%m-%dT14:00", time.localtime(uniq + offset_days * 86400),
        )
        check_out = time.strftime(
            "%Y-%m-%dT12:00", time.localtime(uniq + (offset_days + 1) * 86400),
        )
        response = api_post(page, base, f"/{SLUG}/timeline/api/bookings/create", {
            "room_number": ROOM_A,
            "name": SMOKE_NAME,
            "phone": SMOKE_PHONE,
            "check_in": check_in,
            "check_out": check_out,
            "status": "booked",
            "rental_type": "daily",
            "deposit": 250000,
            "customer_id": customer_id,
        })
        body = response.json()
        if body.get("success"):
            break
    assert body and body.get("success"), body

    # Tra booking_id từ timeline (create chỉ trả code)
    timeline = json.loads(page.evaluate(
        """async (path) => await (await fetch(path)).text()""",
        f"/{SLUG}/timeline/api/bookings/timeline",
    ))
    room_a_id = next(
        g["id"] for g in timeline["groups"] if g.get("room_number") == ROOM_A
    )
    check_in_date = check_in[:10]
    booking_id = next(
        item["booking_id"]
        for item in timeline["items"]
        if item["group"] == room_a_id and item["start"].startswith(check_in_date)
    )
    return {
        "booking_id": booking_id,
        "code": body["code"],
        "check_in": check_in,
        "check_out": check_out,
    }
