def test_warehouse_page_exposes_expiry_and_disposal_controls(client, seed_hotels, login_as):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)
    response = client.get(f'/{hotel.slug}/warehouse/warehouse')
    html = response.get_data(as_text=True)
    for control in ('warehouse-expiring-count', 'warehouse-expired-count', 'batchModal', 'disposeModal', 'adjustModal', 'restock-expires-at', 'warehouse-feedback'):
        assert f'id="{control}"' in html


def test_warehouse_uses_shared_kpi_table_and_data_states(client, seed_hotels, login_as):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    response = client.get(f'/{hotel.slug}/warehouse/warehouse')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert html.count('kpi-card') >= 2
    assert 'kpi-card--warning' in html
    assert 'kpi-card--danger' in html
    assert 'data-table-card' in html
    assert 'data-table-shell' in html
    assert 'data-state data-state--loading' in html
    assert 'renderWarehouseTableState' in html
    assert "emptyAction.addEventListener('click', openAddModal)" in html
    assert 'Kho chưa có vật tư' in html


def test_warehouse_renderer_keeps_api_values_out_of_html_sinks():
    source = open('templates/warehouse/index.html', encoding='utf-8').read()

    assert 'tbody.innerHTML' not in source
    assert 'sel.innerHTML' not in source
    assert "getElementById('batch-list').innerHTML" not in source
    assert 'document.createElement' in source
    assert '.textContent' in source
    assert 'addEventListener' in source
    assert 'btn btn-icon' in source


def test_warehouse_async_submits_have_busy_guards_and_modal_status():
    source = open('templates/warehouse/index.html', encoding='utf-8').read()

    for action in ('save', 'restock', 'dispose', 'adjust'):
        assert f"warehouseSubmitting.has('{action}')" in source
    for button_id in (
        'item-save-button',
        'restock-submit-button',
        'dispose-submit-button',
        'adjust-submit-button',
    ):
        assert f'id="{button_id}"' in source
        assert f"'{button_id}'" in source
    for status_id in (
        'item-form-status',
        'restock-form-status',
        'dispose-form-status',
        'adjust-form-status',
    ):
        assert f'id="{status_id}"' in source
    assert 'function setWarehouseSubmitBusy' in source
    assert "button.setAttribute('aria-busy'" in source
    assert '.finally(' in source
