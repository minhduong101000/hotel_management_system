import pytest
from app import create_app, db

@pytest.fixture()
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-secret",
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture()
def client(app):
    return app.test_client()

@pytest.fixture()
def seed_hotels(app):
    from models import Hotel, User, Room, Customer, Booking, BookingRoom
    from extensions import db
    from datetime import datetime, timedelta

    hotel_a = Hotel(name="Central Hotel", slug="central")
    hotel_b = Hotel(name="Riverside Hotel", slug="riverside")
    db.session.add_all([hotel_a, hotel_b])
    db.session.flush()

    user_a = User(username="admin_a", role="admin", hotel_id=hotel_a.id)
    user_a.set_password("correct-password")
    master_admin = User(username="master", role="admin", is_super_admin=True)
    master_admin.set_password("correct-password")
    
    user_b = User(username="admin_b", role="admin", hotel_id=hotel_b.id)
    user_b.set_password("correct-password")

    db.session.add_all([user_a, user_b, master_admin])
    
    room_a = Room(hotel_id=hotel_a.id, room_number="101", room_type="Standard", price_per_night=500000, price_initial_block=300000, initial_hours=2)
    room_b = Room(hotel_id=hotel_b.id, room_number="101", room_type="Standard", price_per_night=500000, price_initial_block=300000, initial_hours=2)
    db.session.add_all([room_a, room_b])
    db.session.flush()

    customer_a = Customer(hotel_id=hotel_a.id, name="Nguyen Van A")
    customer_b = Customer(hotel_id=hotel_b.id, name="Tran Van B")
    db.session.add_all([customer_a, customer_b])
    db.session.flush()

    booking_a = Booking(hotel_id=hotel_a.id, code="BKA", customer_id=customer_a.id)
    booking_b = Booking(hotel_id=hotel_b.id, code="BKB", customer_id=customer_b.id)
    db.session.add_all([booking_a, booking_b])
    db.session.flush()

    now = datetime.now()
    br_a = BookingRoom(hotel_id=hotel_a.id, booking_id=booking_a.id, room_id=room_a.id, 
                        check_in_expected=now, check_out_expected=now + timedelta(days=1), status='booked')
    br_b = BookingRoom(hotel_id=hotel_b.id, booking_id=booking_b.id, room_id=room_b.id, 
                        check_in_expected=now, check_out_expected=now + timedelta(days=1), status='booked')
    db.session.add_all([br_a, br_b])
    db.session.commit()

    return hotel_a, hotel_b, user_a, master_admin, br_a, br_b

@pytest.fixture()
def login_as():
    def _login(client, user):
        if user.is_super_admin:
            hotel_slug = "central"
        else:
            hotel_slug = user.hotel.slug
            
        client.post(f"/{hotel_slug}/login", data={"username": user.username, "password": "correct-password"}, follow_redirects=True)
    return _login

@pytest.fixture()
def booked_room(app, seed_hotels):
    from models import BookingRoom, Room
    from extensions import db
    hotel_a, _, user_a, _, br_a, _ = seed_hotels
    
    room2 = Room(hotel_id=hotel_a.id, room_number="102", room_type="Standard", price_per_night=500000, price_initial_block=300000, initial_hours=2)
    db.session.add(room2)
    db.session.flush()
    
    br2 = BookingRoom(hotel_id=hotel_a.id, booking_id=br_a.booking_id, room_id=room2.id, status='booked')
    db.session.add(br2)
    db.session.commit()
    
    return hotel_a, user_a, br_a, br2

@pytest.fixture()
def upcoming_booking(app, seed_hotels):
    hotel_a, _, user_a, _, br_a, _ = seed_hotels
    # Just use br_a
    return hotel_a, user_a, br_a.room, br_a


@pytest.fixture()
def utc_container():
    """Ép đồng hồ tiến trình chạy UTC như container production.

    Không dùng monkeypatch.setenv vì thứ tự teardown khiến tzset() chạy trước
    khi biến môi trường được khôi phục.
    """
    import os
    import time as _time

    original = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    _time.tzset()
    try:
        yield
    finally:
        if original is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original
        _time.tzset()
