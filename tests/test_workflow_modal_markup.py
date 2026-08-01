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
    assert 'id="qr-image-input"' in partial
    assert 'id="qr-image-preview"' in partial
    assert 'id="qr-upload-status"' in partial
    assert 'startQRScannerCamera()' in partial


def test_qr_scanner_supports_desktop_image_import_before_camera():
    source = (ROOT / 'static/js/qr_scanner.js').read_text(encoding='utf-8')

    assert 'function handleQRImageUpload' in source
    assert '.scanFile(file, true)' in source
    assert 'function startQRScannerCamera' in source


def test_room_map_and_timeline_share_the_group_booking_modal_partial():
    for template in ('templates/rooms/map.html', 'templates/rooms/timeline.html'):
        source = (ROOT / template).read_text(encoding='utf-8')

        assert '{% include "rooms/_group_booking_modal.html" %}' in source

    partial = (ROOT / 'templates/rooms/_group_booking_modal.html').read_text(encoding='utf-8')
    for element_id in ('g_check_in', 'g_check_out', 'roomSelectionList', 'availCount', 'group_total_deposit', 'group_note'):
        assert f'id="{element_id}"' in partial


def test_room_map_and_timeline_share_the_checkout_modal_partial():
    for template in ('templates/rooms/map.html', 'templates/rooms/timeline.html'):
        source = (ROOT / template).read_text(encoding='utf-8')

        assert '{% include "rooms/_checkout_modal.html" %}' in source

    partial = (ROOT / 'templates/rooms/_checkout_modal.html').read_text(encoding='utf-8')
    for element_id in ('co-room-number', 'co-customer', 'room-fee-table-body', 'table-services-body', 'co-final-payment'):
        assert f'id="{element_id}"' in partial


def test_room_map_and_timeline_share_the_booking_modal_partial():
    for template in ('templates/rooms/map.html', 'templates/rooms/timeline.html'):
        source = (ROOT / template).read_text(encoding='utf-8')

        assert '{% include "rooms/_booking_modal.html" %}' in source

    partial = (ROOT / 'templates/rooms/_booking_modal.html').read_text(encoding='utf-8')
    for element_id in ('bk-room-id', 'bk-phone', 'bk-daily-in', 'bk-hourly-in', 'bk-deposit'):
        assert f'id="{element_id}"' in partial
    assert 'aria-labelledby="bookingModalTitle"' in partial
    assert 'aria-label="Đóng modal đặt phòng"' in partial
    assert 'data-booking-submit' in partial
    assert 'aria-busy="false"' in partial


def test_room_map_and_timeline_share_the_group_checkout_modal_partial():
    for template in ('templates/rooms/map.html', 'templates/rooms/timeline.html'):
        source = (ROOT / template).read_text(encoding='utf-8')

        assert '{% include "rooms/_group_checkout_modal.html" %}' in source

    partial = (ROOT / 'templates/rooms/_group_checkout_modal.html').read_text(encoding='utf-8')
    for element_id in ('gc-booking-code', 'gc-room-list', 'gc-grand-total', 'gc-deposit', 'gc-final-total'):
        assert f'id="{element_id}"' in partial
