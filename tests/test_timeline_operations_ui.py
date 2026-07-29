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


def test_timeline_manager_supports_view_ranges_filters_and_feedback_states():
    source = open('static/js/timeline_manager.js', encoding='utf-8').read()

    assert 'function setTimelineViewMode' in source
    assert 'function shiftTimeline' in source
    assert 'function applyTimelineStatusFilter' in source
    assert 'function showTimelineState' in source
    assert "res.ok" in source
