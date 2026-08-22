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
