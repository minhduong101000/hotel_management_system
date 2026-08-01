import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _assert_label_for(source, control_id):
    assert re.search(
        rf'<label\b[^>]*\bfor="{re.escape(control_id)}"',
        source,
    ), f"Thiếu label liên kết với #{control_id}"


def test_login_fields_have_linked_labels_and_announced_errors():
    source = _source("templates/auth/login.html")

    _assert_label_for(source, "username")
    _assert_label_for(source, "password")
    assert 'id="username"' in source
    assert 'id="password"' in source
    assert 'autocomplete="username"' in source
    assert 'autocomplete="current-password"' in source
    assert 'role="alert"' in source


def test_booking_modal_has_dialog_name_linked_labels_and_error_region():
    source = _source("templates/rooms/_booking_modal.html")

    assert 'aria-labelledby="bookingModalTitle"' in source
    assert 'id="bookingModalTitle"' in source
    assert 'aria-label="Đóng modal đặt phòng"' in source
    assert 'id="booking-form-status"' in source
    assert 'role="alert"' in source
    assert 'aria-live="assertive"' in source
    for control_id in (
        "bk-phone",
        "bk-name",
        "bk-cccd",
        "bk-address",
        "bk-deposit",
        "bk-note",
        "bk-daily-in",
        "bk-daily-out",
        "bk-hourly-in",
        "bk-hourly-out",
    ):
        _assert_label_for(source, control_id)


def test_customer_modal_has_linked_labels_error_region_and_busy_button():
    source = _source("templates/customers/index.html")

    assert 'aria-labelledby="modalTitle"' in source
    assert 'aria-label="Đóng modal khách hàng"' in source
    assert 'id="customer-form-status"' in source
    assert 'role="alert"' in source
    assert 'aria-live="assertive"' in source
    assert 'id="customer-save-button"' in source
    assert 'aria-busy="false"' in source
    for control_id in (
        "search-input",
        "cus-name",
        "cus-phone",
        "cus-cccd",
        "cus-email",
        "cus-address",
    ):
        _assert_label_for(source, control_id)


def test_checkout_modals_have_names_close_labels_and_announced_status():
    checkout = _source("templates/rooms/_checkout_modal.html")
    group_checkout = _source("templates/rooms/_group_checkout_modal.html")

    assert 'aria-labelledby="checkoutModalTitle"' in checkout
    assert 'id="checkoutModalTitle"' in checkout
    assert 'aria-label="Đóng hóa đơn phòng"' in checkout
    assert 'id="checkout-status"' in checkout
    assert 'aria-live="polite"' in checkout
    assert 'aria-busy="false"' in checkout

    assert 'aria-labelledby="groupCheckoutModalLabel"' in group_checkout
    assert 'aria-label="Đóng hóa đơn đoàn"' in group_checkout
    assert 'id="gc-checkout-status"' in group_checkout
    assert 'aria-live="polite"' in group_checkout
    assert 'aria-busy="false"' in group_checkout


def test_reschedule_errors_are_announced_and_async_buttons_expose_busy_state():
    template = _source("templates/rooms/timeline.html")
    script = _source("static/js/timeline_manager.js")

    assert 'id="reschedule-status"' in template
    assert 'role="alert"' in template
    assert 'aria-live="assertive"' in template
    assert 'aria-busy="false"' in template
    assert re.search(
        r'id="reschedule-room-select"[^>]*data-modal-initial-focus',
        template,
    )
    assert "showRescheduleStatus" in script
    assert "setRescheduleButtonBusy" in script
    assert ".focus()" in script


def test_shared_modal_helper_moves_and_restores_focus():
    base = _source("templates/layouts/base.html")
    helper = _source("static/js/modal_accessibility.js")

    assert "modal_accessibility.js" in base
    assert "shown.bs.modal" in helper
    assert "hidden.bs.modal" in helper
    assert "event.relatedTarget" in helper
    assert "focusOrigins" in helper
    assert ".focus(" in helper
    assert "document.readyState === 'loading'" in helper
    assert "bindModalAccessibility" in helper
    assert "window.requestAnimationFrame" not in helper
    assert "const explicitTarget = modal.querySelector('[data-modal-initial-focus]')" in helper
    assert "if (explicitTarget) return explicitTarget" in helper
    assert "findReplacementFocusOrigin" in helper
    assert "record.ariaLabel" in helper


def test_shared_focus_and_touch_targets_remain_visible_and_large_enough():
    source = _source("static/css/style.css")

    assert ":focus-visible" in source
    assert "outline: 3px solid var(--color-focus-ring)" in source
    assert ".customer-action-button" in source
    assert "min-width: 44px" in source
    assert "min-height: 44px" in source
    assert ".modal .btn-close" in source


def test_async_workflows_guard_double_submission_with_text_feedback():
    customer = _source("static/js/customer.js")
    checkout = _source("static/js/checkout.js")
    room = _source("static/js/room.js")
    timeline = _source("static/js/timeline_manager.js")

    assert "customerSubmitting" in customer
    assert "Đang lưu" in customer
    assert "checkoutSubmitting" in checkout
    assert "if (checkoutSubmitting) return" in checkout
    assert "groupCheckoutSubmitting" in checkout
    for script in (room, timeline):
        assert "beginBookingSubmission" in script
        assert "endBookingSubmission" in script
