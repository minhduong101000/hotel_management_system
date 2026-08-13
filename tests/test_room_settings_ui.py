from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE = ROOT / "templates/layouts/base.html"
SETTINGS_TEMPLATE = ROOT / "templates/rooms/settings.html"
PRICE_TEMPLATE = ROOT / "templates/admin/price_manager.html"
SETTINGS_SCRIPT = ROOT / "static/js/room_settings.js"
PRICE_SCRIPT = ROOT / "static/js/price_manager.js"
MAIN_SCRIPT = ROOT / "static/js/main.js"


def test_room_settings_view_is_available_to_staff_admin_and_master(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, admin, master_admin, _, _ = seed_hotels
    from extensions import db
    from models import User

    staff = User(username="room_settings_staff", role="staff", hotel_id=hotel.id)
    staff.set_password("correct-password")
    db.session.add(staff)
    db.session.commit()

    login_as(client, staff)
    staff_response = client.get(f"/{hotel.slug}/rooms/settings")
    assert staff_response.status_code == 200
    client.get(f"/{hotel.slug}/logout")

    login_as(client, admin)
    admin_response = client.get(f"/{hotel.slug}/rooms/settings")
    assert admin_response.status_code == 200
    client.get(f"/{hotel.slug}/logout")

    login_as(client, master_admin)
    master_response = client.get(f"/{hotel.slug}/rooms/settings")
    assert master_response.status_code == 200


def test_room_configuration_navigation_has_one_sidebar_entry_and_deep_links():
    source = BASE_TEMPLATE.read_text(encoding="utf-8")
    settings = SETTINGS_TEMPLATE.read_text(encoding="utf-8")
    price = PRICE_TEMPLATE.read_text(encoding="utf-8")

    assert source.count("Cấu hình phòng & giá") == 1
    assert "url_for('room.settings_view')" in source
    assert "url_for('price.index')" not in source
    assert "room.settings_view" in source
    assert "price.index" in source

    for template in (settings, price):
        assert 'settings-page-tabs' in template
        assert "url_for('room.settings_view')" in template
        assert "url_for('price.index')" in template
        assert "aria-current=" in template


def test_room_settings_page_has_filter_table_states_and_safe_actions():
    source = SETTINGS_TEMPLATE.read_text(encoding="utf-8")

    for identifier in (
        "room-settings-search",
        "room-settings-type-filter",
        "room-settings-status-filter",
        "room-settings-table",
        "room-settings-feedback",
        "room-settings-loading-state",
        "room-settings-empty-state",
        "room-settings-error-state",
        "room-settings-modal",
        "room-rate-modal",
    ):
        assert f'id="{identifier}"' in source
    assert 'id="add-room-button"' in source
    assert "data-room-structure-action" in source
    assert "room-structure-action" not in source.lower().replace(
        "data-room-structure-action", ""
    )
    assert "Xóa phòng" not in source


def test_room_settings_modal_has_linked_labels_announced_errors_and_named_close_controls():
    source = SETTINGS_TEMPLATE.read_text(encoding="utf-8")

    for control_id in (
        "room-number",
        "room-type",
        "room-price-night",
        "room-price-initial",
        "room-initial-hours",
        "room-price-next",
        "rate-price-night",
        "rate-price-initial",
        "rate-initial-hours",
        "rate-price-next",
    ):
        assert f'for="{control_id}"' in source
    for modal_id, title_id, close_label, status_id in (
        (
            "room-settings-modal",
            "room-settings-modal-title",
            "Đóng modal cấu hình phòng",
            "room-settings-form-status",
        ),
        (
            "room-rate-modal",
            "room-rate-modal-title",
            "Đóng modal cập nhật giá phòng",
            "room-rate-form-status",
        ),
    ):
        assert f'id="{modal_id}"' in source
        assert f'aria-labelledby="{title_id}"' in source
        assert f'id="{title_id}"' in source
        assert f'aria-label="{close_label}"' in source
        assert f'id="{status_id}"' in source
    assert source.count('role="alert"') >= 2
    assert source.count('aria-live="assertive"') >= 2
    assert 'aria-busy="false"' in source


def test_staff_hides_structure_actions_but_keeps_default_rate_action(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, _, _, _, _ = seed_hotels
    from extensions import db
    from models import User

    staff = User(username="room_settings_ui_staff", role="staff", hotel_id=hotel.id)
    staff.set_password("correct-password")
    db.session.add(staff)
    db.session.commit()
    login_as(client, staff)

    html = client.get(f"/{hotel.slug}/rooms/settings").get_data(as_text=True)

    assert 'id="add-room-button"' not in html
    assert "data-room-structure-action" not in html
    assert 'id="room-rate-modal"' in html


def test_admin_sees_room_structure_actions(
    client,
    seed_hotels,
    login_as,
):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    html = client.get(f"/{hotel.slug}/rooms/settings").get_data(as_text=True)

    assert 'id="add-room-button"' in html
    assert "data-room-structure-action" in html


def test_special_price_page_has_no_default_rate_table_or_edit_controls():
    source = PRICE_TEMPLATE.read_text(encoding="utf-8")
    script = PRICE_SCRIPT.read_text(encoding="utf-8")

    assert 'id="base-price-table"' not in source
    assert "Giá cơ bản" not in source
    assert "renderBaseTable" not in script
    assert "updateBase" not in script
    assert "/api/prices/rules" in script


def test_room_settings_script_uses_safe_dom_and_handles_mutation_errors():
    source = SETTINGS_SCRIPT.read_text(encoding="utf-8")

    assert "innerHTML" not in source
    assert "onclick" not in source
    assert ".textContent" in source
    assert "createElement" in source
    assert "addEventListener" in source
    for status in ("400", "403", "409"):
        assert f"status === {status}" in source
    assert "AbortController" not in source
    assert "roomSettingsSubmitting" in source
    assert "maintenance" in source
    assert "window.confirm" in source


def test_api_helper_routes_room_settings_requests_to_room_blueprint():
    source = MAIN_SCRIPT.read_text(encoding="utf-8")

    assert "'/api/settings': `/${slug}/rooms`" in source


def test_special_price_script_uses_new_rule_contract_without_hourly_fields():
    source = PRICE_SCRIPT.read_text(encoding="utf-8")

    assert "/api/prices/rules" in source
    assert "price_initial" not in source
    assert "price_next" not in source
    assert "price_daily" in source
