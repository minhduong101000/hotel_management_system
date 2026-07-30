from pathlib import Path

from extensions import db
from models import Customer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CUSTOMER_SCRIPT = PROJECT_ROOT / "static" / "js" / "customer.js"


def test_customer_api_keeps_untrusted_values_as_json_data(
    client, seed_hotels, login_as
):
    hotel, _, admin, _, _, _ = seed_hotels
    payload = {
        "name": '<img src=x onerror="window.reviewXss=123">',
        "phone": "' onclick='window.reviewXss=456",
        "email": "<svg/onload=window.reviewXss=789>@example.test",
        "cccd": "xss-customer",
        "address": '"><script>window.reviewXss=999</script>',
    }
    customer = Customer(hotel_id=hotel.id, **payload)
    db.session.add(customer)
    db.session.commit()
    login_as(client, admin)

    response = client.get(f"/{hotel.slug}/customers/api/customers")

    assert response.status_code == 200
    saved_customer = next(row for row in response.get_json() if row["id"] == customer.id)
    assert saved_customer == {"id": customer.id, **payload}
    assert response.content_type == "application/json"


def test_customer_rows_render_untrusted_values_without_html_sinks():
    source = CUSTOMER_SCRIPT.read_text(encoding="utf-8")

    assert "tr.innerHTML" not in source
    assert "onclick=" not in source
    assert "insertAdjacentHTML" not in source
    assert "document.createElement" in source
    assert ".textContent" in source
    assert "addEventListener" in source


def test_customer_icon_actions_have_contextual_accessible_names():
    source = CUSTOMER_SCRIPT.read_text(encoding="utf-8")

    assert "button.setAttribute('aria-label', label)" in source
    assert "Sửa khách hàng ${c.name" in source
    assert "Xóa khách hàng ${c.name" in source
    assert "c.name" in source
