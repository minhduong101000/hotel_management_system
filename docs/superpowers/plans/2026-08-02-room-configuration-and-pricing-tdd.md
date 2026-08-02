# Kế hoạch TDD: Cấu hình phòng và giá

**Ngày:** 02-08-2026

**Spec nguồn:** `docs/superpowers/specs/2026-08-02-room-configuration-and-pricing-design.md`

**Trạng thái:** Sẵn sàng triển khai

**Mục tiêu:** Xây dựng chức năng quản lý phòng và giá mặc định theo tenant, giữ luật giá đặc biệt chỉ áp dụng cho giá qua đêm, sau đó tích hợp thành một mục điều hướng với hai tab/trang có URL riêng.

## 1. Nguyên tắc triển khai bắt buộc

Mỗi task có thay đổi code phải đi đúng chu kỳ:

1. Viết hoặc sửa test để mô tả hành vi mới.
2. Chạy đúng nhóm test và ghi nhận test đỏ vì hành vi chưa tồn tại, không phải vì lỗi cú pháp/fixture.
3. Triển khai tối thiểu để test xanh.
4. Refactor khi test vẫn xanh.
5. Chạy nhóm test liên quan, `git diff --check` và kiểm tra phạm vi diff.
6. Với task UI, kiểm tra trực quan bằng `bb-browser` trước khi tạo commit.
7. Stage đúng file của task và tạo commit riêng bằng commit message tiếng Anh.

Không gộp code của task sau vào commit hiện tại. Không sửa hai lỗi baseline ngoài phạm vi chỉ để làm full suite xanh.

## 2. Baseline và ràng buộc đã biết

### 2.1 Hành vi phải giữ

- `Room` đã có unique constraint `(hotel_id, room_number)` trong model và migration.
- Giá mặc định nằm trên từng `Room`.
- `PriceRule` chỉ có `price_daily`; không có giá block đầu hoặc giá giờ tiếp theo.
- `pricing_service` hiện đã giữ giá theo giờ của phòng khi áp dụng giá đặc biệt qua đêm.
- Booking đã tạo sử dụng price snapshot; thay đổi bảng giá không được làm đổi booking cũ.
- Staff hiện truy cập và quản lý giá; test `test_staff_can_access_price_management_api` bảo vệ hành vi này.
- Các chặn phòng bảo trì đang có trong tìm phòng, tạo booking, đặt đoàn và dời lịch phải được giữ.
- Bật bảo trì không tự huỷ, dời hoặc sửa booking hiện có.

### 2.2 Lỗi full suite baseline ngoài phạm vi

Lần chạy gần nhất trước kế hoạch có hai lỗi nghiệp vụ không liên quan:

- `tests/test_group_checkout.py::test_group_checkout_excess_deposit_creates_one_refund`.
- `tests/test_inventory_batch_allocations.py::test_consumption_and_restore_use_the_same_batches`.

Trước khi bắt đầu Task 1 phải chạy lại baseline và lưu kết quả. Nếu hai lỗi trên vẫn tồn tại, đánh dấu là baseline; không báo full suite xanh. Bất kỳ lỗi mới nào khác xuất hiện sau task phải được xử lý trong task gây ra lỗi.

### 2.3 File của người dùng không thuộc phạm vi

Các file untracked hoặc thay đổi có sẵn không thuộc chức năng này phải được giữ nguyên. Trước mỗi commit dùng `git status --short` và stage bằng danh sách file tường minh.

## 3. Quyết định kỹ thuật của implementation plan

### 3.1 API

- `GET /<hotel_slug>/rooms/api/settings`: đọc danh sách cấu hình phòng.
- `POST /<hotel_slug>/rooms/api/settings`: tạo phòng; chỉ Hotel admin/Master trong tenant context; nhận cờ boolean `maintenance`, không nhận raw `status`.
- `PUT /<hotel_slug>/rooms/api/settings/<room_id>`: sửa số phòng, loại phòng và giá mặc định; chỉ Hotel admin/Master trong tenant context.
- `PATCH /<hotel_slug>/rooms/api/settings/<room_id>/maintenance`: bật/tắt bảo trì; chỉ Hotel admin/Master trong tenant context.
- Giữ `POST /<hotel_slug>/prices/api/prices/update-base` làm endpoint price-only để Staff tiếp tục sửa giá mà không thể sửa thông tin cấu trúc phòng.
- Thêm `GET /<hotel_slug>/prices/api/prices/rules` cho tab giá đặc biệt; endpoint chỉ trả luật giá và loại phòng, không trả trường giá giờ giả.
- Giữ URL trang giá hiện tại `/<hotel_slug>/prices/admin/price-manager`.

