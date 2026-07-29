from datetime import datetime

from extensions import db
from models.audit_event import AuditEvent


def test_hotel_admin_reads_only_own_activity_log(client, seed_hotels, login_as):
    hotel_a, hotel_b, user_a, _, _, _ = seed_hotels
    db.session.add_all([
        AuditEvent(hotel_id=hotel_a.id, actor_user_id=user_a.id, action='checkin', entity_type='booking_room', entity_id=10, created_at=datetime.now()),
        AuditEvent(hotel_id=hotel_b.id, action='checkout', entity_type='booking_room', entity_id=20, created_at=datetime.now()),
    ])
    db.session.commit()
    login_as(client, user_a)

    response = client.get(f'/{hotel_a.slug}/activity-log/api/events')

    assert response.status_code == 200
    assert response.json['total'] == 1
    assert response.json['items'][0]['action'] == 'checkin'


def test_hotel_admin_sees_activity_log_page_and_navigation(client, seed_hotels, login_as):
    hotel, _, user, _, _, _ = seed_hotels
    login_as(client, user)

    response = client.get(f'/{hotel.slug}/activity-log/')

    assert response.status_code == 200
    assert 'Nhật ký hoạt động'.encode() in response.data
    assert b'audit-list' in response.data


def test_activity_log_paginates_and_includes_actor_name(client, seed_hotels, login_as):
    hotel, _, user, _, _, _ = seed_hotels
    db.session.add_all([
        AuditEvent(hotel_id=hotel.id, actor_user_id=user.id, action=f'action_{index}', entity_type='booking_room', entity_id=index, created_at=datetime(2030, 1, index + 1))
        for index in range(3)
    ])
    db.session.commit(); login_as(client, user)

    response = client.get(f'/{hotel.slug}/activity-log/api/events?page=2&per_page=1')

    assert response.status_code == 200
    assert response.json['total'] == 3
    assert response.json['page'] == 2
    assert response.json['total_pages'] == 3
    assert len(response.json['items']) == 1
    assert response.json['items'][0]['actor_name'] == user.username


def test_activity_log_filters_by_business_group(client, seed_hotels, login_as):
    hotel, _, user, _, _, _ = seed_hotels
    db.session.add_all([
        AuditEvent(hotel_id=hotel.id, actor_user_id=user.id, action='create_booking', entity_type='booking_room', entity_id=1, created_at=datetime.now()),
        AuditEvent(hotel_id=hotel.id, actor_user_id=user.id, action='restock_inventory', entity_type='inventory_item', entity_id=2, created_at=datetime.now()),
    ])
    db.session.commit(); login_as(client, user)

    response = client.get(f'/{hotel.slug}/activity-log/api/events?group=booking')

    assert response.status_code == 200
    assert response.json['total'] == 1
    assert response.json['items'][0]['action'] == 'create_booking'


def test_activity_log_page_has_group_filter_and_pagination_controls(client, seed_hotels, login_as):
    hotel, _, user, _, _, _ = seed_hotels
    login_as(client, user)

    response = client.get(f'/{hotel.slug}/activity-log/')

    assert b'id="audit-group"' in response.data
    assert b'id="audit-pagination"' in response.data
