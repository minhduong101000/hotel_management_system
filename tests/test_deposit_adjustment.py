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
