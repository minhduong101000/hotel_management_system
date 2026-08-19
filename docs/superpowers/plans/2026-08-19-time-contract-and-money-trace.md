# Sửa hợp đồng thời gian, XSS hóa đơn in, dấu vết cọc và chống trùng phòng — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sửa 3 lỗi P1 (không check-in được, thu oan tiền khách, XSS leo thang quyền) cùng 5 lỗi P2 đi kèm, và khóa chúng lại bằng test chạy được dưới `TZ=UTC`.

**Architecture:** Gốc của phần lớn lỗi là `datetime.now()` mang hai ý nghĩa lẫn lộn. Ta thêm hai helper vào `services/time_service.py` rồi phân loại từng lời gọi về đúng helper; quy đổi múi giờ đặt **tại biên** (`build_checkout_quote`, payload timeline) để `pricing_service` giữ nguyên là hàm thuần giờ nghiệp vụ. Ba đường kiểm tra trùng phòng gom về một service dùng chung. Một grep-guard trong test chặn lớp lỗi này tái phát.

**Tech Stack:** Flask, SQLAlchemy, pytest (marker `mysql`/`browser`), Playwright, JS thuần (không framework, không bundler).

**Spec:** `docs/superpowers/specs/2026-08-19-time-contract-and-money-trace-design.md`

## Global Constraints

- **Hai loại mốc thời gian, không được trộn:** cột `*_expected` là **giờ nghiệp vụ VN naive**; cột `created_at`, `*_actual`, `cancelled_at`, `completed_at`, `voided_at` là **UTC naive**.
- **Luật phân loại:** so với `*_expected` → `time_service.business_now_naive()`; ghi timestamp hệ thống → `time_service.utc_now_naive()`; sinh mã/đếm theo ngày → `time_service.business_today()`.
- **Cấm** đặt `TZ` cho container để "chữa" lỗi — spec mục 1 giải thích vì sao đó là cái bẫy.
- Múi giờ nghiệp vụ: `BUSINESS_TIMEZONE`, mặc định `Asia/Bangkok`.
- Điểm đóng băng đồng hồ duy nhất của test: `time_service.utc_now` (monkeypatch).
- Chính sách đã chốt: lễ tân có quyền vận hành như admin; giảm cọc **được phép** nhưng bắt buộc có lý do và để lại bút toán.
- Commit tiếng Anh, cuối message thêm `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Chạy test bằng `venv/bin/python -m pytest`.

## File Structure

**Tạo mới**
| File | Trách nhiệm |
| --- | --- |
| `services/room_availability_service.py` | Nguồn chân lý duy nhất cho "phòng có bận không" |
| `tests/test_timezone_contract.py` | Test hành vi dưới `TZ=UTC` cho 3 lỗi thời gian |
| `tests/test_no_ambient_now.py` | Grep-guard cấm `datetime.now()` |
| `tests/test_deposit_adjustment.py` | Bút toán điều chỉnh cọc |
| `tests/test_room_availability_service.py` | Ngữ nghĩa bận/trống, gồm khách overstay |
| `tests/test_print_invoice_security.py` | Chuỗi: đường in không nội suy thô |

**Sửa**
| File | Việc |
| --- | --- |
| `services/time_service.py` | +3 helper quy đổi |
| `services/booking_quote_service.py` | Quy đổi tại biên trước khi tính giá; `is_expired` dùng UTC |
| `services/pricing_service.py` | Docstring hợp đồng + mặc định `check_date` theo ngày nghiệp vụ |
| `services/payment_service.py` | +`record_deposit_adjustment` |
| `services/reporting_service.py` | `resolve_report_period` theo ngày nghiệp vụ |
| `services/business_operation_service.py` | `completed_at` dùng UTC |
| `controllers/booking_controller.py` | Guard check-in; timestamp; mã đoàn; dùng service trùng phòng |
| `controllers/timeline_controller.py` | Guard walk-in; clamp trùng phòng; payload timeline; timestamp; mã booking; cọc; lỗ status |
| `controllers/room_controller.py` | Cờ quá giờ; nhãn sắp đến; tìm phòng trống |
| `controllers/master_controller.py` | Đếm booking hôm nay |
| `controllers/expense_controller.py` | `voided_at` |
| `controllers/cashier_controller.py` | Nhãn "Điều chỉnh cọc" |
| `static/js/main.js` | +`escapeHtml` dùng chung |
| `static/js/timeline_manager.js` | Sửa `bdPrintInvoice`; escape sink; gửi lý do giảm cọc |
| `static/js/checkout.js`, `static/js/service.js` | Dùng `escapeHtml` chung |
| `templates/rooms/timeline.html` | Ô lý do giảm cọc; pin html5-qrcode |
| `templates/rooms/map.html` | Pin html5-qrcode |
| `tests/conftest.py` | +fixture `utc_container` |

---

## Task 1: Ba helper quy đổi thời gian

**Files:**
- Modify: `services/time_service.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_time_service.py`

**Interfaces:**
- Produces: `time_service.business_now_naive() -> datetime`, `time_service.to_business_naive(dt) -> datetime | None`, `time_service.business_naive_to_utc(dt) -> datetime | None`; pytest fixture `utc_container`.

> **Ghi chú lệch spec:** spec nêu 2 helper. Ta thêm helper thứ ba `business_naive_to_utc` vì Task 4 đổi payload timeline sang giờ VN, nên đường ghi ngược (`update_timeline` ghi vào `check_in_actual`) cần chiều quy đổi ngược lại. Không có nó thì Task 4 sẽ tạo lỗi mới.

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `tests/test_time_service.py`:

```python
from datetime import datetime, timezone

from services import time_service


def test_business_now_naive_is_vn_wallclock_without_tzinfo(app, monkeypatch):
    # 03:00 UTC = 10:00 giờ VN
    monkeypatch.setattr(
        time_service, "utc_now", lambda: datetime(2026, 8, 19, 3, 0, tzinfo=timezone.utc)
    )
    with app.app_context():
        result = time_service.business_now_naive()
    assert result == datetime(2026, 8, 19, 10, 0)
    assert result.tzinfo is None


def test_to_business_naive_accepts_naive_and_aware_utc(app):
    with app.app_context():
        assert time_service.to_business_naive(datetime(2026, 8, 19, 3, 0)) == datetime(2026, 8, 19, 10, 0)
        assert time_service.to_business_naive(
            datetime(2026, 8, 19, 3, 0, tzinfo=timezone.utc)
        ) == datetime(2026, 8, 19, 10, 0)
        assert time_service.to_business_naive(None) is None


def test_business_naive_to_utc_is_the_exact_inverse(app):
    with app.app_context():
        business = datetime(2026, 8, 19, 10, 0)
        assert time_service.business_naive_to_utc(business) == datetime(2026, 8, 19, 3, 0)
        assert time_service.to_business_naive(
            time_service.business_naive_to_utc(business)
        ) == business
        assert time_service.business_naive_to_utc(None) is None
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_time_service.py -v`
Expected: FAIL — `AttributeError: module 'services.time_service' has no attribute 'business_now_naive'`

- [ ] **Step 3: Thêm 3 helper vào `services/time_service.py`**

Thêm ngay sau hàm `business_today()`:

```python
def business_now_naive() -> datetime:
    """'Bây giờ' theo giờ nghiệp vụ, dạng naive.

    DÙNG KHI: so sánh với các cột *_expected (vốn là giờ nghiệp vụ naive).
    KHÔNG dùng để ghi vào cột timestamp hệ thống — dùng utc_now_naive().
    """
    return business_now().replace(tzinfo=None)


def to_business_naive(utc_dt):
    """Đổi mốc UTC (naive hoặc aware) sang giờ nghiệp vụ dạng naive.

    DÙNG KHI: cần đặt timestamp hệ thống (*_actual, created_at) cạnh giờ dự
    kiến để so sánh hoặc tính tiền.
    """
    if utc_dt is None:
        return None
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(_business_tz()).replace(tzinfo=None)


def business_naive_to_utc(business_dt):
    """Chiều ngược của to_business_naive: giờ nghiệp vụ naive -> UTC naive.

    DÙNG KHI: nhận một mốc giờ nghiệp vụ từ client rồi ghi vào cột *_actual.
    """
    if business_dt is None:
        return None
    if business_dt.tzinfo is not None:
        business_dt = business_dt.replace(tzinfo=None)
    return (
        business_dt.replace(tzinfo=_business_tz())
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )
```

- [ ] **Step 4: Chạy test để xác nhận xanh**

Run: `venv/bin/python -m pytest tests/test_time_service.py -v`
Expected: PASS

- [ ] **Step 5: Thêm fixture `utc_container` vào `tests/conftest.py`**

Thêm vào cuối file. Fixture này **tái lập đúng môi trường production** (container không set `TZ` nên đồng hồ chạy UTC), là thứ khiến các test ở Task 2–4 bắt được lỗi mà máy dev giờ VN che mất.

```python
@pytest.fixture()
def utc_container():
    """Ép đồng hồ tiến trình chạy UTC như container production.

    Không dùng monkeypatch.setenv vì thứ tự teardown khiến tzset() chạy trước
    khi biến môi trường được khôi phục.
    """
    import os
    import time as _time

    original = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    _time.tzset()
    try:
        yield
    finally:
        if original is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original
        _time.tzset()
