def test_hotel_a_cannot_read_hotel_b_room(client, seed_hotels, login_as):
    hotel_a, hotel_b, user_a, _, _, booking_room_b = seed_hotels
    login_as(client, user_a)
    response = client.get(
        f"/{hotel_a.slug}/timeline/api/bookings/{booking_room_b.id}"
    )
    assert response.status_code == 404

def test_user_cannot_login_through_other_hotel_url(client, seed_hotels):
    hotel_a, hotel_b, user_a, *_ = seed_hotels
    response = client.post(
        f"/{hotel_b.slug}/login",
        data={"username": user_a.username, "password": "correct-password"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/{hotel_b.slug}/login")

def test_master_admin_can_open_selected_hotel_context(client, seed_hotels, login_as):
    hotel_a, _, _, master_admin, *_ = seed_hotels
    login_as(client, master_admin)
    response = client.get(f"/{hotel_a.slug}/rooms/api/rooms")
    assert response.status_code == 200