Tách endpoint bảo trì khỏi `PUT` để audit, quyền và cảnh báo vận hành có hợp đồng rõ; `PUT` không nhận thay đổi `status`.

### 3.2 Validation dùng chung

Tạo module dự kiến `services/room_configuration_service.py` để dùng chung:

- Chuẩn hoá/validate số phòng và loại phòng.
- Parse giá hữu hạn, lớn hơn 0.
- Parse `initial_hours` là số nguyên lớn hơn hoặc bằng 1.
- Tạo snapshot Room trước/sau cho audit.
- Serialize cấu hình giá thống nhất.

Controller vẫn chịu trách nhiệm quyền, tenant lookup, HTTP status, transaction và audit. Service không tự commit.

### 3.3 Quyền

Thêm decorator API trả JSON `403` cho thao tác cấu trúc phòng, theo điều kiện:

```text
current_user.is_authenticated
AND (current_user.role == "admin" OR current_user.is_super_admin)
```

Không dùng `admin_required` hiện tại cho API mới vì decorator này redirect HTML và không cho Master admin trong tenant context.

### 3.4 UI

- Một sidebar item: **Cấu hình phòng & giá**.
- Route “Phòng & giá mặc định”: `room.settings_view` tại `/rooms/settings`.
- Route “Giá đặc biệt”: giữ `price.index` tại `/prices/admin/price-manager`.
- Hai tab là `<a>` thật, có `aria-current`, không dùng tab JavaScript chung URL.
- JavaScript cấu hình phòng nằm trong `static/js/room_settings.js`; không phụ thuộc DOM của `price_manager.js`.
- Dữ liệu phòng do người dùng nhập phải render bằng DOM API/`textContent`, không ghép vào `innerHTML` hoặc inline handler.

## 4. Task 0 — Preflight và baseline

Task này chỉ kiểm tra, không thay đổi code và không tạo commit.

### Kiểm tra workspace

```powershell
git status --short
git log -3 --oneline
& '.\venv\Scripts\python.exe' -m flask db heads
```

Xác nhận Alembic có một head. Không stage file untracked của người dùng.

### Kiểm tra schema và baseline liên quan

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_room_schema_constraints.py tests/integration/test_room_migration_mysql.py -q
& '.\venv\Scripts\python.exe' -m pytest tests/test_pricing_tenant_scope.py tests/test_pricing_nightly_breakdown.py tests/test_business_capabilities.py tests/test_audit_log.py -q
& '.\venv\Scripts\python.exe' -m pytest -q
```

Nếu integration MySQL skip vì không có `TEST_MYSQL_DATABASE_URL`, ghi rõ là chưa kiểm chứng ở MySQL; không giả định đã pass.

## 5. Task 1 — API đọc cấu hình phòng theo tenant

### Mục tiêu

Cung cấp contract đọc ổn định cho UI, bao gồm giá mặc định, trạng thái, loại phòng và số booking active để cảnh báo bảo trì; số query không tăng tuyến tính theo số phòng.

### Test đỏ

Tạo `tests/test_room_settings_api.py` với các case:

1. Chưa đăng nhập không đọc được API.
2. Staff, Hotel admin và Master trong tenant context đều đọc được.
3. Response chỉ chứa phòng thuộc `g.hotel_id`; ID/phòng hotel khác không rò rỉ.
4. Hai hotel cùng có phòng `101` vẫn trả đúng bản ghi của từng tenant.
5. Response mỗi phòng có đủ:
   - `id`, `room_number`, `room_type`.
   - `price_per_night`, `price_initial_block`, `initial_hours`, `price_next_hour`.
   - `status`, `clean_status`, `active_booking_count`.
6. `active_booking_count` chỉ đếm `booked` và `checked_in`; không đếm `cancelled`/`checked_out`.
7. `room_types` distinct, thuộc đúng tenant và có thứ tự ổn định.
8. Danh sách phòng có thứ tự ổn định theo số phòng.
9. Query budget không tăng theo 4/40 phòng; test dùng SQLAlchemy event tương tự `test_room_dashboard_query_budget.py`.

Chạy test và xác nhận đỏ vì endpoint chưa tồn tại:

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_room_settings_api.py -q
```

