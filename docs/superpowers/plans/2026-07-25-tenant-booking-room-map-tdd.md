# Kế hoạch triển khai: Multi-tenant an toàn, booking và Sơ đồ phòng

> **Dành cho agentic workers:** BẮT BUỘC dùng `superpowers:subagent-driven-development` (khuyến nghị) hoặc `superpowers:executing-plans` để triển khai từng task. Các bước dùng checkbox để theo dõi.

**Mục tiêu:** Khóa dữ liệu theo đúng khách sạn, dùng `booking_room_id` nhất quán khi nhận phòng, và biến Sơ đồ phòng thành nơi thao tác nhanh có thông báo booking rõ ràng.

**Kiến trúc:** Thay filter SQLAlchemy ngầm bằng helper truy vấn tenant tường minh. Endpoint nhận phòng nhận đúng `booking_room_id`; Timeline và Sơ đồ phòng cùng gọi endpoint đó. Sơ đồ phòng chỉ hiển thị/thao tác nhanh, còn Timeline vẫn là nơi chỉnh sửa booking chi tiết.

**Công nghệ:** Python, Flask, Flask-SQLAlchemy, Flask-Login, pytest, SQLite in-memory, JavaScript thuần, Bootstrap.

## Ràng buộc chung

- Toàn bộ test dùng SQLite riêng; không kết nối hoặc thay đổi MySQL local.
- Mọi task theo red → green → refactor; chạy test ở mỗi bước trước khi chuyển task.
- Không thêm tính năng ngoài multi-tenant, booking/check-in, Sơ đồ phòng và style dùng chung đã nêu trong spec.
- Tài khoản master admin là `is_super_admin=True`, không thuộc hotel; mọi hotel admin/staff có đúng một `hotel_id`.
- Không tin `hotel_id`, `room_number` hay `booking_id` do trình duyệt gửi cho thao tác nhận phòng; server chỉ nhận `booking_room_id` và suy ra dữ liệu còn lại.

---

### Task 1: Thiết lập test độc lập và application factory

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_smoke.py`
- Modify: `app.py`
- Modify: `requirements.txt`

**Interfaces:**
- Cung cấp `create_app(test_config: dict | None = None) -> Flask`.
- Fixture `app` tạo database SQLite mới cho từng test; fixture `client` là Flask test client.
- Fixture `seed_hotels` tạo `central` và `riverside`; fixture `login_as` ghi Flask-Login session cho user chỉ định.

- [ ] **Bước 1: Viết test thất bại cho factory và database tách biệt**

```python
# tests/test_smoke.py
def test_factory_uses_test_database(app):
    assert app.config["TESTING"] is True
    assert app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite")

def test_health_request_does_not_require_mysql(client):
    response = client.get("/")
    assert response.status_code in {302, 404}
```

- [ ] **Bước 2: Chạy test để xác nhận thất bại**

Run: `python -m pytest tests/test_smoke.py -v`

Expected: FAIL vì chưa có fixture `app`/`client` và factory test.

- [ ] **Bước 3: Cài dependency test và tách factory tối thiểu**

Thêm chính xác các dòng sau vào `requirements.txt`:

```text
pytest
```

Đưa phần tạo Flask, cấu hình extension và đăng ký blueprint hiện có từ global `app` vào:

```python
def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    Migrate(app, db)
    # giữ nguyên các hook và register_blueprint hiện có ở đây
    return app

