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


def test_staff_timeline_hides_reschedule_action_and_disables_dragging(
    client, seed_hotels, login_as
):
    from extensions import db
    from models import User

    hotel, _, _, _, _, _ = seed_hotels
    staff = User(username="timeline_staff", role="staff", hotel_id=hotel.id)
    staff.set_password("correct-password")
    db.session.add(staff)
    db.session.commit()
    login_as(client, staff)

    page = client.get(f"/{hotel.slug}/rooms/timeline-view")
    timeline = client.get(f"/{hotel.slug}/timeline/api/bookings/timeline")

    assert page.status_code == 200
    assert 'id="btn-reschedule-booking"' not in page.get_data(as_text=True)
    assert timeline.status_code == 200
    assert all(item["editable"] is False for item in timeline.get_json()["items"])
