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
