from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE = ROOT / "templates" / "layouts" / "base.html"
STYLE_SHEET = ROOT / "static" / "css" / "style.css"


def test_authenticated_room_map_uses_application_shell(client, seed_hotels, login_as):
    hotel_a, _, user_a, *_ = seed_hotels
    login_as(client, user_a)

    response = client.get(f"/{hotel_a.slug}/rooms/dashboard/room-map")

    assert response.status_code == 200
    assert b"app-sidebar" in response.data
    assert b"app-content" in response.data
    assert b"app-topbar" in response.data


def test_base_layout_has_viewport_and_shared_ui_components():
    source = BASE_TEMPLATE.read_text(encoding="utf-8")

    assert 'name="viewport"' in source
    assert '<main class="app-content"' in source
    assert 'class="app-topbar"' in source
    assert 'class="skip-link"' in source
    assert 'aria-current=' in source


def test_shared_styles_define_semantic_tokens_focus_and_tablet_layout():
    source = STYLE_SHEET.read_text(encoding="utf-8")

    for token in (
        "--color-primary",
        "--color-surface",
        "--color-background",
        "--color-border",
        "--color-success",
        "--color-warning",
        "--color-danger",
    ):
        assert token in source

    assert ":focus-visible" in source
    assert ".page-header" in source
    assert ".page-header__description" in source
    assert ".filter-bar" in source
    assert ".skip-link" in source
    assert "@media (max-width: 991.98px)" in source
    assert ".app-sidebar" in source
