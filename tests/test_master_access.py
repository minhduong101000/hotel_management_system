def test_master_console_requires_master_role(client, seed_hotels, login_as):
    _, _, hotel_admin, master_admin, *_ = seed_hotels

    login_as(client, hotel_admin)
    assert client.get('/master').status_code == 403

    client.get('/central/logout')
    login_as(client, master_admin)
    assert client.get('/master').status_code == 200


def test_master_dashboard_shows_hotels_without_guest_details(client, seed_hotels, login_as):
    hotel_a, hotel_b, _, master_admin, *_ = seed_hotels
    login_as(client, master_admin)

    response = client.get('/master')

    assert hotel_a.name.encode() in response.data
    assert hotel_b.name.encode() in response.data
    assert b'Nguyen Van A' not in response.data


def test_master_enters_selected_hotel(client, seed_hotels, login_as):
    hotel_a, _, _, master_admin, *_ = seed_hotels
    login_as(client, master_admin)

    response = client.get(f'/master/hotels/{hotel_a.id}/enter')

    assert response.status_code == 302
    assert response.headers['Location'].endswith(
        f'/{hotel_a.slug}/rooms/dashboard/room-map'
    )


def test_master_login_is_separate_from_tenant_login(client, seed_hotels):
    _, _, _, master_admin, *_ = seed_hotels

    response = client.post('/master/login', data={
        'username': master_admin.username,
        'password': 'correct-password',
    })

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/master')


def test_hotel_admin_cannot_use_master_login(client, seed_hotels):
    _, _, hotel_admin, *_ = seed_hotels

    response = client.post('/master/login', data={
        'username': hotel_admin.username,
        'password': 'correct-password',
    })

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/master/login')

    page = client.get('/master/login')
    assert 'Master admin không hợp lệ.'.encode() in page.data


def test_master_can_toggle_hotel_active_state(client, seed_hotels, login_as):
    hotel_a, _, _, master_admin, *_ = seed_hotels
    login_as(client, master_admin)

    response = client.post(f'/master/hotels/{hotel_a.id}/toggle-active')

    assert response.status_code == 302
    assert hotel_a.is_active is False
