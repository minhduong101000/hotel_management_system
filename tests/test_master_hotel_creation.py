from models import Hotel, User


def test_master_creates_hotel_and_first_admin(client, seed_hotels, login_as):
    _, _, _, master_admin, *_ = seed_hotels
    login_as(client, master_admin)

    response = client.post('/master/hotels/create', data={
        'name': 'Sunrise Hotel',
        'slug': 'sunrise',
        'admin_username': 'sunrise_admin',
        'admin_password': 'safe-password',
    })

    assert response.status_code == 302
    hotel = Hotel.query.filter_by(slug='sunrise').one()
    admin = User.query.filter_by(username='sunrise_admin').one()
    assert admin.hotel_id == hotel.id
    assert admin.role == 'admin'
    assert admin.is_super_admin is False
    assert admin.password_hash != 'safe-password'


def test_duplicate_hotel_slug_rolls_back_admin(client, seed_hotels, login_as):
    hotel_a, _, _, master_admin, *_ = seed_hotels
    login_as(client, master_admin)

    response = client.post('/master/hotels/create', data={
        'name': 'Duplicate Hotel',
        'slug': hotel_a.slug,
        'admin_username': 'should_not_exist',
        'admin_password': 'safe-password',
    })

    assert response.status_code == 400
    assert User.query.filter_by(username='should_not_exist').first() is None


def test_inactive_hotel_blocks_tenant_login(client, seed_hotels):
    hotel_a, _, admin_a, *_ = seed_hotels
    hotel_a.is_active = False
    from extensions import db
    db.session.commit()

    response = client.post(f'/{hotel_a.slug}/login', data={
        'username': admin_a.username,
        'password': 'correct-password',
    })

    assert response.status_code == 404
