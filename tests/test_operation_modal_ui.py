def test_short_operational_forms_use_shared_modal_component(client, seed_hotels, login_as):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    for path in (
        '/customers/customers',
        '/services/services',
        '/prices/admin/price-manager',
        '/warehouse/warehouse',
        '/expenses/expenses',
    ):
        response = client.get(f'/{hotel.slug}{path}')

        assert response.status_code == 200
        assert b'operation-modal' in response.data
