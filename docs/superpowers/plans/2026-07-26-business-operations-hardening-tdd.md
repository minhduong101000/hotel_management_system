# Kế hoạch TDD: Hoàn thiện nghiệp vụ vận hành và đối soát

**Ngày:** 26-07-2026  
**Spec nguồn:** `docs/superpowers/specs/2026-07-26-business-operations-hardening-design.md`  
**Trạng thái:** Sẵn sàng triển khai

## 1. Quy tắc thực hiện

- Mỗi task theo thứ tự test đỏ → triển khai tối thiểu → refactor → test liên quan → full suite.
- Không chạy migration trên dữ liệu local đang dùng trước khi có migration/backfill riêng được kiểm tra trên bản sao.
- Các test mutation phải kiểm tra cả response lẫn database: Payment, BookingRoom, InventoryItem và AuditEvent không được thay đổi dở dang.
- Mọi test tenant dùng ít nhất hai hotel.
- Với thay đổi UI quyền/thông báo, kiểm tra desktop bằng `bb-browser` trước khi bàn giao.

## 2. Đợt 1 — Idempotency checkout và refund

### Task 1.1: Định nghĩa operation reference

**Test đỏ trước:** tạo `tests/test_payment_idempotency.py`.

Cases:

1. Checkout cùng `BookingRoom` hai lần chỉ có một bộ Payment settlement.
2. Retry cùng request checkout trả kết quả idempotent hoặc `409` có reference, không ghi thêm Payment.
3. Hủy/refund cùng booking room hai lần không tạo refund/cancellation fee lần hai.
4. Operation/payment tenant A không thể bị lookup hoặc tái sử dụng tại tenant B.

### Task 1.2: Migration và model

**Dự kiến sửa:** `models/payment.py`, model/migration mới nếu cần.

- Thêm `operation_key` hoặc bảng `BusinessOperation` tenant-scoped.
- Đặt unique constraint/index phù hợp để database chặn trùng trong trường hợp cạnh tranh.
- Có migration và script kiểm tra backfill; không backfill im lặng Payment cũ.

### Task 1.3: Tích hợp checkout/cancel

**Dự kiến sửa:** `controllers/booking_controller.py`, `controllers/timeline_controller.py`, `services/payment_service.py`.

- Kiểm tra operation trước khi ghi Payment.
- Ghi trạng thái nghiệp vụ, Payment và operation trong một transaction.
- Chuẩn hóa JSON response có `operation_key`/payment reference.
- Bắt buộc `reason` khi refund/hủy có tiền theo chính sách đã chốt.

## 3. Đợt 2 — Audit log nền tảng

### Task 2.1: Model và service audit

**Test đỏ trước:** `tests/test_audit_log.py`.

Cases:

1. Event có `hotel_id`, actor, action, entity và request/operation reference.
2. Snapshot không chứa password/token.
3. Tenant B không đọc được event tenant A.
4. Retry operation idempotent không tạo event tiền trùng.

**Dự kiến thêm:** `models/audit_event.py`, `services/audit_service.py`, migration.

### Task 2.2: Áp dụng theo thứ tự rủi ro

1. Checkout, refund, phí hủy và hủy booking.
2. Nhập/sửa/xóa kho.
3. Sửa giá/rule giá.
4. Xóa/sửa dịch vụ và customer.
5. Thay đổi user/hotel.

Mỗi task thêm test actor, tenant và snapshot trước/sau trước khi gắn audit event.

## 4. Đợt 3 — Chống overlap/concurrency booking

### Task 3.1: Test đỏ logic và transaction

**File:** `tests/test_booking_overlap.py`.

- Overlap cùng phòng trả `409`.
- Hai khoảng sát nhau ở mốc checkout/check-in được chấp nhận.
- Tạo, kéo timeline, đổi phòng và thêm phòng đoàn dùng cùng luật.
- Test cạnh tranh ở integration database production; SQLite test ghi rõ giới hạn lock.

### Task 3.2: Triển khai

- Tách helper overlap dùng chung.
- Khóa Room hoặc dùng chiến lược transaction theo database production.
- Không tạo Booking/BookingRoom/cọc/payment khi conflict.

## 5. Đợt 4 — Capability-based authorization

### Task 4.1: Chốt test quyền

**File:** `tests/test_business_capabilities.py`.

Theo chính sách đã duyệt:

- Staff được booking, check-in, order, checkout, nhập/sửa/xóa kho, dịch vụ, giá, hủy trước check-in và refund có lý do.
- Hotel admin và Master admin trong tenant context có các quyền trên, cùng chi phí/nhân sự/cấu hình theo scope.
- Master admin quản lý hotel; Staff không quản lý hotel/nhân sự.

### Task 4.2: Triển khai backend và UI

**Dự kiến sửa:** `decorators.py`, controllers liên quan, template/JS hiển thị action.

- Capability decorator trả JSON `403` cho API.
- Đảm bảo refund bắt buộc `reason` ở backend, UI hiển thị trường bắt buộc.
- Dùng `bb-browser` cho Staff, Hotel admin và Master admin trên desktop.

## 6. Đợt 5 — Khách trùng SĐT

### Task 5.1: Test đỏ

**File:** `tests/test_customer_phone_matching.py`.

- Hai khách cùng SĐT cùng tenant trả danh sách ứng viên.
- Tạo booking không tự lấy bản ghi đầu tiên khi có nhiều ứng viên.
- Tenant khác không có trong kết quả.

### Task 5.2: Triển khai

- Thêm endpoint/search contract trả danh sách khách theo SĐT.
- UI yêu cầu chọn khách hoặc tạo khách mới khi trùng.
- Kiểm tra bằng `bb-browser`.

## 7. Đợt 6 — Xác nhận và sửa báo cáo

### Task 6.1: Test đỏ

**File:** `tests/test_report_room_revenue.py`.

- Dùng Room ID khác BookingRoom ID để xác nhận join đúng theo `BookingRoom.room_id`.
- Báo cáo chỉ bao gồm tenant hiện tại và trạng thái hoàn tất/hủy theo quy ước đã chốt.

### Task 6.2: Triển khai tối thiểu

- Sửa join/query khi test chứng minh sai.
- Chạy regression báo cáo và tenant isolation.

## 8. Kiểm tra cuối cùng

1. Chạy full pytest bằng môi trường TDD của project.
2. Chạy migration trên database copy, xác nhận unique/index và rollback.
3. Dùng `bb-browser` cho checkout/refund reason, permission Staff/Admin/Master, trùng SĐT.
4. Báo cáo operation contract, migration/backfill và các chính sách refund đã áp dụng.
