# Kế hoạch TDD: Master Console và quản trị admin theo khách sạn

**Mục tiêu:** Xây dựng giao diện Master Console riêng để quản lý hotel, tạo Hotel admin và vào hỗ trợ từng hotel; đồng thời cô lập quản lý user theo `hotel_id`.

**Phạm vi:** Thực hiện đúng spec `2026-07-26-master-admin-and-hotel-admin-design.md`. Không thêm dashboard doanh thu, role mới hoặc multi-hotel user.

## Quy tắc thực hiện

- Mỗi task: test thất bại → code tối thiểu → test pass → refactor → commit.
- Test dùng SQLite fixture hiện có; không dùng MySQL local.
- Không tự chạy `refactor.py`; thay đổi query tenant phải tường minh.
- Không commit nếu test của task chưa pass.

---

### Task 1: Phân tách quyền Master admin

**Files:**

- Modify: `decorators.py`
- Modify: `app.py`
- Create: `controllers/master_controller.py`
- Create: `tests/test_master_access.py`

**Mục tiêu:** Chỉ Master admin truy cập `/master/*`; Hotel admin và staff nhận 403.

1. Viết test thất bại:

```python
def test_master_can_open_console(client, seed_hotels, login_as):
    _, _, _, master, *_ = seed_hotels
    login_as(client, master, path="/master/login")
    assert client.get("/master").status_code == 200

def test_hotel_admin_cannot_open_console(client, seed_hotels, login_as):
    _, _, hotel_admin, *_ = seed_hotels
    login_as(client, hotel_admin)
    assert client.get("/master").status_code == 403
```

2. Chạy:

```powershell
python -m pytest tests/test_master_access.py -v
```

Kỳ vọng: FAIL vì chưa có route/guard Master.

3. Thêm decorator:

```python
def master_admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if not current_user.is_super_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped
```

4. Tạo `master_bp`, route `/master/login` chỉ xác thực `User.is_super_admin=True`; đăng ký blueprint không có tenant prefix trong `create_app`.

5. Chạy lại focused test; commit:

```powershell
git add decorators.py app.py controllers/master_controller.py tests/test_master_access.py
git commit -m "feat: add master admin access control"
```

### Task 2: Master Console dashboard và danh sách hotel

**Files:**

- Modify: `controllers/master_controller.py`
- Create: `templates/master/base.html`
- Create: `templates/master/dashboard.html`
- Create: `templates/master/hotels.html`
- Modify: `tests/test_master_access.py`

**Mục tiêu:** Master xem tổng quan hệ thống và danh sách hotel, không nhận booking/khách chi tiết trộn tenant.

1. Viết test thất bại:

```python
def test_master_dashboard_returns_system_counts_only(client, seed_hotels, login_as):
    hotel_a, hotel_b, _, master, *_ = seed_hotels
    login_as(client, master, path="/master/login")
    response = client.get("/master")
    assert response.status_code == 200
    assert b"Master Console" in response.data
    assert str(2).encode() in response.data
    assert b"Nguyen Van A" not in response.data

def test_master_hotel_list_contains_each_hotel(client, seed_hotels, login_as):
    hotel_a, hotel_b, _, master, *_ = seed_hotels
    login_as(client, master, path="/master/login")
    response = client.get("/master/hotels")
    assert hotel_a.name.encode() in response.data
    assert hotel_b.name.encode() in response.data
```

2. Chạy focused test; xác nhận FAIL.

3. Implement:

- `/master` trả tổng `Hotel`, hotel active/inactive, `Room`, room occupied, booking tạo trong ngày.
- `/master/hotels` trả danh sách hotel kèm số phòng, số user và Hotel admin đầu tiên.
- Dùng query theo `Hotel.id` để group count; dashboard không serialize Customer/Booking detail.
- Dùng layout `templates/master/base.html` riêng, có nhãn `Master Console`.

4. Chạy test Task 2; commit:

```powershell
git add controllers/master_controller.py templates/master tests/test_master_access.py
git commit -m "feat: add master console dashboard"
```

### Task 3: Tạo hotel và Hotel admin trong transaction

**Files:**

- Modify: `controllers/master_controller.py`
- Modify: `templates/master/hotels.html`
- Create: `tests/test_master_hotel_creation.py`

**Mục tiêu:** Master tạo hotel cùng admin đầu tiên; lỗi validation rollback toàn bộ.

1. Viết test thất bại:

```python
def test_master_creates_hotel_and_first_admin(client, app, seed_hotels, login_as):
    _, _, _, master, *_ = seed_hotels
    login_as(client, master, path="/master/login")
    response = client.post("/master/hotels/create", data={
        "name": "Sunrise Hotel", "slug": "sunrise",
        "admin_username": "sunrise_admin", "admin_password": "safe-password",
    })
    assert response.status_code == 302
    hotel = Hotel.query.filter_by(slug="sunrise").one()
    admin = User.query.filter_by(username="sunrise_admin").one()
    assert admin.hotel_id == hotel.id
    assert admin.role == "admin"
    assert admin.is_super_admin is False
    assert admin.password_hash != "safe-password"

def test_duplicate_slug_rolls_back_hotel_and_admin(client, seed_hotels, login_as):
    hotel_a, _, _, master, *_ = seed_hotels
    login_as(client, master, path="/master/login")
    response = client.post("/master/hotels/create", data={
        "name": "Duplicate", "slug": hotel_a.slug,
        "admin_username": "new_admin", "admin_password": "safe-password",
    })
    assert response.status_code == 400
    assert User.query.filter_by(username="new_admin").first() is None
```

