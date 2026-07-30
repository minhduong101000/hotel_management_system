import pytest
from sqlalchemy import event

from extensions import db
from models.room import Room


@pytest.mark.parametrize("room_total", [4, 40])
def test_room_dashboard_query_count_does_not_grow_with_room_total(
    client, seed_hotels, login_as, room_total
):
    hotel, _, admin, _, active_stay, _ = seed_hotels
    active_stay.status = "checked_in"
    active_stay.room.status = "occupied"
    for number in range(2, room_total + 1):
        db.session.add(
            Room(
                hotel_id=hotel.id,
                room_number=f"{number:03d}",
                room_type="Standard",
                price_per_night=500_000,
                price_initial_block=300_000,
                initial_hours=2,
            )
        )
    db.session.commit()
    login_as(client, admin)

    statements = []

    def count_statement(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(db.engine, "before_cursor_execute", count_statement)
    try:
        response = client.get(f"/{hotel.slug}/rooms/api/rooms")
    finally:
        event.remove(db.engine, "before_cursor_execute", count_statement)

    assert response.status_code == 200
    assert len(response.get_json()["rooms"]) == room_total
    assert len(statements) <= 5, "\n\n".join(statements)
