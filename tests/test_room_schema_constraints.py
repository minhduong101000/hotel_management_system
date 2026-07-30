import pytest
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.hotel import Hotel
from models.room import Room


def test_room_metadata_scopes_number_uniqueness_to_hotel():
    constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in Room.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }

    assert constraints == {
        "uq_rooms_hotel_room_number": ("hotel_id", "room_number")
    }


def test_room_number_can_repeat_across_hotels_but_not_within_one_hotel(app):
    hotel_a = Hotel(name="Khách sạn A", slug="room-constraint-a")
    hotel_b = Hotel(name="Khách sạn B", slug="room-constraint-b")
    db.session.add_all([hotel_a, hotel_b])
    db.session.flush()

    db.session.add_all(
        [
            Room(
                hotel_id=hotel_a.id,
                room_number="101",
                room_type="Standard",
                price_per_night=500_000,
                price_initial_block=300_000,
                initial_hours=2,
            ),
            Room(
                hotel_id=hotel_b.id,
                room_number="101",
                room_type="Standard",
                price_per_night=500_000,
                price_initial_block=300_000,
                initial_hours=2,
            ),
        ]
    )
    db.session.commit()

    db.session.add(
        Room(
            hotel_id=hotel_a.id,
            room_number="101",
            room_type="Standard",
            price_per_night=500_000,
            price_initial_block=300_000,
            initial_hours=2,
        )
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