2. Chạy test; xác nhận FAIL.

3. Implement trong một `try/except` transaction: validate input, kiểm tra slug/username, `db.session.add(hotel)`, `flush`, tạo `User(... hotel_id=hotel.id)`, `set_password`, `commit`; mọi exception `rollback` và trả lỗi 400.

4. Thêm form tạo hotel + Hotel admin trong Master Console; không đưa `is_super_admin` hoặc `hotel_id` vào input client.

5. Chạy test Task 3; commit.

### Task 4: Vào hỗ trợ hotel và trạng thái hoạt động

**Files:**

- Modify: `controllers/master_controller.py`
- Modify: `templates/layouts/base.html`
- Modify: `tests/test_master_access.py`

**Mục tiêu:** Master vào đúng tenant context; hotel inactive chặn login user thường.

1. Viết test thất bại:

```python
def test_master_enter_redirects_to_selected_hotel(client, seed_hotels, login_as):
    hotel_a, _, _, master, *_ = seed_hotels
    login_as(client, master, path="/master/login")
    response = client.get(f"/master/hotels/{hotel_a.id}/enter")
    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        f"/{hotel_a.slug}/rooms/dashboard/room-map"
    )

def test_inactive_hotel_blocks_hotel_admin_login(client, seed_hotels):
    hotel_a, _, user_a, *_ = seed_hotels
    hotel_a.is_active = False
    db.session.commit()
    response = client.post(f"/{hotel_a.slug}/login", data={
        "username": user_a.username, "password": "correct-password",
    })
    assert response.status_code in {403, 404}
```

2. Chạy test; xác nhận FAIL nếu behavior chưa đúng.

3. Implement route `enter` bằng `tenant_get_or_404(Hotel, hotel_id)` không phù hợp vì Master route không có `g.hotel_id`; dùng `Hotel.query.get_or_404(hotel_id)` chỉ tại Master Console. Route redirect tới map tenant. Thêm action toggle active POST với confirm UI.

4. Trong tenant layout, nếu `current_user.is_super_admin`, hiển thị nhãn `Đang hỗ trợ: <tên hotel>` và link `/master`.

5. Chạy test Task 4; commit.

### Task 5: Cô lập quản lý user của Hotel admin

**Files:**

- Modify: `controllers/staff_controller.py`
- Modify: `templates/staff/index.html`
- Create: `tests/test_hotel_user_management.py`

**Mục tiêu:** Hotel admin chỉ quản lý user của chính hotel và không thể tạo/đụng Master admin.

1. Viết test thất bại:

```python
def test_hotel_admin_lists_only_own_users(client, seed_hotels, login_as):
    hotel_a, hotel_b, admin_a, _, _, _ = seed_hotels
    login_as(client, admin_a)
    response = client.get(f"/{hotel_a.slug}/staff/")
    assert b"admin_a" in response.data
    assert b"admin_b" not in response.data

def test_hotel_admin_cannot_delete_user_from_other_hotel(client, seed_hotels, login_as):
    hotel_a, _, admin_a, _, _, _ = seed_hotels
    user_b = User.query.filter_by(username="admin_b").one()
    login_as(client, admin_a)
    response = client.post(f"/{hotel_a.slug}/staff/delete/{user_b.id}")
    assert response.status_code == 404
```

2. Chạy test; xác nhận FAIL.

3. Implement:

- List: `tenant_query(User)` không dùng được vì User master có `hotel_id=NULL`; dùng `User.query.filter(User.hotel_id == g.hotel_id)`.
- Create: `User(..., hotel_id=g.hotel_id, is_super_admin=False)`; role chỉ nhận `admin`/`staff` whitelist.
- Reset/delete: query `User.query.filter(User.id == user_id, User.hotel_id == g.hotel_id).first_or_404()`.
- Chặn xóa self và chặn xóa admin cuối cùng bằng count user role admin trong hotel.

4. Bổ sung test create user không thể nhận hotel khác/super admin và test không xóa admin cuối cùng.

5. Chạy `python -m pytest tests/test_hotel_user_management.py -v`; commit.

## Kiểm chứng cuối

- [ ] `python -m pytest -v` pass trong Python environment hoạt động.
- [ ] Master login vào `/master`; Hotel admin/staff bị 403 với mọi `/master/*`.
- [ ] Master tạo hotel, tạo admin đầu tiên, tạm ngưng/kích hoạt và vào hỗ trợ hotel thành công.
- [ ] Hotel admin không thấy hoặc thao tác user của hotel khác.
- [ ] Không thay đổi dữ liệu MySQL local khi chạy test.
