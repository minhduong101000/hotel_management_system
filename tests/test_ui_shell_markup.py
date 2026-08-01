import re
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
        "--font-sans",
        "--color-primary",
        "--color-accent",
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
    assert "Be+Vietnam+Pro" in source
    assert ".customer-action-button" in source
    assert ".modal .btn-close" in source


def test_visual_refresh_defines_bright_semantic_tokens_and_spacing_scale():
    source = STYLE_SHEET.read_text(encoding="utf-8")

    for token in (
        "--color-brand-navy",
        "--color-action",
        "--color-action-hover",
        "--color-info",
        "--color-surface-teal",
        "--color-surface-blue",
        "--color-text",
        "--color-muted-text",
        "--space-1",
        "--space-2",
        "--space-3",
        "--space-4",
        "--space-5",
        "--space-6",
    ):
        assert token in source

    assert "'Be Vietnam Pro', 'Noto Sans', sans-serif" in source


def test_visual_refresh_defines_shared_button_sizes_and_interaction_states():
    source = STYLE_SHEET.read_text(encoding="utf-8")

    assert re.search(
        r"\.app-content\s+\.btn\s*\{[^}]*min-height:\s*44px",
        source,
        re.DOTALL,
    )
    assert re.search(
        r"\.app-content\s+\.btn-sm\s*\{[^}]*min-height:\s*36px",
        source,
        re.DOTALL,
    )
    assert re.search(
        r"\.page-header\s+\.btn-sm\s*\{[^}]*min-height:\s*44px",
        source,
        re.DOTALL,
    )
    assert re.search(
        r"\.app-content\s+\.btn-lg\s*\{[^}]*min-height:\s*48px",
        source,
        re.DOTALL,
    )
    assert re.search(
        r"\.btn-icon\s*\{[^}]*min-width:\s*44px[^}]*min-height:\s*44px",
        source,
        re.DOTALL,
    )
    assert ".app-content .btn:hover:not(:disabled)" in source
    assert ".app-content .btn:active:not(:disabled)" in source
    assert ".app-content .btn:focus-visible" in source
    assert ".app-content .btn:disabled" in source
    assert '.app-content .btn[aria-busy="true"]' in source


def test_visual_refresh_defines_shared_data_kpi_and_numeric_components():
    source = STYLE_SHEET.read_text(encoding="utf-8")

    for selector in (
        ".data-state__icon",
        ".data-state__title",
        ".data-state__description",
        ".data-state__actions",
        ".kpi-card",
        ".button-group",
        ".numeric-tabular",
    ):
        assert selector in source

    assert "font-variant-numeric: tabular-nums" in source
