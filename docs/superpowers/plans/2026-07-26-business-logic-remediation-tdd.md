# Kế hoạch TDD: Khắc phục logic nghiệp vụ và an toàn dữ liệu

**Ngày:** 26-07-2026  
**Spec nguồn:** `docs/superpowers/specs/2026-07-26-business-logic-remediation-design.md`  
**Trạng thái:** Đã hoàn thành Đợt 0–4 và phần chính sách hủy phòng đã chốt; mức hoàn/lý do hoàn vẫn để quyết định sau.

## 1. Quy tắc triển khai

- Không chạy migration hoặc sửa dữ liệu local hiện có trong đợt code đầu tiên nếu chưa có migration plan được duyệt.
- Mỗi task theo đúng thứ tự: test đỏ → xác nhận đỏ → triển khai tối thiểu → refactor → test liên quan → full suite.
- Test cross-tenant là bắt buộc cho mọi endpoint/query có `hotel_id`.
- Các thay đổi quyền, tiền, kho và hủy booking không chỉ kiểm tra HTTP status; phải kiểm tra database không bị mutation sai.
- Mọi test chạy bằng:

```powershell
& 'C:\tmp\hotel-management-tdd-venv\Scripts\python.exe' -m pytest -q
```

## 2. Đợt 0 — Baseline và fixture dùng chung

### Task 0.1: Ghi baseline

**Không sửa logic.**

1. Chạy toàn bộ pytest và ghi số test/warning hiện tại.
2. Kiểm tra `tests/conftest.py` đã có hai hotel, user tenant, Master admin, Room, Booking và BookingRoom.
3. Bổ sung fixture nhỏ chỉ khi cần, không sửa fixture đang dùng rộng rãi nếu có thể tạo dữ liệu ngay trong test.

### Task 0.2: Chuẩn hóa helper assertion transaction

**Test đỏ trước:** tạo `tests/helpers.py` hoặc helper nội bộ test để snapshot count/quantity/payment trước mutation.

**Mục tiêu:** test P0/P1 xác nhận được rollback: không phát sinh BookingService/Payment, số lượng kho không đổi, trạng thái booking không đổi khi request lỗi.

## 3. Đợt 1 — P0: PriceRule tenant scope

### Task 1.1: Test đỏ giá không lẫn tenant

**File test tạo mới:** `tests/test_pricing_tenant_scope.py`

Cases:

1. Hotel A và B cùng `room_type`, cùng ngày; chỉ hotel B có PriceRule giá đặc biệt. Giá phòng hotel A phải là giá niêm yết.
2. Rule của hotel A áp dụng cho room hotel A theo priority/ngày/thứ.
3. Giá giờ của room không bị Rule giá ngày ghi đè.

### Task 1.2: Triển khai tối thiểu

**File sửa:** `services/pricing_service.py`

- Thêm điều kiện `PriceRule.hotel_id == room.hotel_id` trong candidate query.
- Nếu thiếu `room.hotel_id`, không lấy candidate rule tenant.
- Giữ nguyên interface hàm để không làm vỡ room controller/timeline controller.

### Task 1.3: Refactor và kiểm tra

- Đặt helper query rule nếu điều kiện trở nên dài.
- Chạy `tests/test_pricing_tenant_scope.py`, test giá hiện hữu nếu có, `tests/test_tenant_isolation.py`, rồi full suite.

## 4. Đợt 2 — P0: Hủy booking an toàn

### Task 2.1: Test đỏ route hủy booking

**File test tạo mới:** `tests/test_booking_cancellation.py`

Cases:

1. Hủy theo `booking_room_id` chỉ hủy đúng một phòng trong booking đoàn.
2. Hủy theo `booking_id` hủy tất cả phòng active của booking.
3. ID không phải số trả `400`; ID tenant khác trả `404`.
4. Hủy lại cùng booking room không tạo thêm Payment/refund hoặc đổi trạng thái lần nữa.
5. Booking room `checked_out` bị từ chối.
6. Case checked-in sẽ được viết sau khi bạn chốt chính sách ở spec mục 7.

