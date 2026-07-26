# Kế hoạch TDD: Chuẩn hóa giao diện Sơ đồ phòng

**Mục tiêu:** Mọi trạng thái phòng dùng cùng một cấu trúc card, chỉ thay màu/nội dung/action; loại bỏ code notice cũ không còn dùng và giữ luồng check-in chính xác theo `booking_room_id`.

## Phạm vi

- Chuẩn hóa card: trống, có booking, đang ở, quá giờ trả, bẩn, bảo trì.
- Hiển thị nhiều booking notice rõ ràng, không chỉ `notices[0]`.
- Loại bỏ inline style/class trùng lặp và code `.notices-wrapper` không còn tồn tại.
- Không thay đổi quy tắc booking, thanh toán, checkout hay API ngoài trường dữ liệu map đang có.

## Cấu trúc card bắt buộc

Mọi card có cùng ba vùng:

1. `room-card__header`: số phòng, loại phòng, icon trạng thái.
2. `room-card__body`: nhãn trạng thái chính và thông tin phụ.
3. `room-card__footer`: action chính bên trái, badge/trạng thái phụ bên phải.

Trạng thái dùng modifier class: `room-card--available`, `room-card--booked`, `room-card--occupied`, `room-card--overdue`, `room-card--dirty`, `room-card--maintenance`, `room-card--hourly`.

---

### Task 1: Khóa contract dữ liệu và test API

**Files:**

- Modify: `tests/test_room_notices.py`
- Modify: `controllers/room_controller.py` nếu test phát hiện thiếu dữ liệu

1. Viết test thất bại xác nhận room trống có nhiều notice trả theo thời gian tăng dần; mỗi notice có `booking_room_id`, `guest_name`, `check_in_expected`, `check_out_expected`, `deposit`, `status`, `type`.
2. Chạy:

```powershell
python -m pytest tests/test_room_notices.py -v -p no:cacheprovider
```

3. Chỉ sửa API tối thiểu để contract pass; không đổi endpoint.
4. Chạy lại test và commit.

### Task 2: Tạo CSS component thống nhất

**Files:**

- Modify: `static/css/style.css`
- Create: `tests/test_room_map_card_markup.py`

1. Viết test thất bại đọc `static/js/room.js` và xác nhận sáu modifier class cùng ba vùng `room-card__header/body/footer` tồn tại.
2. Tạo class chung cho kích thước, spacing, màu, hover, typography và action; không dùng inline gradient hoặc inline spacing cho trạng thái card.
3. Tạo biến màu riêng cho `available`, `booked`, `occupied`, `overdue`, `dirty`, `maintenance`, `hourly`.
4. Chạy test markup và kiểm tra CSS không còn selector `.notices-wrapper`.

### Task 3: Refactor render card theo một factory

**Files:**

- Modify: `static/js/room.js`
- Modify: `tests/test_room_map_card_markup.py`

1. Viết test thất bại xác nhận `renderRoomCard(room)` là entry point duy nhất và không còn `room.notices[0]`.
2. Tạo `renderRoomCard(room)` trả card DOM; tạo helper `createRoomCardShell(room, modifier, icon)` để dựng ba vùng chung.
3. Tách renderer nhỏ theo trạng thái:

```javascript
renderAvailableCard(room, shell)
renderBookedCard(room, shell)
renderOccupiedCard(room, shell)
renderDirtyCard(room, shell)
renderMaintenanceCard(room, shell)
```

4. Dùng `textContent` cho số phòng, loại phòng, tên khách, giờ và giá; không chèn dữ liệu API vào `innerHTML`/inline `onclick`.
5. Chạy test markup; kiểm tra `rg "notices\[0\]|notices-wrapper|guestName\.innerHTML" static/js/room.js` không có kết quả.

### Task 4: Notice booking và modal nhận phòng

**Files:**

- Modify: `static/js/room.js`
- Modify: `templates/rooms/map.html`
- Modify: `tests/test_checkin.py`
- Modify: `tests/test_room_map_card_markup.py`

1. Viết test thất bại xác nhận action notice dùng `booking_room_id` dạng số nguyên và có thể render nhiều notice.
2. Mỗi notice là button/card nhỏ trong body; bấm vào mở modal xác nhận gồm tên khách, giờ nhận/trả, cọc, trạng thái.
3. `confirmAndCheckIn()` chuyển hidden value bằng `Number(...)`, từ chối nếu không phải số nguyên dương, rồi gửi `{booking_room_id: number}`.
4. Bỏ code popover/notice cũ không dùng.
5. Chạy `tests/test_checkin.py` và test room-map markup.

### Task 5: Kiểm tra trực quan bằng bb-browser

**Files:**

- Không thêm code, chỉ lưu screenshot vào `tmp/`.

1. Chạy app local với database có dữ liệu test/manual.
2. Dùng `bb-browser` mở Sơ đồ phòng và chụp screenshot desktop.
3. Xác nhận trực quan sáu trạng thái: trống, booked, đang ở, quá giờ, bẩn, bảo trì.
4. Bấm notice → modal → xác nhận check-in; kiểm tra room đổi trạng thái đúng.
5. Kiểm tra console errors qua `bb-browser errors` và lưu screenshot trước/sau.

## Kiểm chứng cuối

- [ ] Focused tests của từng task pass.
- [ ] `python -m pytest -q -p no:cacheprovider` pass.
- [ ] `bb-browser` snapshot/screenshot xác nhận card cùng cấu trúc và không có console error.
- [ ] Không có dữ liệu API khách được đưa vào `innerHTML`.
