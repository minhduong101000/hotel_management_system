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