### Triển khai tối thiểu

File dự kiến:

- `controllers/room_controller.py`.
- `tests/test_room_settings_api.py`.

Thực hiện:

- Thêm route `GET /api/settings` với `login_required`.
- Lấy `Room` bằng `tenant_query(Room)`.
- Dùng một grouped subquery trên `BookingRoom` để lấy `active_booking_count`, không query count trong vòng lặp.
- Serialize số tiền thành JSON number ổn định.
- Lấy danh sách loại phòng từ kết quả đã load hoặc một query distinct cố định; không tạo N+1.
- Không thêm route HTML hoặc UI trong task này.

### Refactor và kiểm tra xanh

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_room_settings_api.py tests/test_room_dashboard_query_budget.py tests/test_room_notices.py -q
git diff --check
```

Rà diff để chắc chắn không thay `GET /api/rooms` vận hành hiện tại.

**Commit:** `feat: expose tenant room configuration`

## 6. Task 2 — Tạo phòng với quyền, validation và audit

### Mục tiêu

Hotel admin/Master trong tenant context tạo được phòng; Staff bị chặn ở backend; lỗi validation và trùng số phòng có response ổn định.

### Test đỏ

Tạo:

- `tests/test_room_settings_create.py`.
- Mở rộng `tests/test_business_capabilities.py`.
- Mở rộng `tests/test_audit_log.py`.

Case bắt buộc:

1. Staff gọi `POST` nhận `403` JSON với `error_code="forbidden"`.
2. Hotel admin tạo phòng nhận `201` và response có Room vừa tạo.
3. Master admin trong đúng tenant context tạo được phòng cho tenant đó.
4. Payload chứa `hotel_id` khác bị bỏ qua; server luôn dùng `g.hotel_id`.
5. Trim số phòng/loại phòng trước khi lưu.
6. Cùng hotel trùng số phòng trả `409`, `error_code="room_number_conflict"`.
7. Hai hotel được phép có cùng số phòng.
8. Validation `400`, `error_code="validation_error"` và lỗi theo field cho:
   - Số phòng rỗng hoặc dài hơn 10 ký tự.
   - Loại phòng rỗng hoặc dài hơn 20 ký tự.
   - Giá rỗng, bằng 0, âm, `NaN`, vô hạn hoặc không phải số.
   - `initial_hours` không phải số nguyên hoặc nhỏ hơn 1.
   - `maintenance` không phải boolean.
   - Raw `status`/field ngoài whitelist không được dùng để tạo `occupied`.
9. Bỏ `maintenance` hoặc gửi `false` tạo Room với `status="available"`; gửi `true` tạo Room với `status="maintenance"`; cả hai có `clean_status="cleaned"`.
10. Tạo thành công ghi audit `create_room` đúng tenant và snapshot, gồm trạng thái ban đầu.
11. Validation/conflict không tạo Room và không tạo audit dở dang.
12. Giả lập `IntegrityError` do race unique và xác nhận rollback + `409`, không trả `500`.

Chạy đỏ:

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_room_settings_create.py tests/test_business_capabilities.py tests/test_audit_log.py -q
```

### Triển khai tối thiểu

File dự kiến:

- `decorators.py`.
- `services/room_configuration_service.py`.
- `controllers/room_controller.py`.
- Các test trên.

Thực hiện:

- Thêm decorator API quản lý cấu trúc phòng, trả JSON `403`.
- Viết validator thuần, không commit trong service.
- Khởi tạo `Room(hotel_id=g.hotel_id, ...)` tường minh.
- Flush trước audit để có entity ID; audit và Room cùng một transaction.
- Bắt `IntegrityError`, rollback và map unique conflict sang `409`.
- Không nhận raw `status`; map duy nhất từ `maintenance=true/false` sang `maintenance`/`available`.

