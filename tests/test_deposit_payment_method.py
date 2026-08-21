"""Tiền cọc phải ghi đúng phương thức khách trả (spec 21-08-2026).

Trước đợt này cả ba nơi ghi cọc đều cứng hoá 'cash': dữ liệu sản phẩm cho thấy
49/49 khoản cọc mang nhãn tiền mặt, kể cả khoản khách chuyển khoản — cuối ca
đếm két sẽ thiếu đúng những khoản đó.
"""

from decimal import Decimal
from pathlib import Path

from extensions import db
from models import Payment
from services import payment_service

ROOT = Path(__file__).resolve().parents[1]


def _source(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_normalize_accepts_the_three_supported_methods():
    for method in ("cash", "banking", "credit_card"):
        assert payment_service.normalize_payment_method(method) == method


def test_normalize_is_forgiving_about_case_and_spacing():
    assert payment_service.normalize_payment_method("  Banking ") == "banking"
    assert payment_service.normalize_payment_method("CREDIT_CARD") == "credit_card"


def test_normalize_falls_back_to_cash_instead_of_raising():
    """Đây là nhãn kế toán, không phải điều kiện an toàn: một lỗi gõ không được
    làm hỏng thao tác của lễ tân."""
    for value in ("bitcoin", "", None, 123):
        assert payment_service.normalize_payment_method(value) == "cash"


def test_new_booking_records_the_selected_deposit_method(client, seed_hotels, login_as):
    hotel, _, admin, _, br, _ = seed_hotels
    room_number = br.room.room_number
    br.status = "cancelled"          # giải phóng phòng seed để tạo booking mới
    db.session.commit()
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/create",
        json={
            "room_number": room_number,
            "status": "booked",
            "rental_type": "daily",
            "customer_name": "Khach Chuyen Khoan",
            "customer_phone": "0900777001",
            "check_in": "2026-10-01T14:00",
            "check_out": "2026-10-02T12:00",
            # Cọc phải đúng 50% hoặc 100% tiền phòng dự kiến, nếu không request
            # bị chặn TRƯỚC khi tới bước ghi sổ. Phòng seed 500.000/đêm x 1 đêm.
            "deposit": 500000,
            "deposit_payment_method": "banking",
            "source": "walk_in",
        },
    )

    assert response.get_json()["success"] is True, response.get_json()
    deposit = Payment.query.filter_by(payment_type="deposit").one()
    assert deposit.payment_method == "banking"


def test_group_booking_records_the_selected_deposit_method(client, seed_hotels, login_as):
    hotel, _, admin, _, br, _ = seed_hotels
    room_id = br.room_id
    br.status = "cancelled"
    db.session.commit()
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/bookings/api/bookings/group_create",
        json={
            "customer": {"phone": "0900777002", "name": "Doan Chuyen Khoan"},
            "room_ids": [room_id],
            "check_in": "2026-10-05",
            "check_out": "2026-10-06",
            "deposit": 500000,
            "deposit_payment_method": "credit_card",
        },
    )

    assert response.get_json()["success"] is True, response.get_json()
    deposit = Payment.query.filter_by(payment_type="deposit").one()
    assert deposit.payment_method == "credit_card"


def test_topping_up_a_deposit_records_the_selected_method(client, seed_hotels, login_as):
    hotel, _, admin, _, br, _ = seed_hotels
    br.room_deposit_amount = 0
    db.session.commit()
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json={
            "booking_id": br.booking_id,
            "booking_room_id": br.id,
            "room_id": br.room_id,
            "status": br.status,
            "check_in": "2026-10-01T14:00",
            "check_out": "2026-10-02T12:00",
            "deposit": 200000,
            "deposit_payment_method": "banking",
        },
    )

    assert response.get_json()["success"] is True, response.get_json()
    deposit = Payment.query.filter_by(payment_type="deposit").one()
    assert deposit.payment_method == "banking"


def test_deposit_defaults_to_cash_when_the_client_sends_nothing(client, seed_hotels, login_as):
    """Client cũ chưa biết trường mới vẫn phải chạy đúng như trước."""
    hotel, _, admin, _, br, _ = seed_hotels
    br.room_deposit_amount = 0
    db.session.commit()
    login_as(client, admin)

    client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json={
            "booking_id": br.booking_id,
            "booking_room_id": br.id,
            "room_id": br.room_id,
            "status": br.status,
            "check_in": "2026-10-01T14:00",
            "check_out": "2026-10-02T12:00",
            "deposit": 150000,
        },
    )

    assert Payment.query.filter_by(payment_type="deposit").one().payment_method == "cash"


