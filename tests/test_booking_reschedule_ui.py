def test_timeline_exposes_reschedule_controls(client, seed_hotels, login_as):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    response = client.get(f'/{hotel.slug}/rooms/timeline-view')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="rescheduleModal"' in html
    assert 'id="reschedule-room-select"' in html
    assert 'id="reschedule-reason"' in html
    assert 'value="keep"' in html
    assert 'value="reprice"' in html
    assert 'id="reschedule-check-availability"' in html
    assert 'id="reschedule-price-summary"' in html
    assert 'id="bd-reschedule-history"' in html


def test_reschedule_endpoint_is_mapped_to_timeline_blueprint():
    source = open('static/js/main.js', encoding='utf-8').read()
    timeline_source = open('static/js/timeline_manager.js', encoding='utf-8').read()

    assert "'/api/bookings/reschedule'" in source
    assert "data.status === 'booked'" in timeline_source