### Refactor và kiểm tra xanh

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_room_settings_create.py tests/test_business_capabilities.py tests/test_audit_log.py tests/test_room_schema_constraints.py -q
git diff --check
```

Nếu MySQL integration khả dụng, thêm test cạnh tranh/trùng unique vào `tests/integration/test_room_migration_mysql.py` hoặc file integration mới và chạy riêng.

**Commit:** `feat: create tenant rooms safely`

## 7. Task 3 — Sửa phòng và giá mặc định theo field-level permission

### Mục tiêu

Admin/Master sửa được thông tin cấu trúc và bộ giá; Staff chỉ tiếp tục dùng endpoint price-only, không thể chèn field cấu trúc vào payload.

### Test đỏ

Tạo `tests/test_room_settings_update.py`; mở rộng:

- `tests/test_business_capabilities.py`.
- `tests/test_audit_log.py`.
- `tests/test_pricing_quote.py`.

Case bắt buộc:

1. Hotel admin `PUT` sửa số phòng, loại phòng và toàn bộ giá mặc định thành công.
2. Master trong đúng tenant context sửa được.
3. Staff gọi `PUT` nhận `403` JSON.
4. Room ID của hotel khác trả `404`, không tiết lộ dữ liệu.
5. Đổi sang số phòng trùng trong cùng tenant trả `409`; transaction không sửa nửa chừng.
6. Validation giá/chuỗi dùng cùng contract Task 2.
7. `PUT` không chấp nhận đổi `status`; bảo trì phải qua endpoint riêng.
8. Update thành công ghi `update_room` với snapshot trước/sau.
9. Validation/conflict không ghi audit.
10. Staff vẫn gọi `POST /prices/api/prices/update-base` thành công và sửa được đủ `price_per_night`, `price_initial_block`, `initial_hours`, `price_next_hour`.
11. Payload Staff thêm `room_number`, `room_type`, `status` vào endpoint price-only không làm thay đổi các field này.
12. Endpoint price-only từ chối giá 0/âm/`NaN`/vô hạn theo cùng validator và trả `400`.
13. Sửa giá mặc định làm báo giá mới dùng giá mới khi không có rule.
14. Booking đã có `price_breakdown_snapshot` vẫn giữ số tiền cũ sau khi cấu hình giá đổi.

Chạy đỏ:

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_room_settings_update.py tests/test_business_capabilities.py tests/test_audit_log.py tests/test_pricing_quote.py -q
```

### Triển khai tối thiểu

File dự kiến:

- `services/room_configuration_service.py`.
- `controllers/room_controller.py`.
- `controllers/price_controller.py`.
- Các test trên.

Thực hiện:

- Thêm `PUT /api/settings/<room_id>` với tenant lookup và decorator cấu trúc phòng.
- Reuse validator giá chung cho cả full update và endpoint price-only.
- Whitelist field riêng cho structural update và price-only update; price-only gồm đủ bốn trường cấu hình giá, kể cả `initial_hours`.
- Không cho `PUT` thay status/clean status.
- Giữ audit `update_base_price` của endpoint cũ; full update dùng `update_room` chứa cả bộ giá.
- Không sửa snapshot của `BookingRoom`.