app = create_app()
```

Tạo fixture database:

```python
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
```

- [ ] **Bước 4: Chạy lại test**

Run: `python -m pytest tests/test_smoke.py -v`

Expected: PASS, không có kết nối MySQL.

- [ ] **Bước 5: Commit**

```powershell
git add app.py requirements.txt tests/conftest.py tests/test_smoke.py
git commit -m "test: add isolated Flask test setup"
```

### Task 2: Helper truy vấn tenant và quyền đăng nhập theo hotel

**Files:**
- Create: `services/tenant_service.py`
- Create: `tests/test_tenant_isolation.py`
- Modify: `extensions.py`
- Modify: `controllers/auth_controller.py`
- Modify: `controllers/room_controller.py`

**Interfaces:**
- `current_hotel_id() -> int`: trả `g.hotel_id`, abort 404 nếu tenant context vắng mặt.
- `tenant_query(model) -> Query`: query có điều kiện `model.hotel_id == current_hotel_id()`.
- `tenant_get_or_404(model, record_id) -> Model`: trả đúng bản ghi tenant hoặc 404.

- [ ] **Bước 1: Viết test thất bại cho truy cập chéo tenant và login sai hotel**

```python
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
```

Test đầu tiên sử dụng chính endpoint chi tiết booking-room đã có: `GET /<hotel_slug>/timeline/api/bookings/<booking_room_id>`.

- [ ] **Bước 2: Chạy test để xác nhận thất bại**

Run: `python -m pytest tests/test_tenant_isolation.py -v`

Expected: FAIL vì filter global bỏ qua `.first()`/lookup theo ID.

- [ ] **Bước 3: Cài helper và thay thế lookup theo ID của luồng room/booking**

```python
# services/tenant_service.py
from flask import abort, g

def current_hotel_id():
    hotel_id = getattr(g, "hotel_id", None)
    if hotel_id is None:
        abort(404)
    return hotel_id

def tenant_query(model):
    return model.query.filter(model.hotel_id == current_hotel_id())

def tenant_get_or_404(model, record_id):
    return tenant_query(model).filter(model.id == record_id).first_or_404()
```

Xóa listener `ensure_hotel_isolation` trong `extensions.py`. Giữ listener `before_flush` để tự gán `hotel_id`. Thay các `Room.query.get(...)`, `Booking.query.get(...)`, `BookingRoom.query.get(...)` và `filter_by(...).first()` trong `room_controller.py`, `booking_controller.py`, `timeline_controller.py` của luồng này bằng helper hoặc `tenant_query`.

Trong auth, chỉ tìm user thuộc `g.hotel_id`, trừ tài khoản master admin; sau đó giữ kiểm tra quyền hiện có.

- [ ] **Bước 4: Chạy lại test tenant**

Run: `python -m pytest tests/test_tenant_isolation.py -v`

Expected: PASS; hotel A không đọc được dữ liệu hotel B và login sai URL bị chặn.

- [ ] **Bước 5: Commit**

```powershell
git add extensions.py services/tenant_service.py controllers/auth_controller.py controllers/room_controller.py controllers/booking_controller.py controllers/timeline_controller.py tests/test_tenant_isolation.py
git commit -m "fix: scope booking and room access by hotel"
```

### Task 3: Nhận phòng chính xác theo booking-room

**Files:**
- Create: `tests/test_checkin.py`
- Modify: `controllers/booking_controller.py`
- Modify: `static/js/room.js`
- Modify: `static/js/timeline_manager.js`

**Interfaces:**
- `POST /<hotel_slug>/bookings/api/rooms/checkin` body: `{ "booking_room_id": int }`.
- Thành công trả `{ "success": true, "booking_room_id": int, "message": str }`.
- Thất bại trả JSON `{ "success": false, "msg": str }` với 400 hoặc 404 phù hợp.

- [ ] **Bước 1: Viết test thất bại cho định danh booking-room và state transition**

```python
def test_checkin_changes_only_requested_booking_room(client, booked_room, login_as):
    hotel, user, first_booking_room, second_booking_room = booked_room
    login_as(client, user)
    response = client.post(
        f"/{hotel.slug}/bookings/api/rooms/checkin",
        json={"booking_room_id": second_booking_room.id},
    )
    assert response.status_code == 200
    db.session.refresh(first_booking_room)
    db.session.refresh(second_booking_room)
    assert first_booking_room.status == "booked"
    assert second_booking_room.status == "checked_in"

def test_checkin_rejects_booking_room_from_another_hotel(client, seed_hotels, login_as):
    hotel_a, hotel_b, user_a, _, booking_room_a, booking_room_b = seed_hotels
    login_as(client, user_a)
    response = client.post(
        f"/{hotel_a.slug}/bookings/api/rooms/checkin",
        json={"booking_room_id": booking_room_b.id},
    )
    assert response.status_code == 404
