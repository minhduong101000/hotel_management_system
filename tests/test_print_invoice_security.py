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