def test_all_three_deposit_modals_offer_the_payment_method_choice():
    cases = (
        ("templates/rooms/_booking_modal.html", "bk-deposit-method"),
        ("templates/rooms/_group_booking_modal.html", "group-deposit-method"),
        ("templates/rooms/timeline.html", "edit-deposit-method"),
    )
    for rel, input_id in cases:
        source = _source(rel)
        assert f'id="{input_id}"' in source, f"{rel} thiếu input ẩn {input_id}"
        for method in ("cash", "banking", "credit_card"):
            assert f'data-method="{method}"' in source, f"{rel} thiếu nút {method}"
        assert "setDepositPaymentMethod" in source, f"{rel} chưa nối hàm chọn"


def test_each_deposit_button_writes_to_its_own_modal_hidden_input():
    """Đấu nhầm dây giữa ba modal là lỗi im lặng: nút vẫn sáng, nhưng phương
    thức rơi vào input ẩn của modal khác và payload gửi đi giá trị mặc định."""
    cases = (
        ("templates/rooms/_booking_modal.html", "bk-deposit-method"),
        ("templates/rooms/_group_booking_modal.html", "group-deposit-method"),
        ("templates/rooms/timeline.html", "edit-deposit-method"),
    )
    all_ids = {input_id for _, input_id in cases}
    for rel, input_id in cases:
        source = _source(rel)
        for method in ("cash", "banking", "credit_card"):
            expected = f"setDepositPaymentMethod('{method}', this, '{input_id}')"
            assert expected in source, f"{rel}: nút {method} chưa trỏ đúng {input_id}"
        for wrong in all_ids - {input_id}:
            assert f"this, '{wrong}')" not in source, f"{rel}: có nút trỏ nhầm sang {wrong}"


def test_each_method_group_declares_which_input_it_resets():
    """`resetDepositPaymentMethod` tìm nhóm nút qua `data-method-input`.

    Trước đó nó suy ra nhóm từ vị trí trong DOM (thẻ anh em liền trước). Suy theo
    vị trí hỏng lặng lẽ khi ai đó chèn thêm thẻ vào giữa: input ẩn vẫn về 'cash'
    nhưng nút "Chuyển khoản" vẫn sáng — dán nhãn sai đúng thứ nhánh này sinh ra
    để sửa. Thuộc tính liên kết tường minh làm phép tìm không phụ thuộc bố cục.
    """
    cases = (
        ("templates/rooms/_booking_modal.html", "bk-deposit-method"),
        ("templates/rooms/_group_booking_modal.html", "group-deposit-method"),
        ("templates/rooms/timeline.html", "edit-deposit-method"),
    )
    for rel, input_id in cases:
        assert f'data-method-input="{input_id}"' in _source(rel), (
            f"{rel}: nhóm nút chưa khai nó thuộc input {input_id}"
        )

    main_js = _source("static/js/main.js")
    assert "data-method-input" in main_js, "main.js chưa tìm nhóm qua thuộc tính liên kết"
    assert "previousElementSibling" not in _function_body(
        main_js, "resetDepositPaymentMethod"
    ), "vẫn còn suy nhóm nút theo vị trí trong DOM"


def test_shared_deposit_method_helper_lives_in_main_js():
    assert "function setDepositPaymentMethod(" in _source("static/js/main.js")


def test_cashier_report_labels_each_deposit_with_its_own_method(
    client, seed_hotels, login_as
):
    """Spec 21-08 §5.1: sổ quỹ nhóm đúng theo phương thức — tạo hai khoản cọc
    khác phương thức, gọi endpoint sổ quỹ, khẳng định mỗi dòng mang đúng nhãn.

    Trước fix này server ghi đúng payment_method vào Payment nhưng không trả
    lại giá trị đó trong response — chủ khách sạn mở Sổ Quỹ vẫn không thấy vì
    sao két thiếu tiền.
    """
    hotel, _, admin, _, br, _ = seed_hotels
    payment_service.record_deposit(
        booking_id=br.booking_id,
        amount=Decimal("500000"),
        payment_method="cash",
        note="Nhận cọc tiền mặt",
    )
    payment_service.record_deposit(
        booking_id=br.booking_id,
        amount=Decimal("700000"),
        payment_method="banking",
        note="Nhận cọc chuyển khoản",
    )
    db.session.commit()
    login_as(client, admin)

    response = client.get(f"/{hotel.slug}/cashier/api/reports/cashier?period=week")

    assert response.status_code == 200
    records = response.get_json()["data"]["records"]
    by_note = {row["note"]: row for row in records}
    assert by_note["Nhận cọc tiền mặt"]["payment_method"] == "cash"
    assert by_note["Nhận cọc tiền mặt"]["payment_method_label"] == "Tiền mặt"
    assert by_note["Nhận cọc chuyển khoản"]["payment_method"] == "banking"
    assert by_note["Nhận cọc chuyển khoản"]["payment_method_label"] == "Chuyển khoản"


