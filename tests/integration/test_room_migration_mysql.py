from pathlib import Path

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app import create_app
from extensions import db
from models.hotel import Hotel
from models.room import Room


pytestmark = pytest.mark.mysql
MIGRATIONS_DIRECTORY = str(
    Path(__file__).resolve().parents[2] / "migrations"
)


def _migration_app(database_url):
    return create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": database_url,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "mysql-migration-test-secret",
        }
    )


def _upgrade(database_url, revision="head"):
    app = _migration_app(database_url)
    with app.app_context():
        upgrade(directory=MIGRATIONS_DIRECTORY, revision=revision)
        db.engine.dispose()


def _room_unique_constraints():
    return {
        constraint["name"]: tuple(constraint["column_names"])
        for constraint in inspect(db.engine).get_unique_constraints("rooms")
    }


def test_empty_database_upgrade_enforces_tenant_room_number(mysql_database_url):
    app = _migration_app(mysql_database_url)
    with app.app_context():
        upgrade(directory=MIGRATIONS_DIRECTORY)

        assert _room_unique_constraints() == {
            "uq_rooms_hotel_room_number": ("hotel_id", "room_number")
        }

        hotel_a = Hotel.query.filter_by(slug="central").one()
        hotel_b = Hotel(name="Khách sạn B", slug="room-mysql-b")
        db.session.add(hotel_b)
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
        db.session.rollback()
        db.engine.dispose()


@pytest.mark.parametrize("old_head", ["a6b0c4d8e1f3", "c8d2e3f4a5b6"])
def test_upgrade_from_each_previous_head(mysql_database_url, old_head):
    _upgrade(mysql_database_url, old_head)
    _upgrade(mysql_database_url)

    app = _migration_app(mysql_database_url)
    with app.app_context():
        assert _room_unique_constraints() == {
            "uq_rooms_hotel_room_number": ("hotel_id", "room_number")
        }
        db.engine.dispose()


def test_upgrade_stops_when_same_hotel_has_duplicate_room_numbers(
    mysql_database_url,
    capsys,
):
    app = _migration_app(mysql_database_url)
    with app.app_context():
        upgrade(directory=MIGRATIONS_DIRECTORY, revision="d9e3f4a5b6c7")

        old_constraint = next(
            constraint
            for constraint in inspect(db.engine).get_unique_constraints("rooms")
            if tuple(constraint["column_names"]) == ("room_number",)
        )
        db.session.execute(
            db.text(f"ALTER TABLE rooms DROP INDEX `{old_constraint['name']}`")
        )
        db.session.execute(
            db.text(
                "INSERT INTO rooms "
                "(hotel_id, room_number, room_type, price_per_night, "
                "price_initial_block, initial_hours) "
                "VALUES (1, 'DUP', 'Standard', 500000, 300000, 2), "
                "(1, 'DUP', 'Standard', 500000, 300000, 2)"
            )
        )
        db.session.commit()

        capsys.readouterr()
        with pytest.raises(SystemExit):
            upgrade(directory=MIGRATIONS_DIRECTORY)
        assert "trùng số phòng" in capsys.readouterr().err
        db.engine.dispose()


def test_downgrade_stops_when_hotels_share_a_room_number(
    mysql_database_url,
    capsys,
):
    app = _migration_app(mysql_database_url)
    with app.app_context():
        upgrade(directory=MIGRATIONS_DIRECTORY)

        hotel_a = Hotel.query.filter_by(slug="central").one()
        hotel_b = Hotel(name="Khách sạn B", slug="downgrade-room-b")
        db.session.add(hotel_b)
        db.session.flush()
        db.session.add_all(
            [
                Room(
                    hotel_id=hotel_a.id,
                    room_number="SHARED",
                    room_type="Standard",
                    price_per_night=500_000,
                    price_initial_block=300_000,
                    initial_hours=2,
                ),
                Room(
                    hotel_id=hotel_b.id,
                    room_number="SHARED",
                    room_type="Standard",
                    price_per_night=500_000,
                    price_initial_block=300_000,
                    initial_hours=2,
                ),
            ]
        )
        db.session.commit()

        capsys.readouterr()
        with pytest.raises(SystemExit):
            downgrade(
                directory=MIGRATIONS_DIRECTORY,
                revision="d9e3f4a5b6c7",
            )
        assert "unique số phòng toàn hệ thống" in capsys.readouterr().err
        db.engine.dispose()
