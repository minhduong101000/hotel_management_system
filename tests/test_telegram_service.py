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


@pytest.mark.parametrize(
    "make_exc",
    [
        lambda: OSError("mạng hỏng"),
        lambda: RuntimeError("lỗi bất ngờ không liên quan mạng"),
    ],
    ids=["OSError", "RuntimeError"],
)
def test_a_network_error_does_not_escape_and_kill_the_loop(make_exc):
    """Bộ canh chạy vòng lặp vô hạn. Một ngoại lệ thoát ra là container chết và
    hệ thống cảnh báo im lặng — đúng thứ nó sinh ra để chống.

    Tham số hoá cả OSError (lỗi mạng điển hình) lẫn RuntimeError (một ngoại lệ
    bất kỳ khác) để chắc chắn cài đặt bắt Exception nói chung, chứ không chỉ
    bắt riêng OSError rồi để lọt các loại lỗi khác thoát ra ngoài."""

    def transport(url, payload, timeout):
        raise make_exc()

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
    `str(exc)` vào log là ghi thẳng token ra đĩa.

    Kiểm cả chuỗi token đầy đủ lẫn từng nửa của nó (id số đứng trước dấu hai
    chấm, và phần bí mật đứng sau) — một rò rỉ một phần (ví dụ chỉ lộ id số)
    vẫn phải bị bắt, không chỉ rò rỉ toàn bộ chuỗi mới bị bắt."""
    bot_id, _, secret = TOKEN.partition(":")

    outcome = telegram_service.send_message(
        "xin chào", bot_token=TOKEN, chat_id=CHAT, transport=transport
    )

    assert not outcome.delivered
    assert TOKEN not in outcome.reason
    assert "FAKE-TOKEN" not in outcome.reason
    assert bot_id not in outcome.reason
    assert secret not in outcome.reason


def test_send_message_adds_no_third_party_dependency():
    """requirements.txt không có requests/httpx — cố ý. Dùng urllib của thư viện
    chuẩn, đúng như healthcheck trong docker-compose.yml."""
    from pathlib import Path

    source = Path(telegram_service.__file__).read_text(encoding="utf-8")
    assert "import requests" not in source
    assert "import httpx" not in source
    assert "urllib" in source
