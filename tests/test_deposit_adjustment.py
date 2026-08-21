"""Giảm cọc phải để lại bút toán — chính sách chốt 19-08.

Sổ tiền là append-only: sửa số thì thêm dòng, không đè dòng cũ.
"""

from decimal import Decimal

import pytest

from extensions import db
from models import Payment
from services import payment_service


def test_record_deposit_adjustment_writes_a_negative_ledger_row(app, seed_hotels):
    _, _, _, _, br, _ = seed_hotels

    payment = payment_service.record_deposit_adjustment(
        booking_id=br.booking_id,
        amount=Decimal("-4500000"),
        note="Điều chỉnh cọc: gõ nhầm số 0",
    )
    db.session.commit()

    assert payment.payment_type == "deposit_adjustment"
    assert payment.amount == Decimal("-4500000.00")
    assert "gõ nhầm" in payment.note


def test_record_deposit_adjustment_rejects_a_positive_amount(app, seed_hotels):
    """Tăng cọc là nhận thêm tiền — phải đi qua record_deposit."""
    _, _, _, _, br, _ = seed_hotels

    with pytest.raises(ValueError):
        payment_service.record_deposit_adjustment(
            booking_id=br.booking_id,
            amount=Decimal("100000"),
            note="sai hướng",
        )


def test_adjustment_lowers_the_refund_cap(app, seed_hotels):
    """Trần hoàn tiền = tổng đã thu, nên phải tụt theo dòng âm."""
    from services import refund_service

    _, _, _, _, br, _ = seed_hotels
    payment_service.record_deposit(
        booking_id=br.booking_id, amount=Decimal("5000000"), note="Nhận cọc"
    )
    db.session.commit()
    cap_before = refund_service.refundable_cap(br.booking)

    payment_service.record_deposit_adjustment(
        booking_id=br.booking_id,
        amount=Decimal("-4500000"),
        note="Điều chỉnh cọc: gõ nhầm số 0",
    )
    db.session.commit()

    assert cap_before == Decimal("5000000.00")
    assert refund_service.refundable_cap(br.booking) == Decimal("500000.00")


