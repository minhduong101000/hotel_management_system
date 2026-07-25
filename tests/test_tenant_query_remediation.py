import pytest
from extensions import db
from models import Hotel, Room, Booking, BookingRoom, Customer

def test_timeline_room_update_rejects_cross_tenant(client, seed_hotels, login_as):
    """
    Timeline room update API should return 404 if booking_room_id belongs to another hotel,
    rather than throwing a 500 error due to tenant_query(...).get(...)
    """
    hotel_a, hotel_b, user_a, master_admin, br_a, br_b = seed_hotels

    # Login to Hotel A
    login_as(client, user_a)
    
    # Try to move BookingRoom from Hotel B into Room in Hotel A via timeline API
    res = client.post("/central/timeline/api/timeline/update", data={
        "booking_room_id": br_b.id,
        "new_room_id": br_a.room_id,
        "new_start": "2026-07-25T14:00",
        "new_end": "2026-07-26T12:00"
    })
    
    # The endpoint should gracefully return 404 since br_b belongs to Hotel B
    assert res.status_code == 404

def test_booking_detail_rejects_cross_tenant(client, seed_hotels, login_as):
    """
    Booking API should return 404 if booking_id belongs to another hotel
    """
    hotel_a, hotel_b, user_a, master_admin, br_a, br_b = seed_hotels

    # Login to Hotel A
    login_as(client, user_a)
    
    # Try to view Booking from Hotel B
    res = client.get(f"/central/booking/{br_b.booking_id}")
    
    # The endpoint should return 404
    assert res.status_code == 404
