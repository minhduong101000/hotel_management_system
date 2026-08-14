import re
from pathlib import Path


def _source(path):
    return Path(path).read_text(encoding="utf-8")


def _assert_label_for(source, control_id):
    assert re.search(
        rf'<label\b[^>]*\bfor="{re.escape(control_id)}"', source
    ), f"Thiếu label liên kết với #{control_id}"
    assert re.search(
        rf'\bid="{re.escape(control_id)}"', source
    ), f"Thiếu control #{control_id}"


def test_refund_modal_has_labeled_controls_and_context_numbers():
    billing = _source("templates/billing/index.html")
    assert 'id="refundModal"' in billing
    for control_id in (
        "refund-base-unused",
        "refund-base-total",
        "refund-percent-input",
        "refund-amount-input",
        "refund-method",
        "refund-reason-input",
    ):
        _assert_label_for(billing, control_id)
    # Ba con số ngữ cảnh bắt buộc (điền từ server preview)
    for span_id in ("refund-cap", "refund-base-value", "refund-already"):
        assert f'id="{span_id}"' in billing, f"Thiếu #{span_id}"
    # Khu báo lỗi phải là live region
    assert re.search(
        r'id="refund-error"[^>]*role="alert"|role="alert"[^>]*id="refund-error"',
        billing,
    )
    # Nút xác nhận hiển thị số tiền quy đổi
    assert 'id="refund-confirm-amount"' in billing
    # Nút mở form nằm trong footer modal hóa đơn
    assert 'id="btn-open-refund"' in billing


def test_refund_js_uses_server_preview_not_client_math():
    js = _source("static/js/refund.js")
    assert "/api/refunds/preview" in js
    assert "/api/refunds" in js
    assert "crypto.randomUUID" in js, "client_key phải sinh ngẫu nhiên cho idempotency"
    # Số tiền hiển thị lấy từ response server (refund_amount), không tự nhân % ở client
    assert "refund_amount" in js
    assert "toLocaleString" in js


def test_billing_bill_renders_effective_refunds_section():
    billing = _source("templates/billing/index.html")
    assert 'id="md-refunds-section"' in billing
    assert 'id="md-refunds-body"' in billing
