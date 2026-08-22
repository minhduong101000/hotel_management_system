# Cảnh báo vận hành qua Telegram — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Một container canh chừng gửi Telegram khi `web` chết, khi bản sao lưu hỏng hoặc quá hạn, khi đĩa gần đầy — kèm một tin tóm tắt mỗi sáng để chứng minh chính nó còn sống.

**Architecture:** Toàn bộ phần **quyết định** nằm trong `services/alert_service.py` dưới dạng hàm thuần: nhận `now` và các quan sát làm tham số, không gọi mạng, không đọc đĩa, không xem đồng hồ. `services/telegram_service.py` chỉ lo gửi, nhận transport tiêm vào nên test không chạm Internet. `scripts/alert_watch.py` là lớp I/O mỏng ghép chúng lại. Nhờ vậy mọi thứ dễ sai đều kiểm được bằng pytest thường.

**Tech Stack:** Python 3.12, `urllib.request` (thư viện chuẩn — repo **không** có `requests`), pytest, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-08-22-telegram-alerts-design.md`

## Global Constraints

- **Không thêm thư viện nào vào `requirements.txt`.** `requests`/`httpx` đều không có sẵn; dùng `urllib.request`, đúng như healthcheck trong `docker-compose.yml` đang làm.
- Ngưỡng: `web` hỏng **2 chu kỳ liên tiếp**; backup quá **26 giờ** dùng `>` (đúng 26 giờ **chưa** kêu); đĩa **≥ 85%** dùng `>=` (đúng 85% **đã** kêu). Hai phép so sánh cố ý khác nhau.
- Nhắc lại khi vẫn hỏng: mỗi **6 giờ**. Đang hỏng mà chưa tới hạn thì **im lặng**.
- Tin tóm tắt lúc **7 giờ sáng giờ Việt Nam**, mỗi ngày một lần, có gửi bù nếu container tắt lúc 7h.
- **`notified_status`, `last_notified_at`, `last_summary_date` CHỈ cập nhật sau khi gửi thành công.** `status` thì luôn cập nhật. Đây là bất biến quan trọng nhất của plan này.
- `TELEGRAM_BOT_TOKEN` hoặc `TELEGRAM_CHAT_ID` rỗng = **tắt hẳn**, không gọi mạng.
- **Không bao giờ để token lọt vào log hay thông báo lỗi.** URL Telegram *chứa* token, và `str(urllib.error.HTTPError)` *có* URL — nên không được dùng `str(exc)`.
- Không dùng `datetime.now()` / `date.today()` / `datetime.utcnow()` trong `controllers/`, `services/`, `models/` — có lưới `tests/test_no_ambient_now.py`. Thời gian lấy từ `services/time_service.py`.
- Không dùng `db.func.now()` trong `models/` — cùng lưới đó chặn.
- Test chạy bằng `venv/bin/python -m pytest` (KHÔNG dùng `python` hệ thống).
- Suite phải xanh với **cùng số test** dưới cả `TZ=UTC` lẫn `TZ=Asia/Ho_Chi_Minh`.
- Commit tiếng Anh, dòng cuối: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

## File Structure

**Tạo**

| File | Trách nhiệm |
| --- | --- |
| `services/alert_service.py` | Thuần. Chấm điểm 3 phép kiểm, máy trạng thái, quyết định gửi gì, soạn câu chữ. |
| `services/telegram_service.py` | Gửi một tin. Transport tiêm được. Cấu hình rỗng = không làm gì. |
| `scripts/__init__.py` | Rỗng — để `python -m scripts.alert_watch` chạy được. |
| `scripts/alert_watch.py` | Vòng lặp + I/O thật. `--once`, `--test-message`. |
| `tests/test_alert_service.py` | Phủ toàn bộ phần quyết định. |
| `tests/test_telegram_service.py` | Phủ phần gửi, không chạm mạng. |
| `tests/test_alert_infrastructure.py` | Khoá khai báo compose + `.env.example`. |
| `docs/runbooks/telegram-alerts.md` | Hướng dẫn lấy token, chat_id, kiểm tay. |

**Sửa**

| File | Thay đổi |
| --- | --- |
| `services/time_service.py` | Thêm `utc_naive_from_timestamp` |
| `tests/test_time_service.py` | Test cho hàm mới |
| `docker-compose.yml` | Thêm service `alerts`, thêm volume `alert_state` |
| `.env.example` | Thêm khối biến `TELEGRAM_*` / `ALERT_*` |

**Bẫy đã biết — đọc trước khi làm:**

1. **`scripts/` chưa tồn tại.** Phải tạo cả `scripts/__init__.py`, nếu không `python -m scripts.alert_watch` báo `No module named scripts`.
2. **`str(urllib.error.HTTPError)` chứa URL đầy đủ**, mà URL Telegram chứa token. Dùng `type(exc).__name__` và mã HTTP, tuyệt đối không `str(exc)` hay `exc.url`.
3. **`time_service._business_tz()` đọc config Flask nếu đang trong app context**, không thì rơi về `Asia/Bangkok`. `scripts/alert_watch.py` chạy **ngoài** app context nên luôn là `Asia/Bangkok` (UTC+7, cùng offset với `Asia/Ho_Chi_Minh`). Đừng cố tạo app context — không cần.
4. **`time_service.utc_now()` là điểm monkeypatch duy nhất** (docstring của nó nói vậy). Test nào cần cố định thời gian thì patch nó, đừng patch `business_now`.
5. Top-level `volumes:` trong `docker-compose.yml` ở **dòng 118**, đã có `dbdata`, `caddy_data`, `caddy_config`.

---

## Task 1: Đổi mtime của tệp sang UTC-naive

**Files:**
- Modify: `services/time_service.py`
- Test: `tests/test_time_service.py`

**Interfaces:**
- Produces: `time_service.utc_naive_from_timestamp(timestamp: float) -> datetime`

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_time_service.py`:

```python
def test_utc_naive_from_timestamp_converts_a_posix_stamp():
    from datetime import datetime, timezone

    from services import time_service

    # 2026-08-22 01:30:00 UTC
    stamp = datetime(2026, 8, 22, 1, 30, tzinfo=timezone.utc).timestamp()

    assert time_service.utc_naive_from_timestamp(stamp) == datetime(2026, 8, 22, 1, 30)


def test_utc_naive_from_timestamp_ignores_the_machine_timezone(monkeypatch):
    """Đây là lý do hàm này tồn tại.

    `datetime.fromtimestamp(ts)` trần diễn giải theo giờ MÁY, nên cùng một tệp
    sẽ ra hai kết quả khác nhau giữa máy lập trình (giờ VN) và container
    (UTC) — lệch đúng 7 tiếng, đủ để một bản sao lưu 25 giờ tuổi bị chấm là
    32 giờ và kêu oan mỗi ngày.
    """
    import time as time_module
    from datetime import datetime, timezone

    from services import time_service

    stamp = datetime(2026, 8, 22, 1, 30, tzinfo=timezone.utc).timestamp()
    expected = datetime(2026, 8, 22, 1, 30)

    for zone in ("UTC", "Asia/Ho_Chi_Minh", "America/New_York"):
        monkeypatch.setenv("TZ", zone)
        time_module.tzset()
        assert time_service.utc_naive_from_timestamp(stamp) == expected

    monkeypatch.delenv("TZ", raising=False)
    time_module.tzset()
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_time_service.py -k utc_naive_from_timestamp -v`
Expected: FAIL — `AttributeError: module 'services.time_service' has no attribute 'utc_naive_from_timestamp'`

- [ ] **Step 3: Thêm hàm vào `services/time_service.py`**

Đặt ngay sau `utc_now_naive` (khoảng dòng 37):