```

- [ ] **Bước 2: Chạy test để xác nhận thất bại**

Run: `python -m pytest tests/test_checkin.py -v`

Expected: FAIL vì endpoint hiện nhận room number và có thể chọn dòng booking đầu tiên.

- [ ] **Bước 3: Thực hiện thay đổi tối thiểu**

Trong `checkin_room`, lấy ID và scope tenant trước mọi thao tác:

```python
booking_room_id = request.get_json(silent=True, {}).get("booking_room_id")
if not isinstance(booking_room_id, int):
    return jsonify(success=False, msg="Thiếu booking_room_id hợp lệ."), 400

booking_room = tenant_get_or_404(BookingRoom, booking_room_id)
room = booking_room.room
```

Chỉ tiếp tục nếu status `booked`; kiểm tra sạch, không occupied và mốc ba giờ. Cập nhật booking-room, room và booking cha trong cùng transaction. Bỏ fallback chọn booking đầu tiên.

Trong `room.js`, API upcoming trả thêm `booking_room_id` và `performCheckIn` chỉ gửi ID đó. Trong Timeline, `performCheckInFromTimeline` dùng hidden `bd-booking-room-id` và gọi cùng body.

- [ ] **Bước 4: Chạy focused tests**

Run: `python -m pytest tests/test_checkin.py -v`

Expected: PASS; chính xác một booking-room được nhận phòng và cross-tenant bị 404.

- [ ] **Bước 5: Commit**

```powershell
git add controllers/booking_controller.py static/js/room.js static/js/timeline_manager.js tests/test_checkin.py
git commit -m "fix: check in exact booking room"
```

### Task 4: Dữ liệu thông báo booking và menu thao tác nhanh trên Sơ đồ phòng

**Files:**
- Create: `tests/test_room_map.py`
- Modify: `controllers/room_controller.py`
- Modify: `templates/rooms/map.html`
- Modify: `static/js/room.js`
- Modify: `static/css/style.css`

**Interfaces:**
- Mỗi room có `upcoming_booking` hoặc `waiting_booking` dạng `{booking_room_id, guest_name, check_in_expected, check_out_expected, deposit, status}` hoặc `null`.
- Menu phòng trống không có booking: `Đặt trước`, `Vào ở ngay`.
- Menu booking sắp đến: `Nhận phòng`, `Xem chi tiết`.

- [ ] **Bước 1: Viết test thất bại cho dữ liệu notice**

```python
def test_room_map_returns_complete_upcoming_booking_notice(client, upcoming_booking, login_as):
    hotel, user, room, booking_room = upcoming_booking
    login_as(client, user)
    payload = client.get(f"/{hotel.slug}/rooms/api/rooms").get_json()
    room_payload = next(item for item in payload["rooms"] if item["id"] == room.id)
    assert room_payload["upcoming_booking"] == {
        "booking_room_id": booking_room.id,
        "guest_name": booking_room.booking.customer.name,
        "check_in_expected": booking_room.check_in_expected.strftime("%Y-%m-%dT%H:%M"),
        "check_out_expected": booking_room.check_out_expected.strftime("%Y-%m-%dT%H:%M"),
        "deposit": float(booking_room.room_deposit_amount),
        "status": "booked",
    }
