from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_complex_operational_workflows_use_shared_modal_variants():
    for template in (
        'templates/rooms/map.html',
        'templates/rooms/timeline.html',
        'templates/billing/index.html',
    ):
        source = (ROOT / template).read_text(encoding='utf-8')

        assert 'workflow-modal' in source


def test_shared_styles_cover_wide_and_fullscreen_workflow_modals():
    source = (ROOT / 'static/css/style.css').read_text(encoding='utf-8')

    assert '.workflow-modal' in source
    assert '.workflow-modal--fullscreen' in source
    assert '.workflow-modal--wide' in source


def test_room_map_group_booking_contains_controls_required_by_group_booking_script():
    source = (ROOT / 'templates/rooms/_group_booking_modal.html').read_text(encoding='utf-8')

    for element_id in ('g_check_in', 'g_check_out', 'roomSelectionList', 'availCount', 'group_total_deposit', 'group_note'):
        assert f'id="{element_id}"' in source


def test_room_map_and_timeline_share_the_qr_scanner_modal_partial():
    for template in ('templates/rooms/map.html', 'templates/rooms/timeline.html'):
        source = (ROOT / template).read_text(encoding='utf-8')

        assert '{% include "rooms/_qr_scanner_modal.html" %}' in source

    partial = (ROOT / 'templates/rooms/_qr_scanner_modal.html').read_text(encoding='utf-8')
    assert 'id="qrScannerModal"' in partial
    assert 'id="qr-reader"' in partial


def test_room_map_and_timeline_share_the_group_booking_modal_partial():
    for template in ('templates/rooms/map.html', 'templates/rooms/timeline.html'):
        source = (ROOT / template).read_text(encoding='utf-8')

        assert '{% include "rooms/_group_booking_modal.html" %}' in source

    partial = (ROOT / 'templates/rooms/_group_booking_modal.html').read_text(encoding='utf-8')
    for element_id in ('g_check_in', 'g_check_out', 'roomSelectionList', 'availCount', 'group_total_deposit', 'group_note'):
        assert f'id="{element_id}"' in partial
