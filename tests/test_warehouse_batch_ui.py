def test_warehouse_page_exposes_expiry_and_disposal_controls(client, seed_hotels, login_as):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)
    response = client.get(f'/{hotel.slug}/warehouse/warehouse')
    html = response.get_data(as_text=True)
    for control in ('warehouse-expiring-count', 'warehouse-expired-count', 'batchModal', 'disposeModal', 'adjustModal', 'restock-expires-at', 'warehouse-feedback'):
        assert f'id="{control}"' in html