### Task 2.2: Triển khai tối thiểu

**File sửa:** `controllers/timeline_controller.py`

- Sửa parse ID và tenant query cho `booking_room_id`/`booking_id`.
- Đặt guard trạng thái trước khi tính refund/ghi Payment.
- Trả response JSON status rõ ràng: 400 input sai, 404 ngoài tenant/không có, 409 trạng thái không cho hủy.
- Ghi/refactor payment theo một nhánh duy nhất để retry không nhân đôi.

### Task 2.3: Kiểm tra

- Chạy test mới, `tests/test_tenant_query_remediation.py`, `tests/test_tenant_isolation.py`, full suite.
- Nếu UI timeline thay response/error, dùng `bb-browser` mở modal hủy và kiểm tra thông báo lỗi/success.

## 5. Đợt 3 — P0: Order dịch vụ, hotel_id và dữ liệu lịch sử

### Task 3.1: Test đỏ order mutation

**Mở rộng:** `tests/test_order_history.py`; tạo `tests/test_order_submission.py`.

Cases:

1. Order món mới tạo BookingService có `hotel_id`, booking_id, room_id, service_id, quantity và price snapshot đúng.
2. Order lại cùng món cộng dồn quantity, không tạo dòng trùng.
3. `items=[]`, quantity 0/âm, service ID sai kiểu trả 400 và không mutate.
4. Service thuộc hotel B gửi qua hotel A trả 404/400, không trừ kho/không tạo line item.
5. Chỉ phòng checked-in mới gọi món được.

### Task 3.2: Triển khai tối thiểu

**File sửa:** `controllers/booking_controller.py`

- Validate payload trước mutation.
- Gán `hotel_id=g.hotel_id` cho BookingService mới.
- Dùng transaction/rollback cho toàn request.
- Chuẩn hóa response lỗi/success; giữ API contract UI hiện có.

### Task 3.3: Kiểm tra UI lịch sử món gọi

**File liên quan:** `static/js/service.js`, `templates/rooms/map.html`.

- Chạy test API/history và markup hiện có.
- Dùng `bb-browser`: mở phòng checked-in, thấy mục `Đã gọi`; thêm món qua dữ liệu local test an toàn hoặc chỉ kiểm tra đến trước submit nếu không được phép mutation.

## 6. Điểm dừng phê duyệt 1 — Chính sách tồn kho và quyền

Không triển khai Đợt 4–6 trước khi bạn chốt:

1. Chặn order thiếu kho hay cho phép tồn âm? **Đã chốt: chặn thiếu kho; chỉ dịch vụ có liên kết kho mới trừ tồn.**
2. Staff có checkout/hoàn-hủy có tiền hay không? **Đã chốt: Staff được thao tác checkout; quyền và chính sách hoàn tiền chi tiết giữ lại để chốt sau.**
3. Hủy phòng checked-in có bị cấm hoàn toàn hay dùng flow riêng? **Đã chốt: không hủy sau check-in; chỉ checkout.**

Tồn kho được bổ sung tại trang Kho hàng. Gọi/sửa dịch vụ phòng chỉ làm giảm hoặc hoàn lại phần chênh lệch tồn theo hóa đơn.

## 7. Đợt 4 — P1: Kho atomic và tenant-safe

### Task 4.1: Test đỏ kho

**File test tạo mới:** `tests/test_inventory_order_safety.py`

Cases:

1. Order đủ hàng trừ đúng kho của hotel hiện tại.
2. Một món thiếu hàng làm toàn order rollback, bao gồm item đủ hàng trước đó.
3. Không có InventoryItem liên kết vẫn cho gọi service, không trừ kho.
4. Cùng service_id/record mapping sai tenant không bị mutate.
5. Update service quantity khôi phục/trừ lại đúng và không âm kho.

### Task 4.2: Triển khai tối thiểu

**File sửa:** `services/inventory_service.py`, `controllers/booking_controller.py`.

