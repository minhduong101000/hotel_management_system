from extensions import db
from models import Booking, BookingRoom
from datetime import datetime, timedelta

def test_rooms_api_returns_correct_notices(client, seed_hotels, login_as):
    hotel_a, _, user_a, _, br_a, _ = seed_hotels
    
    # Create another booking for the SAME room
    now = datetime.now()
    booking2 = Booking(hotel_id=hotel_a.id, code="BK_TEST_2", customer_id=br_a.booking.customer_id)
    db.session.add(booking2)
    db.session.flush()
    
    br_a2 = BookingRoom(
        hotel_id=hotel_a.id, 
        booking_id=booking2.id, 
        room_id=br_a.room_id, 
        check_in_expected=now + timedelta(hours=5), 
        check_out_expected=now + timedelta(days=1, hours=5), 
        status='booked'
    )
    db.session.add(br_a2)
    db.session.commit()
    
    login_as(client, user_a)
    response = client.get(f"/{hotel_a.slug}/rooms/api/rooms")
    data = response.json
    rooms = data.get("rooms", [])
    
    room_data = next((r for r in rooms if r["id"] == br_a.room_id), None)
    assert room_data is not None
    assert "notices" in room_data
    assert len(room_data["notices"]) == 2
    
    notice_ids = [n["booking_room_id"] for n in room_data["notices"]]
    assert br_a.id in notice_ids
    assert br_a2.id in notice_ids
    
    # Check exact fields in one notice
    n1 = next(n for n in room_data["notices"] if n["booking_room_id"] == br_a.id)
    assert "type" in n1
    assert "status" in n1
    assert "guest_name" in n1
    assert "check_in_expected" in n1
    assert "check_out_expected" in n1
    assert "deposit" in n1
    
    # ensure it doesn't leak hotel_b
    hotel_b = seed_hotels[1]
    br_b = seed_hotels[5]
    assert br_b.id not in notice_ids
