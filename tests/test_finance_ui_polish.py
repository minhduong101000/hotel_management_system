def test_finance_and_audit_pages_use_shared_page_header(client, seed_hotels, login_as):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    for path in (
        '/reports/reports/revenue',
        '/cashier/reports/cashier',
        '/expenses/expenses',
        '/activity-log/',
    ):
        response = client.get(f'/{hotel.slug}{path}')

        assert response.status_code == 200
        assert b'page-header' in response.data