### Refactor và kiểm tra xanh

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_room_settings_update.py tests/test_business_capabilities.py tests/test_audit_log.py tests/test_pricing_quote.py tests/test_pricing_nightly_breakdown.py tests/test_csrf_protection.py -q
git diff --check
```

**Commit:** `feat: update room settings and default rates`

## 8. Task 4 — Bật/tắt bảo trì có cảnh báo nhưng không hard block booking cũ

### Mục tiêu

Cung cấp mutation bảo trì riêng, ghi audit và trả đủ dữ liệu cảnh báo; không tự động thay đổi booking hiện có.

### Test đỏ

Tạo `tests/test_room_settings_maintenance.py`; mở rộng `tests/test_audit_log.py`.

Case bắt buộc:

1. Staff gọi endpoint nhận `403` JSON.
2. Admin/Master tenant context bật/tắt bảo trì thành công.
3. Room hotel khác trả `404`.
4. Payload chỉ chấp nhận boolean `maintenance`; giá trị mơ hồ trả `400`.
5. Bật bảo trì khi không có booking trả `active_booking_count=0`, không có hard-block warning.
6. Bật bảo trì khi có `booked` hoặc `checked_in` vẫn thành công, response có:
   - `active_booking_count` đúng.
   - `warning=true`.
   - Message nói hệ thống không tự xử lý booking.
7. Booking, cọc, khách, thời gian và trạng thái `BookingRoom` không bị thay đổi.
8. Bật bảo trì giữ nguyên `clean_status`.
9. Tắt bảo trì khi còn `checked_in` đưa trạng thái vật lý về `occupied`.
10. Tắt bảo trì khi không còn `checked_in` đưa về `available` và vẫn giữ `clean_status`.
11. Audit `set_room_maintenance`/`clear_room_maintenance` có snapshot trước/sau đúng tenant.
12. Request lặp cùng trạng thái là idempotent về dữ liệu; không tạo log chuyển trạng thái giả nếu không có thay đổi.
13. Regression: search không trả phòng bảo trì; tạo booking đơn/đoàn và reschedule vẫn giữ các chặn hiện có.

Không thêm test yêu cầu check-in mới bị hard block; quyết định nghiệp vụ đã chốt là không mở rộng cơ chế này trong đợt cấu hình.

Chạy đỏ:

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_room_settings_maintenance.py tests/test_audit_log.py -q
```

### Triển khai tối thiểu

File dự kiến:

- `services/room_configuration_service.py` hoặc reuse helper trạng thái trong `services/booking_state_service.py` nếu phù hợp.
- `controllers/room_controller.py`.
- Các test trên.

Thực hiện:

- Thêm `PATCH /api/settings/<room_id>/maintenance`.
- Count active booking tenant-scoped trước mutation.
- Khi bật: set `Room.status="maintenance"`, không chạm `BookingRoom`.
- Khi tắt: query tồn tại `checked_in`; derive `occupied` hoặc `available`.
- Giữ `clean_status` nguyên trạng.
- Chỉ ghi audit khi trạng thái thực sự thay đổi.
- Response trả Room mới, count và warning để UI không phải suy đoán.

### Refactor và kiểm tra xanh

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_room_settings_maintenance.py tests/test_room_notices.py tests/test_booking_overlap.py tests/test_booking_reschedule.py tests/test_audit_log.py -q
git diff --check
```

**Commit:** `feat: manage room maintenance status`

## 9. Task 5 — Contract giá đặc biệt chỉ qua đêm

### Mục tiêu

Tạo API dữ liệu riêng cho tab giá đặc biệt, loại bỏ trường giá giờ giả khỏi contract mới và khóa regression precedence giá.

### Test đỏ

Tạo `tests/test_price_rule_contract.py`; mở rộng:

- `tests/test_pricing_tenant_scope.py`.
- `tests/test_business_capabilities.py`.
- `tests/test_audit_log.py` nếu refactor mutation.

Case bắt buộc:

1. `GET /prices/api/prices/rules` chỉ trả rule và `room_types` của tenant hiện tại.
2. Mỗi rule có `id`, `name`, `room_type`, `priority`, ngày, thứ, `is_active`, `price_daily`; không có `price_initial` hoặc `price_next`.
3. Staff, Admin và Master trong tenant context vẫn truy cập được theo quyền hiện tại.
4. Tạo/sửa rule chỉ ghi `price_daily`; payload thừa `price_initial`/`price_next` không làm thay đổi giá giờ của Room.
5. Rule hotel khác không xuất hiện và không thể sửa/xoá bằng ID tenant khác.
6. Không có rule phù hợp: `p_night`, `p_initial`, `p_next`, `initial_hours` đều lấy từ Room.
7. Có rule phù hợp: chỉ `p_night` đổi; ba giá trị theo giờ giữ nguyên.
8. Rule inactive, ngoài khoảng ngày hoặc sai ngày trong tuần không áp dụng.
9. Rule priority cao hơn được chọn theo logic hiện có.
10. URL/API hiện có phục vụ trang giá không bị 404 trong giai đoạn chuyển tiếp.

Chạy đỏ và xác nhận endpoint mới chưa tồn tại:

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_price_rule_contract.py tests/test_pricing_tenant_scope.py tests/test_business_capabilities.py -q
```

