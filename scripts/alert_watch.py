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