```

- [ ] **Bước 2: Chạy test để xác nhận thất bại**

Run: `python -m pytest tests/test_room_map.py -v`

Expected: FAIL vì API hiện chỉ trả chuỗi `upcoming`/`waiting`.

- [ ] **Bước 3: Trả dữ liệu notice và render menu không dùng inline handler mới**

Backend thay các trường chuỗi bằng object interface nêu trên. Frontend tạo một popup Bootstrap gắn với card; escape mọi chuỗi khách bằng `textContent` trước khi chèn vào DOM.

```javascript
function checkInBooking(bookingRoomId) {
  return fetch(api('/api/rooms/checkin'), {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({booking_room_id: bookingRoomId}),
  });
}
```

Nút `Xem chi tiết` điều hướng đến `/${hotelSlug}/timeline-view?booking_room_id=${encodeURIComponent(id)}`. Timeline đọc query parameter, tải detail qua endpoint hiện có và mở modal detail; không tạo API mới.

- [ ] **Bước 4: Chạy test API và kiểm tra giao diện thủ công**

Run: `python -m pytest tests/test_room_map.py -v`

Expected: PASS.

Kiểm tra thủ công: phòng trống hiện menu hai hành động; booking sắp đến hiện tên khách/cọc/giờ; `Nhận phòng` chỉ chuyển đúng booking; `Xem chi tiết` mở đúng modal Timeline.

- [ ] **Bước 5: Commit**

```powershell
git add controllers/room_controller.py templates/rooms/map.html static/js/room.js static/css/style.css tests/test_room_map.py
git commit -m "feat: add room map booking notice actions"
```

### Task 5: Thành phần UI chung và regression suite

**Files:**
- Modify: `static/css/style.css`
- Create: `static/js/ui_formatters.js`
- Modify: `templates/layouts/base.html`
- Modify: `templates/rooms/map.html`
- Modify: `templates/rooms/timeline.html`
- Modify: `static/js/room.js`
- Modify: `static/js/timeline_manager.js`
- Modify: `tests/test_tenant_isolation.py`
- Modify: `tests/test_checkin.py`
- Modify: `tests/test_room_map.py`

**Interfaces:**
- `window.hotelUi.formatVnd(value)` trả chuỗi VND theo locale `vi-VN`.
- `window.hotelUi.formatDateTime(value)` trả ngày giờ `vi-VN` hoặc `—` khi input rỗng.
- CSS classes: `.status-badge`, `.status-booked`, `.status-checked-in`, `.status-checked-out`, `.status-cancelled`, `.status-dirty`, `.status-maintenance`, `.quick-action-menu`.

- [ ] **Bước 1: Viết test regression thất bại cho master admin context**

```python
def test_master_admin_can_open_selected_hotel_context(client, seed_hotels, login_as):
    hotel_a, _, _, master_admin, *_ = seed_hotels
    login_as(client, master_admin)
    response = client.get(f"/{hotel_a.slug}/rooms/api/rooms")
    assert response.status_code == 200
```

- [ ] **Bước 2: Chạy test để xác nhận hành vi hiện tại hoặc chỉ ra regression**

Run: `python -m pytest tests/test_tenant_isolation.py::test_master_admin_can_open_selected_hotel_context -v`

Expected: PASS nếu master admin đã vào được context URL; nếu FAIL, sửa `load_current_hotel` để master admin vẫn nhận `g.hotel_id` từ URL nhưng không bị từ chối.

- [ ] **Bước 3: Tạo formatter và áp dụng class trạng thái**

```javascript
window.hotelUi = {
  formatVnd(value) {
    return new Intl.NumberFormat('vi-VN', {maximumFractionDigits: 0}).format(Number(value || 0)) + ' đ';
  },
  formatDateTime(value) {
    return value ? new Intl.DateTimeFormat('vi-VN', {dateStyle: 'short', timeStyle: 'short'}).format(new Date(value)) : '—';
  },
};
```

Nạp file này một lần trong `base.html` trước các script màn hình. Dùng formatter và status classes tại Sơ đồ phòng/Timeline; giữ nguyên markup không liên quan. Header hiện `g.current_hotel.name` khi có tenant context để master admin thấy hotel đang hỗ trợ.

- [ ] **Bước 4: Chạy regression suite đầy đủ**

Run: `python -m pytest -v`

Expected: PASS cho toàn bộ test mới, không kết nối MySQL.

- [ ] **Bước 5: Commit**

```powershell
git add static/css/style.css static/js/ui_formatters.js templates/layouts/base.html templates/rooms/map.html templates/rooms/timeline.html static/js/room.js static/js/timeline_manager.js tests
git commit -m "feat: standardize tenant booking interface"
```

## Kiểm chứng sau cùng

- [ ] Chạy `python -m pytest -v` trong virtual environment đã được sửa hoặc environment mới có dependency.
- [ ] Chạy app local bằng database phát triển sau khi backup database; xác nhận login cho hai hotel khác nhau không thấy dữ liệu chéo nhau.
- [ ] Kiểm tra thủ công bốn trường hợp: phòng trống, phòng có booking tương lai, phòng chờ nhận, phòng đang ở.
- [ ] Kiểm tra booking đoàn: chọn một phòng cụ thể từ Sơ đồ phòng chỉ nhận phòng đúng `booking_room_id`.
- [ ] Xác nhận master admin thấy tên hotel context khi hỗ trợ, còn hotel admin/staff không có chức năng đổi hotel.
