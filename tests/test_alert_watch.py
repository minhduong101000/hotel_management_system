"""Kiểm phần NỐI DÂY của bộ canh (`scripts/alert_watch.py`).

Khác với `tests/test_alert_service.py` (thuần, không I/O), các test ở đây gọi
thẳng `_newest_backup` / `run_cycle` — nơi có ghi đĩa và (được monkeypatch)
mạng — để khoá đúng cái mà lớp thuần không thấy được: I/O có thật sự được nối
đúng dây hay không.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path

from scripts import alert_watch
from services import alert_service as alerts
from services import telegram_service, time_service


def _touch_backup(folder: Path, name: str, *, age_seconds: float, size_bytes: int = 9_400) -> Path:
    path = folder / name
    path.write_bytes(b"\x1f\x8b" + b"0" * (size_bytes - 2))  # đủ giả gzip header
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))
    return path


# --- Fix 4: race giữa chu kỳ kiểm và mysqldump đang chạy dở ---


def test_newest_backup_ignores_a_file_still_inside_the_grace_window(tmp_path):
    """Tệp mới tạo trong cửa sổ ân hạn có thể vẫn đang được `mysqldump | gzip`
    ghi dở — rỗng hoặc cụt không phân biệt được với một bản dump chết, CHỈ tuổi
    mới phân biệt được. Phải bỏ qua, không báo lỗi oan."""
    _touch_backup(tmp_path, "hotel-fresh.sql.gz", age_seconds=5, size_bytes=0)
    older = _touch_backup(tmp_path, "hotel-older.sql.gz", age_seconds=3600)

    result, _ = alert_watch._newest_backup(
        tmp_path, alerts.empty_state(), min_age_seconds=120
    )

    assert result is not None
    assert result.name == older.name


def test_newest_backup_returns_none_when_the_only_candidate_is_too_young(tmp_path):
    _touch_backup(tmp_path, "hotel-fresh.sql.gz", age_seconds=5)

    result, _ = alert_watch._newest_backup(
        tmp_path, alerts.empty_state(), min_age_seconds=120
    )

    assert result is None


def test_newest_backup_does_not_cache_a_verdict_for_a_file_still_too_young(tmp_path):
    """Một tệp bị bỏ qua vì còn non tuổi không được để lại `gzip_ok=False`
    trong cache — chu kỳ sau, khi nó đã đủ tuổi, phải được kiểm gzip LẠI chứ
    không ăn phải phán quyết cũ của lúc nó còn dở dang."""
    _touch_backup(tmp_path, "hotel-fresh.sql.gz", age_seconds=5, size_bytes=0)

    _, state = alert_watch._newest_backup(
        tmp_path, alerts.empty_state(), min_age_seconds=120
    )

    assert state.get("backup_gzip_cache") is None


def test_newest_backup_accepts_a_file_past_the_grace_window(tmp_path):
    older = _touch_backup(tmp_path, "hotel-ok.sql.gz", age_seconds=300)

    result, _ = alert_watch._newest_backup(
        tmp_path, alerts.empty_state(), min_age_seconds=120
    )

    assert result is not None
    assert result.name == older.name
