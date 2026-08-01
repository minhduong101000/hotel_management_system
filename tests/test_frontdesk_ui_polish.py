def test_customer_and_billing_pages_use_shared_page_header(client, seed_hotels, login_as):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)
    for path in ('/customers/customers', '/billing/billing'):
        response = client.get(f'/{hotel.slug}{path}')
        assert response.status_code == 200
        assert b'page-header' in response.data


def test_service_price_and_warehouse_pages_use_shared_page_header(client, seed_hotels, login_as):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)
    for path in ('/services/services', '/prices/admin/price-manager', '/warehouse/warehouse'):
        response = client.get(f'/{hotel.slug}{path}')
        assert response.status_code == 200
        assert b'page-header' in response.data


def test_customer_search_uses_a_spaced_search_bar(client, seed_hotels, login_as):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    response = client.get(f'/{hotel.slug}/customers/customers')

    assert response.status_code == 200
    assert b'customer-search-bar' in response.data


def test_room_map_initial_loading_state_uses_shared_data_state(client, seed_hotels, login_as):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    response = client.get(f'/{hotel.slug}/rooms/dashboard/room-map')

    assert response.status_code == 200
    assert b'data-state data-state--loading' in response.data
    assert b'data-state__title' in response.data
    assert 'Đang tải dữ liệu phòng'.encode() in response.data


def test_timeline_initial_loading_state_uses_shared_data_state(client, seed_hotels, login_as):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    response = client.get(f'/{hotel.slug}/rooms/timeline-view')

    assert response.status_code == 200
    assert b'id="timeline-loading-state"' in response.data
    assert b'id="visualization" class="d-none"' in response.data
    assert b'data-state data-state--loading' in response.data
    assert b'data-state__title' in response.data
    assert 'Đang tải Timeline'.encode() in response.data