```

- [ ] **Step 6: Xác nhận fixture hoạt động**

Run:
```bash
venv/bin/python -m pytest tests/test_time_service.py -q && \
venv/bin/python -c "
import os, time
os.environ['TZ']='UTC'; time.tzset()
from datetime import datetime
print('naive now duoi TZ=UTC:', datetime.now())
"
```
Expected: test PASS, và dòng in ra lệch 7 tiếng so với đồng hồ VN.

- [ ] **Step 7: Commit**

```bash
git add services/time_service.py tests/test_time_service.py tests/conftest.py
git commit -m "feat: add business/UTC conversion helpers and a UTC-clock test fixture

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 2: Sửa guard check-in và walk-in (P1)

**Files:**
- Modify: `controllers/booking_controller.py` (khoảng dòng 157-164)
- Modify: `controllers/timeline_controller.py` (khoảng dòng 516-520)
- Test: `tests/test_timezone_contract.py` (tạo mới)

**Interfaces:**
- Consumes: `time_service.business_now_naive()`, `time_service.utc_now_naive()`, fixture `utc_container` (Task 1).

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/test_timezone_contract.py`:

```python
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
    room_id = br.room_id
    # Dọn phòng seed để không vướng guard 'phòng đang có khách'
    br.status = "cancelled"
    db.session.commit()

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/create",
        json={
            "room_id": room_id,
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
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_timezone_contract.py -v`
Expected: FAIL — test 1 và test 4 trả 400 với thông báo "Chỉ được check-in sớm tối đa 3 giờ…" / "Chỉ được vào ở ngay sớm tối đa 3 giờ…". Đây chính là lỗi P1 tái lập được.

- [ ] **Step 3: Sửa guard check-in trong `controllers/booking_controller.py`**

Tìm khối bắt đầu bằng `now = datetime.now()` trong `checkin_room` và thay bằng:

```python
    # Hai loại "bây giờ" khác nhau: so với giờ hẹn (VN) và ghi mốc thực tế (UTC)
    now_business = time_service.business_now_naive()
    now_utc = time_service.utc_now_naive()
    if booking_room.check_in_expected and booking_room.check_in_expected - now_business > timedelta(hours=3):
        return jsonify({'success': False, 'msg': 'Chỉ được check-in sớm tối đa 3 giờ trước giờ booking.'}), 400

    booking_state_service.check_in_room(
        booking_room,
        checked_in_at=now_utc,
    )
```

Nếu `time_service` chưa có trong khối import của file, thêm nó vào import `from services import (...)`.

- [ ] **Step 4: Sửa guard walk-in trong `controllers/timeline_controller.py`**

Thay dòng `now = datetime.now()` ngay trước `if status == 'checked_in':` bằng:

```python
        now = time_service.business_now_naive()
```

Thêm `time_service` vào khối `from services import (...)` ở đầu file nếu chưa có.

- [ ] **Step 5: Chạy test để xác nhận xanh**

Run: `venv/bin/python -m pytest tests/test_timezone_contract.py -v`
Expected: PASS (4/4)

- [ ] **Step 6: Chạy suite để chắc không vỡ chỗ khác**

Run: `venv/bin/python -m pytest -m "not mysql" -q`
Expected: PASS toàn bộ

- [ ] **Step 7: Commit**

```bash
git add controllers/booking_controller.py controllers/timeline_controller.py tests/test_timezone_contract.py
git commit -m "fix: compare check-in guards against business time, not container clock

Guests arriving at their booked hour were rejected for four hours because
check_in_expected (VN wall clock) was compared with datetime.now() (UTC in
the container). Walk-in check-in was rejected outright.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 3: Quy đổi tại biên định giá (P1 — thu oan tiền khách)

**Files:**
- Modify: `services/booking_quote_service.py` (`build_checkout_quote`, `is_expired`)
- Modify: `services/pricing_service.py` (docstring hợp đồng)
- Modify: `controllers/booking_controller.py` (2 dòng `datetime.now()` của đường preview/checkout)
- Test: `tests/test_timezone_contract.py`

**Interfaces:**
- Consumes: `time_service.to_business_naive`, `time_service.utc_now_naive`.
- Produces: hợp đồng "mọi tham số datetime của `calculate_complex_hotel_bill` là giờ nghiệp vụ VN naive".

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_timezone_contract.py`:

```python
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
    assert float(quote["total"]) == 500000.0, quote
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_timezone_contract.py -k surcharge -v`
Expected: FAIL — `total` ra 1.000.000 thay vì 500.000 (đúng số tiền bị thu oan).

- [ ] **Step 3: Đưa hai mốc thời gian của đường checkout về UTC tường minh**

Trong `controllers/booking_controller.py`, hai dòng của đường preview:

```python
    check_in_time = booking_room.check_in_actual or booking_room.check_in_expected or time_service.utc_now_naive()
    check_out_time = time_service.utc_now_naive().replace(microsecond=0)
```

và dòng `checkout_at=datetime.now().replace(microsecond=0)` trong hàm checkout lẻ:

```python
            checkout_at=time_service.utc_now_naive().replace(microsecond=0),
```

Thêm `time_service` vào khối import `from services import (...)` nếu chưa có.

- [ ] **Step 4: Quy đổi tại biên trong `services/booking_quote_service.py`**

Trong `build_checkout_quote`, thay khối tính `check_in` và lời gọi `_room_quote`:

```python
    checkout_at = checkout_at.replace(microsecond=0)

    # pricing_service là hàm THUẦN giờ nghiệp vụ: quy đổi mọi mốc UTC tại đây.
    # Lưu ý: checkout_at trả ra trong quote phải GIỮ NGUYÊN UTC vì nó dùng cho
    # quote_fingerprint và được ghi vào check_out_actual.
    if booking_room.check_in_actual:
        check_in_business = time_service.to_business_naive(booking_room.check_in_actual)
    else:
        check_in_business = booking_room.check_in_expected or time_service.to_business_naive(checkout_at)
    checkout_business = time_service.to_business_naive(checkout_at)

    room_quote = _room_quote(
        booking_room.room,
        check_in_business,
        checkout_business,
        booking_room.rental_type,
        expected_check_in=booking_room.check_in_expected,
        expected_check_out=booking_room.check_out_expected,
        price_breakdown_snapshot=booking_room.price_breakdown_snapshot,
        hourly_price_snapshot=booking_room.hourly_price_snapshot,
    )
```

Thêm `from services import time_service` vào đầu file nếu chưa có.

- [ ] **Step 5: Sửa `is_expired` dùng UTC**

`expires_at` được tính từ `checkout_at` (UTC) nên `now` mặc định cũng phải là UTC:

```python
def is_expired(quote, now=None):
    now = (now or time_service.utc_now_naive()).replace(microsecond=0)
    return now > datetime.fromisoformat(quote["expires_at"])
```

- [ ] **Step 6: Ghi hợp đồng vào docstring `calculate_complex_hotel_bill`**

Thêm vào đầu docstring của hàm trong `services/pricing_service.py`:

```python
    """...

    HỢP ĐỒNG THỜI GIAN: mọi tham số datetime (check_in, check_out,
    expected_check_in, expected_check_out) phải là GIỜ NGHIỆP VỤ VN dạng naive.
    Người gọi chịu trách nhiệm quy đổi — xem build_checkout_quote.
    """
```

- [ ] **Step 7: Chạy test để xác nhận xanh**

Run: `venv/bin/python -m pytest tests/test_timezone_contract.py -v && venv/bin/python -m pytest tests/test_checkout_settlement.py tests/test_pricing_quote.py tests/test_checkout_quote_staleness.py -q`
Expected: PASS toàn bộ

- [ ] **Step 8: Commit**

```bash
git add services/booking_quote_service.py services/pricing_service.py controllers/booking_controller.py tests/test_timezone_contract.py
git commit -m "fix: normalize checkout quote times to business timezone before pricing

check_in_actual (UTC) was compared with check_in_expected (VN wall clock)
inside the surcharge calculation, billing an on-time daily guest a full extra
night as an 'arrived 7h early' surcharge. Conversion now happens at the quote
boundary; pricing_service is documented as business-time only.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 4: Cờ quá giờ, clamp trùng phòng và payload timeline

**Files:**
- Modify: `controllers/timeline_controller.py` (dòng ~68, ~132, ~208, ~224-232, ~297-298, ~845-862)
- Modify: `controllers/room_controller.py` (dòng ~283, ~399)
- Test: `tests/test_timezone_contract.py`

**Interfaces:**
- Consumes: `time_service.business_now_naive`, `time_service.to_business_naive`, `time_service.business_naive_to_utc`.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_timezone_contract.py`:

```python
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
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_timezone_contract.py -k "overstay or business_time or overdue" -v`
Expected: FAIL — `is_overstay` là `False` và `start` ra `07:00`.

- [ ] **Step 3: Sửa hai clamp trùng phòng**

Trong `controllers/timeline_controller.py`, ở `_has_room_time_conflict` và `_has_active_booking_conflict`, thay `now = datetime.now()` bằng:

```python
    now = time_service.business_now_naive()
```

- [ ] **Step 4: Đưa payload timeline về một hệ quy chiếu duy nhất**

Thêm helper ngay trước `get_timeline`:

```python
def _business_range(br, now_business):
    """Mốc bắt đầu/kết thúc của một bar, luôn ở giờ nghiệp vụ.

    check_in_actual là UTC còn check_in_expected đã là giờ nghiệp vụ, nên phải
    quy đổi trước khi trộn — nếu không bar sẽ nhảy lùi lúc khách check-in.
    """
    start = (
        time_service.to_business_naive(br.check_in_actual)
        if br.check_in_actual
        else br.check_in_expected
    )
    end = (
        time_service.to_business_naive(br.check_out_actual)
        if br.check_out_actual
        else br.check_out_expected
    )
    if not start:
        start = now_business
    if not end:
        end = start + timedelta(hours=1)
    return start, end
```

Trong `get_timeline`, thay `now = datetime.now()` bằng `now = time_service.business_now_naive()` và thay khối xác định start/end bằng:

```python
        start, end = _business_range(br, now)

        if br.status == 'checked_in' and end < now:
            end = now
```

- [ ] **Step 5: Giữ đường ghi ngược đúng hệ quy chiếu**

Trong `update_timeline`, client giờ gửi lên giờ nghiệp vụ, nên khi ghi vào cột `*_actual` (UTC) phải quy đổi ngược:

```python
        if start_str:
            new_start = _normalize_dt(datetime.fromisoformat(start_str.replace("Z", "+00:00")))
            if br.status == 'checked_in':
                br.check_in_actual = time_service.business_naive_to_utc(new_start)
            else:
                br.check_in_expected = new_start
            target_start = new_start

        if end_str:
            new_end = _normalize_dt(datetime.fromisoformat(end_str.replace("Z", "+00:00")))
            if br.status == 'checked_out':
                br.check_out_actual = time_service.business_naive_to_utc(new_end)
            else:
                br.check_out_expected = new_end
            target_end = new_end
```

- [ ] **Step 6: Sửa hai mốc trong `controllers/room_controller.py`**

Thay `now = datetime.now()` (trong hàm dashboard) bằng:

```python
        now = time_service.business_now_naive()
```

và dòng `is_overdue`:

```python
                    room_data['is_overdue'] = time_service.business_now_naive() > br.check_out_expected
```

Thêm `from services import time_service` nếu file chưa import.

- [ ] **Step 7: Chạy test để xác nhận xanh**

Run: `venv/bin/python -m pytest tests/test_timezone_contract.py -v && venv/bin/python -m pytest tests/test_timeline_api_fields.py tests/test_timeline_operations_ui.py -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add controllers/timeline_controller.py controllers/room_controller.py tests/test_timezone_contract.py
git commit -m "fix: overstay flags and timeline payload use business time

The overstay badge fired seven hours late and the conflict clamp that keeps an
overstaying guest's room busy was dead for that window. Timeline bars mixed UTC
actuals with VN expected times in one field, so a bar jumped backwards on
check-in; the payload is now business time end to end, with update_timeline
converting back before writing *_actual.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 5: Nhóm B — timestamp hệ thống ghi UTC

**Files:**
- Modify: `controllers/timeline_controller.py` (~594, 606, 649, 654, 1115, 1163, 1288, 1366)
- Modify: `controllers/booking_controller.py` (~869, 884, 971, 1200, 1376)
- Modify: `controllers/expense_controller.py` (~289)
- Modify: `services/business_operation_service.py` (~49)
- Modify: `services/refund_service.py` (~85)
- Test: `tests/test_timezone_contract.py`

**Interfaces:**
- Consumes: `time_service.utc_now_naive()`; `payment_service._now()` (mặc định sẵn có).

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_timezone_contract.py`:

```python
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
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_timezone_contract.py -k created_at -v`
Expected: FAIL — `created_at` ra 19:00 (giờ VN) thay vì 12:00 UTC.

- [ ] **Step 3: Xóa tham số `created_at` thừa ở 4 lời gọi `payment_service.record_*`**

`payment_service._now()` đã mặc định `utc_now_naive()`, nên cách sửa đúng là **xóa hẳn dòng**:

- `controllers/timeline_controller.py`: xóa `created_at=datetime.now(),` trong lời gọi `record_deposit` (~606), `record_cancellation_fee` (~1163), `record_deposit` nộp thêm cọc (~1288).
- `controllers/booking_controller.py`: xóa `created_at=datetime.now(),` trong lời gọi `record_deposit` của đặt đoàn (~884).

- [ ] **Step 4: Thay các mốc còn lại bằng `utc_now_naive()`**

Với những chỗ ghi thẳng vào cột (không qua `payment_service`), **thay** chứ không xóa — vì default của model `Booking.created_at` là `db.func.now()` (giờ session MySQL, không đáng tin):

| File | Chỗ sửa |
| --- | --- |
| `controllers/timeline_controller.py` | `created_at=datetime.now()` khi tạo `Booking` (~594); `checked_in_at=datetime.now()` (~649); `changed_at=datetime.now()` (~654); `cancelled_at = datetime.now()` (~1115); `br.check_in_actual = datetime.now()` (~1366) |
| `controllers/booking_controller.py` | `created_at=datetime.now()` khi tạo `Booking` (~869); `changed_at=datetime.now()` (~971); `checkout_at=datetime.now().replace(microsecond=0)` của group checkout (~1200, ~1376) |
| `controllers/expense_controller.py` | `expense.voided_at = datetime.now()` (~289) |
| `services/business_operation_service.py` | `operation.completed_at = datetime.now()` (~49) |
| `services/refund_service.py` | `effective_at = effective_at or datetime.now()` (~85) |

Tất cả thay bằng `time_service.utc_now_naive()` (giữ nguyên `.replace(microsecond=0)` ở đâu đang có). Thêm import `time_service` vào file nào còn thiếu.

- [ ] **Step 5: Chạy test để xác nhận xanh**

Run: `venv/bin/python -m pytest tests/test_timezone_contract.py -v`
Expected: PASS

- [ ] **Step 6: Chạy toàn bộ suite nhanh**

Run: `venv/bin/python -m pytest -m "not mysql" -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add controllers/ services/ tests/test_timezone_contract.py
git commit -m "fix: system timestamps go through time_service instead of the ambient clock

created_at, *_actual, cancelled_at, completed_at and voided_at were written
with datetime.now(), which only happened to match the UTC contract because the
container has no TZ set. On any VN-clock host the ledger silently mixed two
time frames and evening receipts landed on the next business day.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 6: Nhóm C — mã và bộ đếm theo ngày nghiệp vụ

**Files:**
- Modify: `controllers/timeline_controller.py` (~119), `controllers/booking_controller.py` (~863, ~198), `controllers/master_controller.py` (~45)
- Modify: `services/pricing_service.py` (~120, ~138), `services/reporting_service.py` (~26)
- Test: `tests/test_timezone_contract.py`

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_timezone_contract.py`:

```python
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
    room_id = br.room_id
    br.status = "cancelled"
    db.session.commit()

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/create",
        json={
            "room_id": room_id,
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
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_timezone_contract.py -k "booking_code or price_rule" -v`
Expected: FAIL — mã chứa `260818`; `_default_price_date` chưa tồn tại.

- [ ] **Step 3: Sửa mã booking và mã đoàn**

`controllers/timeline_controller.py` trong `generate_booking_code`:

```python
    date_str = time_service.business_today().strftime('%y%m%d')
```

`controllers/booking_controller.py` trong đường tạo đoàn:

```python
        time_prefix = time_service.business_now_naive().strftime('%y%m%d-%H%M%S')
```

Và dòng hiển thị ngày cọc (~198) đổi sang giờ nghiệp vụ:

```python
    deposit_date = (
        time_service.format_business(booking.created_at)
        if booking.created_at
        else time_service.format_business(time_service.utc_now_naive())
    )
```

- [ ] **Step 4: Sửa mặc định ngày dò bảng giá**

Trong `services/pricing_service.py`, thêm helper dùng chung rồi thay hai chỗ `check_date = check_date or datetime.now()`:

```python
def _default_price_date():
    """Ngày/giờ mặc định khi dò PriceRule — theo lịch nghiệp vụ VN.

    Dùng giờ máy sẽ khiến rule lễ/Tết và rule cuối tuần chỉ có hiệu lực từ
    7 giờ sáng trong deployment UTC.
    """
    from services import time_service

    return time_service.business_now_naive()
```

rồi:

```python
    check_date = check_date or _default_price_date()
```

- [ ] **Step 5: Sửa bộ đếm dashboard và kỳ báo cáo**

`controllers/master_controller.py`:

```python
    today_business = time_service.business_today()
    start_utc, end_utc = time_service.business_day_utc_bounds(today_business)
    metrics = {
        'total_rooms': Room.query.count(),
        'occupied_rooms': Room.query.filter_by(status='occupied').count(),
        'today_bookings': Booking.query.filter(
            Booking.created_at >= start_utc,
            Booking.created_at < end_utc,
        ).count(),
    }
```

`services/reporting_service.py` — sổ quỹ đã tự truyền `now` đúng giờ nghiệp vụ rồi
(`cashier_controller.py:33`), nhưng mặc định của hàm vẫn bám đồng hồ máy nên mọi
người gọi sau này đều dính bẫy:

```python
def resolve_report_period(period, start_value=None, end_value=None, now=None):
    from services import time_service

    now = now or time_service.business_now_naive()
```

- [ ] **Step 6: Chạy test để xác nhận xanh**

Run: `venv/bin/python -m pytest tests/test_timezone_contract.py -v && venv/bin/python -m pytest tests/test_report_period_utc.py tests/test_pricing_quote.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add controllers/ services/ tests/test_timezone_contract.py
git commit -m "fix: booking codes, price rules and counters follow the business day

Between midnight and 07:00 VN the UTC date is still the previous day, so
BK-/GRP- codes printed yesterday, holiday and weekend price rules took effect
seven hours late, and the dashboard counter disagreed with the reports.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 7: Grep-guard chặn tái phát

**Files:**
- Create: `tests/test_no_ambient_now.py`

- [ ] **Step 1: Viết test (đỏ nếu còn sót chỗ nào)**

```python
"""Chặn `datetime.now()` quay lại controllers/services.

Đây là lưới giữ cho lớp lỗi 17-08 không tái phát: `datetime.now()` lấy giờ đồng
hồ máy nên sai CẢ HAI vế của hợp đồng thời gian — nó không phải giờ nghiệp vụ
để so với *_expected, cũng không đảm bảo là UTC để ghi timestamp.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ("controllers", "services")
# datetime.now(timezone.utc) có tham số nên không khớp — chỉ bắt lời gọi trần.
BARE_NOW = re.compile(r"\bdatetime\.now\(\s*\)")


def test_no_ambient_datetime_now_in_controllers_and_services():
    offenders = []
    for folder in FOLDERS:
        for path in sorted((ROOT / folder).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if BARE_NOW.search(line):
                    offenders.append(f"{rel}:{lineno}: {line.strip()}")

    assert not offenders, (
        "datetime.now() lấy giờ đồng hồ máy nên sai cả hai vế của hợp đồng thời gian.\n"
        "Dùng time_service.business_now_naive() khi so với *_expected, "
        "hoặc time_service.utc_now_naive() khi ghi timestamp hệ thống.\n"
        + "\n".join(offenders)
    )
```

- [ ] **Step 2: Chạy test**

Run: `venv/bin/python -m pytest tests/test_no_ambient_now.py -v`
Expected: PASS nếu Task 2–6 đã quét sạch. Nếu FAIL, danh sách in ra chính là các chỗ còn sót — sửa từng chỗ theo luật phân loại rồi chạy lại.

- [ ] **Step 3: Chứng minh lưới thật sự bắt được**

```bash
printf '\nfrom datetime import datetime\n_probe = datetime.now()\n' >> services/reporting_service.py
venv/bin/python -m pytest tests/test_no_ambient_now.py -q   # phải ĐỎ
git checkout services/reporting_service.py
venv/bin/python -m pytest tests/test_no_ambient_now.py -q   # phải XANH trở lại
```
Expected: đỏ rồi xanh đúng như trên.

- [ ] **Step 4: Commit**

```bash
git add tests/test_no_ambient_now.py
git commit -m "test: guard against ambient datetime.now() returning to controllers

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 8: Bịt XSS ở hóa đơn in (P1)

**Files:**
- Modify: `static/js/main.js`
- Modify: `static/js/timeline_manager.js` (`bdPrintInvoice`, ~1113-1181)
- Create: `tests/test_print_invoice_security.py`
- Modify: `tests/browser/test_smoke_flows.py`

**Interfaces:**
- Produces: hàm toàn cục `escapeHtml(value) -> string` trong `main.js` (được nạp ở mọi trang tenant qua `layouts/base.html`).

- [ ] **Step 1: Viết test chuỗi thất bại**

Tạo `tests/test_print_invoice_security.py`:

```python
"""Cửa sổ in hóa đơn là sink XSS: nó document.write chuỗi HTML tự ghép.

Popup mở bằng window.open('', '_blank') nên same-origin với app, và app không
có CSP, nên mã trong tên khách sẽ chạy với phiên của người bấm in.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_shared_escape_helper_exists_in_main_js():
    main_js = _source("static/js/main.js")
    assert "function escapeHtml(" in main_js
    assert "textContent" in main_js


def test_print_invoice_escapes_every_interpolated_field():
    script = _source("static/js/timeline_manager.js")
    start = script.index("function bdPrintInvoice()")
    end = script.index("function bdUpdateServiceQty(")
    body = script[start:end]

    for raw in ("${customer}", "${bookingCode}", "${room}", "${total}", "${created}"):
        assert raw not in body, f"{raw} chưa được escape trong bdPrintInvoice"
    for safe in (
        "${escapeHtml(customer)}",
        "${escapeHtml(bookingCode)}",
        "${escapeHtml(room)}",
    ):
        assert safe in body, f"thiếu {safe}"
    # Không được sao chép innerHTML của bảng: nó kế thừa mọi chỗ chưa escape
    assert "bd-invoice-table-body')?.innerHTML" not in body
    assert "buildPrintRows(" in body
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_print_invoice_security.py -v`
Expected: FAIL — `function escapeHtml(` chưa có trong `main.js`.

- [ ] **Step 3: Thêm `escapeHtml` vào `static/js/main.js`**

Thêm vào đầu file, ngay trước `function api(path)`:

```javascript
/**
 * Escape dữ liệu người dùng trước khi ghép vào chuỗi HTML.
 * Dùng khi buộc phải dựng HTML bằng chuỗi; nơi nào đặt được textContent thì
 * ưu tiên textContent.
 */
function escapeHtml(value) {
    const holder = document.createElement('div');
    holder.textContent = value == null ? '' : String(value);
    return holder.innerHTML;
}
```

- [ ] **Step 4: Dựng lại các dòng hóa đơn từ dữ liệu và escape mọi trường**

Trong `static/js/timeline_manager.js`, thêm helper ngay trước `bdPrintInvoice`:

```javascript
// Dựng dòng hóa đơn từ DỮ LIỆU thay vì sao chép innerHTML của bảng đang hiển thị
// — bản sao đó kế thừa mọi chỗ chưa escape của renderer.
function buildPrintRows() {
    const rows = [];
    let stt = 1;
    if (bookingDetailRoomLine && Number(bookingDetailRoomFee) > 0) {
        rows.push(`
            <tr>
                <td>${stt++}</td>
                <td>${escapeHtml(bookingDetailRoomLine.name)}</td>
                <td>1</td>
                <td>${escapeHtml(formatVND(bookingDetailRoomFee))}</td>
                <td>${escapeHtml(formatVND(bookingDetailRoomFee))}</td>
            </tr>
        `);
    }
    bookingDetailServicesLines.forEach(line => {
        const qty = Number(line.quantity || 0);
        const lineTotal = qty * Number(line.price || 0);
        rows.push(`
            <tr>
                <td>${stt++}</td>
                <td>${escapeHtml(line.name || 'Dich vu')}</td>
                <td>${qty}</td>
                <td>${escapeHtml(formatVND(line.price))}</td>
                <td>${escapeHtml(formatVND(lineTotal))}</td>
            </tr>
        `);
    });
    return rows.join('');
}
```

Trong `bdPrintInvoice`, thay dòng lấy `tableHtml`:

```javascript
    const tableHtml = buildPrintRows();
```

và escape mọi trường trong template — 6 chỗ nội suy trong khối `.meta`, tiêu đề `<title>` và dòng tổng tiền:

```javascript
            <title>Hoa don ${escapeHtml(bookingCode)}</title>
```

```javascript
            <div class="meta">
                <div><strong>Ma booking:</strong> ${escapeHtml(bookingCode)}</div>
                <div><strong>Khach hang:</strong> ${escapeHtml(customer)}</div>
                <div><strong>Phong:</strong> ${escapeHtml(room)}</div>
                <div><strong>Nhan phong:</strong> ${escapeHtml(checkIn) || '-'}</div>
                <div><strong>Tra phong:</strong> ${escapeHtml(checkOut) || '-'}</div>
                <div><strong>Tao luc:</strong> ${escapeHtml(created)}</div>
            </div>
```

```javascript
            <div class="total">Tong tien: ${escapeHtml(total)}</div>
```

- [ ] **Step 5: Chạy test chuỗi để xác nhận xanh**

Run: `venv/bin/python -m pytest tests/test_print_invoice_security.py -v`
Expected: PASS

- [ ] **Step 6: Thêm test trình duyệt chứng minh mã không chạy**

Thêm vào cuối `tests/browser/test_smoke_flows.py`:

```python
def test_b5_print_invoice_does_not_execute_injected_guest_name(admin_page, base):
    """Tên khách độc hại không được chạy trong cửa sổ in.

    bdPrintInvoice đọc textContent của #bd-customer-label rồi ghép thẳng vào
    HTML, nên đặt textContent đúng bằng payload là tái lập chính xác đường đi
    của tên khách do server trả về verbatim. Mở modal bằng JS như B2/B4.
    """
    page = admin_page
    page.goto(f"{base}/{SLUG}/rooms/timeline-view")
    page.evaluate(
        "bootstrap.Modal.getOrCreateInstance("
        "document.getElementById('bookingDetailModal')).show()"
    )
    page.wait_for_selector("#bookingDetailModal.show", timeout=8_000)
    page.evaluate("window.__xssFired = false")
    page.evaluate(
        "document.getElementById('bd-customer-label').textContent ="
        " '<img src=x onerror=\"window.opener.__xssFired = true\">'"
    )

    with page.expect_popup() as popup_info:
        page.click('button[onclick="bdPrintInvoice()"]')
    popup = popup_info.value
    popup.wait_for_load_state()
    page.wait_for_timeout(1_000)

    assert page.evaluate("window.__xssFired") is False
    popup.close()
```

- [ ] **Step 7: Chạy test trình duyệt**

```bash
docker compose build web && docker compose up -d web && sleep 5
set -a; source .env; set +a
BROWSER_BASE_URL=http://127.0.0.1:8000 BROWSER_ADMIN_PASSWORD="$ADMIN_PASSWORD" \
  venv/bin/python -m pytest tests/browser -q
```
Expected: PASS (5/5). Nếu B5 đỏ trước khi sửa JS thì đó chính là bằng chứng lỗi — sửa xong phải xanh.

- [ ] **Step 8: Commit**

```bash
git add static/js/main.js static/js/timeline_manager.js tests/test_print_invoice_security.py tests/browser/test_smoke_flows.py
git commit -m "fix: escape guest data in the print-invoice popup

bdPrintInvoice interpolated the guest name straight into a document.write
string in a same-origin popup with no CSP, so a name like <img onerror=...>
ran with the printing user's session — an admin's, when an admin printed.
Rows are now rebuilt from data instead of copying the table's innerHTML.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 9: Escape các sink còn lại

**Files:**
- Modify: `static/js/timeline_manager.js` (~565, ~993, ~1057, ~1432, ~1438)
- Modify: `static/js/checkout.js` (~213, ~387)
- Modify: `static/js/service.js` (~103, ~168)
- Test: `tests/test_print_invoice_security.py`

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_print_invoice_security.py`:

```python
def test_service_and_room_names_are_escaped_before_innerhtml():
    """Tên dịch vụ do admin nhập; tenant admin thù địch không được chạy JS
    trong trình duyệt của mọi lễ tân."""
    for rel, raw in (
        ("static/js/checkout.js", "${item.name}"),
        ("static/js/service.js", "${item.name}"),
        ("static/js/timeline_manager.js", "${line.name || 'Dich vu'}"),
    ):
        assert raw not in _source(rel), f"{rel} còn nội suy thô {raw}"


def test_checkout_uses_the_shared_escape_helper():
    checkout = _source("static/js/checkout.js")
    assert "function checkoutEscapeHtml" not in checkout
    assert "escapeHtml(" in checkout
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_print_invoice_security.py -v`
Expected: FAIL — các chuỗi thô vẫn còn.

- [ ] **Step 3: Escape trong `static/js/timeline_manager.js`**

Catalog dịch vụ (~993):

```javascript
                    <div class="fw-bold">${escapeHtml(s.name || 'Dich vu')}</div>
```

Dòng hóa đơn (~1057):

```javascript
                    <td>${escapeHtml(line.name || 'Dich vu')}</td>
```

Ba chỗ dựng `<option>` số phòng (~565, ~1432, ~1438) — escape cả text lẫn thuộc tính:

```javascript
            sel.innerHTML += `<option value="${r.id}">${escapeHtml(r.number || r.room_number)}</option>`;
```

```javascript
                roomSelect.innerHTML += `<option value="${r.booking_room_id}" data-room-id="${r.room_id}" data-room-number="${escapeHtml(r.room_number)}" title="${escapeHtml(statusLabel)}">${escapeHtml(r.room_number)}</option>`;
```

```javascript
                roomSelect.innerHTML += `<option value="${r.id}" data-room-id="${r.id}" data-room-number="${escapeHtml(roomNumber)}">${escapeHtml(roomNumber)}</option>`;
```

- [ ] **Step 4: Gộp helper trùng trong `static/js/checkout.js`**

Xóa định nghĩa `checkoutEscapeHtml` (~387-391) và thay mọi lời gọi `checkoutEscapeHtml(` thành `escapeHtml(`:

```bash
cd /Users/duongnguyen1010/code/Python/hotel_management_system
sed -i '' 's/checkoutEscapeHtml(/escapeHtml(/g' static/js/checkout.js
```

Rồi xóa thủ công khối định nghĩa hàm cũ (giờ đã thành `function escapeHtml(value) {` trùng tên trong file này).

Escape tên dịch vụ ở `renderServicesInternal` (~213):

```javascript
                  <span class="fw-bold text-dark">${escapeHtml(item.name)}</span>
```

- [ ] **Step 5: Escape trong `static/js/service.js`**

Hai chỗ `${item.name}` (~103 menu POS, ~168 giỏ hàng) đổi thành `${escapeHtml(item.name)}`.

- [ ] **Step 6: Kiểm tra cú pháp và chạy test**

Run:
```bash
node --check static/js/main.js && node --check static/js/timeline_manager.js && \
node --check static/js/checkout.js && node --check static/js/service.js && \
venv/bin/python -m pytest tests/test_print_invoice_security.py tests/test_customer_render_security.py -v
```
Expected: JS OK, test PASS

- [ ] **Step 7: Commit**

```bash
git add static/js/
git commit -m "fix: escape service and room names before innerHTML, unify escape helper

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 10: Bút toán điều chỉnh cọc

**Files:**
- Modify: `services/payment_service.py`
- Modify: `controllers/cashier_controller.py` (~93-118)
- Create: `tests/test_deposit_adjustment.py`

**Interfaces:**
- Produces: `payment_service.record_deposit_adjustment(*, booking_id, amount, note, payment_method='cash', created_at=None, flush=False, business_operation=None, component_key=None, created_by=None) -> Payment`; loại thanh toán mới `deposit_adjustment` (số tiền âm).

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/test_deposit_adjustment.py`:

```python
"""Giảm cọc phải để lại bút toán — chính sách chốt 19-08.

Sổ tiền là append-only: sửa số thì thêm dòng, không đè dòng cũ.
"""

from decimal import Decimal

import pytest

from extensions import db
from models import Payment
from services import payment_service


def test_record_deposit_adjustment_writes_a_negative_ledger_row(app, seed_hotels):
    _, _, _, _, br, _ = seed_hotels

    payment = payment_service.record_deposit_adjustment(
        booking_id=br.booking_id,
        amount=Decimal("-4500000"),
        note="Điều chỉnh cọc: gõ nhầm số 0",
    )
    db.session.commit()

    assert payment.payment_type == "deposit_adjustment"
    assert payment.amount == Decimal("-4500000.00")
    assert "gõ nhầm" in payment.note


def test_record_deposit_adjustment_rejects_a_positive_amount(app, seed_hotels):
    """Tăng cọc là nhận thêm tiền — phải đi qua record_deposit."""
    _, _, _, _, br, _ = seed_hotels

    with pytest.raises(ValueError):
        payment_service.record_deposit_adjustment(
            booking_id=br.booking_id,
            amount=Decimal("100000"),
            note="sai hướng",
        )


def test_adjustment_lowers_the_refund_cap(app, seed_hotels):
    """Trần hoàn tiền = tổng đã thu, nên phải tụt theo dòng âm."""
    from services import refund_service

    _, _, _, _, br, _ = seed_hotels
    payment_service.record_deposit(
        booking_id=br.booking_id, amount=Decimal("5000000"), note="Nhận cọc"
    )
    db.session.commit()
    cap_before = refund_service.refundable_cap(br.booking)

    payment_service.record_deposit_adjustment(
        booking_id=br.booking_id,
        amount=Decimal("-4500000"),
        note="Điều chỉnh cọc: gõ nhầm số 0",
    )
    db.session.commit()

    assert cap_before == Decimal("5000000.00")
    assert refund_service.refundable_cap(br.booking) == Decimal("500000.00")


def test_customer_bill_sees_the_net_deposit_not_the_correction_pair(app, seed_hotels):
    """Nội bộ thấy đủ hai dòng, hóa đơn khách chỉ thấy số ròng.

    Bảng "hoàn tiền" trên hóa đơn khách chỉ lọc payment_type == 'refund'
    (billing_controller), nên dòng điều chỉnh không lọt ra ngoài; còn tổng tiền
    đã thu là phép cộng nên tự trừ đi phần điều chỉnh.
    """
    _, _, _, _, br, _ = seed_hotels
    payment_service.record_deposit(
        booking_id=br.booking_id, amount=Decimal("5000000"), note="Nhận cọc"
    )
    payment_service.record_deposit_adjustment(
        booking_id=br.booking_id,
        amount=Decimal("-4500000"),
        note="Điều chỉnh cọc: gõ nhầm số 0",
    )
    db.session.commit()

    payments = br.booking.payments
    assert len(payments) == 2                                        # sổ nội bộ: đủ 2 dòng
    assert sum(p.amount for p in payments) == Decimal("500000.00")   # khách: số ròng
    assert not [p for p in payments if p.payment_type == "refund"]   # không phải hoàn tiền


def test_cashier_report_labels_the_adjustment(client, seed_hotels, login_as):
    hotel, _, admin, _, br, _ = seed_hotels
    payment_service.record_deposit_adjustment(
        booking_id=br.booking_id,
        amount=Decimal("-4500000"),
        note="Điều chỉnh cọc: gõ nhầm số 0",
    )
    db.session.commit()
    login_as(client, admin)   # sổ quỹ là @admin_required

    response = client.get(f"/{hotel.slug}/cashier/api/reports/cashier?period=week")

    assert response.status_code == 200
    labels = [row["type_label"] for row in response.get_json()["data"]["records"]]
    assert "Điều chỉnh cọc" in labels
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_deposit_adjustment.py -v`
Expected: FAIL — `module 'services.payment_service' has no attribute 'record_deposit_adjustment'`

- [ ] **Step 3: Thêm `record_deposit_adjustment` vào `services/payment_service.py`**

Đặt ngay sau `record_deposit`:

```python
def record_deposit_adjustment(
    *,
    booking_id: int,
    amount,
    note: str,
    payment_method: str = "cash",
    created_at: Optional[datetime] = None,
    flush: bool = False,
    business_operation: Optional[BusinessOperation] = None,
    component_key: Optional[str] = None,
    created_by: Optional[int] = None,
) -> Payment:
    """Ghi một dòng ÂM khi tiền cọc bị điều chỉnh giảm.

    Sổ tiền là append-only: sửa số cọc thì thêm dòng đối ứng, không sửa dòng cũ.
    Đây KHÔNG phải hoàn tiền cho khách (dùng refund_service) mà là điều chỉnh
    số đã ghi nhận — ví dụ lễ tân gõ dư một số 0.
    """
    normalized = _to_decimal_amount(amount)
    if normalized >= 0:
        raise ValueError("record_deposit_adjustment chỉ nhận số âm; tăng cọc dùng record_deposit.")

    return _create_payment(
        booking_id=booking_id,
        amount=normalized,
        payment_method=payment_method,
        payment_type="deposit_adjustment",
        note=note,
        created_at=created_at,
        flush=flush,
        business_operation=business_operation,
        component_key=component_key,
        created_by=created_by,
    )
```

> `_to_decimal_amount` là helper sẵn có ở `services/payment_service.py:13`. `Optional`, `datetime`, `Payment`, `BusinessOperation` đã được import ở đầu file cho các hàm `record_*` khác.

- [ ] **Step 4: Thêm nhãn trong `controllers/cashier_controller.py`**

Thêm một nhánh vào chuỗi `if/elif` gán `type_label`, đặt ngay sau nhánh `deposit`:

```python
            elif p.payment_type == 'deposit_adjustment':
                type_label = 'Điều chỉnh cọc'
```

- [ ] **Step 5: Chạy test để xác nhận xanh**

Run: `venv/bin/python -m pytest tests/test_deposit_adjustment.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add services/payment_service.py controllers/cashier_controller.py tests/test_deposit_adjustment.py
git commit -m "feat: add deposit_adjustment ledger entry for downward deposit corrections

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 11: Bắt lý do khi giảm cọc và giữ số cọc gốc

**Files:**
- Modify: `controllers/timeline_controller.py` (~1278-1294)
- Modify: `templates/rooms/timeline.html` (ô cọc trong `editBookingModal`)
- Modify: `static/js/timeline_manager.js` (`saveBookingChanges`)
- Test: `tests/test_deposit_adjustment.py`

**Interfaces:**
- Consumes: `payment_service.record_deposit_adjustment` (Task 10).
- Produces: `/api/bookings/update` nhận thêm trường `deposit_reason`; lỗi thiếu lý do trả `error_code: 'deposit_reason_required'`.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_deposit_adjustment.py`:

```python
def _update_payload(br, deposit, reason=None):
    payload = {
        "booking_id": br.booking_id,
        "booking_room_id": br.id,
        "room_id": br.room_id,
        "status": br.status,
        "check_in": "2026-08-19T14:00",
        "check_out": "2026-08-20T12:00",
        "deposit": deposit,
    }
    if reason is not None:
        payload["deposit_reason"] = reason
    return payload


def test_lowering_a_deposit_without_a_reason_is_rejected(client, seed_hotels, login_as):
    hotel, _, admin, _, br, _ = seed_hotels
    br.room_deposit_amount = 5000000
    br.room_deposit_original = 5000000
    db.session.commit()
    login_as(client, admin)
    before = Payment.query.count()

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json=_update_payload(br, 500000),
    )

    body = response.get_json()
    assert body["success"] is False
    assert body["error_code"] == "deposit_reason_required"
    db.session.refresh(br)
    assert float(br.room_deposit_amount) == 5000000.0   # không đổi gì
    assert Payment.query.count() == before


def test_lowering_a_deposit_with_a_reason_leaves_a_trace(client, seed_hotels, login_as):
    hotel, _, admin, _, br, _ = seed_hotels
    br.room_deposit_amount = 5000000
    br.room_deposit_original = 5000000
    db.session.commit()
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json=_update_payload(br, 500000, reason="gõ nhầm số 0"),
    )

    assert response.get_json()["success"] is True, response.get_json()
    db.session.refresh(br)
    assert float(br.room_deposit_amount) == 500000.0
    # Số cọc GỐC phải còn nguyên — đây là bản ghi duy nhất về số ban đầu
    assert float(br.room_deposit_original) == 5000000.0
    adjustment = Payment.query.filter_by(payment_type="deposit_adjustment").one()
    assert float(adjustment.amount) == -4500000.0
    assert "gõ nhầm số 0" in adjustment.note


def test_raising_a_deposit_needs_no_reason(client, seed_hotels, login_as):
    hotel, _, admin, _, br, _ = seed_hotels
    br.room_deposit_amount = 500000
    br.room_deposit_original = 500000
    db.session.commit()
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json=_update_payload(br, 800000),
    )

    assert response.get_json()["success"] is True
    assert Payment.query.filter_by(payment_type="deposit").count() == 1
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_deposit_adjustment.py -k deposit -v`
Expected: FAIL — hiện tại giảm cọc vẫn thành công, không có `error_code`, `room_deposit_original` bị ghi đè.

- [ ] **Step 3: Sửa khối cọc trong `update_booking`**

Trong `controllers/timeline_controller.py`, thay khối `if new_deposit is not None:` bằng:

```python
        if new_deposit is not None:
            room_deposit = max(0.0, float(new_deposit))
            old_deposit = float(br.room_deposit_amount or 0)

            if room_deposit > old_deposit:
                # Nhận thêm tiền: ghi nhận vào sổ quỹ như một khoản cọc mới.
                payment_service.record_deposit(
                    booking_id=br.booking_id,
                    amount=room_deposit - old_deposit,
                    payment_method='cash',
                    note=f"Nộp thêm cọc cho phòng {br.room.room_number if br.room else br.room_id} (Cập nhật đơn)",
                    created_by=current_user.id,
                )
            elif room_deposit < old_deposit:
                # Giảm cọc là sửa số đã ghi nhận -> bắt buộc có lý do và để lại
                # bút toán đối ứng. Sổ tiền append-only: không sửa dòng cũ.
                deposit_reason = (data.get('deposit_reason') or '').strip()
                if not deposit_reason:
                    return jsonify({
                        'success': False,
                        'error_code': 'deposit_reason_required',
                        'msg': 'Giảm tiền cọc phải có lý do để đối soát.',
                    }), 400

                payment_service.record_deposit_adjustment(
                    booking_id=br.booking_id,
                    amount=room_deposit - old_deposit,
                    note=f"Điều chỉnh cọc phòng {br.room.room_number if br.room else br.room_id}: {deposit_reason}",
                    created_by=current_user.id,
                )
                audit_service.record_event(
                    hotel_id=br.hotel_id,
                    actor_user_id=current_user.id,
                    action='deposit_adjustment',
                    entity_type='booking_room',
                    entity_id=br.id,
                    before_data={'room_deposit_amount': old_deposit},
                    after_data={'room_deposit_amount': room_deposit, 'reason': deposit_reason},
                )

            br.room_deposit_amount = room_deposit
            # Chỉ nâng mốc gốc khi thu THÊM tiền; giảm cọc không được xóa dấu vết
            # số tiền ban đầu đã nhận.
            if br.status not in ['cancelled', 'checked_out'] and room_deposit > float(br.room_deposit_original or 0):
                br.room_deposit_original = room_deposit
```

> Chữ ký thật của hàm là `record_event(*, hotel_id, actor_user_id, action, entity_type, entity_id, operation_key=None, before_data=None, after_data=None)` — khối trên đã dùng đúng.

- [ ] **Step 4: Chạy test để xác nhận xanh**

Run: `venv/bin/python -m pytest tests/test_deposit_adjustment.py -v`
Expected: PASS

- [ ] **Step 5: Thêm ô lý do vào modal sửa booking**

Trong `templates/rooms/timeline.html`, thay khối cột tiền cọc trong `editBookingModal`:

```html
                    <div class="col-md-6">
                        <label class="pos-label" for="edit-deposit">Tiền đặt cọc (VNĐ)</label>
                        <input type="number" class="form-control fw-bold" id="edit-deposit" placeholder="0" oninput="toggleDepositReason()">
                        <small class="text-muted d-block mt-1">Khoản cọc được trừ trực tiếp khi thanh toán.</small>
                        <div id="deposit-adjust-block" class="mt-2" style="display: none;">
                            <label class="pos-label" for="deposit-adjust-reason">Lý do giảm cọc <span class="text-danger" aria-hidden="true">*</span></label>
                            <input type="text" class="form-control form-control-sm" id="deposit-adjust-reason" autocomplete="off" placeholder="Ví dụ: gõ nhầm số 0">
                            <small class="text-muted d-block mt-1">Sổ quỹ sẽ ghi một dòng điều chỉnh kèm lý do này.</small>
                        </div>
                    </div>
```

Thêm `<input type="hidden" id="edit-deposit-original">` ngay cạnh `<input type="hidden" id="edit-booking-room-id">` để JS biết số cọc lúc mở modal.

- [ ] **Step 6: Nối JS**

Trong `static/js/timeline_manager.js`, thêm hàm:

```javascript
// Ô lý do chỉ hiện khi số cọc bị GIẢM so với lúc mở modal.
function toggleDepositReason() {
    const block = document.getElementById('deposit-adjust-block');
    if (!block) return;
    const current = Number(document.getElementById('edit-deposit')?.value || 0);
    const original = Number(document.getElementById('edit-deposit-original')?.value || 0);
    block.style.display = current < original ? 'block' : 'none';
}
```

Trong `openEditModal`, ngay sau dòng gán `edit-deposit`, thêm:

```javascript
        const depositOriginal = document.getElementById('edit-deposit-original');
        if (depositOriginal) depositOriginal.value = data.deposit || 0;
        toggleDepositReason();
```

Trong `saveBookingChanges`, thêm trường vào `data` và chặn sớm ở client:

```javascript
        const depositNow = Number(document.getElementById('edit-deposit').value || 0);
        const depositWas = Number(document.getElementById('edit-deposit-original')?.value || 0);
        const depositReason = document.getElementById('deposit-adjust-reason')?.value.trim() || '';
        if (depositNow < depositWas && !depositReason) {
            alert('Giảm tiền cọc phải có lý do để đối soát.');
            document.getElementById('deposit-adjust-reason')?.focus();
            return;
        }
```

và thêm vào object `data`:

```javascript
            deposit_reason: depositReason,
```

- [ ] **Step 7: Chạy test markup và toàn bộ suite**

Run: `venv/bin/python -m pytest tests/test_accessibility_markup.py tests/test_deposit_adjustment.py -q && node --check static/js/timeline_manager.js && venv/bin/python -m pytest -m "not mysql" -q`
Expected: PASS

> Nếu `test_accessibility_markup` đòi `<label for>` cho mọi control mới, ô `deposit-adjust-reason` ở Step 5 đã có sẵn nhãn liên kết.

- [ ] **Step 8: Commit**

```bash
git add controllers/timeline_controller.py templates/rooms/timeline.html static/js/timeline_manager.js tests/test_deposit_adjustment.py
git commit -m "feat: require a reason and leave a ledger trace when a deposit is lowered

Lowering a deposit silently changed the number, wrote nothing to the cash book
and overwrote room_deposit_original — erasing the only record of what was
actually collected. Raising a deposit is unchanged.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 12: Service dùng chung cho "phòng có bận không"

**Files:**
- Create: `services/room_availability_service.py`
- Create: `tests/test_room_availability_service.py`

**Interfaces:**
- Produces: `room_availability_service.has_room_conflict(*, room_id, start_dt, end_dt, exclude_booking_room_id=None, now=None) -> bool`; `room_availability_service.occupied_room_ids(*, start_dt, end_dt, now=None) -> set[int]`. Cả hai nhận/so **giờ nghiệp vụ naive** và phải chạy trong app context có tenant.

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/test_room_availability_service.py`:

```python
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
```

> Cơ chế tenant: `services/tenant_service.py` đọc `g.hotel_id` (abort 404 nếu thiếu), nên `test_request_context()` + gán `g.hotel_id` là đủ — không cần đăng nhập. Đường dẫn trong `test_request_context` không quan trọng.

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_room_availability_service.py -v`
Expected: FAIL — `No module named 'services.room_availability_service'`

- [ ] **Step 3: Tạo `services/room_availability_service.py`**

```python
"""Nguồn chân lý duy nhất cho câu hỏi 'phòng này có bận không'.

Trước 19-08 mỗi đường đặt phòng tự kiểm tra một kiểu: đường đặt lẻ xét cả giờ
thực tế lẫn khách ở quá hẹn, còn đường đặt đoàn và tìm phòng trống chỉ so giờ
dự kiến nên vẫn mời phòng đang có người.

HỢP ĐỒNG: mọi tham số datetime là GIỜ NGHIỆP VỤ naive (cùng hệ với *_expected).
"""

from models import BookingRoom
from services import time_service
from services.tenant_service import tenant_query

ACTIVE_STATUSES = ('booked', 'checked_in')


def _naive(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


def _row_window(row, now):
    """Khoảng thời gian phòng bị chiếm bởi một dòng BookingRoom.

    Trả về (start, end, busy_without_end): busy_without_end nghĩa là khách đang
    ở mà không có mốc kết thúc -> coi như chiếm phòng vô thời hạn.
    """
    # *_actual lưu UTC còn *_expected đã là giờ nghiệp vụ. Phải quy đổi TRƯỚC
    # khi trộn, nếu không cửa sổ bận của khách đang ở sẽ bắt đầu sớm 7 tiếng và
    # chặn oan những booking hợp lệ.
    start = (
        time_service.to_business_naive(row.check_in_actual)
        if row.check_in_actual
        else _naive(row.check_in_expected)
    )
    end = (
        time_service.to_business_naive(row.check_out_actual)
        if row.check_out_actual
        else _naive(row.check_out_expected)
    )

    if row.status == 'checked_in' and not end:
        return start, end, True

    if row.status == 'checked_in' and end and end < now:
        # Khách ở quá hẹn vẫn đang chiếm phòng cho tới bây giờ.
        end = now

    return start, end, False


def _conflicting_rows(rows, start_dt, end_dt, now):
    for row in rows:
        row_start, row_end, busy_without_end = _row_window(row, now)
        if busy_without_end:
            yield row
            continue
        if not row_start or not row_end:
            continue
        # [a,b) giao [c,d) khi a < d và b > c
        if row_start < end_dt and row_end > start_dt:
            yield row


def has_room_conflict(
    *,
    room_id,
    start_dt,
    end_dt,
    exclude_booking_room_id=None,
    now=None,
) -> bool:
    start_dt = _naive(start_dt)
    end_dt = _naive(end_dt)
    if not start_dt or not end_dt:
        return False

    now = now or time_service.business_now_naive()
    query = tenant_query(BookingRoom).filter(
        BookingRoom.room_id == room_id,
        BookingRoom.status.in_(ACTIVE_STATUSES),
    )
    if exclude_booking_room_id is not None:
        query = query.filter(BookingRoom.id != int(exclude_booking_room_id))

    return any(_conflicting_rows(query.all(), start_dt, end_dt, now))


def occupied_room_ids(*, start_dt, end_dt, now=None) -> set:
    start_dt = _naive(start_dt)
    end_dt = _naive(end_dt)
    if not start_dt or not end_dt:
        return set()

    now = now or time_service.business_now_naive()
    rows = tenant_query(BookingRoom).filter(
        BookingRoom.status.in_(ACTIVE_STATUSES),
    ).all()

    return {row.room_id for row in _conflicting_rows(rows, start_dt, end_dt, now)}
```

- [ ] **Step 4: Chạy test để xác nhận xanh**

Run: `venv/bin/python -m pytest tests/test_room_availability_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/room_availability_service.py tests/test_room_availability_service.py
git commit -m "feat: single source of truth for room availability

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 13: Chuyển ba đường đặt phòng sang service chung

**Files:**
- Modify: `controllers/timeline_controller.py` (`_has_room_time_conflict`, `_has_active_booking_conflict`)
- Modify: `controllers/booking_controller.py` (~903-908)
- Modify: `controllers/room_controller.py` (~530-543)
- Test: `tests/test_room_availability_service.py`

**Interfaces:**
- Consumes: `room_availability_service.has_room_conflict`, `room_availability_service.occupied_room_ids` (Task 12).

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_room_availability_service.py`:

```python
def test_search_does_not_offer_a_room_with_an_overstaying_guest(
    client, seed_hotels, login_as, frozen_noon
):
    hotel, _, admin, _, br, _ = seed_hotels
    br.status = "checked_in"
    br.check_in_expected = datetime(2026, 8, 18, 14, 0)
    br.check_out_expected = datetime(2026, 8, 19, 12, 0)   # quá hẹn
    db.session.commit()
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/rooms/api/rooms/search",
        json={"check_in": "2026-08-19T14:00:00", "check_out": "2026-08-20T12:00:00"},
    )

    grouped = response.get_json()["data"]
    offered = [r["number"] for rooms in grouped.values() for r in rooms]
    assert br.room.room_number not in offered


def test_group_booking_refuses_a_room_with_an_overstaying_guest(
    client, seed_hotels, login_as, frozen_noon
):
    hotel, _, admin, _, br, _ = seed_hotels
    br.status = "checked_in"
    br.check_in_expected = datetime(2026, 8, 18, 14, 0)
    br.check_out_expected = datetime(2026, 8, 19, 12, 0)
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
```

> Payload đúng theo `create_group_booking`: `customer` là dict (`phone`, `name`, `cccd`, `address`), ngày lấy 10 ký tự đầu rồi tự gán 14:00/12:00, và tiền cọc được kiểm tra **trước** vòng lặp xét từng phòng. Khi mọi phòng đều bận, endpoint trả `{'success': False, 'msg': 'Không đặt được phòng nào (trùng lịch hết)!'}`.

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_room_availability_service.py -k "overstaying" -v`
Expected: FAIL — cả hai đường đều nhận phòng đang có khách.

- [ ] **Step 3: Rút ruột hai helper trong `controllers/timeline_controller.py`**

Giữ nguyên tên hàm (nhiều nơi đang gọi), chỉ ủy quyền vào service:

```python
def _has_room_time_conflict(
    *,
    room_id: int,
    start_dt: datetime,
    end_dt: datetime,
    exclude_booking_room_id: int | None = None,
) -> bool:
    """Return True if another active booking overlaps [start_dt, end_dt) in the same room."""
    return room_availability_service.has_room_conflict(
        room_id=room_id,
        start_dt=_normalize_dt(start_dt),
        end_dt=_normalize_dt(end_dt),
        exclude_booking_room_id=exclude_booking_room_id,
    )


def _has_active_booking_conflict(room_id, check_in_dt, check_out_dt):
    """Trả về True nếu phòng có booking active bị giao thời gian."""
    return room_availability_service.has_room_conflict(
        room_id=room_id,
        start_dt=_normalize_dt(check_in_dt),
        end_dt=_normalize_dt(check_out_dt),
    )
```

Thêm `room_availability_service` vào khối `from services import (...)`.

- [ ] **Step 4: Sửa đường đặt đoàn trong `controllers/booking_controller.py`**

Thay khối `is_taken = tenant_query(BookingRoom).filter(...)`:

```python
            is_taken = room_availability_service.has_room_conflict(
                room_id=r_id,
                start_dt=check_in,
                end_dt=check_out,
            )

            if is_taken:
                errors.append(f"Phòng {current_room.room_number} đã có lịch.")
                continue
```

Thêm import `room_availability_service`.

- [ ] **Step 5: Sửa đường tìm phòng trống trong `controllers/room_controller.py`**

Thay khối `occupied_room_ids = db.session.query(...)`:

```python
        # --- 1. LỌC PHÒNG BẬN (dùng chung ngữ nghĩa với đường đặt phòng) ---
        busy_room_ids = room_availability_service.occupied_room_ids(
            start_dt=check_in,
            end_dt=check_out,
        )

        # --- 2. LẤY PHÒNG TRỐNG ---
        available_rooms = tenant_query(Room).filter(
            Room.status != 'maintenance'
        ).all()
        available_rooms = [r for r in available_rooms if r.id not in busy_room_ids]
```

Thêm import `room_availability_service`.

- [ ] **Step 6: Chạy test để xác nhận xanh**

Run: `venv/bin/python -m pytest tests/test_room_availability_service.py tests/test_room_search_api.py -v`
Expected: PASS

- [ ] **Step 7: Chạy toàn bộ suite**

Run: `venv/bin/python -m pytest -m "not mysql" -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add controllers/ tests/test_room_availability_service.py
git commit -m "fix: group booking and room search honour actual stay times

Both paths compared only expected times, so a room whose guest had overstayed
was offered as free and could be booked over. All three booking paths now go
through room_availability_service.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 14: Vá lỗ kiểm tra trùng lịch ở `update_booking`

**Files:**
- Modify: `controllers/timeline_controller.py` (~1311-1332)
- Test: `tests/test_room_availability_service.py`

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_room_availability_service.py`:

```python
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
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_room_availability_service.py -k without_status -v`
Expected: FAIL — request thành công, `status` thành `None`.

- [ ] **Step 3: Sửa cổng trạng thái trong `update_booking`**

Thay khối kiểm tra trùng và khối gán trạng thái:

```python
        # Thiếu status không có nghĩa là "bỏ qua kiểm tra" — giữ nguyên trạng
        # thái hiện tại và vẫn phải soi trùng lịch.
        effective_status = new_status or br.status

        # Validate overlap BEFORE applying room/time changes.
        if effective_status in ['booked', 'checked_in']:
            candidate_start = parsed_check_in if parsed_check_in else (br.check_in_actual or br.check_in_expected)
            candidate_end = parsed_check_out if parsed_check_out else (br.check_out_actual or br.check_out_expected)
            candidate_start = _normalize_dt(candidate_start)
            candidate_end = _normalize_dt(candidate_end)

            if candidate_start and candidate_end and candidate_end <= candidate_start:
                return jsonify({'success': False, 'msg': 'Giờ check-out phải sau giờ check-in.'})

            if candidate_start and candidate_end:
                if _has_room_time_conflict(
                    room_id=new_room_id,
                    start_dt=candidate_start,
                    end_dt=candidate_end,
                    exclude_booking_room_id=br.id,
                ):
                    return jsonify({'success': False, 'msg': 'Trùng lịch: Phòng đã có booking trong khoảng thời gian này.'})

        # Cập nhật thông tin mới
        br.room_id = new_room_id
        br.status = effective_status
```

- [ ] **Step 4: Chạy test để xác nhận xanh**

Run: `venv/bin/python -m pytest tests/test_room_availability_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add controllers/timeline_controller.py tests/test_room_availability_service.py
git commit -m "fix: update_booking validates overlap even when status is omitted

A direct API call without a status field skipped the conflict check, still
applied the new room and times, and wrote status = None.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 15: Pin html5-qrcode

**Files:**
- Modify: `templates/rooms/map.html` (~200), `templates/rooms/timeline.html` (~452)
- Test: `tests/test_ui_regression.py`

**Interfaces:**
- Consumes: không. Đây là ngoại lệ có chủ ý của spec mục 6 — vendor toàn bộ CDN để đợt sau, nhưng pin thì làm ngay vì đúng lớp lỗi vis-timeline đã gãy một lần.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_ui_regression.py`:

```python
def test_external_scripts_are_version_pinned():
    """unpkg không kèm version sẽ trả bản MỚI NHẤT ở mỗi lần cache miss —
    đúng cách vis-timeline từng trôi version và làm gãy Timeline."""
    from pathlib import Path

    for rel in ("templates/rooms/map.html", "templates/rooms/timeline.html"):
        source = Path(rel).read_text(encoding="utf-8")
        assert "unpkg.com/html5-qrcode\"" not in source, f"{rel}: html5-qrcode chưa pin version"
        assert "unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js" in source
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_ui_regression.py -k pinned -v`
Expected: FAIL

- [ ] **Step 3: Pin version ở cả hai template**

Thay ở `templates/rooms/map.html` và `templates/rooms/timeline.html`:

```html
<script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
```

- [ ] **Step 4: Chạy test để xác nhận xanh**

Run: `venv/bin/python -m pytest tests/test_ui_regression.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add templates/rooms/map.html templates/rooms/timeline.html tests/test_ui_regression.py
git commit -m "fix: pin html5-qrcode to 2.3.8

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Nghiệm thu

- [ ] **Bước 1: Suite đầy đủ, hai lần, hai múi giờ**

```bash
venv/bin/python -m pytest -m "not mysql" -q
TZ=UTC venv/bin/python -m pytest -m "not mysql" -q
TZ=Asia/Ho_Chi_Minh venv/bin/python -m pytest -m "not mysql" -q
```
Expected: cả ba lần đều xanh với **cùng số test**. Đây là bằng chứng kết quả không còn phụ thuộc đồng hồ máy — trước đợt này chạy `TZ=UTC` sẽ đỏ.

- [ ] **Bước 2: Bộ MySQL**

```bash
set -a; source .env; set +a
TEST_MYSQL_DATABASE_URL="mysql+pymysql://root:${MYSQL_ROOT_PASSWORD}@127.0.0.1:3306/hotel_test" \
  venv/bin/python -m pytest -m mysql -q
```
Expected: PASS

- [ ] **Bước 3: Dựng lại stack và chạy bộ trình duyệt**

```bash
docker compose build web && docker compose up -d web && sleep 5
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/healthz
set -a; source .env; set +a
BROWSER_BASE_URL=http://127.0.0.1:8000 BROWSER_ADMIN_PASSWORD="$ADMIN_PASSWORD" \
  venv/bin/python -m pytest tests/browser -q
```
Expected: `200`, và 5/5 test trình duyệt xanh.

- [ ] **Bước 4: Kiểm chứng tay trong container (đúng môi trường production)**

1. Tạo một booking với giờ nhận = giờ hiện tại → bấm **Nhận phòng** → phải vào được ngay (trước đây báo "chỉ được check-in sớm tối đa 3 giờ").
2. Bấm **Thanh toán** phòng đó → hóa đơn **không** có dòng "Phụ thu phát sinh · Sớm 7.0h".
3. Sửa cọc từ 5.000.000 xuống 500.000 → modal bắt nhập lý do; lưu xong xem Sổ Quỹ thấy dòng **Điều chỉnh cọc** kèm lý do, còn hóa đơn khách chỉ hiện số ròng.
4. Để một khách quá giờ hẹn 1 phút → badge **Quá giờ** hiện ngay, và thử đặt phòng đó cho khung giờ chồng lấn → bị từ chối.

- [ ] **Bước 5: Đóng dấu spec, push và theo dõi CI**

```bash
git push origin dev
gh run list --branch dev --limit 1
```
Expected: cả 3 job CI xanh. Sau đó thêm dòng "ĐÃ TRIỂN KHAI" vào đầu spec và commit.
