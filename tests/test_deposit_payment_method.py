"""Tiền cọc phải ghi đúng phương thức khách trả (spec 21-08-2026).

Trước đợt này cả ba nơi ghi cọc đều cứng hoá 'cash': dữ liệu sản phẩm cho thấy
49/49 khoản cọc mang nhãn tiền mặt, kể cả khoản khách chuyển khoản — cuối ca
đếm két sẽ thiếu đúng những khoản đó.
"""

from extensions import db
from models import Payment
from services import payment_service


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
