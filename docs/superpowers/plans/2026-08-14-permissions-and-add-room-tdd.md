# Kế hoạch TDD: Chuẩn hóa quyền và add-room

**Ngày:** 14-08-2026 · **Spec nguồn:** `2026-08-14-permissions-and-add-room-design.md` · **Trạng thái:** Sẵn sàng (nghiệp vụ đã chốt cùng ngày)

Chu kỳ mỗi hạng mục: RED → GREEN → regression hạng mục → commit riêng tiếng Anh.

## Bối cảnh code (khảo sát 14-08)

| Thứ | Vị trí |
|---|---|
| Hình mẫu decorator đúng | `decorators.py:47` `room_structure_required` (admin ∨ super_admin, 403 JSON) |
| Decorator cần sửa | `decorators.py:5` `admin_required` (chỉ role admin, flash+redirect mọi loại request) |
| Services CRUD cần chặn | `controllers/service_controller.py:24,52,75` (POST/PUT/DELETE); GET :17 giữ staff |
| Price manager cần chặn | `controllers/price_controller.py` — view :32 + 4 API |
| Unauthorized handler | chưa có — thêm `@login_manager.unauthorized_handler` trong `create_app` (app.py) |
| Add-room mẫu logic | `controllers/timeline_controller.py:471` `create_booking` (conflict check :494, breakdown :614-618, audit :639) |
| JS đã gọi sẵn | `static/js/timeline_manager.js:1366` `addRoomToExistingBooking()` |

## Hạng mục 1 — `admin_required` nhận Master + trả 403 JSON cho API; chặn services/prices

**Files:** `decorators.py`, `controllers/service_controller.py`, `controllers/price_controller.py`, `tests/test_permission_matrix.py` (mới).

RED (tạo user staff + dùng master từ seed):
1. `test_staff_cannot_mutate_services_api` — POST/PUT/DELETE `/api/services` → 403 JSON `error_code='forbidden'`, không mutation, GET vẫn 200.
2. `test_staff_cannot_touch_price_manager` — GET all-data + POST update-base/save-rule + DELETE delete-rule → 403 JSON.
3. `test_master_admin_passes_admin_required_in_tenant` — master (`is_super_admin`, role staff) GET `/central/cashier/api/reports/cashier` → 200 (trước: 302 flash).
4. `test_staff_html_admin_page_still_redirects` — staff GET `/central/expenses/expenses` → 302 (hành vi HTML giữ nguyên).

GREEN: viết lại `admin_required` theo mẫu `room_structure_required` + nhánh JSON/HTML (`request.path` chứa `/api/` hoặc `request.is_json`); thêm `@admin_required` vào 3 mutation services + toàn bộ price_controller.

Commit: `feat: admin_required accepts master admin and returns JSON 403; lock services/prices mutations`

## Hạng mục 2 — 401 JSON khi hết phiên cho API

**Files:** `app.py`, `tests/test_permission_matrix.py`.

RED: `test_unauthenticated_api_gets_401_json` — không login GET `/central/rooms/api/rooms` → 401 + `error_code='unauthenticated'`; GET `/central/billing/billing` → 302 login. Quét test cũ đang assert 302 cho API chưa login và cập nhật theo spec (đối chiếu từng ca trước khi sửa).

GREEN: `@login_manager.unauthorized_handler` trong `create_app`: path chứa `/api/` → 401 JSON; ngược lại redirect `url_for('auth.login', next=...)` như login_view cũ.

Commit: `feat: JSON 401 for unauthenticated API calls`

## Hạng mục 3 — Endpoint add-room

**Files:** `controllers/timeline_controller.py`, `tests/test_add_room_to_booking.py` (mới).

RED:
1. `test_add_room_appends_to_existing_booking` — đơn 1 phòng, thêm phòng 102: BookingRoom mới `booked` cùng booking, `price_breakdown_snapshot` đủ đêm, `room_deposit_amount == 0`, audit `add_room_to_booking`, booking status giữ đúng qua `aggregate_booking_state`.
2. `test_add_room_rejects_conflict` — phòng đích có lịch chồng → 409, không mutation.
3. `test_add_room_rejects_finished_booking` — booking `cancelled`/`completed` → 409.
4. `test_add_room_rejects_cross_tenant_room` — phòng hotel B → 404.
5. `test_add_room_requires_login_json` — chưa login → 401 (sau HM2).
6. Staff thêm được (vận hành quầy).

GREEN: route `POST /api/bookings/add-room` trong timeline_bp theo spec mục 2, tái dùng `_has_active_booking_conflict` + `get_nightly_price_breakdown` + `with_for_update()` trên phòng.

Commit: `feat: add-room-to-booking endpoint backing the existing timeline button`

## Hạng mục 4 — load_dotenv + tài liệu + regression tổng

1. `config.py`: `from dotenv import load_dotenv; load_dotenv()` đầu file (trước khi đọc os.environ).
2. Cập nhật sổ tay nghiệp vụ mục 5 (2 dòng P0/P1 còn lại → đã xử lý) và mục 2 (ma trận quyền mới); spec remediation cũ đánh dấu "Đã triển khai".
3. `pytest -m "not mysql"` + `pytest -m mysql` xanh toàn bộ; commit + push.

Commit: `docs: business guide reflects normalized permission matrix` (+ chore load_dotenv gộp hạng mục 4)
