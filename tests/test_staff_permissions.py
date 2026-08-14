from extensions import db
from models import User


def _create_staff(hotel):
    staff = User(username='permission_staff', role='staff', hotel_id=hotel.id)
    staff.set_password('correct-password')
    db.session.add(staff)
    db.session.commit()
    return staff


def test_staff_is_redirected_from_sensitive_admin_routes(client, seed_hotels, login_as):
    hotel, _, _, _, _, _ = seed_hotels
    staff = _create_staff(hotel)
    login_as(client, staff)

    protected_html_routes = [
        f'/{hotel.slug}/expenses/expenses',
        f'/{hotel.slug}/cashier/reports/cashier',
        f'/{hotel.slug}/reports/reports/revenue',
        f'/{hotel.slug}/staff/',
        f'/{hotel.slug}/activity-log/',
    ]
    protected_api_routes = [
        f'/{hotel.slug}/expenses/api/expenses',
        f'/{hotel.slug}/cashier/api/reports/cashier',
        f'/{hotel.slug}/reports/api/reports/revenue',
        f'/{hotel.slug}/activity-log/api/events',
    ]
    for route in protected_html_routes:
        response = client.get(route)
        assert response.status_code == 302
        assert f'/{hotel.slug}/rooms/dashboard/room-map' in response.headers['Location']
    # API tra 403 JSON may doc duoc thay vi redirect HTML (14-08)
    for route in protected_api_routes:
        response = client.get(route)
        assert response.status_code == 403, route
        assert response.json['error_code'] == 'forbidden' 


def test_staff_sidebar_hides_sensitive_admin_navigation(client, seed_hotels, login_as):
    hotel, _, _, _, _, _ = seed_hotels
    staff = _create_staff(hotel)
    login_as(client, staff)

    response = client.get(f'/{hotel.slug}/rooms/dashboard/room-map')

    assert response.status_code == 200
    for label in ('Sổ Quỹ', 'Nhật ký hoạt động', 'Doanh thu', 'Chi phí', 'Cấu hình & Nhân sự'):
        assert label.encode() not in response.data
