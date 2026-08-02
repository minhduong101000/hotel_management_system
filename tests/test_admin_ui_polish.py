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


def test_hotel_login_uses_refreshed_shell_without_legacy_inline_colors():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (root / 'templates' / 'auth' / 'login.html').read_text(encoding='utf-8')

    for class_name in (
        'login-shell',
        'login-brand-mark',
        'login-form',
        'login-submit',
        'login-footer',
    ):
        assert class_name in source

    assert '#2980b9' not in source
    assert 'style=' not in source
    assert "js/login.js" in source


def test_hotel_login_script_handles_password_visibility_and_submit_feedback():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (root / 'static' / 'js' / 'login.js').read_text(encoding='utf-8')

    assert "login-password-toggle" in source
    assert "password.type" in source
    assert "aria-pressed" in source
    assert "aria-label" in source
    assert "password.focus()" not in source
    assert "addEventListener('submit'" in source
    assert "submitButton.disabled = true" in source
    assert "aria-busy" in source
    assert "Đang đăng nhập" in source


def test_staff_and_audit_use_shared_cards_tables_and_data_states(client, seed_hotels, login_as):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    staff = client.get(f'/{hotel.slug}/staff/').get_data(as_text=True)
    audit = client.get(f'/{hotel.slug}/activity-log/').get_data(as_text=True)

    for html in (staff, audit):
        assert 'data-table-card' in html
        assert 'data-table-shell' in html
    assert 'staff-form-card' in staff
    assert 'btn btn-icon btn-outline-primary' in staff
    assert 'aria-label="Lưu mật khẩu mới' in staff
    assert 'btn btn-outline-danger' in staff
    assert 'data-filter-bar' in audit
    assert 'data-state data-state--loading' in audit


def test_master_dashboard_and_login_use_accessible_polished_components():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    base = (root / 'templates' / 'master' / 'base.html').read_text(encoding='utf-8')
    dashboard = (root / 'templates' / 'master' / 'dashboard.html').read_text(encoding='utf-8')
    login = (root / 'templates' / 'master' / 'login.html').read_text(encoding='utf-8')

    assert 'master-skip-link' in base
    assert 'id="master-main-content"' in base
    assert 'master-kpi-card' in dashboard
    assert 'master-table-card' in dashboard
    assert 'master-empty-state' in dashboard
    assert 'id="master-login-form"' in login
    assert 'id="master-password-toggle"' in login
    assert 'aria-controls="master-password"' in login
    assert 'aria-pressed="false"' in login
    assert 'aria-label="Hiện mật khẩu"' in login
    assert 'id="master-login-submit"' in login
    assert 'aria-busy="false"' in login
    assert 'id="master-login-status"' in login
    assert 'role="status"' in login
    assert 'style=' not in login
