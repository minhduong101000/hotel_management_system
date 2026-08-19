"""Cửa sổ in hóa đơn là sink XSS: nó document.write chuỗi HTML tự ghép.

Popup mở bằng window.open('', '_blank') nên same-origin với app, và app không
có CSP, nên mã trong tên khách sẽ chạy với phiên của người bấm in.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_shared_escape_helper_exists_in_main_js():
    main_js = _source("static/js/main.js")
    assert "function escapeHtml(" in main_js
    assert "textContent" in main_js


def test_print_invoice_escapes_every_interpolated_field():
    script = _source("static/js/timeline_manager.js")
    start = script.index("function bdPrintInvoice()")
    end = script.index("function bdUpdateServiceQty(")
    body = script[start:end]

    for raw in ("${customer}", "${bookingCode}", "${room}", "${total}", "${created}"):
        assert raw not in body, f"{raw} chưa được escape trong bdPrintInvoice"
    for safe in (
        "${escapeHtml(customer)}",
        "${escapeHtml(bookingCode)}",
        "${escapeHtml(room)}",
    ):
        assert safe in body, f"thiếu {safe}"
    # Không được sao chép innerHTML của bảng: nó kế thừa mọi chỗ chưa escape
    assert "bd-invoice-table-body')?.innerHTML" not in body
    assert "buildPrintRows(" in body


def test_service_and_room_names_are_escaped_before_innerhtml():
    """Tên dịch vụ do admin nhập; tenant admin thù địch không được chạy JS
    trong trình duyệt của mọi lễ tân."""
    for rel, raw in (
        ("static/js/checkout.js", "${item.name}"),
        ("static/js/service.js", "${item.name}"),
        ("static/js/timeline_manager.js", "${line.name || 'Dich vu'}"),
    ):
        assert raw not in _source(rel), f"{rel} còn nội suy thô {raw}"


def test_checkout_uses_the_shared_escape_helper():
    checkout = _source("static/js/checkout.js")
    assert "function checkoutEscapeHtml" not in checkout
    assert "escapeHtml(" in checkout


def test_room_number_options_are_built_via_dom_api_not_html_attribute_interpolation():
    """escapeHtml() chỉ an toàn cho nội dung text, KHÔNG cho thuộc tính HTML
    (nó không escape dấu nháy kép). Số phòng là chuỗi tự do admin nhập; nếu
    nội suy vào `data-room-number="${...}"` hay `title="${...}"` thì một số
    phòng chứa `"` có thể thoát khỏi thuộc tính và chèn handler sự kiện.
    Phải dựng <option> bằng DOM API (createElement/dataset/textContent) để
    loại bỏ cả lớp lỗi, thay vì escape thủ công cho từng ngữ cảnh."""
    script = _source("static/js/timeline_manager.js")
    start = script.index("async function openBookingDetailModal(")
    end = script.index("roomSelect.onchange = () => {")
    body = script[start:end]

    forbidden = (
        'data-room-number="${',
        'title="${',
        "roomSelect.innerHTML +=",
    )
    for pattern in forbidden:
        assert pattern not in body, f"còn nội suy thô vào thuộc tính HTML: {pattern}"

    assert body.count("document.createElement('option')") == 2
    assert "option.dataset.roomNumber = r.room_number" in body
    assert "option.dataset.roomNumber = roomNumber" in body
    assert "option.title = statusLabel" in body
    assert "option.textContent = r.room_number" in body
    assert "option.textContent = roomNumber" in body
