# Kế hoạch triển khai: Khắc phục tenant query và thông báo booking

> **Dành cho agentic workers:** BẮT BUỘC dùng `superpowers:subagent-driven-development` hoặc `superpowers:executing-plans` để thực hiện từng task theo TDD. Các bước dùng checkbox để theo dõi.

**Mục tiêu:** Không còn lỗi `.get()` trên query đã scope tenant, mọi API tenant-owned chặn truy cập chéo hotel, và Sơ đồ phòng có notice an toàn/đủ dữ liệu với thao tác nhanh.

**Kiến trúc:** Dùng duy nhất `tenant_query` cho danh sách và `tenant_get_or_404` cho lookup bắt buộc. Không dùng refactor regex thêm nữa; thay thế từng query theo hành vi endpoint. API room map trả notice đầy đủ; JavaScript tạo popover qua DOM API để dữ liệu khách luôn qua `textContent`.

**Công nghệ:** Flask, Flask-SQLAlchemy, pytest, SQLite test database, JavaScript thuần, Bootstrap.

## Ràng buộc chung

- Không thay đổi MySQL local; mọi test dùng SQLite từ fixture hiện có.
- Mỗi thay đổi theo red → green → refactor và chạy focused test trước.
- Không dùng `tenant_query(Model).get(...)`.
- Không dùng `Model.query` hoặc `db.session.query(Model)` cho model tenant-owned trong request có `hotel_slug`.
- Không render dữ liệu API của khách bằng `innerHTML`.

---

### Task 1: Loại bỏ `.get()` sai sau tenant query

**Files:**
- Modify: `controllers/timeline_controller.py`
- Modify: `controllers/booking_controller.py`
- Modify: `controllers/room_controller.py`
- Create: `tests/test_tenant_query_regression.py`

**Interfaces:**
- `tenant_get_or_404(Model, id)` dùng khi endpoint cần 404 nếu không tìm thấy/sai tenant.
- `tenant_query(Model).filter(Model.id == id).first()` dùng khi endpoint chấp nhận `None` và tự trả JSON lỗi.

- [ ] **Bước 1: Viết test thất bại cho endpoint Timeline đang dùng `.get()`**

```python
def test_timeline_update_does_not_raise_query_get_error(client, booked_room, login_as):
    hotel, user, _, booking_room = booked_room
    login_as(client, user)

    response = client.post(f"/{hotel.slug}/timeline/api/bookings/update_timeline", json={
        "id": booking_room.id,
        "room_id": booking_room.room_id,
        "start": booking_room.check_in_expected.strftime("%Y-%m-%dT%H:%M"),
        "end": booking_room.check_out_expected.strftime("%Y-%m-%dT%H:%M"),
    })

    assert response.status_code != 500
```

- [ ] **Bước 2: Chạy test để xác nhận thất bại**

Run: `python -m pytest tests/test_tenant_query_regression.py -v`

Expected: FAIL hoặc HTTP 500 có lỗi `Query.get() being called on a Query with existing criterion`.

- [ ] **Bước 3: Thay từng lookup theo đúng hành vi**

Ví dụ lookup bắt buộc trong Timeline:

```python
br = tenant_get_or_404(BookingRoom, br_id)
old_room = tenant_get_or_404(Room, br.room_id)
new_room = tenant_get_or_404(Room, new_room_id)
```

Ví dụ lookup có thể thiếu trong booking/service:

```python
service = tenant_query(Service).filter(Service.id == service_id).first()
if not service:
    return jsonify(success=False, msg="Không tìm thấy dịch vụ."), 404
```

Thay toàn bộ kết quả của lệnh sau trong ba controller, không thay bằng regex tự động:

```powershell
rg -n "tenant_query\([^\)]*\)\.get\(" controllers/timeline_controller.py controllers/booking_controller.py controllers/room_controller.py
```

- [ ] **Bước 4: Chạy focused test và scan**

Run:

```powershell
python -m pytest tests/test_tenant_query_regression.py -v
rg -n "tenant_query\([^\)]*\)\.get\(" controllers/timeline_controller.py controllers/booking_controller.py controllers/room_controller.py
```

Expected: pytest PASS; `rg` không có kết quả.

- [ ] **Bước 5: Commit**

```powershell
git add controllers/timeline_controller.py controllers/booking_controller.py controllers/room_controller.py tests/test_tenant_query_regression.py
git commit -m "fix: remove invalid tenant query get calls"
```

### Task 2: Hoàn chỉnh scope tenant ở endpoint theo ID