def test_cashier_report_shows_a_neutral_label_for_a_deposit_correction(
    client, seed_hotels, login_as
):
    """Fix 5: một đính chính không phải tiền thật di chuyển — không được gắn
    nhãn phương thức thật (mặc định 'cash') vào một dòng không có tiền rời két."""
    hotel, _, admin, _, br, _ = seed_hotels
    payment_service.record_deposit_adjustment(
        booking_id=br.booking_id,
        amount=Decimal("-100000"),
        note="Điều chỉnh cọc: gõ nhầm số 0",
    )
    db.session.commit()
    login_as(client, admin)

    response = client.get(f"/{hotel.slug}/cashier/api/reports/cashier?period=week")

    row = next(
        r for r in response.get_json()["data"]["records"] if r["type_raw"] == "deposit_adjustment"
    )
    assert row["payment_method_label"] not in ("Tiền mặt", "cash")
    assert row["payment_method_label"] == "—"


def _function_body(source, name):
    """Cắt thân một hàm khai báo ở cấp cao nhất.

    Bốn hàm gửi payload đều là `function X(` ở cột 0, nên cắt tới `\nfunction `
    kế tiếp là đủ. Phải khớp cả dấu `(` — `saveBookingChangesFromDetail` có tiền
    tố trùng với `saveBookingChanges` và sẽ cắt nhầm nếu bỏ dấu ngoặc.
    """
    marker = f"function {name}("
    start = source.index(marker)
    rest = source[start + 1:]
    end = rest.find("\nfunction ")
    return rest if end == -1 else rest[:end]


def test_every_booking_path_sends_the_deposit_method():
    """Bốn nơi dựng payload, nằm rải ở ba file — trong đó `timeline_manager.js`
    có hai. Kiểm theo từng hàm chứ không grep cả file: grep cả file sẽ xanh ngay
    cả khi một trong hai hàm bị bỏ sót."""
    cases = (
        ("static/js/timeline_manager.js", "submitFullBooking"),
        ("static/js/timeline_manager.js", "saveBookingChanges"),
        ("static/js/room.js", "submitFullBooking"),
        ("static/js/group_booking.js", "submitGroupBooking"),
    )
    for rel, func in cases:
        body = _function_body(_source(rel), func)
        assert "deposit_payment_method" in body, f"{rel}::{func} chưa gửi phương thức"


def _listener_body(source, marker):
    """Cắt thân một listener ẩn danh đăng ký bằng addEventListener(...).

    Không có tên hàm để tìm '\\nfunction ' kế tiếp như _function_body, nên cắt
    tới dòng đóng '});' ở cột 0 — cách các listener trong codebase này kết thúc.
    """
    start = source.index(marker)
    rest = source[start + len(marker):]
    end = rest.find("\n});")
    return rest if end == -1 else rest[:end]


def test_shared_reset_helper_lives_in_main_js():
    assert "function resetDepositPaymentMethod(" in _source("static/js/main.js")


def test_every_modal_opener_resets_the_deposit_method_to_cash():
    """Bug sign-flipped của chính vấn đề branch này sửa: nút Chuyển khoản còn
    sáng từ booking trước ám vào booking cash tiếp theo, két bị dư đúng số đó.

    Kiểm theo từng hàm/listener mở modal, không grep cả file: một hàm bị bỏ sót
    vẫn phải bị bắt.
    """
    function_cases = (
        ("static/js/room.js", "openBookingModal"),
        ("static/js/timeline_manager.js", "openCreateModal"),
        ("static/js/timeline_manager.js", "openEditModal"),
    )
    for rel, func in function_cases:
        body = _function_body(_source(rel), func)
        assert "resetDepositPaymentMethod" in body, f"{rel}::{func} chưa reset phương thức cọc"

    group_source = _source("static/js/group_booking.js")
    listener_body = _listener_body(
        group_source,
        "addEventListener('show.bs.modal', function () {",
    )
    assert "resetDepositPaymentMethod" in listener_body, (
        "group_booking.js: listener mở modal chưa reset group-deposit-method"
    )