def test_customer_bill_sees_the_net_deposit_not_the_correction_pair(
    client, seed_hotels, login_as
):
    """Nội bộ thấy đủ hai dòng, hóa đơn khách chỉ thấy số ròng.

    Gọi endpoint billing thật (`/api/billing/detail/<booking_id>?type=booking`)
    thay vì tự lọc payment_type trong test, để khoá đúng hành vi thật của
    `_effective_refunds_data` (billing_controller.py) — hàm đó lọc
    payment_type == 'refund', nên dòng 'deposit_adjustment' không lọt ra
    bảng "hoàn tiền" trên hóa đơn khách; final_payment (tổng tiền đã thu) là
    phép cộng nên tự trừ đi phần điều chỉnh.
    """
    hotel, _, admin, _, br, _ = seed_hotels
    booking = br.booking
    payment_service.record_deposit(
        booking_id=br.booking_id, amount=Decimal("5000000"), note="Nhận cọc"
    )
    payment_service.record_deposit_adjustment(
        booking_id=br.booking_id,
        amount=Decimal("-4500000"),
        note="Điều chỉnh cọc: gõ nhầm số 0",
    )
    db.session.commit()

    payments = booking.payments
    assert len(payments) == 2   # sổ nội bộ: đủ 2 dòng

    login_as(client, admin)
    response = client.get(
        f"/{hotel.slug}/billing/api/billing/detail/{booking.id}?type=booking"
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["refunds"] == []             # điều chỉnh không phải hoàn tiền
    assert data["final_payment"] == 500000.0  # khách: số ròng


def test_cashier_report_labels_the_adjustment(client, seed_hotels, login_as):
    hotel, _, admin, _, br, _ = seed_hotels
    payment_service.record_deposit_adjustment(
        booking_id=br.booking_id,
        amount=Decimal("-4500000"),
        note="Điều chỉnh cọc: gõ nhầm số 0",
    )
    db.session.commit()
    login_as(client, admin)   # sổ quỹ là @admin_required

    response = client.get(f"/{hotel.slug}/cashier/api/reports/cashier?period=week")

    assert response.status_code == 200
    labels = [row["type_label"] for row in response.get_json()["data"]["records"]]
    assert "Điều chỉnh cọc" in labels


def test_cashier_report_kpi_classifies_adjustment_by_type_not_sign(
    client, seed_hotels, login_as
):
    """Reviewer finding (fix round 1): tổng hợp KPI phải theo payment_type,
    không theo dấu của amount.

    Trước khi sửa, cashier_controller cộng dồn theo dấu: mọi số âm (kể cả
    'deposit_adjustment') rơi vào total_refunded, khiến thẻ KPI "Tổng hoàn
    cọc" hiện sai — lẫn một bút toán điều chỉnh (không phải hoàn tiền cho
    khách) vào tổng hoàn tiền thực tế.
    """
    hotel, _, admin, _, br, _ = seed_hotels
    payment_service.record_deposit(
        booking_id=br.booking_id, amount=Decimal("5000000"), note="Nhận cọc"
    )
    payment_service.record_deposit_adjustment(
        booking_id=br.booking_id,
        amount=Decimal("-4500000"),
        note="Điều chỉnh cọc: gõ nhầm số 0",
    )
    db.session.commit()
    login_as(client, admin)

    response = client.get(f"/{hotel.slug}/cashier/api/reports/cashier?period=week")

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["total_refunded"] == 0.0        # điều chỉnh không phải hoàn tiền
    assert data["total_received"] == 500000.0   # đã trừ đúng phần điều chỉnh
    assert data["net_amount"] == 500000.0        # số ròng không đổi


def _update_payload(br, deposit, reason=None, change_type=None):
    payload = {
        "booking_id": br.booking_id,
        "booking_room_id": br.id,
        "room_id": br.room_id,
        "status": br.status,
        "check_in": "2026-08-19T14:00",
        "check_out": "2026-08-20T12:00",
        "deposit": deposit,
    }
    if reason is not None:
        payload["deposit_reason"] = reason
    if change_type is not None:
        payload["deposit_change_type"] = change_type
    return payload


def test_lowering_a_deposit_without_a_reason_is_rejected(client, seed_hotels, login_as):
    hotel, _, admin, _, br, _ = seed_hotels
    br.room_deposit_amount = 5000000
    br.room_deposit_original = 5000000
    db.session.commit()
    login_as(client, admin)
    before = Payment.query.count()

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json=_update_payload(br, 500000, change_type="correction"),
    )

    body = response.get_json()
    assert body["success"] is False
    assert body["error_code"] == "deposit_reason_required"
    db.session.refresh(br)
    assert float(br.room_deposit_amount) == 5000000.0   # không đổi gì
    assert Payment.query.count() == before


def test_lowering_a_deposit_with_a_reason_leaves_a_trace(client, seed_hotels, login_as):
    hotel, _, admin, _, br, _ = seed_hotels
    br.room_deposit_amount = 5000000
    br.room_deposit_original = 5000000
    db.session.commit()
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json=_update_payload(br, 500000, reason="gõ nhầm số 0", change_type="correction"),
    )

    assert response.get_json()["success"] is True, response.get_json()
    db.session.refresh(br)
    assert float(br.room_deposit_amount) == 500000.0
    # Số cọc GỐC phải còn nguyên — đây là bản ghi duy nhất về số ban đầu
    assert float(br.room_deposit_original) == 5000000.0
    adjustment = Payment.query.filter_by(payment_type="deposit_adjustment").one()
    assert float(adjustment.amount) == -4500000.0
    assert "gõ nhầm số 0" in adjustment.note


def test_raising_a_deposit_needs_no_reason(client, seed_hotels, login_as):
    hotel, _, admin, _, br, _ = seed_hotels
    br.room_deposit_amount = 500000
    br.room_deposit_original = 500000
    db.session.commit()
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json=_update_payload(br, 800000),
    )

    assert response.get_json()["success"] is True
    assert Payment.query.filter_by(payment_type="deposit").count() == 1