### Triển khai tối thiểu

File dự kiến:

- `controllers/price_controller.py`.
- `services/pricing_service.py` chỉ khi test phát hiện thiếu contract; không refactor vô cớ.
- Các test trên.

Thực hiện:

- Thêm endpoint đọc rules mới, tenant-scoped.
- Serialize đúng field thật của `PriceRule`.
- Khi tạo rule, gán `hotel_id=g.hotel_id` tường minh.
- Giữ endpoint save/delete và audit hiện có; siết tenant lookup nếu test đỏ phát hiện thiếu.
- Không thêm cột database cho giá giờ đặc biệt.
- Giữ endpoint `all-data` trong task này để tránh phá UI cũ trước khi UI mới được commit.

### Refactor và kiểm tra xanh

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_price_rule_contract.py tests/test_pricing_tenant_scope.py tests/test_pricing_nightly_breakdown.py tests/test_business_capabilities.py tests/test_audit_log.py -q
git diff --check
```

**Commit:** `feat: expose nightly price rule contract`

## 10. Task 6 — UI tích hợp “Cấu hình phòng & giá”

### Mục tiêu

Trong một hạng mục độc lập, thêm trang phòng/giá mặc định, chuyển trang giá hiện tại thành tab giá đặc biệt và thay navigation. Sau commit này không còn hai nơi cùng sửa giá mặc định.

### Test đỏ

Tạo:

- `tests/test_room_settings_ui.py`.
- `tests/test_room_settings_render_security.py`.

Mở rộng:

- `tests/test_frontdesk_ui_polish.py`.
- `tests/test_accessibility_markup.py`.
- `tests/test_ui_shell_markup.py`.
- `tests/test_ui_regression.py`.

Test markup/route bắt buộc:

1. `/<hotel_slug>/rooms/settings` trả `200` cho Staff/Admin/Master đúng tenant.
2. Sidebar chỉ còn một label “Cấu hình phòng & giá”; active ở cả `room.settings_view` và `price.index`.
3. Hai trang đều có hai link tab thật, đúng URL và `aria-current`.
4. URL cũ `/prices/admin/price-manager` vẫn trả `200`.
5. Trang giá đặc biệt không còn bảng `base-price-table` hoặc nút sửa giá mặc định.
6. Trang phòng có page header, filter, bảng, loading/empty/error state và modal.
7. Admin/Master thấy “Thêm phòng”, sửa cấu trúc và bảo trì; Staff không thấy các action này.
8. Staff vẫn có action sửa giá mặc định.
9. Modal có label liên kết cho toàn bộ field, close accessible name, error region và status region.
10. Không có action xoá phòng.
11. Nút primary/outline/icon dùng component hiện có; vùng bấm đạt 44 px.
12. JavaScript không ghép `room_number`/`room_type` vào `innerHTML`, inline `onclick` hoặc attribute HTML.
13. JavaScript có nhánh xử lý `400`, `403`, `409`, network error và double submit.
14. Filter tìm kiếm/status/type không gọi mutation và không làm mất dữ liệu gốc.
15. Warning bảo trì có nội dung chữ và yêu cầu xác nhận nhưng không biến thành hard block.
16. CSS có wrapper cuộn bảng, modal viewport-safe và input 16 px ở mobile.

Chạy đỏ:

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_room_settings_ui.py tests/test_room_settings_render_security.py tests/test_frontdesk_ui_polish.py tests/test_accessibility_markup.py tests/test_ui_shell_markup.py tests/test_ui_regression.py -q
```

### Triển khai tối thiểu

File dự kiến:

- `controllers/room_controller.py`.
- `templates/rooms/settings.html`.
- `templates/admin/price_manager.html`.
- `templates/layouts/base.html`.
- `static/js/room_settings.js`.
- `static/js/price_manager.js`.
- `static/css/style.css`.
- Các test trên.

Thực hiện theo thứ tự:

