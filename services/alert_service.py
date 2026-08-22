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
    return state.get("checks", {}).get(
        check,
        {"status": OK, "notified_status": OK, "last_notified_at": None},
    )


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
