from extensions import db
from models import User


def test_hotel_admin_lists_only_own_users(client, seed_hotels, login_as):
    hotel_a, _, admin_a, _, *_ = seed_hotels
    login_as(client, admin_a)

    response = client.get(f'/{hotel_a.slug}/staff/')

    assert b'admin_a' in response.data
    assert b'admin_b' not in response.data


def test_hotel_admin_cannot_delete_other_hotel_user(client, seed_hotels, login_as):
    hotel_a, _, admin_a, _, *_ = seed_hotels
    admin_b = User.query.filter_by(username='admin_b').one()
    login_as(client, admin_a)

    response = client.post(f'/{hotel_a.slug}/staff/delete/{admin_b.id}')

    assert response.status_code == 404


def test_hotel_admin_cannot_delete_last_admin(client, seed_hotels, login_as):
    hotel_a, _, admin_a, _, *_ = seed_hotels
    login_as(client, admin_a)

    response = client.post(f'/{hotel_a.slug}/staff/delete/{admin_a.id}')

    assert response.status_code == 302
    assert db.session.get(User, admin_a.id) is not None
