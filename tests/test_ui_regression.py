import pytest


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


@pytest.mark.parametrize(
    "path",
    (
        "rooms/dashboard/room-map",
        "rooms/timeline-view",
        "customers/customers",
        "billing/billing",
        "cashier/reports/cashier",
        "prices/admin/price-manager",
        "services/services",
        "warehouse/warehouse",
        "reports/reports/revenue",
        "expenses/expenses",
        "staff/",
        "activity-log/",
    ),
)
def test_refreshed_admin_pages_keep_the_application_landmarks(
    client,
    seed_hotels,
    login_as,
    path,
):
    hotel, _, admin, _, _, _ = seed_hotels
    login_as(client, admin)

    response = client.get(f"/{hotel.slug}/{path}")

    assert response.status_code == 200
    assert b'id="app-content"' in response.data
    assert b'class="app-topbar"' in response.data
    assert b'class="app-sidebar"' in response.data


def test_api_helper_maps_addroom_and_no_bare_customer_fetch():
    from pathlib import Path
    main_js = Path("static/js/main.js").read_text(encoding="utf-8")
    timeline_js = Path("static/js/timeline_manager.js").read_text(encoding="utf-8")
    # add-room phải đi qua timeline blueprint (bug 14-08: rơi vào prefix bookings -> 404)
    timeline_block = main_js.split("TIMELINE SPECIALS")[1].split("prefixMap")[0]
    assert "'/api/bookings/add-room'" in timeline_block
    # Không còn fetch trần thiếu prefix tenant
    assert "fetch(`/api/customers" not in timeline_js


def test_external_scripts_are_version_pinned():
    """unpkg không kèm version sẽ trả bản MỚI NHẤT ở mỗi lần cache miss —
    đúng cách vis-timeline từng trôi version và làm gãy Timeline."""
    from pathlib import Path

    for rel in ("templates/rooms/map.html", "templates/rooms/timeline.html"):
        source = Path(rel).read_text(encoding="utf-8")
        assert "unpkg.com/html5-qrcode\"" not in source, f"{rel}: html5-qrcode chưa pin version"
        assert "unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js" in source
