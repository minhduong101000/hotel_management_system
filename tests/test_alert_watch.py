"""Kiểm phần NỐI DÂY của bộ canh (`scripts/alert_watch.py`).

Khác với `tests/test_alert_service.py` (thuần, không I/O), các test ở đây gọi
thẳng `_newest_backup` / `run_cycle` — nơi có ghi đĩa và (được monkeypatch)
mạng — để khoá đúng cái mà lớp thuần không thấy được: I/O có thật sự được nối
đúng dây hay không.
"""

from __future__ import annotations

import gzip
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import alert_watch
from services import alert_service as alerts
from services import telegram_service, time_service


def _touch_backup(folder: Path, name: str, *, age_seconds: float, size_bytes: int = 9_400) -> Path:
    path = folder / name
    path.write_bytes(b"\x1f\x8b" + b"0" * (size_bytes - 2))  # đủ giả gzip header
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))
    return path


def _write_healthy_backup(folder: Path, name: str, *, age_seconds: float) -> Path:
    """Một bản `.sql.gz` THẬT SỰ giải nén được — dùng cho các test không nhắm
    vào chính phép kiểm backup, để phép kiểm đó luôn ra OK và không gây nhiễu."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(gzip.compress(b"-- fake mysqldump output\n" * 50))
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))
    return path


def _base_config(tmp_path, **overrides) -> dict:
    config = {
        "bot_token": "123:abc",
        "chat_id": "-1",
        "web_url": "http://web:8000/healthz",
        "web_threshold": 2,
        "backup_dir": tmp_path / "backups",
        "backup_max_age_hours": 26.0,
        "backup_min_age_seconds": 120.0,
        "disk_threshold": 85.0,
        "repeat_hours": 6.0,
        "summary_hour": 7,
        "state_file": tmp_path / "state" / "alerts.json",
    }
    config.update(overrides)
    return config


class _FakeSender:
    """Ghi lại mọi tin đã 'gửi' thay vì gọi Telegram thật."""

    def __init__(self, *, delivered: bool = True):
        self.delivered = delivered
        self.sent: list[str] = []

    def __call__(self, text, *, bot_token, chat_id, transport=None, timeout=10):
        self.sent.append(text)
        return telegram_service.SendOutcome(
            self.delivered, "đã gửi" if self.delivered else "mô phỏng lỗi mạng"
        )


def _freeze_business_hour(monkeypatch, *, bangkok_hour: int) -> None:
    """Cố định đồng hồ ở giờ Bangkok cho trước, tránh tin sáng chen vào các
    test không nhắm tới nó. UTC = Bangkok - 7."""
    utc_hour = (bangkok_hour - 7) % 24
    monkeypatch.setattr(
        time_service,
        "utc_now",
        lambda: datetime(2026, 1, 1, utc_hour, 0, tzinfo=timezone.utc),
    )


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


# --- Fix 5: run_cycle nối dây thật — không còn test nào chạm tới nó trước đây ---


def test_web_alert_only_fires_after_two_consecutive_failed_cycles(tmp_path, monkeypatch):
    """Test hồi quy CHO FIX 1: nếu trạng thái không sống sót qua hai lần gọi
    `run_cycle` (ví dụ vì `_save_state` ghi vào một `/state` không có quyền
    ghi), `web_consecutive_failures` không bao giờ vượt quá 1 và cảnh báo web
    — quan trọng nhất trong ba phép kiểm — không bao giờ kêu."""
    config = _base_config(tmp_path)
    _write_healthy_backup(config["backup_dir"], "hotel-ok.sql.gz", age_seconds=3600)
    _freeze_business_hour(monkeypatch, bangkok_hour=3)  # tránh tin sáng chen vào

    monkeypatch.setattr(alert_watch, "_probe_web", lambda url: False)
    monkeypatch.setattr(alert_watch, "_disk_used_percent", lambda path: 10.0)
    sender = _FakeSender(delivered=True)
    monkeypatch.setattr(telegram_service, "send_message", sender)

    alert_watch.run_cycle(config)
    assert sender.sent == [], "nhịp hỏng ĐẦU TIÊN chưa tới ngưỡng, không được báo"

    alert_watch.run_cycle(config)
    assert len(sender.sent) == 1, "nhịp hỏng THỨ HAI đạt ngưỡng 2, phải báo đúng một lần"
    assert "🔴" in sender.sent[0]
    assert "Web" in sender.sent[0]


def test_summary_hour_is_read_in_business_time_not_utc(tmp_path, monkeypatch):
    """00:05 UTC = 07:05 giờ Bangkok. Nếu `run_cycle` bị nối nhầm với
    `time_service.utc_now()` thay vì `business_now()`, tin sáng sẽ không tới
    lúc 07:05 UTC+7 mà tới lúc 00:05 UTC+7 (tức 17:05 hôm trước theo giờ Bangkok)."""
    config = _base_config(tmp_path)
    # Cố ý KHÔNG tạo backup nào: chỉ cần tin tóm tắt có xuất hiện, không cần
    # mọi phép kiểm đều OK.
    monkeypatch.setattr(
        time_service, "utc_now", lambda: datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc)
    )
    monkeypatch.setattr(alert_watch, "_probe_web", lambda url: True)
    monkeypatch.setattr(alert_watch, "_disk_used_percent", lambda path: 10.0)
    sender = _FakeSender(delivered=True)
    monkeypatch.setattr(telegram_service, "send_message", sender)

    assert time_service.business_now().hour == 7

    alert_watch.run_cycle(config)

    assert any("☀️" in text for text in sender.sent), "tin sáng phải được gửi lúc 07:05 giờ Bangkok"


def test_a_failed_send_is_retried_every_cycle_until_it_succeeds(tmp_path, monkeypatch):
    """Telegram lỗi mạng không được phép làm mất cảnh báo: chạy hai chu kỳ với
    gửi tin luôn thất bại thì cảnh báo phải được thử gửi lại CẢ HAI lần."""
    config = _base_config(tmp_path)
    _write_healthy_backup(config["backup_dir"], "hotel-ok.sql.gz", age_seconds=3600)
    _freeze_business_hour(monkeypatch, bangkok_hour=3)

    monkeypatch.setattr(alert_watch, "_probe_web", lambda url: True)
    monkeypatch.setattr(alert_watch, "_disk_used_percent", lambda path: 91.0)  # FAIL: >= 85
    sender = _FakeSender(delivered=False)
    monkeypatch.setattr(telegram_service, "send_message", sender)

    alert_watch.run_cycle(config)
    alert_watch.run_cycle(config)

    disk_alerts = [text for text in sender.sent if "Đĩa" in text]
    assert len(disk_alerts) == 2, "gửi lỗi thì chu kỳ sau phải thử lại, không được coi như đã báo"


# --- Fix 6: ba việc nhỏ ---


def test_disk_used_percent_matches_df_not_the_filesystem_reserve(monkeypatch, tmp_path):
    """`shutil.disk_usage().total` gồm cả khối dự trữ mà `df` không tính vào
    mẫu số — chia cho `total` đọc cao hơn `df` vài điểm phần trăm. Công thức
    đúng là `used / (used + free)`, khớp với lệnh runbook bảo chủ khách sạn
    chạy tay để đối chiếu."""
    import shutil as shutil_module
    from collections import namedtuple

    Usage = namedtuple("Usage", "total used free")
    # total=100 nhưng used(70)+free(20)=90 -> 10 "dự trữ" filesystem không ai
    # dùng được. used/total = 70%, used/(used+free) = 77.78%.
    monkeypatch.setattr(
        shutil_module, "disk_usage", lambda path: Usage(total=100, used=70, free=20)
    )

    result = alert_watch._disk_used_percent(tmp_path)

    assert result == pytest.approx(70 / 90 * 100)


def test_send_does_not_log_when_telegram_is_simply_unconfigured(monkeypatch, capsys):
    """Chưa điền TELEGRAM_BOT_TOKEN/CHAT_ID là trạng thái BÌNH THƯỜNG trên máy
    dev và CI — log nó ra ở MỖI lần thông báo mỗi chu kỳ là nhiễu thuần túy."""
    monkeypatch.setattr(
        telegram_service,
        "send_message",
        lambda text, **kw: telegram_service.SendOutcome(
            False, "chưa cấu hình Telegram — bỏ qua"
        ),
    )

    ok = alert_watch._send("tin thử", _base_config(Path("/unused")))

    assert ok is False
    assert capsys.readouterr().out == ""


def test_send_still_logs_a_real_delivery_failure(monkeypatch, capsys):
    """Ngược lại: một lỗi gửi THẬT (mạng, token sai, HTTP 4xx/5xx) vẫn phải lên
    log — chỉ riêng lý do 'chưa cấu hình' mới là tín hiệu bình thường."""
    monkeypatch.setattr(
        telegram_service,
        "send_message",
        lambda text, **kw: telegram_service.SendOutcome(False, "Telegram trả về HTTP 401"),
    )

    ok = alert_watch._send("tin thử", _base_config(Path("/unused")))

    assert ok is False
    assert "HTTP 401" in capsys.readouterr().out
