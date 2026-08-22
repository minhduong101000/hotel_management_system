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

    `last_notified_at` được đặt gần đây (còn trong cửa sổ nhắc lại) một cách
    cố ý: nếu để None, nhánh "vẫn đang fail, tới hạn nhắc" sẽ tự gửi lại vì
    chưa từng có mốc thời gian nào — che mất lỗi nếu code so `status` thay vì
    `notified_status`. Đặt gần đây buộc chỉ có đường so `notified_status` mới
    gửi được, đúng cái bất biến cần chứng minh.
    """
    state = _state(
        alerts.CHECK_DISK,
        status=alerts.FAIL,
        notified_status=alerts.OK,
        last_notified_at=NOW - timedelta(minutes=1),
    )
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


def test_acknowledge_copies_the_observed_status_rather_than_assuming_failure():
    """Bổ sung sau review: mọi test khác chỉ ghi nhận phép kiểm ĐANG HỎNG, nên
    một bản cài đặt ghi cứng `notified_status = FAIL` vẫn xanh hết. Ca này khoá
    việc `acknowledge` phải CHÉP trạng thái vừa quan sát.

    Nó chạy ở đường hồi phục thật: hỏng → đã báo hỏng → nay ổn trở lại, gửi tin
    🟢 xong thì ghi nhận là ĐÃ BÁO ỔN.
    """
    state = _state(alerts.CHECK_DISK, status=alerts.OK, notified_status=alerts.FAIL)

    updated = alerts.acknowledge(state=state, check=alerts.CHECK_DISK, now=NOW)

    assert updated["checks"][alerts.CHECK_DISK]["notified_status"] == alerts.OK


def test_the_repeat_window_fires_exactly_on_the_boundary():
    """Biên dùng `>=`: đúng 6 giờ là nhắc lại. Hai test lân cận để margin 1 phút
    nên không bắt được nếu ai đó đổi `>=` thành `>`."""
    state = _state(
        alerts.CHECK_DISK,
        status=alerts.FAIL,
        notified_status=alerts.FAIL,
        last_notified_at=NOW - timedelta(hours=6),
    )
    results = [alerts.evaluate_disk(used_percent=91, threshold_percent=85)]

    notes = alerts.decide_notifications(
        state=state, results=results, now=NOW, repeat_after_hours=6
    )

    assert len(notes) == 1


def test_empty_state_is_json_serialisable():
    import json

    json.dumps(alerts.empty_state())
