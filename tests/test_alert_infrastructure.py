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
    """Bộ canh không được phép xoá hay sửa bản sao lưu.

    Cố ý tìm trong `_alerts_block()` chứ không phải toàn file: `db-backup`
    cũng mount `./backups`, nhưng KHÔNG `:ro` (nó cần ghi để tạo bản mới và
    dọn theo retention). Tìm trên toàn file sẽ pass ngay cả khi chuỗi
    `:ro` bị gắn nhầm service khác — không chứng minh được đúng service
    `alerts` bị hạn chế chỉ đọc.
    """
    block = _alerts_block()
    assert "./backups:/backups:ro" in block


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

    # Chỉ nhìn dòng bắt đầu bằng "TELEGRAM_BOT_TOKEN=" thì bỏ lọt token dán
    # nhầm chỗ khác (bị comment, dán vào TELEGRAM_CHAT_ID, hay có khoảng
    # trắng trước dấu "="). Token Telegram có hình dạng cố định — số rồi dấu
    # hai chấm rồi chuỗi base64url — nên quét luôn cả file theo hình dạng đó,
    # bất kể nó nằm ở đâu.
    import re

    token_shaped = re.search(r"\d{6,}:[A-Za-z0-9_-]{30,}", env)
    assert token_shaped is None, f"chuỗi giống token Telegram thật: {token_shaped.group()!r}"
