"""Tờ hóa đơn IN phải liệt kê đúng các dòng mà màn hình đang hiện.

Màn hình (renderBookingDetailServices) ưu tiên bookingDetailRoomBreakdown —
mảng nhiều dòng: tiền từng đêm, phụ thu trả muộn... Nếu bản in gộp tất cả
thành một dòng tổng thì khách cầm tờ giấy không biết mình bị thu thêm vì cái
gì, dù con số tổng vẫn khớp.

Test chạy chính hàm buildPrintRows() cắt ra từ file JS thật bằng node, thay vì
đoán qua văn bản nguồn.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TIMELINE_JS = ROOT / "static" / "js" / "timeline_manager.js"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="cần node để chạy hàm JS thật"
)


def _slice(source, start_marker, end_marker):
    start = source.index(start_marker)
    return source[start : source.index(end_marker, start)]


def _build_print_rows(
    *,
    breakdown=(),
    room_fee=0,
    room_line=None,
    services=(),
):
    source = TIMELINE_JS.read_text(encoding="utf-8")
    state = {
        "bookingDetailRoomBreakdown": list(breakdown),
        "bookingDetailRoomFee": room_fee,
        "bookingDetailRoomLine": room_line or {"name": "Tiền phòng", "price": room_fee},
        "bookingDetailServicesLines": list(services),
    }
    script = f"""
const state = {json.dumps(state, ensure_ascii=False)};
var bookingDetailRoomBreakdown = state.bookingDetailRoomBreakdown;
var bookingDetailRoomFee = state.bookingDetailRoomFee;
var bookingDetailRoomLine = state.bookingDetailRoomLine;
var bookingDetailServicesLines = state.bookingDetailServicesLines;
function escapeHtml(value) {{
    return (value == null ? '' : String(value))
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}}
{_slice(source, "function formatVND(", "function parseDateInput(")}
{_slice(source, "function buildPrintRows()", "function bdPrintInvoice()")}
process.stdout.write(buildPrintRows());
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as handle:
        handle.write(script)
        handle.flush()
        result = subprocess.run(
            [shutil.which("node"), handle.name],
            capture_output=True,
            text=True,
            check=True,
        )
    return result.stdout


def test_print_keeps_every_breakdown_line_including_the_late_checkout_surcharge():
    """Ca hỏng có thật: khách trả muộn 3 tiếng, màn hình hiện 2 dòng, tờ in
    trước đây chỉ có một dòng 1.000.000 đ không giải thích gì."""
    html = _build_print_rows(
        breakdown=[
            {"label": "Tiền phòng", "detail": "1 đêm", "amount": 800000},
            {"label": "Phụ thu phát sinh", "detail": "Muộn 3.0h", "amount": 200000},
        ],
        room_fee=1000000,
    )

    assert "Phụ thu phát sinh" in html, "bản in mất dòng phụ thu"
    assert "Muộn 3.0h" in html, "bản in mất phần diễn giải phụ thu"
    assert "800.000 đ" in html and "200.000 đ" in html
    assert html.count("<tr>") == 2, "phải in đúng số dòng màn hình đang hiện"
    assert "1.000.000 đ" not in html, "không được gộp lại thành một dòng tổng"


def test_print_numbers_breakdown_and_service_rows_in_one_sequence():
    html = _build_print_rows(
        breakdown=[
            {"label": "Tiền phòng", "amount": 500000},
            {"label": "Phụ thu phát sinh", "amount": 100000},
        ],
        room_fee=600000,
        services=[{"name": "Nuoc suoi", "quantity": 2, "price": 15000}],
    )

    assert html.count("<tr>") == 3
    for order in ("<td>1</td>", "<td>2</td>", "<td>3</td>"):
        assert order in html


def test_print_falls_back_to_the_single_room_line_without_a_breakdown():
    html = _build_print_rows(room_fee=450000, room_line={"name": "Tiền phòng", "price": 450000})

    assert html.count("<tr>") == 1
    assert "450.000 đ" in html


def test_print_shows_a_zero_room_line_just_like_the_screen():
    """Màn hình vẫn vẽ dòng `0 đ`; bản in im lặng thì hai bên lệch nhau."""
    html = _build_print_rows(room_fee=0, room_line={"name": "Tiền phòng", "price": 0})

    assert html.count("<tr>") == 1
    assert "0 đ" in html


def test_print_escapes_the_breakdown_label_and_detail():
    """label mang rule_tag = tên rule giá do admin nhập tự do."""
    html = _build_print_rows(
        breakdown=[
            {
                "label": "<img src=x onerror=alert(1)>",
                "detail": "<script>alert(2)</script>",
                "amount": 100000,
            }
        ],
        room_fee=100000,
    )

    assert "<img" not in html and "<script>" not in html
    assert "&lt;img" in html and "&lt;script&gt;" in html
