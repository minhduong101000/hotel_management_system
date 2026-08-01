from pathlib import Path


def test_room_map_uses_human_status_and_notice_formatter():
    source = Path('static/js/room.js').read_text(encoding='utf-8')
    assert 'formatRoomStatus' in source
    assert 'formatNoticeTime' in source
    assert "badge.textContent = modifier" not in source


def test_room_map_card_only_exposes_nearest_booking_information():
    source = Path('static/js/room.js').read_text(encoding='utf-8')

    assert 'getNearestNotice(room.notices)' in source
    assert "action.textContent = 'Xem thông tin'" in source
    assert 'showNoticeInfo(nearestNotice)' in source
    assert 'room.notices.forEach(notice =>' not in source


def test_room_map_booking_information_modal_has_contact_and_deposit():
    template = Path('templates/rooms/map.html').read_text(encoding='utf-8')

    assert 'id="ci-guest-phone"' in template
    assert 'id="ci-deposit"' in template


def test_room_card_uses_compact_visual_hierarchy_and_accessible_action_styles():
    script = Path('static/js/room.js').read_text(encoding='utf-8')
    styles = Path('static/css/style.css').read_text(encoding='utf-8')

    assert "room-card__eyebrow" in script
    assert "room-card__detail" in script
    assert ".room-card__action" in styles
    assert "min-height: 36px" in styles
    assert "@media (prefers-reduced-motion: reduce)" in styles
    assert ".room-card__body { overflow-y: auto; }" not in styles


def test_room_map_toolbar_and_sidebar_brand_use_compact_grouped_markup():
    room_map = Path('templates/rooms/map.html').read_text(encoding='utf-8')
    base_layout = Path('templates/layouts/base.html').read_text(encoding='utf-8')

    assert 'room-map-toolbar' in room_map
    assert 'room-map-toolbar__stats' in room_map
    assert 'status-badge status-badge--' in room_map
    assert 'sidebar-brand__hotel' in base_layout
    assert 'sidebar-support-banner' in base_layout


def test_room_map_uses_shared_toolbar_group_and_structured_data_states():
    template = Path('templates/rooms/map.html').read_text(encoding='utf-8')
    script = Path('static/js/room.js').read_text(encoding='utf-8')

    assert 'room-map-toolbar__controls button-group' in template
    assert 'id="filter-status"' in template
    assert 'id="stat-occupied"' in template
    assert 'id="stat-dirty"' in template
    assert 'id="stat-available"' in template
    assert 'data-state data-state--loading' in template
    assert 'renderRoomMapState' in script
    assert 'let hasLoadedRooms = false' in script
    assert 'if (!hasLoadedRooms)' in script
    assert 'hasLoadedRooms = true' in script
    for class_name in (
        'data-state__icon',
        'data-state__title',
        'data-state__description',
        'data-state__actions',
    ):
        assert class_name in script
    assert "retryButton.addEventListener('click', loadRoomsData)" in script
    assert "'<div class=\"col-12 text-center text-muted mt-5\"><i>" not in script


def test_room_cards_use_tinted_surface_status_rail_and_named_badge():
    script = Path('static/js/room.js').read_text(encoding='utf-8')
    styles = Path('static/css/style.css').read_text(encoding='utf-8')

    assert 'room-card__status-icon' in script
    assert 'status-badge--${modifier}' in script
    assert '.room-card::before' in styles
    for modifier in (
        'available',
        'booked',
        'occupied',
        'hourly',
        'overdue',
        'dirty',
        'maintenance',
    ):
        assert f'.room-card--{modifier}' in styles
        assert f'.room-card .status-badge--{modifier}' in styles


def test_occupied_room_card_opens_order_modal_without_interfering_checkout():
    script = Path('static/js/room.js').read_text(encoding='utf-8')

    assert "card.setAttribute('role', 'button')" in script
    assert "card.addEventListener('click', () => openOrderModal(room.number))" in script
    assert "event.stopPropagation(); checkOut(room.number)" in script
    assert "event.key === 'Enter' || event.key === ' '" in script


def test_order_modal_includes_persisted_order_summary():
    template = Path('templates/rooms/map.html').read_text(encoding='utf-8')
    service_script = Path('static/js/service.js').read_text(encoding='utf-8')

    assert 'id="existing-order-list"' in template
    assert 'id="existing-order-total"' in template
    assert 'loadExistingOrders(roomNumber)' in service_script