1. Thêm route HTML `room.settings_view` với `login_required`.
2. Tạo shared tab nav partial chỉ khi giúp tránh lặp mà không làm Jinja phức tạp; nếu không, giữ markup nhỏ, đồng nhất ở hai template.
3. Tạo bảng phòng/giá mặc định và filter client-side.
4. Render hàng bằng DOM API và `textContent`.
5. Admin/Master dùng modal full create/edit; create form gửi toggle `maintenance` boolean. Staff dùng chế độ price-only với đủ bốn trường giá, kể cả `initial_hours`, và endpoint price-only hiện có.
6. Khi bật bảo trì và `active_booking_count > 0`, hiển thị warning theo spec rồi mới gửi PATCH nếu người dùng xác nhận.
7. Dùng busy state, disable submit và focus management.
8. Refactor `price_manager.html` chỉ còn luật giá đặc biệt; `price_manager.js` dùng endpoint `/api/prices/rules`.
9. Đổi sidebar item và active selector; không thêm item giá thứ hai.
10. Dùng visual token, button, DataState và modal class hiện có; không tạo design language mới.

### Kiểm tra tự động xanh

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_room_settings_ui.py tests/test_room_settings_render_security.py tests/test_room_settings_api.py tests/test_room_settings_create.py tests/test_room_settings_update.py tests/test_room_settings_maintenance.py tests/test_price_rule_contract.py tests/test_frontdesk_ui_polish.py tests/test_accessibility_markup.py tests/test_ui_shell_markup.py tests/test_ui_regression.py tests/test_csrf_protection.py -q
git diff --check
```

### Kiểm tra `bb-browser` trước commit

Chạy ứng dụng bằng database cô lập dành cho kiểm tra UI; không tạo phòng thử trong dữ liệu development hiện có.

Kiểm tra desktop:

- 1920 px, Hotel admin:
  - Mở menu và hai tab; refresh/Back giữ đúng URL.
  - Loading, populated và empty state nếu fixture cho phép.
  - Thêm phòng hợp lệ.
  - Validation rỗng/số tiền sai.
  - Trùng số phòng `409` giữ dữ liệu và focus đúng field.
  - Sửa số/loại phòng và giá mặc định.
  - Bật bảo trì có/không có booking; warning không hard block.
  - Tắt bảo trì.
- 1440 hoặc 1024 px, Staff:
  - Không thấy nút thêm/sửa cấu trúc/bảo trì.
  - Sửa được giá mặc định.
  - Mở tab giá đặc biệt, tạo/sửa rule đến bước xác nhận.
- Keyboard:
  - Tab theo thứ tự hợp lý.
  - Escape đóng modal.
  - Focus trở về trigger.
- Accessibility tree, console và errors không có lỗi mới.
- Không có body overflow; bảng chỉ cuộn trong wrapper.

Sau kiểm tra, xoá database/screenshot tạm bằng thao tác an toàn và xác nhận target chính xác.

**Commit:** `feat: unify room and pricing configuration`

## 11. Task 7 — Regression cuối và bàn giao

Task này là verification gate. Không tạo commit rỗng. Nếu phát hiện lỗi, trước khi sửa phải thêm test đỏ vào file phù hợp, sửa tối thiểu, chạy lại và tạo commit fix riêng với message mô tả đúng lỗi.

### Test tự động theo phạm vi

```powershell
& '.\venv\Scripts\python.exe' -m pytest `
  tests/test_room_settings_api.py `
  tests/test_room_settings_create.py `
  tests/test_room_settings_update.py `
  tests/test_room_settings_maintenance.py `
  tests/test_room_settings_ui.py `
  tests/test_room_settings_render_security.py `
  tests/test_price_rule_contract.py `
  tests/test_pricing_tenant_scope.py `
  tests/test_pricing_nightly_breakdown.py `
  tests/test_pricing_quote.py `
  tests/test_business_capabilities.py `
  tests/test_audit_log.py `
  tests/test_csrf_protection.py `
  tests/test_accessibility_markup.py `
  tests/test_ui_shell_markup.py `
  tests/test_ui_regression.py -q