```python
def utc_naive_from_timestamp(timestamp: float) -> datetime:
    """Đổi dấu thời gian POSIX (ví dụ `os.stat().st_mtime`) sang UTC-naive.

    Đi qua `timezone.utc` chứ không qua giờ máy, nên kết quả đúng bất kể
    container đặt TZ gì — điều mà `datetime.fromtimestamp()` trần KHÔNG đảm bảo.
    """
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)
```

- [ ] **Step 4: Chạy test để xác nhận xanh**

Run: `venv/bin/python -m pytest tests/test_time_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/time_service.py tests/test_time_service.py
git commit -m "feat: convert file mtimes to UTC-naive without going through the machine clock

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 2: Chấm điểm ba phép kiểm

**Files:**
- Create: `services/alert_service.py`
- Test: `tests/test_alert_service.py`

**Interfaces:**
- Produces:
  - hằng `OK = "ok"`, `FAIL = "fail"`, `CHECK_WEB = "web"`, `CHECK_BACKUP = "backup"`, `CHECK_DISK = "disk"`
  - `CheckResult(name: str, status: str, detail: str)` — dataclass frozen, có property `ok -> bool`
  - `BackupFile(name: str, size_bytes: int, modified_at: datetime, gzip_ok: bool)` — dataclass frozen, `modified_at` là UTC-naive
  - `next_consecutive_failures(*, previous: int, probe_ok: bool) -> int`
  - `evaluate_web(*, consecutive_failures: int, threshold: int) -> CheckResult`
  - `evaluate_backup(*, newest: BackupFile | None, now: datetime, max_age_hours: float) -> CheckResult`
  - `evaluate_disk(*, used_percent: float, threshold_percent: float) -> CheckResult`

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/test_alert_service.py`:

```python
"""Phần quyết định của bộ canh — thuần, nên kiểm được không cần mạng lẫn đồng hồ.

Mọi hàm ở đây nhận `now` làm tham số. Đó là điều kiện để các test dưới đây chạy
ra cùng kết quả dưới mọi TZ.
"""

from datetime import datetime, timedelta

from services import alert_service as alerts

NOW = datetime(2026, 8, 22, 3, 0)      # UTC-naive


def _backup(*, hours_old=1.0, size_bytes=9_400_000, gzip_ok=True, name="hotel-20260822-000102.sql.gz"):
    return alerts.BackupFile(
        name=name,
        size_bytes=size_bytes,
        modified_at=NOW - timedelta(hours=hours_old),
        gzip_ok=gzip_ok,
    )


# --- web ---

def test_web_is_ok_below_the_failure_threshold():
    """Một nhịp trượt là chuyện thường: container web có healthcheck 15 giây và
    tự restart. Kêu ngay nhịp đầu nghĩa là gửi tin mỗi lần deploy."""
    result = alerts.evaluate_web(consecutive_failures=1, threshold=2)
    assert result.ok


def test_web_fails_when_it_reaches_the_threshold():
    result = alerts.evaluate_web(consecutive_failures=2, threshold=2)
    assert not result.ok
    assert result.name == alerts.CHECK_WEB


def test_consecutive_failures_reset_on_a_good_probe():
    assert alerts.next_consecutive_failures(previous=5, probe_ok=True) == 0
    assert alerts.next_consecutive_failures(previous=5, probe_ok=False) == 6


# --- backup ---

def test_backup_fails_when_the_folder_is_empty():
    result = alerts.evaluate_backup(newest=None, now=NOW, max_age_hours=26)
    assert not result.ok
    assert "chưa có" in result.detail.lower() or "không có" in result.detail.lower()


def test_backup_fails_on_a_zero_byte_file():
    """mysqldump chết giữa chừng vẫn để lại tệp đúng tên, đúng giờ, rỗng ruột."""
    result = alerts.evaluate_backup(newest=_backup(size_bytes=0), now=NOW, max_age_hours=26)
    assert not result.ok


def test_backup_fails_when_the_archive_is_corrupt():
    result = alerts.evaluate_backup(newest=_backup(gzip_ok=False), now=NOW, max_age_hours=26)
    assert not result.ok


def test_backup_is_ok_exactly_at_the_age_limit():
    """Biên dùng `>`: đúng 26 giờ CHƯA kêu. Lịch dump hằng ngày trôi vài phút là
    bình thường; kêu oan thì bot bị tắt thông báo."""
    result = alerts.evaluate_backup(newest=_backup(hours_old=26), now=NOW, max_age_hours=26)
    assert result.ok


def test_backup_fails_just_past_the_age_limit():
    result = alerts.evaluate_backup(
        newest=_backup(hours_old=26.02), now=NOW, max_age_hours=26
    )
    assert not result.ok


def test_backup_detail_names_the_file_and_its_age():
    result = alerts.evaluate_backup(newest=_backup(hours_old=3), now=NOW, max_age_hours=26)
    assert result.ok
    assert "hotel-20260822-000102.sql.gz" in result.detail
    assert "3" in result.detail


# --- đĩa ---

def test_disk_is_ok_below_the_threshold():
    assert alerts.evaluate_disk(used_percent=84.9, threshold_percent=85).ok


def test_disk_fails_exactly_at_the_threshold():
    """Biên dùng `>=`: đĩa đầy là ngưỡng an toàn nên nghiêng về kêu sớm — ngược
    với tuổi backup vốn nghiêng về không kêu oan."""
    assert not alerts.evaluate_disk(used_percent=85.0, threshold_percent=85).ok


def test_disk_detail_shows_the_percentage():
    result = alerts.evaluate_disk(used_percent=42.3, threshold_percent=85)
    assert "42" in result.detail
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_alert_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.alert_service'`

- [ ] **Step 3: Tạo `services/alert_service.py`**

```python
"""Phần quyết định của bộ canh vận hành.

Mọi thứ ở đây THUẦN: nhận `now` và các quan sát làm tham số, không gọi mạng,
không đọc đĩa, không xem đồng hồ. Phần I/O nằm ở `scripts/alert_watch.py`.

Ranh giới đặt như vậy vì toàn bộ phần dễ sai là phần quyết định — và phần đó
không cần I/O nào để kiểm.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

OK = "ok"
FAIL = "fail"

CHECK_WEB = "web"
CHECK_BACKUP = "backup"
CHECK_DISK = "disk"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str

    @property
    def ok(self) -> bool:
        return self.status == OK


@dataclass(frozen=True)
class BackupFile:
    name: str
    size_bytes: int
    modified_at: datetime      # UTC-naive
    gzip_ok: bool


def _human_size(size_bytes: int) -> str:
    megabytes = size_bytes / (1024 * 1024)
    if megabytes >= 1:
        return f"{megabytes:.1f} MB"
    return f"{size_bytes / 1024:.0f} KB"


def _human_age(delta: timedelta) -> str:
    hours = delta.total_seconds() / 3600
    if hours < 1:
        return f"{delta.total_seconds() / 60:.0f} phút trước"
    if hours < 48:
        return f"{hours:.0f} giờ trước"
    return f"{hours / 24:.0f} ngày trước"


def next_consecutive_failures(*, previous: int, probe_ok: bool) -> int:
    return 0 if probe_ok else previous + 1


def evaluate_web(*, consecutive_failures: int, threshold: int) -> CheckResult:
    """`web` tự restart được, nên chỉ kêu sau `threshold` nhịp hỏng liên tiếp."""
    if consecutive_failures >= threshold:
        return CheckResult(
            CHECK_WEB,
            FAIL,
            f"không phản hồi {consecutive_failures} lần liên tiếp",
        )
    return CheckResult(CHECK_WEB, OK, "bình thường")


def evaluate_backup(
    *, newest: Optional[BackupFile], now: datetime, max_age_hours: float
) -> CheckResult:
    """Ba tầng: có tệp → không rỗng → giải nén được tới byte cuối.

    Chỉ nhìn tên và dấu thời gian là tự lừa mình: shell tạo tệp TRƯỚC khi
    mysqldump chạy xong, nên một lần dump chết giữa chừng vẫn để lại tệp đúng
    tên, đúng giờ, rỗng hoặc cụt.
    """
    if newest is None:
        return CheckResult(CHECK_BACKUP, FAIL, "chưa có bản sao lưu nào trong thư mục")

    if newest.size_bytes == 0:
        return CheckResult(CHECK_BACKUP, FAIL, f"bản mới nhất RỖNG ({newest.name})")

    if not newest.gzip_ok:
        return CheckResult(
            CHECK_BACKUP, FAIL, f"bản mới nhất giải nén lỗi ({newest.name})"
        )

    age = now - newest.modified_at
    if age > timedelta(hours=max_age_hours):
        return CheckResult(
            CHECK_BACKUP,
            FAIL,
            f"bản mới nhất đã {_human_age(age)} — quá hạn {max_age_hours:g} giờ",
        )

    return CheckResult(
        CHECK_BACKUP,
        OK,
        f"bản mới nhất {_human_age(age)} ({newest.name}, {_human_size(newest.size_bytes)})",
    )


def evaluate_disk(*, used_percent: float, threshold_percent: float) -> CheckResult:
    """Dùng `>=`: đĩa đầy là ngưỡng an toàn nên nghiêng về kêu sớm."""
    if used_percent >= threshold_percent:
        return CheckResult(
            CHECK_DISK,
            FAIL,
            f"đã dùng {used_percent:.0f}% (ngưỡng {threshold_percent:g}%)",
        )
    return CheckResult(CHECK_DISK, OK, f"đã dùng {used_percent:.0f}%")
```