def test_lowering_a_deposit_to_zero_still_keeps_the_original_mark(
    client, seed_hotels, login_as
):
    """Biên: giảm cọc VỀ 0 (không phải chỉ giảm một phần) vẫn phải đi qua
    cùng đường tiền — bút toán đối ứng đúng bằng -old_deposit, và
    room_deposit_original không bị xóa dấu vết.
    """
    hotel, _, admin, _, br, _ = seed_hotels
    br.room_deposit_amount = 5000000
    br.room_deposit_original = 5000000
    db.session.commit()
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json=_update_payload(
            br, 0, reason="Gõ nhầm số 0 khi nhận cọc", change_type="correction"
        ),
    )

    assert response.get_json()["success"] is True, response.get_json()
    db.session.refresh(br)
    assert float(br.room_deposit_amount) == 0.0
    assert float(br.room_deposit_original) == 5000000.0
    adjustment = Payment.query.filter_by(payment_type="deposit_adjustment").one()
    assert float(adjustment.amount) == -5000000.0


def test_lowering_a_deposit_without_stating_the_intent_is_rejected(
    client, seed_hotels, login_as
):
    """Có lý do bằng chữ vẫn chưa đủ: phải nói rõ tiền có rời két hay không."""
    from models.audit_event import AuditEvent

    hotel, _, admin, _, br, _ = seed_hotels
    br.room_deposit_amount = 5000000
    br.room_deposit_original = 5000000
    db.session.commit()
    login_as(client, admin)
    payments_before = Payment.query.count()
    audit_before = AuditEvent.query.count()

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json=_update_payload(br, 500000, reason="gõ nhầm số 0"),
    )

    body = response.get_json()
    assert body["success"] is False
    assert body["error_code"] == "deposit_change_type_required"
    db.session.refresh(br)
    assert float(br.room_deposit_amount) == 5000000.0     # không đổi gì
    assert Payment.query.count() == payments_before
    assert AuditEvent.query.count() == audit_before   # từ chối thì không ghi nhật ký


def test_money_returned_to_the_guest_is_pushed_to_the_refund_flow(
    client, seed_hotels, login_as
):
    """Điều chỉnh cọc không có trần cứng và không hiện trên hóa đơn khách, nên
    nó không được dùng làm đường cho tiền rời két."""
    from models.audit_event import AuditEvent

    hotel, _, admin, _, br, _ = seed_hotels
    br.room_deposit_amount = 5000000
    br.room_deposit_original = 5000000
    db.session.commit()
    login_as(client, admin)
    payments_before = Payment.query.count()
    audit_before = AuditEvent.query.count()

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json=_update_payload(
            br, 0, reason="khách hủy, đã đưa lại tiền", change_type="returned_to_guest"
        ),
    )

    body = response.get_json()
    assert body["success"] is False
    assert body["error_code"] == "use_refund_flow"
    assert "Hoàn tiền" in body["msg"]
    db.session.refresh(br)
    assert float(br.room_deposit_amount) == 5000000.0
    assert Payment.query.count() == payments_before
    assert AuditEvent.query.count() == audit_before   # từ chối thì không ghi nhật ký


def test_an_unknown_change_type_is_rejected_like_a_missing_one(
    client, seed_hotels, login_as
):
    hotel, _, admin, _, br, _ = seed_hotels
    br.room_deposit_amount = 5000000
    br.room_deposit_original = 5000000
    db.session.commit()
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json=_update_payload(
            br, 500000, reason="gõ nhầm", change_type="something_else"
        ),
    )

    assert response.get_json()["error_code"] == "deposit_change_type_required"


def test_the_audit_trail_keeps_the_stated_intent(client, seed_hotels, login_as):
    """Đối soát về sau phải đọc được mục đích, không chỉ câu chữ tự do."""
    from models.audit_event import AuditEvent

    hotel, _, admin, _, br, _ = seed_hotels
    br.room_deposit_amount = 5000000
    br.room_deposit_original = 5000000
    db.session.commit()
    login_as(client, admin)

    client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json=_update_payload(
            br, 500000, reason="gõ nhầm số 0", change_type="correction"
        ),
    )

    event = AuditEvent.query.filter_by(action="deposit_adjustment").one()
    assert event.after_data["change_type"] == "correction"
    assert event.after_data["reason"] == "gõ nhầm số 0"
