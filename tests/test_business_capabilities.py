from extensions import db
from models import User


def test_staff_can_access_price_management_api(client, seed_hotels, login_as):
    hotel, _, _, _, _, _ = seed_hotels
    staff = User(username="staff_price", role="staff", hotel_id=hotel.id)
    staff.set_password("correct-password")
    db.session.add(staff)
    db.session.commit()
    login_as(client, staff)

    response = client.get(f"/{hotel.slug}/prices/api/prices/all-data")
    page_response = client.get(f"/{hotel.slug}/prices/admin/price-manager")

    assert response.status_code == 200
    assert page_response.status_code == 200
    assert "Quản lý Giá phòng" in page_response.text