- [ ] **Step 4: Chạy test để xác nhận xanh**

Run: `venv/bin/python -m pytest tests/test_alert_service.py -v`
Expected: PASS (12 test)

- [ ] **Step 5: Commit**

```bash
git add services/alert_service.py tests/test_alert_service.py
git commit -m "feat: score the three operational checks as pure functions

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 3: Máy trạng thái và chống làm phiền

**Files:**
- Modify: `services/alert_service.py`
- Test: `tests/test_alert_service.py`

**Interfaces:**
- Consumes: `CheckResult`, `OK`, `FAIL`, `CHECK_*` (Task 2)
- Produces:
  - `Notification(check: Optional[str], text: str)` — dataclass frozen; `check=None` nghĩa là tin tóm tắt
  - `empty_state() -> dict`
  - `observe(*, state: dict, results: list[CheckResult]) -> dict`
  - `decide_notifications(*, state: dict, results: list[CheckResult], now: datetime, repeat_after_hours: float) -> list[Notification]`
  - `acknowledge(*, state: dict, check: str, now: datetime) -> dict`
  - `format_alert(result: CheckResult) -> str`

Hình dạng trạng thái (JSON hoá được, lưu ở `/state/alerts.json`):

```python
{
    "checks": {
        "web":    {"status": "ok", "notified_status": "ok", "last_notified_at": None},
        "backup": {"status": "ok", "notified_status": "ok", "last_notified_at": None},
        "disk":   {"status": "ok", "notified_status": "ok", "last_notified_at": None},
    },
    "web_consecutive_failures": 0,
    "last_summary_date": None,
}
```

`last_notified_at` là chuỗi ISO hoặc `None`.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_alert_service.py`:

```python
# --- máy trạng thái ---

def _state(check, *, status, notified_status, last_notified_at=None):
    state = alerts.empty_state()
    state["checks"][check] = {
        "status": status,
        "notified_status": notified_status,
        "last_notified_at": last_notified_at.isoformat() if last_notified_at else None,
    }
    return state


def test_a_healthy_check_that_stays_healthy_sends_nothing():
    state = _state(alerts.CHECK_DISK, status=alerts.OK, notified_status=alerts.OK)
    results = [alerts.evaluate_disk(used_percent=42, threshold_percent=85)]

    notes = alerts.decide_notifications(
        state=state, results=results, now=NOW, repeat_after_hours=6
    )

    assert notes == []


def test_going_from_ok_to_fail_sends_an_alert():
    state = _state(alerts.CHECK_DISK, status=alerts.OK, notified_status=alerts.OK)
    results = [alerts.evaluate_disk(used_percent=91, threshold_percent=85)]

    notes = alerts.decide_notifications(
        state=state, results=results, now=NOW, repeat_after_hours=6
    )

    assert len(notes) == 1
    assert notes[0].check == alerts.CHECK_DISK
    assert "🔴" in notes[0].text


def test_recovering_sends_a_green_message():
    state = _state(alerts.CHECK_DISK, status=alerts.FAIL, notified_status=alerts.FAIL)
    results = [alerts.evaluate_disk(used_percent=40, threshold_percent=85)]

    notes = alerts.decide_notifications(
        state=state, results=results, now=NOW, repeat_after_hours=6
    )

    assert len(notes) == 1
    assert "🟢" in notes[0].text


def test_a_still_failing_check_stays_quiet_until_the_repeat_window():
    """Kêu mỗi 5 phút thì bị tắt thông báo, và bot bị tắt thông báo thì vô dụng
    y như không có."""
    state = _state(
        alerts.CHECK_DISK,
        status=alerts.FAIL,
        notified_status=alerts.FAIL,
        last_notified_at=NOW - timedelta(hours=5, minutes=59),
    )
    results = [alerts.evaluate_disk(used_percent=91, threshold_percent=85)]

    notes = alerts.decide_notifications(
        state=state, results=results, now=NOW, repeat_after_hours=6
    )

    assert notes == []


def test_a_still_failing_check_reminds_after_the_repeat_window():
    state = _state(
        alerts.CHECK_DISK,
        status=alerts.FAIL,
        notified_status=alerts.FAIL,
        last_notified_at=NOW - timedelta(hours=6, minutes=1),
    )
    results = [alerts.evaluate_disk(used_percent=91, threshold_percent=85)]

    notes = alerts.decide_notifications(
        state=state, results=results, now=NOW, repeat_after_hours=6
    )

    assert len(notes) == 1


def test_a_failed_send_is_retried_on_the_next_cycle():
    """TEST QUAN TRỌNG NHẤT của plan này.

    Chu kỳ trước đã quan sát ra 'fail' (nên `status` = fail) nhưng Telegram lỗi
    mạng nên chưa báo được (`notified_status` vẫn = ok). Chu kỳ này PHẢI gửi
    lại. Nếu code ghi `notified_status` trước khi gửi, cảnh báo đó mất vĩnh
    viễn và hệ thống trông vẫn khoẻ mạnh.
    """
    state = _state(alerts.CHECK_DISK, status=alerts.FAIL, notified_status=alerts.OK)
    results = [alerts.evaluate_disk(used_percent=91, threshold_percent=85)]

    notes = alerts.decide_notifications(
        state=state, results=results, now=NOW, repeat_after_hours=6
    )

    assert len(notes) == 1, "cảnh báo chưa gửi được phải được thử lại"


def test_observe_updates_status_but_never_notified_status():
    state = _state(alerts.CHECK_DISK, status=alerts.OK, notified_status=alerts.OK)
    results = [alerts.evaluate_disk(used_percent=91, threshold_percent=85)]

    updated = alerts.observe(state=state, results=results)

    assert updated["checks"][alerts.CHECK_DISK]["status"] == alerts.FAIL
    assert updated["checks"][alerts.CHECK_DISK]["notified_status"] == alerts.OK


def test_acknowledge_advances_notified_status_and_the_timestamp():
    state = _state(alerts.CHECK_DISK, status=alerts.FAIL, notified_status=alerts.OK)

    updated = alerts.acknowledge(state=state, check=alerts.CHECK_DISK, now=NOW)

    entry = updated["checks"][alerts.CHECK_DISK]
    assert entry["notified_status"] == alerts.FAIL
    assert entry["last_notified_at"] == NOW.isoformat()


def test_empty_state_is_json_serialisable():
    import json

    json.dumps(alerts.empty_state())
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_alert_service.py -v`
Expected: FAIL — `AttributeError: module 'services.alert_service' has no attribute 'empty_state'`

