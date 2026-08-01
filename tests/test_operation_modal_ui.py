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


def test_warehouse_modal_headers_match_action_semantics(client, seed_hotels, login_as):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    response = client.get(f'/{hotel.slug}/warehouse/warehouse')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert html.count('operation-modal__header--teal') >= 3
    assert 'id="disposeModal"' in html
    assert 'operation-modal__header--danger' in html
    assert 'operation-modal--danger' in html


def test_service_and_price_modals_are_named_labelled_and_announce_submission(
    client, seed_hotels, login_as
):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    service_html = client.get(
        f'/{hotel.slug}/services/services'
    ).get_data(as_text=True)
    assert 'aria-labelledby="serviceModalTitle"' in service_html
    assert 'id="serviceModalTitle"' in service_html
    assert 'aria-label="Đóng modal dịch vụ"' in service_html
    assert 'operation-modal__header--teal' in service_html
    assert 'for="service-name"' in service_html
    assert 'for="service-price"' in service_html
    assert 'id="service-form-status"' in service_html
    assert 'role="alert"' in service_html
    assert 'aria-live="assertive"' in service_html
    assert 'id="service-save-button"' in service_html
    assert 'aria-busy="false"' in service_html

    price_html = client.get(
        f'/{hotel.slug}/prices/admin/price-manager'
    ).get_data(as_text=True)
    assert 'aria-labelledby="ruleModalTitle"' in price_html
    assert 'id="ruleModalTitle"' in price_html
    assert 'aria-label="Đóng modal luật giá"' in price_html
    assert 'operation-modal__header--teal' in price_html
    for control_id in (
        'r-name',
        'r-room-type',
        'r-priority',
        'r-start',
        'r-end',
        'r-price-daily',
    ):
        assert f'for="{control_id}"' in price_html
    assert 'id="r-price-initial"' not in price_html
    assert 'id="r-price-next"' not in price_html
    assert 'id="rule-form-status"' in price_html
    assert 'role="alert"' in price_html
    assert 'aria-live="assertive"' in price_html
    assert 'id="rule-save-button"' in price_html
    assert 'aria-busy="false"' in price_html