- Đổi interface service kho nhận `hotel_id`.
- Tách `validate_inventory` và `deduct_inventory` để validate toàn bộ trước mutation.
- Không dùng `max(0, ...)` để che thiếu kho; trả lỗi domain rõ ràng.
- Cập nhật toàn bộ call site order/update service tương ứng.

### Task 4.3: Kiểm tra

- Test kho mới, order submission, tenant isolation, full suite.
- UI gọi món kiểm tra thông báo thiếu kho bằng `bb-browser` nếu có thay đổi message.

## 8. Đợt 5 — P1: Capability-based authorization và idempotency tiền

### Task 5.1: Chốt capability map thành test

**File test tạo mới:** `tests/test_business_capabilities.py`

Theo quyết định đã duyệt, tạo bảng test Staff/Hotel admin/Master cho:

- booking create/update/check-in;
- gọi dịch vụ;
- checkout;
- hủy/refund/VAT/cọc/group checkout;
- giá, kho, dịch vụ, chi phí, nhân sự.

### Task 5.2: Triển khai quyền backend

**File sửa dự kiến:** `decorators.py`, controllers booking/timeline/warehouse/expense/price/service.

- Tạo decorator capability tái dùng.
- API trả JSON `403`; view HTML có thể redirect/flash theo quy ước hiện có.
- Không dựa vào việc ẩn nút UI.

### Task 5.3: Idempotency Payment/checkout

**File test tạo mới:** `tests/test_checkout_idempotency.py`

Cases:

1. Checkout lần hai/retry không tạo Payment trùng.
2. Refund/hủy retry không tạo refund/cancellation fee trùng.
3. Response thành công có reference/payment id.

**File sửa dự kiến:** `controllers/booking_controller.py`, `controllers/timeline_controller.py`, `services/payment_service.py`, có thể migration/index sau khi được duyệt.

## 9. Đợt 6 — P1: Chống overlap/concurrency booking

### Task 6.1: Test đỏ conflict thời gian

**File test tạo mới:** `tests/test_booking_overlap.py`

Cases:

1. Hai booking active overlap cùng room bị `409`.
2. Check-out booking A đúng bằng check-in booking B được chấp nhận.
3. Update timeline/chuyển phòng cũng bị kiểm tra overlap.
4. Test transaction/concurrency ở mức phù hợp backend hiện tại; nếu SQLite không mô phỏng lock MySQL chính xác, viết integration test MySQL riêng và ghi rõ giới hạn.

### Task 6.2: Triển khai tối thiểu

**File sửa dự kiến:** `controllers/timeline_controller.py`, `controllers/booking_controller.py`, migration/index nếu cần.

- Tạo helper overlap query dùng chung.
- Chạy check trong transaction trước persist.
- Quyết định chiến lược row lock/MySQL sau khi kiểm tra dialect môi trường.

## 10. Đợt 7 — P2: Audit trail và khách trùng SĐT

### Task 7.1: Audit log

**Test đỏ trước:** `tests/test_audit_log.py`.

- Action nhạy cảm tạo audit event có hotel_id, actor, entity, action và snapshot tối thiểu.
- Tenant khác không đọc được audit event.
- Password/token không xuất hiện trong snapshot.

**File mới/sửa dự kiến:** model/migration audit event, service audit, controllers mutation, view/API audit theo quyền.

### Task 7.2: Trùng SĐT khách hàng

Chỉ triển khai sau khi bạn duyệt chính sách:

- Giữ SĐT không unique; endpoint tìm kiếm trả danh sách ứng viên, UI yêu cầu chọn.
- Test không tự chọn bản ghi đầu tiên khi có nhiều khách cùng số.

## 11. Kiểm tra cuối cùng

1. Full pytest và ghi rõ số test/warning.
2. Rà migration/backfill trên database copy local.
3. `bb-browser` cho các thay đổi UI: order history, lỗi kho, quyền Staff/Admin/Master, hủy booking/refund nếu được triển khai.
4. Báo cáo API contract thay đổi, policy đã áp dụng và phần không thể kiểm chứng (đặc biệt concurrency MySQL nếu môi trường local chỉ dùng SQLite).