- [ ] **Step 3: Thêm máy trạng thái vào `services/alert_service.py`**

Thêm vào cuối tệp:

```python
@dataclass(frozen=True)
class Notification:
    check: Optional[str]      # None = tin tóm tắt
    text: str


ALL_CHECKS = (CHECK_WEB, CHECK_BACKUP, CHECK_DISK)

_LABELS = {
    CHECK_WEB: "Web",
    CHECK_BACKUP: "Backup",
    CHECK_DISK: "Đĩa",
}


def empty_state() -> dict:
    return {
        "checks": {
            name: {"status": OK, "notified_status": OK, "last_notified_at": None}
            for name in ALL_CHECKS
        },
        "web_consecutive_failures": 0,
        "last_summary_date": None,
    }


def _entry(state: dict, check: str) -> dict:
    return state.get("checks", {}).get(check) or {
        "status": OK,
        "notified_status": OK,
        "last_notified_at": None,
    }


def format_alert(result: CheckResult) -> str:
    mark = "🟢" if result.ok else "🔴"
    verb = "đã trở lại bình thường" if result.ok else "CÓ VẤN ĐỀ"
    return f"{mark} {_LABELS[result.name]} {verb}: {result.detail}"


def observe(*, state: dict, results: list[CheckResult]) -> dict:
    """Ghi nhận quan sát mới.

    LUÔN cập nhật `status`. KHÔNG đụng `notified_status` — cái đó chỉ nhúc nhích
    sau khi gửi thành công (xem `acknowledge`).
    """
    updated = {**state, "checks": {**state.get("checks", {})}}
    for result in results:
        entry = dict(_entry(state, result.name))
        entry["status"] = result.status
        updated["checks"][result.name] = entry
    return updated


def decide_notifications(
    *,
    state: dict,
    results: list[CheckResult],
    now: datetime,
    repeat_after_hours: float,
) -> list[Notification]:
    """Gửi khi trạng thái lệch với cái đã báo, hoặc khi đã tới hạn nhắc lại.

    So với `notified_status` chứ không với `status`, nên một lần gửi hỏng sẽ tự
    được thử lại ở chu kỳ sau.
    """
    notifications = []
    for result in results:
        entry = _entry(state, result.name)

        if result.status != entry.get("notified_status", OK):
            notifications.append(Notification(result.name, format_alert(result)))
            continue

        if result.status == FAIL:
            stamp = entry.get("last_notified_at")
            due = stamp is None or (
                now - datetime.fromisoformat(stamp)
                >= timedelta(hours=repeat_after_hours)
            )
            if due:
                notifications.append(Notification(result.name, format_alert(result)))

    return notifications


def acknowledge(*, state: dict, check: str, now: datetime) -> dict:
    """Chỉ gọi SAU KHI Telegram nhận tin thành công."""
    updated = {**state, "checks": {**state.get("checks", {})}}
    entry = dict(_entry(state, check))
    entry["notified_status"] = entry.get("status", OK)
    entry["last_notified_at"] = now.isoformat()
    updated["checks"][check] = entry
    return updated
```

- [ ] **Step 4: Chạy test để xác nhận xanh**

Run: `venv/bin/python -m pytest tests/test_alert_service.py -v`
Expected: PASS (21 test — 12 của Task 2 + 9 mới)

- [ ] **Step 5: Chứng minh bất biến "chỉ ghi sau khi gửi thành công" thật sự được canh**

Sửa tạm `decide_notifications`, đổi dòng

```python
        if result.status != entry.get("notified_status", OK):
```

thành

```python
        if result.status != entry.get("status", OK):
```

Run: `venv/bin/python -m pytest tests/test_alert_service.py -k failed_send -v`
Expected: FAIL — `cảnh báo chưa gửi được phải được thử lại`

Hoàn nguyên bằng tay (**không** dùng `git checkout` — Task 3 chưa commit), chạy lại:

Run: `venv/bin/python -m pytest tests/test_alert_service.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add services/alert_service.py tests/test_alert_service.py
git commit -m "feat: notify on state change with a repeat window, not every cycle

State only counts as reported once Telegram accepted it, so a failed send is
retried next cycle instead of being swallowed.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 4: Tin tóm tắt mỗi sáng

**Files:**
- Modify: `services/alert_service.py`
- Test: `tests/test_alert_service.py`

**Interfaces:**
- Consumes: `CheckResult`, `Notification`, `empty_state` (Task 2, 3)
- Produces:
  - `format_summary(*, results: list[CheckResult], business_date: date) -> str`
  - `decide_summary(*, state: dict, results: list[CheckResult], business_now_dt: datetime, business_date: date, summary_hour: int) -> Optional[Notification]`
  - `acknowledge_summary(*, state: dict, business_date: date) -> dict`

`decide_summary` nhận **giờ nghiệp vụ đã tính sẵn** làm tham số, không tự gọi `time_service`. Nhờ vậy nó thuần và test chạy giống nhau ở mọi TZ.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_alert_service.py`:

```python
# --- tin tóm tắt ---

from datetime import date as _date

BUSINESS_DAY = _date(2026, 8, 22)


def _all_ok():
    return [
        alerts.evaluate_web(consecutive_failures=0, threshold=2),
        alerts.evaluate_backup(newest=_backup(hours_old=3), now=NOW, max_age_hours=26),
        alerts.evaluate_disk(used_percent=42, threshold_percent=85),
    ]


def test_no_summary_before_the_configured_hour():
    note = alerts.decide_summary(
        state=alerts.empty_state(),
        results=_all_ok(),
        business_now_dt=datetime(2026, 8, 22, 6, 59),
        business_date=BUSINESS_DAY,
        summary_hour=7,
    )
    assert note is None


def test_summary_is_sent_once_the_hour_arrives():
    note = alerts.decide_summary(
        state=alerts.empty_state(),
        results=_all_ok(),
        business_now_dt=datetime(2026, 8, 22, 7, 0),
        business_date=BUSINESS_DAY,
        summary_hour=7,
    )
    assert note is not None
    assert note.check is None
    assert "22/08/2026" in note.text


def test_summary_is_not_repeated_the_same_day():
    state = alerts.acknowledge_summary(state=alerts.empty_state(), business_date=BUSINESS_DAY)

    note = alerts.decide_summary(
        state=state,
        results=_all_ok(),
        business_now_dt=datetime(2026, 8, 22, 11, 0),
        business_date=BUSINESS_DAY,
        summary_hour=7,
    )
    assert note is None


def test_a_late_start_still_gets_the_summary():
    """Container tắt lúc 7h, bật lại lúc 9h — vẫn phải gửi bù, không mất ngày.

    Không có tin sáng nghĩa là bot chết; nếu bỏ qua chỉ vì lỡ giờ thì tín hiệu
    'bot còn sống' trở thành tín hiệu giả."""
    note = alerts.decide_summary(
        state=alerts.empty_state(),
        results=_all_ok(),
        business_now_dt=datetime(2026, 8, 22, 9, 30),
        business_date=BUSINESS_DAY,
        summary_hour=7,
    )
    assert note is not None


def test_summary_lists_all_three_checks_with_their_state():
    text = alerts.format_summary(results=_all_ok(), business_date=BUSINESS_DAY)
    assert "Web" in text
    assert "Backup" in text
    assert "Đĩa" in text
    assert text.count("✅") == 3


def test_summary_marks_a_failing_check():
    results = [
        alerts.evaluate_web(consecutive_failures=0, threshold=2),
        alerts.evaluate_backup(newest=None, now=NOW, max_age_hours=26),
        alerts.evaluate_disk(used_percent=42, threshold_percent=85),
    ]
    text = alerts.format_summary(results=results, business_date=BUSINESS_DAY)
    assert "❌" in text
    assert text.count("✅") == 2


def test_the_summary_hour_is_read_in_business_time_not_utc(monkeypatch):
    """Kiểm phần NỐI DÂY, không phải phần thuần.

    07:00 giờ Việt Nam là 00:00 UTC. Nếu ai đó nối `decide_summary` với
    `utc_now()` thay vì `business_now()`, tin sáng sẽ tới lúc 2h chiều.
    """
    from datetime import timezone

    from services import time_service

    monkeypatch.setattr(
        time_service, "utc_now", lambda: datetime(2026, 8, 22, 0, 5, tzinfo=timezone.utc)
    )

    assert time_service.business_now().hour == 7
    assert time_service.business_today() == BUSINESS_DAY
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_alert_service.py -k summary -v`
Expected: FAIL — `AttributeError: module 'services.alert_service' has no attribute 'decide_summary'`