& '.\venv\Scripts\python.exe' -m pytest -q
git diff --check
```

Nếu full suite vẫn chỉ còn đúng hai baseline đã ghi ở mục 2.2, báo rõ; không tuyên bố full suite xanh. Nếu xuất hiện lỗi mới, truy về task gây regression và xử lý trước bàn giao.

### Integration database

Khi `TEST_MYSQL_DATABASE_URL` khả dụng:

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/integration/test_room_migration_mysql.py -q
```

Xác nhận ít nhất:

- Unique cùng tenant.
- Cho phép trùng số phòng giữa hai tenant.
- API map race unique thành `409` nếu có test integration tương ứng.

Nếu không có database integration, nêu rõ phần chưa thể kiểm chứng.

### Ma trận `bb-browser` cuối

| Viewport | Vai trò/trạng thái | Luồng bắt buộc |
|---:|---|---|
| 1920 px | Admin, dữ liệu populated | Navigation, tạo/sửa, bảo trì, chuyển hai tab |
| 1440 px | Staff | Chỉ sửa giá; không có action cấu trúc; quản lý rule |
| 1024 px | Admin | Toolbar wrap, bảng cuộn, modal không vượt viewport |
| 768 px | Admin | Sidebar drawer, tab, filter, bảng và modal |
| 375 px | Staff/Admin | Không body overflow, input 16 px, touch target và modal scroll |

Với mỗi màn hình:

- Kiểm tra screenshot và accessibility tree.
- Kiểm tra `console`/`errors` không có lỗi mới.
- Kiểm tra keyboard, Escape và focus restore.
- Kiểm tra empty, error, conflict và success state khi fixture cô lập cho phép.
- Không để lại dữ liệu/screenshot tạm trong workspace.

## 12. Thứ tự commit dự kiến

1. `feat: expose tenant room configuration`
2. `feat: create tenant rooms safely`
3. `feat: update room settings and default rates`
4. `feat: manage room maintenance status`
5. `feat: expose nightly price rule contract`
6. `feat: unify room and pricing configuration`

Task regression cuối chỉ tạo commit nếu có test/fix thực tế; không tạo commit rỗng để đủ danh sách.

## 13. Điểm dừng và điều kiện không tự mở rộng

Dừng task hiện tại và báo người dùng nếu:

- Schema database thực tế không có các cột/constraint như model và cần migration mới ngoài dự kiến.
- Quyền giá thực tế khác test hiện tại và cần quyết định lại Staff/Admin.
- Một loại phòng cần trở thành entity riêng với CRUD/foreign key.
- Người dùng yêu cầu xoá cứng phòng, lịch bảo trì theo thời gian, tầng/tiện nghi hoặc bulk import.
- Cần thay đổi snapshot/checkout của booking cũ.
- UI muốn tự dời/huỷ booking khi bảo trì.
- MySQL cho kết quả unique/transaction khác SQLite và cần thay đổi schema hoặc locking.

Không tự sửa hai baseline group checkout/FEFO trong kế hoạch này.

## 14. Định nghĩa hoàn tất

Chức năng chỉ được xem là hoàn tất khi:

- Sáu commit chức năng độc lập đã hoàn thành theo TDD.
- Mỗi hành vi mới có bằng chứng test đỏ trước khi triển khai và test xanh sau đó.
- Tenant isolation, quyền Staff/Admin/Master, CSRF, validation, audit và unique conflict đều được kiểm chứng.
- Staff chỉ sửa giá; không thể thay đổi số phòng, loại phòng hoặc bảo trì qua UI/API.
- Giá đặc biệt chỉ thay giá qua đêm; giá theo giờ luôn lấy mặc định của Room.
- Booking snapshot cũ không đổi khi sửa cấu hình.
- Bảo trì cảnh báo nhưng không tự thay đổi booking hiện có.
- Sidebar có một mục, hai tab có URL riêng và URL giá cũ vẫn hoạt động.
- Không còn hai nơi cùng sửa giá mặc định.
- UI đạt yêu cầu accessibility/responsive của spec và đã kiểm tra bằng `bb-browser` ở desktop.
- Không có JavaScript/console error mới.
- Full suite không có lỗi mới ngoài baseline đã ghi; mọi phần integration chưa chạy được được bàn giao minh bạch.
- `git status --short` chỉ còn các file của người dùng đã tồn tại ngoài phạm vi, không còn thay đổi dở của chức năng.
