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


def test_finance_pages_share_filters_kpis_tables_and_loading_states(
    client, seed_hotels, login_as
):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    for path in (
        '/reports/reports/revenue',
        '/cashier/reports/cashier',
        '/expenses/expenses',
    ):
        response = client.get(f'/{hotel.slug}{path}')
        html = response.get_data(as_text=True)

        assert response.status_code == 200
        assert 'data-filter-bar' in html
        assert 'kpi-card' in html
        assert 'data-table-card' in html
        assert 'data-table-shell' in html
        assert 'data-state data-state--loading' in html
        assert 'data-state__title' in html


def test_revenue_has_accessible_chart_states_summaries_and_period_label(
    client, seed_hotels, login_as
):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    html = client.get(
        f'/{hotel.slug}/reports/reports/revenue'
    ).get_data(as_text=True)

    assert 'id="revenue-chart-state"' in html
    assert 'id="occupancy-chart-state"' in html
    assert 'id="revenue-chart-content" class="finance-chart-content d-none"' in html
    assert 'id="occupancy-chart-content" class="finance-chart-content d-none"' in html
    assert 'id="revenue-chart-summary"' in html
    assert 'id="occupancy-chart-summary"' in html
    assert 'aria-describedby="revenue-chart-summary"' in html
    assert 'aria-describedby="occupancy-chart-summary"' in html
    assert 'id="report-period-label"' in html


def test_expense_page_exposes_void_workflow_instead_of_direct_delete(
    client, seed_hotels, login_as
):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    html = client.get(f'/{hotel.slug}/expenses/expenses').get_data(as_text=True)

    assert 'id="voidExpenseModal"' in html
    assert 'operation-modal--danger' in html
    assert 'id="void-expense-reason"' in html
    assert 'id="void-expense-submit-button"' in html
    assert 'aria-busy="false"' in html