**Files:**
- Modify: `controllers/customer_controller.py`
- Modify: `controllers/service_controller.py`
- Modify: `controllers/warehouse_controller.py`
- Modify: `controllers/expense_controller.py`
- Modify: `controllers/price_controller.py`
- Modify: `controllers/billing_controller.py`
- Modify: `controllers/cashier_controller.py`
- Modify: `controllers/report_controller.py`
- Modify: `services/pricing_service.py`
- Modify: `services/inventory_service.py`
- Modify: `tests/test_tenant_isolation.py`

**Interfaces:**
- Với update/delete/detail theo ID, dùng `tenant_get_or_404`.
- Với list/report, bắt đầu bằng `tenant_query(Model)` trước mọi filter, join, aggregate hoặc count.

- [ ] **Bước 1: Viết test thất bại cho các resource quan trọng còn trực tiếp query**

```python
@pytest.mark.parametrize("path", [
    "/customers/api/customers/{customer_id}",
    "/services/api/services/{service_id}",
    "/warehouse/api/warehouse/{inventory_id}",
    "/expenses/api/expenses/{expense_id}",
])
def test_hotel_cannot_mutate_other_hotel_resource(client, two_hotel_resources, login_as, path):
    hotel_a, user_a, hotel_b_ids = two_hotel_resources
    login_as(client, user_a)
    response = client.delete(f"/{hotel_a.slug}" + path.format(**hotel_b_ids))
    assert response.status_code == 404
```

Tạo fixture `two_hotel_resources` với `Customer`, `Service`, `InventoryItem`, `Expense` ở hotel B, có ID và các foreign key hợp lệ.

- [ ] **Bước 2: Chạy test để xác nhận thất bại**

Run: `python -m pytest tests/test_tenant_isolation.py -v`

Expected: FAIL vì endpoint dùng `Model.query.get(...)` hoặc list/report lấy dữ liệu không lọc `hotel_id`.

- [ ] **Bước 3: Scope từng controller và service**

Mẫu bắt buộc cho xóa/sửa:

```python
resource = tenant_get_or_404(ResourceModel, resource_id)
```

Mẫu bắt buộc cho list:

```python
query = tenant_query(ResourceModel)
items = query.order_by(ResourceModel.id.desc()).all()
```

Mẫu cho aggregate/join:

```python
query = tenant_query(BookingRoom).join(Booking)
query = query.filter(Booking.hotel_id == current_hotel_id())
```

Rà bằng lệnh sau, phân loại mỗi kết quả là system-only hoặc thay helper; không giữ query tenant-owned trực tiếp trong controller/service:

```powershell
rg -n "\b(Room|Booking|BookingRoom|Customer|Service|Payment|InventoryItem|Expense|PriceRule)\.query\b|db\.session\.query\((Room|Booking|BookingRoom|Customer|Service|Payment|InventoryItem|Expense|PriceRule)" controllers services -g '*.py'
```

- [ ] **Bước 4: Chạy focused tests**

Run: `python -m pytest tests/test_tenant_isolation.py -v`

Expected: PASS; mọi ID thuộc hotel B trả 404 khi gọi qua URL hotel A.

- [ ] **Bước 5: Commit**

```powershell
git add controllers services tests/test_tenant_isolation.py
git commit -m "fix: scope tenant-owned endpoints by hotel"
```

### Task 3: Hoàn thiện dữ liệu notice và test contract API

**Files:**
- Modify: `controllers/room_controller.py`
- Modify: `tests/test_room_notices.py`

**Interfaces:**
- `notices: list[dict]`, mỗi phần tử gồm `booking_room_id`, `type`, `status`, `guest_name`, `check_in_expected`, `check_out_expected`, `deposit`.

- [ ] **Bước 1: Mở rộng test thất bại thành contract đầy đủ**

```python
assert room_data["notices"] == [{
    "booking_room_id": br_a.id,
    "type": "waiting",
    "status": "booked",
    "guest_name": "Nguyen Van A",
    "check_in_expected": br_a.check_in_expected.strftime("%Y-%m-%dT%H:%M"),
    "check_out_expected": br_a.check_out_expected.strftime("%Y-%m-%dT%H:%M"),
    "deposit": float(br_a.room_deposit_amount or 0),
}]
```

Tạo booking hotel B cho cùng thời điểm và xác nhận ID đó không xuất hiện. Tạo hai booking hotel A có giờ khác nhau và assert mảng tăng dần theo `check_in_expected`.

- [ ] **Bước 2: Chạy test để xác nhận thất bại**

Run: `python -m pytest tests/test_room_notices.py -v`

