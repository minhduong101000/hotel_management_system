def test_timeline_has_navigation_view_and_status_controls(client, seed_hotels, login_as):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    response = client.get(f'/{hotel.slug}/rooms/timeline-view')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    for control_id in (
        'timeline-prev',
        'timeline-next',
        'timeline-today',
        'timeline-range-label',
        'timeline-view-day',
        'timeline-view-3days',
        'timeline-view-week',
        'timeline-view-2weeks',
        'timeline-view-month',
        'timeline-status-filter',
        'timeline-state',
        'timeline-empty-notice',
    ):
        assert f'id="{control_id}"' in html

    # Toolbar một hàng + segmented + legend chấm màu (thiết kế 15-08)
    for design_class in ('tlg-toolbar', 'tlg-nav', 'tlg-seg', 'tlg-legend', 'tlg-stats'):
        assert design_class in html
    assert 'id="timeline-view-day"' in html and 'aria-pressed="false"' in html
    assert 'id="timeline-view-3days"' in html and 'aria-pressed="true"' in html
    assert 'onclick="setTimelineViewMode(' in html
    assert 'onclick="shiftTimeline(' in html
    assert 'onchange="applyTimelineStatusFilter()"' in html
    # Filter đủ 5 trạng thái nghiệp vụ + tất cả
    for option in ('booked', 'checked_in', 'hourly', 'group', 'overstay'):
        assert f'value="{option}"' in html


def test_timeline_renders_distinct_structured_data_states_and_light_legend(
    client, seed_hotels, login_as
):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    response = client.get(f'/{hotel.slug}/rooms/timeline-view')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    for state_id in (
        'timeline-loading-state',
        'timeline-no-rooms-state',
        'timeline-empty-notice',
        'timeline-error-state',
    ):
        assert f'id="{state_id}"' in html
    assert 'data-state data-state--loading' in html
    assert 'data-state data-state--empty' in html
    assert 'data-state data-state--error' in html
    assert 'Không có booking phù hợp' in html
    assert 'Khách sạn chưa có phòng' in html
    assert 'onclick="loadTimeline()"' in html
    assert html.count('aria-hidden="true"') >= 5


def test_timeline_manager_supports_view_ranges_filters_and_feedback_states():
    source = open('static/js/timeline_manager.js', encoding='utf-8').read()
    styles = open('static/css/style.css', encoding='utf-8').read()

    assert 'function setTimelineViewMode' in source
    assert 'function shiftTimeline' in source
    assert 'function applyTimelineStatusFilter' in source
    assert 'function showTimelineState' in source
    assert "res.ok" in source
    assert "setAttribute('aria-pressed', String(isActive))" in source
    assert "state === 'no-items'" in source
    assert "state === 'empty'" in source
    assert "state === 'error'" in source
    assert "errorDescription.textContent = message" in source
    assert 'stateNode.innerHTML' not in source
    # Lưới tự vẽ (spec 15-08): không còn vis-timeline, tên khách đổ qua textContent
    assert 'function buildTimelineGrid' in source
    assert 'function renderTimelineStats' in source
    assert 'new vis.' not in source
    assert "'2weeks': 14" in source and 'month: 30' in source
    assert '.tlg-toolbar' in styles
    assert '.tlg-seg__btn.active' in styles
    assert '.tlg-legend__item' in styles
    assert '.tlg-bar--overstay' in styles
    assert '.vis-item' not in styles