- [ ] **Step 3: Thêm phần tóm tắt vào `services/alert_service.py`**

Thêm `date` vào dòng import sẵn có:

```python
from datetime import date, datetime, timedelta
```

Rồi thêm vào cuối tệp:

```python
def format_summary(*, results: list[CheckResult], business_date: date) -> str:
    lines = [f"☀️ Hotel POS — {business_date.strftime('%d/%m/%Y')}"]
    for result in results:
        mark = "✅" if result.ok else "❌"
        lines.append(f"{mark} {_LABELS[result.name]}: {result.detail}")
    return "\n".join(lines)


def decide_summary(
    *,
    state: dict,
    results: list[CheckResult],
    business_now_dt: datetime,
    business_date: date,
    summary_hour: int,
) -> Optional[Notification]:
    """Một tin mỗi ngày nghiệp vụ, kể từ `summary_hour`.

    Dùng `>=` chứ không `==` để container bật muộn vẫn gửi bù: mục đích của tin
    này là chứng minh bot còn sống, nên bỏ qua chỉ vì lỡ giờ sẽ biến nó thành
    tín hiệu giả.

    `business_now_dt` và `business_date` do lớp gọi tính sẵn từ `time_service`,
    để hàm này thuần và test chạy giống nhau ở mọi TZ.
    """
    if business_now_dt.hour < summary_hour:
        return None
    if state.get("last_summary_date") == business_date.isoformat():
        return None
    return Notification(None, format_summary(results=results, business_date=business_date))


def acknowledge_summary(*, state: dict, business_date: date) -> dict:
    """Chỉ gọi SAU KHI Telegram nhận tin thành công."""
    return {**state, "last_summary_date": business_date.isoformat()}
```

- [ ] **Step 4: Chạy test để xác nhận xanh**

Run: `venv/bin/python -m pytest tests/test_alert_service.py -v`
Expected: PASS (28 test — 21 của Task 3 + 7 mới)

- [ ] **Step 5: Xác nhận không phụ thuộc múi giờ**

Run:
```bash
TZ=UTC venv/bin/python -m pytest tests/test_alert_service.py -q
TZ=Asia/Ho_Chi_Minh venv/bin/python -m pytest tests/test_alert_service.py -q
```
Expected: cùng số test, cùng xanh

- [ ] **Step 6: Commit**

```bash
git add services/alert_service.py tests/test_alert_service.py
git commit -m "feat: send one business-morning summary so silence means a dead bot

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 5: Gửi tin Telegram

**Files:**
- Create: `services/telegram_service.py`
- Test: `tests/test_telegram_service.py`

**Interfaces:**
- Produces:
  - `SendOutcome(delivered: bool, reason: str)` — dataclass frozen
  - `send_message(text: str, *, bot_token: str, chat_id: str, transport=None, timeout: float = 10) -> SendOutcome`
  - `transport` là callable `(url: str, payload: bytes, timeout: float) -> int` trả về mã HTTP. Mặc định dùng `urllib.request`.

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/test_telegram_service.py`:

```python
"""Phần gửi tin — kiểm bằng transport giả, không chạm Internet."""

import pytest

from services import telegram_service

TOKEN = "123456:FAKE-TOKEN-DO-NOT-USE"
CHAT = "-1001234567890"


def test_missing_configuration_is_a_no_op_not_an_error():
    """Máy local và CI không có token. Chúng phải im lặng bỏ qua, không nổ, và
    không gọi ra Internet."""
    calls = []

    def transport(url, payload, timeout):
        calls.append(url)
        return 200

    for token, chat in ((None, CHAT), ("", CHAT), (TOKEN, None), (TOKEN, "")):
        outcome = telegram_service.send_message(
            "xin chào", bot_token=token, chat_id=chat, transport=transport
        )
        assert not outcome.delivered

    assert calls == [], "cấu hình rỗng mà vẫn gọi mạng"


def test_a_configured_send_posts_the_expected_url_and_payload():
    import json

    seen = {}

    def transport(url, payload, timeout):
        seen["url"] = url
        seen["payload"] = json.loads(payload.decode("utf-8"))
        return 200

    outcome = telegram_service.send_message(
        "🔴 Đĩa CÓ VẤN ĐỀ", bot_token=TOKEN, chat_id=CHAT, transport=transport
    )

    assert outcome.delivered
    assert seen["url"] == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    assert seen["payload"]["chat_id"] == CHAT
    assert seen["payload"]["text"] == "🔴 Đĩa CÓ VẤN ĐỀ"


def test_a_non_200_response_is_reported_as_undelivered():
    outcome = telegram_service.send_message(
        "xin chào", bot_token=TOKEN, chat_id=CHAT, transport=lambda u, p, t: 403
    )

    assert not outcome.delivered
    assert "403" in outcome.reason


def test_a_network_error_does_not_escape_and_kill_the_loop():
    """Bộ canh chạy vòng lặp vô hạn. Một ngoại lệ thoát ra là container chết và
    hệ thống cảnh báo im lặng — đúng thứ nó sinh ra để chống."""

    def transport(url, payload, timeout):
        raise OSError("mạng hỏng")

    outcome = telegram_service.send_message(
        "xin chào", bot_token=TOKEN, chat_id=CHAT, transport=transport
    )

    assert not outcome.delivered


@pytest.mark.parametrize(
    "transport",
    [
        lambda u, p, t: 403,
        lambda u, p, t: (_ for _ in ()).throw(OSError(f"đã thử {u}")),
    ],
)
def test_the_token_never_leaks_into_the_failure_reason(transport):
    """URL Telegram CHỨA token, và `str(urllib.error.HTTPError)` chứa URL. Đưa
    `str(exc)` vào log là ghi thẳng token ra đĩa."""
    outcome = telegram_service.send_message(
        "xin chào", bot_token=TOKEN, chat_id=CHAT, transport=transport
    )

    assert not outcome.delivered
    assert TOKEN not in outcome.reason
    assert "FAKE-TOKEN" not in outcome.reason


def test_send_message_adds_no_third_party_dependency():
    """requirements.txt không có requests/httpx — cố ý. Dùng urllib của thư viện
    chuẩn, đúng như healthcheck trong docker-compose.yml."""
    from pathlib import Path

    source = Path(telegram_service.__file__).read_text(encoding="utf-8")
    assert "import requests" not in source
    assert "import httpx" not in source
    assert "urllib" in source
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_telegram_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.telegram_service'`