Expected: FAIL vì API hiện trả thiếu `status`, giờ trả và tiền cọc, đồng thời format giờ chưa theo ISO contract.

- [ ] **Bước 3: Trả đúng contract từ API**

```python
notices_map[br.room_id].append({
    "booking_room_id": br.id,
    "type": "waiting" if br.check_in_expected < now else "upcoming",
    "status": br.status,
    "guest_name": customer_name,
    "check_in_expected": br.check_in_expected.strftime("%Y-%m-%dT%H:%M"),
    "check_out_expected": br.check_out_expected.strftime("%Y-%m-%dT%H:%M"),
    "deposit": float(br.room_deposit_amount or 0),
})
```

Giữ `.order_by(BookingRoom.check_in_expected.asc())`; chỉ đưa booking `booked` của `tenant_query(BookingRoom)` vào map.

- [ ] **Bước 4: Chạy focused test**

Run: `python -m pytest tests/test_room_notices.py -v`

Expected: PASS.

- [ ] **Bước 5: Commit**

```powershell
git add controllers/room_controller.py tests/test_room_notices.py
git commit -m "feat: return complete room booking notices"
```

### Task 4: Popover an toàn cho notice trên Sơ đồ phòng

**Files:**
- Modify: `templates/rooms/map.html`
- Modify: `static/js/room.js`
- Modify: `static/css/style.css`
- Modify: `tests/test_ui_regression.py`

**Interfaces:**
- `openBookingNoticePopover(notice, anchor)` nhận notice contract Task 3 và card DOM.
- `performCheckIn(bookingRoomId)` chỉ gọi API khi `Number.isInteger(bookingRoomId) && bookingRoomId > 0`.
- `openTimelineDetail(bookingRoomId)` chuyển đến Timeline với query string `booking_room_id` đã `encodeURIComponent`.

- [ ] **Bước 1: Viết test thất bại kiểm tra contract render an toàn**

```python
def test_room_map_does_not_embed_untrusted_guest_name_as_html(client, upcoming_booking, login_as):
    hotel, user, room, booking_room = upcoming_booking
    booking_room.booking.customer.name = '<img src=x onerror=alert(1)>'
    db.session.commit()
    login_as(client, user)

    response = client.get(f"/{hotel.slug}/rooms/dashboard/room-map")
    assert response.status_code == 200
    assert b"openBookingNoticePopover" in response.data
    assert b"textContent" in response.data
```

- [ ] **Bước 2: Chạy test để xác nhận thất bại**

Run: `python -m pytest tests/test_ui_regression.py -v`

Expected: FAIL vì notice hiện tạo bằng template string trong `innerHTML`.

- [ ] **Bước 3: Tạo popover bằng DOM API**

Tạo static popover container trong `map.html`. Trong `room.js`, card chỉ giữ `data-booking-room-id`; event listener gọi hàm dưới đây:

```javascript
function addText(parent, value, className = '') {
  const node = document.createElement('span');
  node.className = className;
  node.textContent = String(value ?? '—');
  parent.appendChild(node);
  return node;
}
```

Dùng `addText` cho tên khách, giờ nhận/trả, cọc và trạng thái. Tạo button bằng `document.createElement('button')`, gán `addEventListener('click', ...)`; không dùng `onclick` string cho notice. Popover có nút `Nhận phòng`, `Xem chi tiết`; card phòng trống không notice có menu `Đặt trước`, `Vào ở ngay`.

- [ ] **Bước 4: Chạy test và kiểm tra thủ công**

Run: `python -m pytest tests/test_ui_regression.py tests/test_checkin.py -v`

Expected: PASS.

Kiểm tra: tên chứa HTML hiện nguyên văn; notice mở popover; `Nhận phòng` cập nhật đúng booking-room; `Xem chi tiết` đi đúng Timeline.

- [ ] **Bước 5: Commit**

```powershell
git add templates/rooms/map.html static/js/room.js static/css/style.css tests/test_ui_regression.py
git commit -m "fix: render room booking notices safely"
```

## Kiểm chứng sau cùng

- [ ] Chạy `rg -n "tenant_query\([^\)]*\)\.get\(" controllers services`; kết quả rỗng.
- [ ] Rà direct query tenant-owned bằng lệnh Task 2; mọi kết quả phải có lý do system-only hoặc được chuyển sang helper.
- [ ] Chạy `python -m pytest -v` trong interpreter Python hoạt động; toàn bộ test pass.
- [ ] Với hai hotel local, xác nhận thủ công: hotel A không xem/sửa/xóa dữ liệu hotel B; master admin vào URL hotel cụ thể thấy đúng hotel context.
