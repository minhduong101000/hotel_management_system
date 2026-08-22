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
