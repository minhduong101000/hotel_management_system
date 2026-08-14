from extensions import db
from models import Service, User


def _staff(hotel):
    staff = User(username="staff_perm", role="staff", hotel_id=hotel.id)
    staff.set_password("correct-password")
    db.session.add(staff)
    db.session.commit()
    return staff


def test_staff_cannot_mutate_services_api(app, seed_hotels, client, login_as):
    hotel, _, _, _, _, _ = seed_hotels
    with app.app_context():
        staff = _staff(hotel)
        login_as(client, staff)

        created = client.post(
            f"/{hotel.slug}/services/api/services",
            json={"name": "Lậu quyền", "price": 1},
        )
        assert created.status_code == 403
        assert created.json["error_code"] == "forbidden"
        assert Service.query.count() == 0

        service = Service(hotel_id=hotel.id, name="Nước suối", price=10000)
        db.session.add(service)
        db.session.commit()

        updated = client.put(
            f"/{hotel.slug}/services/api/services/{service.id}",
            json={"name": "Đổi lậu", "price": 2},
        )
        deleted = client.delete(f"/{hotel.slug}/services/api/services/{service.id}")
        assert updated.status_code == 403
        assert deleted.status_code == 403
        assert Service.query.filter_by(name="Nước suối").count() == 1

        # Staff vẫn XEM được danh mục (modal gọi dịch vụ cần)
        listed = client.get(f"/{hotel.slug}/services/api/services")
        assert listed.status_code == 200


def test_staff_cannot_touch_price_manager(app, seed_hotels, client, login_as):
    hotel, _, _, _, _, _ = seed_hotels
    with app.app_context():
        staff = _staff(hotel)
        login_as(client, staff)

        # XEM duoc (tu van khach - so tay muc 2.1), SUA thi khong
        all_data = client.get(f"/{hotel.slug}/prices/api/prices/all-data")
        update_base = client.post(
            f"/{hotel.slug}/prices/api/prices/update-base",
            json={"id": 1, "price_per_night": 1},
        )
        save_rule = client.post(
            f"/{hotel.slug}/prices/api/prices/save-rule",
            json={"name": "Lậu", "room_type": "Standard", "priority": 1, "price_daily": 1},
        )
        delete_rule = client.delete(f"/{hotel.slug}/prices/api/prices/delete-rule/1")
        assert all_data.status_code == 200
        assert update_base.status_code == 403
        assert save_rule.status_code == 403
        assert delete_rule.status_code == 403
        assert save_rule.json["error_code"] == "forbidden"


def test_master_admin_passes_admin_required_in_tenant(app, seed_hotels, client, login_as):
    hotel, _, _, _, _, _ = seed_hotels
    with app.app_context():
        # Master THUẦN (không kiêm role admin) — ca bị admin_required khóa oan
        master = User(username="pure_master", role="staff", is_super_admin=True)
        master.set_password("correct-password")
        db.session.add(master)
        db.session.commit()
        login_as(client, master)

        # Trước đây Master role='staff' bị admin_required khóa oan (302 flash)
        cashier = client.get(f"/{hotel.slug}/cashier/api/reports/cashier?period=today")
        assert cashier.status_code == 200, cashier.data[:200]


def test_staff_html_admin_page_still_redirects(app, seed_hotels, client, login_as):
    hotel, _, _, _, _, _ = seed_hotels
    with app.app_context():
        staff = _staff(hotel)
        login_as(client, staff)
        page = client.get(f"/{hotel.slug}/expenses/expenses")
        assert page.status_code == 302  # hành vi HTML giữ nguyên: flash + redirect


def test_unauthenticated_api_gets_401_json(app, seed_hotels, client):
    hotel, _, _, _, _, _ = seed_hotels
    with app.app_context():
        api_response = client.get(f"/{hotel.slug}/rooms/api/rooms")
        assert api_response.status_code == 401
        assert api_response.json["error_code"] == "unauthenticated"

        html_response = client.get(f"/{hotel.slug}/billing/billing")
        assert html_response.status_code == 302
        assert "/login" in html_response.headers["Location"]