- [ ] **Step 3: Tạo `services/telegram_service.py`**

```python
"""Gửi một tin nhắn Telegram.

Dùng `urllib.request` của thư viện chuẩn: repo cố ý không có `requests`, và
`docker-compose.yml` cũng đã dùng `urllib.request` cho healthcheck.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass

API_BASE = "https://api.telegram.org"


@dataclass(frozen=True)
class SendOutcome:
    delivered: bool
    reason: str


def _urllib_transport(url: str, payload: bytes, timeout: float) -> int:
    request = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status


def send_message(
    text: str,
    *,
    bot_token: str | None,
    chat_id: str | None,
    transport=None,
    timeout: float = 10,
) -> SendOutcome:
    """Trả về kết quả thay vì ném ngoại lệ.

    Lớp gọi chạy vòng lặp vô hạn: một ngoại lệ thoát ra là container chết và hệ
    thống cảnh báo im lặng — đúng thứ nó sinh ra để chống.

    Thông báo lỗi KHÔNG BAO GIỜ chứa URL: URL có token trong đó, và
    `str(urllib.error.HTTPError)` in cả URL ra.
    """
    if not bot_token or not chat_id:
        return SendOutcome(False, "chưa cấu hình Telegram — bỏ qua")

    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    url = f"{API_BASE}/bot{bot_token}/sendMessage"
    send = transport or _urllib_transport

    try:
        status = send(url, payload, timeout)
    except Exception as exc:                     # noqa: BLE001 — vòng lặp không được chết
        return SendOutcome(False, f"không gửi được ({type(exc).__name__})")

    if status != 200:
        return SendOutcome(False, f"Telegram trả về HTTP {status}")

    return SendOutcome(True, "đã gửi")
```

- [ ] **Step 4: Chạy test để xác nhận xanh**

Run: `venv/bin/python -m pytest tests/test_telegram_service.py -v`
Expected: PASS (6 test — `token_never_leaks` chạy 2 tham số)

- [ ] **Step 5: Chứng minh test rò token thật sự cắn**

Sửa tạm dòng `except`:

```python
        return SendOutcome(False, f"không gửi được ({exc})")
```

Run: `venv/bin/python -m pytest tests/test_telegram_service.py -k token_never_leaks -v`
Expected: FAIL — token xuất hiện trong `reason`

Hoàn nguyên bằng tay, chạy lại:

Run: `venv/bin/python -m pytest tests/test_telegram_service.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add services/telegram_service.py tests/test_telegram_service.py
git commit -m "feat: send Telegram messages over stdlib urllib without leaking the token

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 6: Vòng lặp và lớp I/O

**Files:**
- Create: `scripts/__init__.py`, `scripts/alert_watch.py`
- Test: kiểm tay (`--once`, `--test-message`) — phần quyết định đã được Task 2-5 phủ

**Interfaces:**
- Consumes: toàn bộ `alert_service` và `telegram_service`, `time_service.utc_naive_from_timestamp`
- Produces: `python -m scripts.alert_watch [--once|--test-message]`

- [ ] **Step 1: Tạo `scripts/__init__.py`**

Tệp rỗng. Không có nó thì `python -m scripts.alert_watch` báo `No module named scripts`.

```bash
mkdir -p scripts && touch scripts/__init__.py
```

- [ ] **Step 2: Tạo `scripts/alert_watch.py`**

```python
"""Bộ canh vận hành: kiểm web, backup, đĩa rồi báo qua Telegram.

Tệp này là lớp I/O MỎNG. Mọi quyết định nằm ở `services/alert_service.py` dưới
dạng hàm thuần, và được pytest phủ ở đó. Giữ tệp này không có logic để phần
không kiểm được cũng là phần không cần kiểm.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path

from services import alert_service as alerts
from services import telegram_service, time_service


def _env(name: str, default: str) -> str:
    return os.environ.get(name) or default


def _config() -> dict:
    return {
        "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
        "interval": float(_env("ALERT_INTERVAL_SECONDS", "300")),
        "web_url": _env("ALERT_WEB_URL", "http://web:8000/healthz"),
        "web_threshold": int(_env("ALERT_WEB_FAIL_THRESHOLD", "2")),
        "backup_dir": Path(_env("ALERT_BACKUP_DIR", "/backups")),
        "backup_max_age_hours": float(_env("ALERT_BACKUP_MAX_AGE_HOURS", "26")),
        "disk_threshold": float(_env("ALERT_DISK_THRESHOLD_PERCENT", "85")),
        "repeat_hours": float(_env("ALERT_REPEAT_HOURS", "6")),
        "summary_hour": int(_env("ALERT_SUMMARY_HOUR", "7")),
        "state_file": Path(_env("ALERT_STATE_FILE", "/state/alerts.json")),
    }


def _load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # Lần chạy đầu, hoặc tệp hỏng: bắt đầu lại từ trạng thái sạch. Mất lịch
        # sử thông báo còn hơn để vòng lặp chết.
        return alerts.empty_state()


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _probe_web(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status == 200
    except Exception:                            # noqa: BLE001
        return False


def _gzip_intact(path: Path) -> bool:
    try:
        with gzip.open(path, "rb") as handle:
            while handle.read(1024 * 1024):
                pass
        return True
    except Exception:                            # noqa: BLE001
        return False


def _newest_backup(folder: Path, state: dict):
    """Tệp `.sql.gz` mới nhất, kèm kết quả kiểm gzip.

    Kiểm gzip phải đọc hết tệp, nên chỉ làm lại khi (tên, kích thước, mtime)
    khác với lần trước — ghi nhớ trong trạng thái. Đọc lại bản dump lớn mỗi 5
    phút là phí I/O vô ích.
    """
    try:
        candidates = sorted(
            folder.glob("*.sql.gz"), key=lambda p: p.stat().st_mtime, reverse=True
        )
    except OSError:
        return None, state

    if not candidates:
        return None, state

    newest = candidates[0]
    stat = newest.stat()
    fingerprint = [newest.name, stat.st_size, stat.st_mtime]

    cached = state.get("backup_gzip_cache") or {}
    if cached.get("fingerprint") == fingerprint:
        gzip_ok = cached["gzip_ok"]
    else:
        gzip_ok = _gzip_intact(newest)
        state = {
            **state,
            "backup_gzip_cache": {"fingerprint": fingerprint, "gzip_ok": gzip_ok},
        }

    return (
        alerts.BackupFile(
            name=newest.name,
            size_bytes=stat.st_size,
            modified_at=time_service.utc_naive_from_timestamp(stat.st_mtime),
            gzip_ok=gzip_ok,
        ),
        state,
    )


def _disk_used_percent(path: Path) -> float:
    usage = shutil.disk_usage(path if path.exists() else path.parent)
    return usage.used / usage.total * 100


def _send(text: str, config: dict) -> bool:
    outcome = telegram_service.send_message(
        text, bot_token=config["bot_token"], chat_id=config["chat_id"]
    )
    if not outcome.delivered:
        print(f"[alerts] không gửi được: {outcome.reason}", flush=True)
    return outcome.delivered


def run_cycle(config: dict) -> None:
    state = _load_state(config["state_file"])

    probe_ok = _probe_web(config["web_url"])
    consecutive = alerts.next_consecutive_failures(
        previous=int(state.get("web_consecutive_failures", 0)), probe_ok=probe_ok
    )
    state = {**state, "web_consecutive_failures": consecutive}

    newest, state = _newest_backup(config["backup_dir"], state)
    now = time_service.utc_now_naive()

    results = [
        alerts.evaluate_web(
            consecutive_failures=consecutive, threshold=config["web_threshold"]
        ),
        alerts.evaluate_backup(
            newest=newest, now=now, max_age_hours=config["backup_max_age_hours"]
        ),
        alerts.evaluate_disk(
            used_percent=_disk_used_percent(config["backup_dir"]),
            threshold_percent=config["disk_threshold"],
        ),
    ]

    notifications = alerts.decide_notifications(
        state=state, results=results, now=now, repeat_after_hours=config["repeat_hours"]
    )
    summary = alerts.decide_summary(
        state=state,
        results=results,
        business_now_dt=time_service.business_now(),
        business_date=time_service.business_today(),
        summary_hour=config["summary_hour"],
    )

    # THỨ TỰ BẮT BUỘC, đừng đảo: `acknowledge` chép `status` sang
    # `notified_status`, nên nó phải chạy SAU `observe`. Đảo lại thì nó ghi nhận
    # nhầm trạng thái của chu kỳ trước, và cảnh báo vừa gửi coi như chưa gửi.
    state = alerts.observe(state=state, results=results)

    # Chỉ ghi nhận ĐÃ BÁO sau khi Telegram nhận thành công. Ghi trước sẽ khiến
    # một lần lỗi mạng nuốt mất cảnh báo vĩnh viễn.
    for note in notifications:
        if _send(note.text, config):
            state = alerts.acknowledge(state=state, check=note.check, now=now)

    if summary is not None and _send(summary.text, config):
        state = alerts.acknowledge_summary(
            state=state, business_date=time_service.business_today()
        )

    _save_state(config["state_file"], state)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Bộ canh vận hành Hotel POS")
    parser.add_argument("--once", action="store_true", help="chạy một chu kỳ rồi thoát")
    parser.add_argument(
        "--test-message",
        action="store_true",
        help="gửi một tin thử rồi thoát (không đọc/ghi trạng thái)",
    )
    args = parser.parse_args(argv)
    config = _config()

    if args.test_message:
        ok = _send("🔔 Hotel POS — tin thử. Nếu anh thấy tin này, cảnh báo đã sẵn sàng.", config)
        return 0 if ok else 1

    if args.once or os.environ.get("ONE_SHOT") == "1":
        run_cycle(config)
        return 0

    while True:
        try:
            run_cycle(config)
        except Exception as exc:                 # noqa: BLE001 — vòng lặp không được chết
            print(f"[alerts] chu kỳ lỗi: {type(exc).__name__}", flush=True)
        time.sleep(config["interval"])


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Kiểm cú pháp và kiểm chạy được**

Run:
```bash
venv/bin/python -m compileall -q scripts/alert_watch.py
ALERT_BACKUP_DIR=./backups ALERT_STATE_FILE=/tmp/alert-state.json \
  ALERT_WEB_URL=http://127.0.0.1:8000/healthz \
  venv/bin/python -m scripts.alert_watch --once
cat /tmp/alert-state.json
```
Expected: chạy xong không lỗi; in `chưa cấu hình Telegram — bỏ qua` nếu có gì cần gửi; `/tmp/alert-state.json` chứa `checks` với ba mục.

- [ ] **Step 4: Chạy toàn bộ suite**

Run: `venv/bin/python -m pytest -m "not mysql" -q`
Expected: PASS — lưới `tests/test_no_ambient_now.py` phải vẫn xanh (`scripts/` không nằm trong vùng nó quét, nhưng `services/` thì có, và hai service mới không được dùng đồng hồ trần).

- [ ] **Step 5: Commit**

```bash
git add scripts/
git commit -m "feat: add the alert watch loop with --once and --test-message

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 7: Khai báo hạ tầng và runbook

**Files:**
- Modify: `docker-compose.yml` (thêm service `alerts`; thêm volume `alert_state` vào khối `volumes:` ở dòng ~118)
- Modify: `.env.example`
- Create: `docs/runbooks/telegram-alerts.md`
- Test: `tests/test_alert_infrastructure.py`

**Interfaces:**
- Consumes: `python -m scripts.alert_watch` (Task 6)

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/test_alert_infrastructure.py`:

```python
"""Khoá phần khai báo hạ tầng.

