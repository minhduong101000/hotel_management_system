"""4 luồng smoke trình duyệt + 2 bất biến toàn cục (console sạch, không 4xx/5xx).

B2 và B4 tái diễn đúng hai bug 14-08 (autofill 404, add-room sai blueprint) —
lưới này tồn tại để lớp lỗi đó không bao giờ lọt lần nữa.
"""

import pytest

from tests.browser.conftest import SLUG, SMOKE_NAME, SMOKE_PHONE, ROOM_B

pytestmark = pytest.mark.browser


def test_b1_login_shows_room_map(admin_page, base):
    assert admin_page.locator(".room-map-grid-shell").is_visible()


def test_b2_phone_autofill_finds_returning_customer(seeded, admin_page, base):
    page = admin_page
    page.goto(f"{base}/{SLUG}/rooms/timeline-view")
    page.evaluate(
        "bootstrap.Modal.getOrCreateInstance(document.getElementById('bookingModal')).show()"
    )
    page.fill("#bk-phone", SMOKE_PHONE)
    # debounce 500ms + fetch; guard 404 sẽ bắt nếu fetch sai prefix tenant
    page.wait_for_function(
        f"document.getElementById('bk-name').value === '{SMOKE_NAME}'",
        timeout=8_000,
    )


def test_b3_refund_modal_shows_server_preview_numbers(seeded, admin_page, base):
    page = admin_page
    page.goto(f"{base}/{SLUG}/billing/billing")
    page.evaluate(f"openRefundModal({seeded['booking_id']})")
    page.wait_for_selector("#refundModal.show", timeout=8_000)
    # 3 con số ngữ cảnh phải được server preview điền (không còn '—')
    for span in ("refund-cap", "refund-base-value", "refund-already"):
        page.wait_for_function(
            f"document.getElementById('{span}').textContent.trim() !== '—'"
            f" && document.getElementById('{span}').textContent.trim() !== ''",
            timeout=8_000,
        )
    cap_text = page.text_content("#refund-cap")
    assert "250" in cap_text.replace(".", "").replace(",", ""), cap_text


def test_b4_add_room_button_reaches_real_endpoint(seeded, admin_page, base):
    page = admin_page
    page.goto(f"{base}/{SLUG}/rooms/timeline-view")
    page.evaluate(
        "bootstrap.Modal.getOrCreateInstance(document.getElementById('editBookingModal')).show()"
    )
    page.evaluate(
        f"document.getElementById('edit-booking-id').value = '{seeded['booking_id']}'"
    )
    # Modal đang mở sẵn khung giờ trống -> điền cùng cửa sổ với booking seed
    page.evaluate(
        f"document.getElementById('edit-checkin').value = '{seeded['check_in']}'"
    )
    page.evaluate(
        f"document.getElementById('edit-checkout').value = '{seeded['check_out']}'"
    )

    alerts = []

    def handle_dialog(dialog):
        if dialog.type == "prompt":
            dialog.accept(ROOM_B)
        else:
            alerts.append(dialog.message)
            dialog.accept()

    page.on("dialog", handle_dialog)
    page.click("#btn-add-room")
    page.wait_for_timeout(2_500)  # prompt -> fetch -> alert
    assert alerts, "Không nhận được phản hồi nào từ nút Thêm phòng"
    assert "Đã thêm phòng" in alerts[-1], alerts


def test_b5_print_invoice_does_not_execute_injected_guest_name(admin_page, base):
    """Tên khách độc hại không được chạy trong cửa sổ in.

    bdPrintInvoice đọc textContent của #bd-customer-label rồi ghép thẳng vào
    HTML, nên đặt textContent đúng bằng payload là tái lập chính xác đường đi
    của tên khách do server trả về verbatim. Mở modal bằng JS như B2/B4.
    """
    page = admin_page
    page.goto(f"{base}/{SLUG}/rooms/timeline-view")
    page.evaluate(
        "bootstrap.Modal.getOrCreateInstance("
        "document.getElementById('bookingDetailModal')).show()"
    )
    page.wait_for_selector("#bookingDetailModal.show", timeout=8_000)
    page.evaluate("window.__xssFired = false")
    page.evaluate(
        "document.getElementById('bd-customer-label').textContent ="
        " '<img src=x onerror=\"window.opener.__xssFired = true\">'"
    )

    with page.expect_popup() as popup_info:
        page.click('button[onclick="bdPrintInvoice()"]')
    popup = popup_info.value
    popup.wait_for_load_state()
    page.wait_for_timeout(1_000)

    assert page.evaluate("window.__xssFired") is False
    popup.close()
