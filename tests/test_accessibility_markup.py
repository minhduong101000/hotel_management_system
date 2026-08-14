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


def test_login_exposes_password_toggle_and_submit_status():
    source = _source("templates/auth/login.html")
    styles = _source("static/css/style.css")

    assert 'id="login-password-toggle"' in source
    assert 'type="button"' in source
    assert 'aria-controls="password"' in source
    assert 'aria-pressed="false"' in source
    assert 'aria-label="Hiện mật khẩu"' in source
    assert 'id="login-submit"' in source
    assert 'aria-busy="false"' in source
    assert 'aria-describedby="login-form-status"' in source
    assert 'id="login-form-status"' in source
    assert 'role="status"' in source
    assert 'aria-live="polite"' in source
    assert re.search(
        r"\.login-password-toggle\s*\{[^}]*min-width:\s*44px[^}]*min-height:\s*44px",
        styles,
        re.DOTALL,
    )
    assert re.search(
        r"\.btn-login\s*\{[^}]*min-height:\s*48px",
        styles,
        re.DOTALL,
    )
    assert re.search(
        r"\.input-wrapper\s+input:focus-visible\s*\{[^}]*outline:\s*3px\s+solid\s+var\(--color-info\)",
        styles,
        re.DOTALL,
    )


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


def test_billing_filters_and_dynamic_detail_actions_have_accessible_names():
    source = _source("templates/billing/index.html")

    _assert_label_for(source, "billing-start-date")
    _assert_label_for(source, "billing-end-date")
    assert 'aria-label="Đóng chi tiết hóa đơn"' in source
    assert "button.setAttribute('aria-label', detailLabel)" in source
    assert 'button.title = detailLabel' in source
    assert 'data-table-state-row' in source
    assert 'role="status"' in source


def test_warehouse_modals_have_names_linked_labels_and_announced_status():
    source = _source("templates/warehouse/index.html")

    for modal_title_id in (
        "itemModalTitle",
        "restockModalTitle",
        "batchModalTitle",
        "disposeModalTitle",
        "adjustModalTitle",
    ):
        assert f'aria-labelledby="{modal_title_id}"' in source
        assert f'id="{modal_title_id}"' in source
    for close_label in (
        "Đóng modal vật tư",
        "Đóng modal nhập kho",
        "Đóng danh sách lô hàng",
        "Đóng modal hủy hàng",
        "Đóng modal điều chỉnh tồn",
    ):
        assert f'aria-label="{close_label}"' in source
    for control_id in (
        "item-code",
        "item-name",
        "item-unit",
        "item-quantity",
        "item-min",
        "item-service",
        "restock-qty",
        "restock-expires-at",
        "dispose-quantity",
        "dispose-reason",
        "adjust-quantity",
        "adjust-reason",
    ):
        _assert_label_for(source, control_id)
    assert source.count('role="alert"') >= 4
    assert source.count('aria-live="assertive"') >= 4


def test_finance_filters_forms_and_modals_have_accessible_names():
    revenue = _source("templates/reports/revenue.html")
    cashier = _source("templates/reports/cashier.html")
    expenses = _source("templates/reports/expenses.html")

    for control_id in ("period-select", "date-start", "date-end"):
        _assert_label_for(revenue, control_id)
    assert 'id="revenue-feedback"' in revenue
    assert 'aria-live="polite"' in revenue

    for control_id in (
        "start-date",
        "end-date",
        "deposit-booking-id",
    ):
        _assert_label_for(cashier, control_id)
    assert 'id="cashier-filter-status"' in cashier
    assert 'id="deposit-print-status"' in cashier

    for control_id in (
        "filter-start",
        "filter-end",
        "filter-category",
        "exp-category",
        "exp-amount",
        "exp-date",
        "exp-desc",
        "wh-existing-item",
        "wh-code",
        "wh-name",
        "wh-unit",
        "wh-qty",
        "wh-min",
        "wh-service",
        "svc-existing-service",
        "svc-name",
        "svc-price",
        "void-expense-reason",
    ):
        _assert_label_for(expenses, control_id)
    assert 'aria-labelledby="expenseModalTitle"' in expenses
    assert 'aria-label="Đóng modal thêm chi phí"' in expenses
    assert 'aria-labelledby="voidExpenseModalTitle"' in expenses
    assert 'aria-label="Đóng modal hủy ghi nhận chi phí"' in expenses
    assert expenses.count('role="alert"') >= 2
    assert expenses.count('aria-live="assertive"') >= 2


def test_staff_audit_and_master_forms_keep_linked_labels_and_named_actions():
    staff = _source("templates/staff/index.html")
    audit = _source("templates/audit/index.html")
    master_login = _source("templates/master/login.html")
    master_dashboard = _source("templates/master/dashboard.html")

    for control_id in ("staff-username", "staff-password", "staff-role"):
        _assert_label_for(staff, control_id)
    assert 'aria-label="Lưu mật khẩu mới cho {{ user.username }}"' in staff

    for control_id in (
        "audit-start",
        "audit-end",
        "audit-group",
        "audit-action",
        "audit-entity",
    ):
        _assert_label_for(audit, control_id)
    assert 'id="audit-feedback"' in audit
    assert 'aria-live="polite"' in audit

    for control_id in ("master-username", "master-password"):
        _assert_label_for(master_login, control_id)
    for control_id in ("hotel-name", "hotel-slug", "admin-username", "admin-password"):
        _assert_label_for(master_dashboard, control_id)


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


def test_shared_buttons_keep_touch_targets_busy_feedback_and_reduced_motion():
    source = _source("static/css/style.css")

    assert ".btn-icon" in source
    assert '.app-content .btn[aria-busy="true"]' in source
    assert "touch-action: manipulation" in source
    assert "@media (prefers-reduced-motion: reduce)" in source


def test_refreshed_modal_close_buttons_all_have_accessible_names():
    templates = (
        "templates/rooms/map.html",
        "templates/rooms/timeline.html",
        "templates/rooms/_booking_modal.html",
        "templates/rooms/_checkout_modal.html",
        "templates/rooms/_group_booking_modal.html",
        "templates/rooms/_group_checkout_modal.html",
        "templates/rooms/_qr_scanner_modal.html",
        "templates/customers/index.html",
        "templates/billing/index.html",
        "templates/warehouse/index.html",
        "templates/services/index.html",
        "templates/admin/price_manager.html",
        "templates/reports/expenses.html",
    )

    for template in templates:
        source = _source(template)
        close_buttons = re.findall(
            r'<button\b[^>]*\bclass="[^"]*\bbtn-close\b[^"]*"[^>]*>',
            source,
            re.DOTALL,
        )
        assert close_buttons, f"Không tìm thấy nút đóng trong {template}"
        for button in close_buttons:
            assert 'aria-label="' in button, f"Nút đóng chưa có tên trong {template}"


def test_group_booking_and_timeline_editor_keep_labels_linked_to_controls():
    group_booking = _source("templates/rooms/_group_booking_modal.html")
    timeline = _source("templates/rooms/timeline.html")

    for control_id in (
        "g_check_in",
        "g_check_out",
        "group_phone",
        "group_name",
        "group_cccd",
        "group_address",
        "group_total_deposit",
        "group_note",
    ):
        _assert_label_for(group_booking, control_id)

    for control_id in (
        "edit-customer",
        "edit-room-select",
        "edit-cccd",
        "edit-address",
        "edit-status",
        "edit-checkin",
        "edit-checkout",
        "edit-deposit",
        "refund-reason",
    ):
        _assert_label_for(timeline, control_id)


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