Ba thứ dưới đây sai thì bộ canh vẫn "chạy" mà vô dụng, và không test nào khác
phát hiện được.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _compose():
    return (ROOT / "docker-compose.yml").read_text(encoding="utf-8")


def test_compose_declares_the_alerts_service():
    compose = _compose()
    assert "\n  alerts:" in compose
    assert "scripts.alert_watch" in compose
    assert "alert_state:" in compose, "thiếu volume giữ trạng thái qua restart"


def _alerts_block():
    """Cắt đúng khối `alerts:` — từ tên service tới service kế tiếp cùng mức thụt
    (hoặc tới khối `volumes:` ở mức gốc).

    Không cắt bằng `split("\\n  ")`: dòng ngay sau `alerts:` đã thụt hai dấu cách
    (`build:`), nên cách đó trả về khối rỗng và test đỏ oan.
    """
    import re

    match = re.search(
        r"\n  alerts:\n(.*?)(?=\n  \w+:\n|\nvolumes:)", _compose(), re.S
    )
    assert match, "không tìm thấy khối alerts trong docker-compose.yml"
    return match.group(1)


def test_alerts_waits_only_for_web_to_start_not_to_be_healthy():
    """`condition: service_healthy` sẽ khiến bộ canh KHÔNG BAO GIỜ khởi động
    đúng vào lúc web hỏng ngay từ đầu — ca đáng báo nhất."""
    block = _alerts_block()
    assert "service_started" in block
    assert "service_healthy" not in block


def test_alerts_mounts_the_backup_folder_read_only():
    """Bộ canh không được phép xoá hay sửa bản sao lưu."""
    compose = _compose()
    assert "./backups:/backups:ro" in compose


def test_env_example_documents_every_alert_key():
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    for key in (
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "ALERT_INTERVAL_SECONDS",
        "ALERT_WEB_URL",
        "ALERT_WEB_FAIL_THRESHOLD",
        "ALERT_BACKUP_DIR",
        "ALERT_BACKUP_MAX_AGE_HOURS",
        "ALERT_DISK_THRESHOLD_PERCENT",
        "ALERT_REPEAT_HOURS",
        "ALERT_SUMMARY_HOUR",
        "ALERT_STATE_FILE",
    ):
        assert key in env, f".env.example thiếu {key}"


