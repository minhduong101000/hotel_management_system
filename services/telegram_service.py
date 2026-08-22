"""Gửi một tin nhắn Telegram.

Dùng `urllib.request` của thư viện chuẩn: repo cố ý không có `requests`, và
`docker-compose.yml` cũng đã dùng `urllib.request` cho healthcheck.
"""

from __future__ import annotations

import json
import urllib.error
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
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        # urlopen NÉM với 4xx/5xx thay vì trả mã. Không bắt ở đây thì mọi lỗi
        # thật (401 sai token, 400 sai chat_id, 429 quá tần suất) đều rơi vào
        # nhánh chung và mất mã — mà mã chính là thứ phân biệt chúng.
        return exc.code


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

    send = transport or _urllib_transport

    try:
        payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
        url = f"{API_BASE}/bot{bot_token}/sendMessage"
        status = send(url, payload, timeout)
    except Exception as exc:                     # noqa: BLE001 — vòng lặp không được chết
        return SendOutcome(False, f"không gửi được ({type(exc).__name__})")

    if status != 200:
        return SendOutcome(False, f"Telegram trả về HTTP {status}")

    return SendOutcome(True, "đã gửi")
