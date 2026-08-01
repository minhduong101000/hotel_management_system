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
        'timeline-status-filter',
        'timeline-state',
        'timeline-empty-notice',
    ):
        assert f'id="{control_id}"' in html

    for group_class in (
        'timeline-toolbar-group--range',
        'timeline-toolbar-group--view',
        'timeline-toolbar-group--actions',
    ):
        assert group_class in html
    assert 'timeline-range-controls button-group' in html
    assert 'timeline-view-switch button-group' in html
    assert 'timeline-toolbar-actions button-group' in html
    assert 'id="timeline-view-day"' in html and 'aria-pressed="false"' in html
    assert 'id="timeline-view-3days"' in html and 'aria-pressed="true"' in html
    assert 'onclick="setTimelineViewMode(' in html
    assert 'onclick="shiftTimeline(' in html
    assert 'onchange="applyTimelineStatusFilter()"' in html


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
    assert '.timeline-toolbar-group--range' in styles
    assert '.timeline-toolbar-group--view' in styles
    assert '.timeline-toolbar-group--actions' in styles
    assert '.timeline-legend .legend-item' in styles
    assert '.legend-overstay { background: linear-gradient' not in styles