def test_no_real_token_is_committed():
    """Token thật lọt vào .env.example là rò bí mật vào lịch sử git."""
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    for line in env.splitlines():
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            assert line.strip() == "TELEGRAM_BOT_TOKEN=", "phải để rỗng"
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_alert_infrastructure.py -v`
Expected: FAIL — `assert '\n  alerts:' in compose`

- [ ] **Step 3: Thêm service vào `docker-compose.yml`**

Chèn sau service `db-backup` (kết thúc khoảng dòng 109), trước `adminer`:

```yaml
  alerts:
    build:
      context: .
      dockerfile: docker/Dockerfile
    command: ["python", "-m", "scripts.alert_watch"]
    environment:
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:-}
      TELEGRAM_CHAT_ID: ${TELEGRAM_CHAT_ID:-}
      ALERT_INTERVAL_SECONDS: ${ALERT_INTERVAL_SECONDS:-300}
      ALERT_WEB_URL: ${ALERT_WEB_URL:-http://web:8000/healthz}
      ALERT_WEB_FAIL_THRESHOLD: ${ALERT_WEB_FAIL_THRESHOLD:-2}
      ALERT_BACKUP_DIR: ${ALERT_BACKUP_DIR:-/backups}
      ALERT_BACKUP_MAX_AGE_HOURS: ${ALERT_BACKUP_MAX_AGE_HOURS:-26}
      ALERT_DISK_THRESHOLD_PERCENT: ${ALERT_DISK_THRESHOLD_PERCENT:-85}
      ALERT_REPEAT_HOURS: ${ALERT_REPEAT_HOURS:-6}
      ALERT_SUMMARY_HOUR: ${ALERT_SUMMARY_HOUR:-7}
      ALERT_STATE_FILE: ${ALERT_STATE_FILE:-/state/alerts.json}
    volumes:
      - ./backups:/backups:ro
      - alert_state:/state
    depends_on:
      web:
        condition: service_started
    restart: unless-stopped
    logging: *default-logging
```

Rồi thêm volume vào khối `volumes:` (dòng ~118):

```yaml
volumes:
  dbdata:
  caddy_data:
  caddy_config:
  alert_state:
```

- [ ] **Step 4: Thêm khối biến vào `.env.example`**

Chèn sau dòng `BACKUP_RETENTION_DAYS` (khoảng dòng 43):

```bash
# Cảnh báo vận hành qua Telegram (spec 22-08-2026).
# Để TRỐNG hai dòng đầu = tắt hẳn, không gọi mạng. Lấy token bằng cách nhắn
# /newbot cho @BotFather; lấy chat_id ở api.telegram.org/bot<TOKEN>/getUpdates.
# Xem docs/runbooks/telegram-alerts.md
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
ALERT_INTERVAL_SECONDS=300
ALERT_WEB_URL=http://web:8000/healthz
ALERT_WEB_FAIL_THRESHOLD=2
ALERT_BACKUP_DIR=/backups
ALERT_BACKUP_MAX_AGE_HOURS=26
ALERT_DISK_THRESHOLD_PERCENT=85
ALERT_REPEAT_HOURS=6
ALERT_SUMMARY_HOUR=7
ALERT_STATE_FILE=/state/alerts.json
```

- [ ] **Step 5: Viết runbook `docs/runbooks/telegram-alerts.md`**

```markdown
# Runbook: Cảnh báo vận hành qua Telegram

## Cài lần đầu

1. Mở Telegram, nhắn `/newbot` cho **@BotFather**. Đặt tên bot. Nhận token dạng
   `123456789:AAH...`.
2. Nhắn một câu bất kỳ cho bot vừa tạo. (Muốn cả nhóm cùng nhận thì thêm bot vào
   group rồi nhắn trong group.)
3. Mở `https://api.telegram.org/bot<TOKEN>/getUpdates`, tìm `"chat":{"id":...}`.
   Group thì `id` là số âm — giữ nguyên dấu trừ.
4. Điền vào `.env` trên VPS:
   ```
   TELEGRAM_BOT_TOKEN=123456789:AAH...
   TELEGRAM_CHAT_ID=-1001234567890
   ```
5. `docker compose up -d alerts`
6. Xác nhận đường dây thông trước khi tin tưởng nó:
   ```bash
   docker compose run --rm alerts python -m scripts.alert_watch --test-message
   ```
   Không thấy tin thì xem log: `docker compose logs alerts`.

## Ba thứ nó canh

| Canh gì | Kêu khi |
| --- | --- |
| Web + DB | `/healthz` hỏng 2 chu kỳ liên tiếp (~10 phút) |
| Backup | quá 26 giờ, hoặc tệp rỗng, hoặc giải nén lỗi |
| Đĩa | đã dùng ≥ 85% |

Chỉ báo khi **đổi trạng thái**, và nhắc lại mỗi 6 giờ nếu vẫn hỏng. Đang hỏng
mà chưa tới hạn nhắc thì im lặng — không có chuyện kêu mỗi 5 phút.

## Tin sáng

07:00 giờ Việt Nam mỗi ngày, kể cả khi mọi thứ bình thường.

**Không có tin sáng nghĩa là bộ canh đã chết** — container tắt, token hỏng, hoặc
VPS ngừng chạy. Đó là toàn bộ mục đích của tin này: yên lặng không còn đồng
nghĩa với ổn.

## Khi nhận được cảnh báo

**🔴 Web:** `docker compose ps` xem `web` còn sống không.
`docker compose logs --tail=100 web`. Thường là restart lỗi hoặc db không lên.

**🔴 Backup:** `docker compose logs --tail=50 db-backup`. Nếu tệp rỗng hoặc hỏng
thì chạy tay một vòng:
`docker compose run --rm -e ONE_SHOT=1 db-backup`.

**🔴 Đĩa:** `df -h`, rồi `du -sh backups/*`. Giảm `BACKUP_RETENTION_DAYS` nếu
bản sao lưu chiếm quá nhiều, hoặc dọn log docker.

## Tắt tạm

Bỏ trống `TELEGRAM_BOT_TOKEN` trong `.env` rồi `docker compose up -d alerts`.
Bộ canh vẫn chạy, vẫn ghi trạng thái, chỉ không gửi gì.
```

- [ ] **Step 6: Chạy test và kiểm cấu hình compose hợp lệ**

Run:
```bash
venv/bin/python -m pytest tests/test_alert_infrastructure.py -v
docker compose config --quiet && echo "compose hợp lệ"
```
Expected: PASS, và compose không báo lỗi cú pháp

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml .env.example docs/runbooks/telegram-alerts.md tests/test_alert_infrastructure.py
git commit -m "feat: run the alert watcher as a compose service with a runbook

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Nghiệm thu

- [ ] **Bước 1: Suite ở cả ba múi giờ**

```bash
venv/bin/python -m pytest -m "not mysql" -q
TZ=UTC venv/bin/python -m pytest -m "not mysql" -q
TZ=Asia/Ho_Chi_Minh venv/bin/python -m pytest -m "not mysql" -q
```
Expected: ba lần xanh với **cùng số test**

- [ ] **Bước 2: Bộ MySQL**

```bash
set -a; source .env; set +a
TEST_MYSQL_DATABASE_URL="mysql+pymysql://root:${MYSQL_ROOT_PASSWORD}@127.0.0.1:3306/hotel_test" venv/bin/python -m pytest -m mysql -q
```
Expected: xanh

- [ ] **Bước 3: Dựng stack và kiểm đường dây**

```bash
docker compose build alerts && docker compose up -d alerts
docker compose logs --tail=20 alerts
docker compose run --rm alerts python -m scripts.alert_watch --once
```
Expected: chạy sạch. Chưa điền token thì log ghi `chưa cấu hình Telegram — bỏ qua` — đó là đúng, không phải lỗi.

- [ ] **Bước 4: Kiểm tay bốn kịch bản**

Chỉ làm được sau khi `.env` có token thật.

1. `--test-message` → tin tới Telegram.
2. `docker compose stop web`, chờ 2 chu kỳ → nhận 🔴. `docker compose start web` → nhận 🟢.
3. Trong thư mục thử: `touch -d '3 days ago'` lên tệp `.sql.gz` mới nhất, trỏ `ALERT_BACKUP_DIR` vào đó, chạy `--once` → nhận cảnh báo quá hạn.
4. Tạo một tệp `.sql.gz` rỗng mới nhất trong thư mục thử, chạy `--once` → nhận cảnh báo backup rỗng.

- [ ] **Bước 5: Đẩy và theo dõi CI**

```bash
git push origin dev
gh run list --branch dev --limit 1
```
Expected: cả 3 job xanh. Sau đó đóng dấu "ĐÃ TRIỂN KHAI" vào đầu spec và commit.

- [ ] **Bước 6: Nhắc chủ dự án một dòng `.env`**

Không phải việc code, nhưng thuộc cùng vấn đề: đặt `BACKUP_RETENTION_DAYS=90`
trên VPS. Hiện đang chạy mặc định 14 ngày, nghĩa là khả năng quay ngược thời
gian chỉ có 14 ngày.
