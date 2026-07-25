def test_ui_renders_without_crashing(client, seed_hotels, login_as):
    hotel_a, hotel_b, user_a, master_admin, br_a, br_b = seed_hotels
    
    login_as(client, user_a)
    response = client.get(f"/{hotel_a.slug}/rooms/dashboard/room-map")
    assert response.status_code == 200
    assert hotel_a.name.encode('utf-8') in response.data

    client.get(f"/{hotel_a.slug}/logout")

    login_as(client, master_admin)
    response = client.get(f"/{hotel_b.slug}/rooms/dashboard/room-map")
    assert response.status_code == 200
    assert hotel_b.name.encode('utf-8') in response.data
