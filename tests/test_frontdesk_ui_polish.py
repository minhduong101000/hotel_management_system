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


def test_customer_and_billing_use_shared_filter_table_and_loading_state(
    client, seed_hotels, login_as
):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    for path in ('/customers/customers', '/billing/billing'):
        response = client.get(f'/{hotel.slug}{path}')

        assert response.status_code == 200
        assert b'data-filter-bar' in response.data
        assert b'data-table-card' in response.data
        assert b'data-table-shell' in response.data
        assert b'data-state data-state--loading' in response.data
        assert b'data-state__title' in response.data


def test_front_desk_list_actions_follow_the_shared_button_hierarchy():
    customer_template = open('templates/customers/index.html', encoding='utf-8').read()
    customer_script = open('static/js/customer.js', encoding='utf-8').read()
    billing_template = open('templates/billing/index.html', encoding='utf-8').read()
    styles = open('static/css/style.css', encoding='utf-8').read()

    assert 'page-header__actions' in customer_template
    assert 'id="add-customer-button"' in customer_template
    assert 'btn btn-primary' in customer_template
    assert 'customer-search-bar__button btn btn-outline-primary' in customer_template
    assert "className: 'btn btn-icon btn-outline-warning'" in customer_script
    assert "className: 'btn btn-icon btn-outline-danger'" in customer_script
    assert 'billing-filter-actions button-group' in billing_template
    assert 'btn btn-outline-primary' in billing_template
    assert '.status-badge--success' in styles


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


def test_service_and_pricing_pages_share_table_shells_and_action_hierarchy(
    client, seed_hotels, login_as
):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    service_response = client.get(f'/{hotel.slug}/services/services')
    price_response = client.get(f'/{hotel.slug}/prices/admin/price-manager')

    assert service_response.status_code == 200
    service_html = service_response.get_data(as_text=True)
    assert 'page-header__actions button-group' in service_html
    assert 'id="add-service-button"' in service_html
    assert 'data-table-card' in service_html
    assert 'data-table-shell' in service_html
    assert 'data-state data-state--loading' in service_html

    assert price_response.status_code == 200
    price_html = price_response.get_data(as_text=True)
    assert 'page-header__actions button-group' in price_html
    assert 'id="refresh-prices-button"' in price_html
    assert 'id="add-price-rule-button"' in price_html
    assert price_html.count('data-table-card') >= 2
    assert price_html.count('data-table-shell') >= 2
    assert price_html.count('data-state data-state--loading') >= 2
