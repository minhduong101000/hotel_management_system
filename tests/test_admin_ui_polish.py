def test_staff_page_uses_shared_management_layout(client, seed_hotels, login_as):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    response = client.get(f'/{hotel.slug}/staff/')

    assert response.status_code == 200
    assert b'page-header' in response.data
    assert b'staff-management' in response.data


def test_master_console_uses_polished_page_landmarks(client, seed_hotels, login_as):
    _, _, _, master_admin, _, _ = seed_hotels
    login_as(client, master_admin)

    dashboard = client.get('/master')

    assert dashboard.status_code == 200
    assert b'master-dashboard' in dashboard.data
    assert b'master-page-header' in dashboard.data


def test_login_templates_use_dedicated_polished_layout_classes():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    assert 'login-card' in (root / 'templates' / 'auth' / 'login.html').read_text(encoding='utf-8')
    assert 'master-login' in (root / 'templates' / 'master' / 'login.html').read_text(encoding='utf-8')
