# Spec: Khắc phục logic nghiệp vụ và tăng độ an toàn dữ liệu

**Ngày:** 26-07-2026  
**Trạng thái:** Chờ phê duyệt triển khai  
**Phạm vi:** Multi-tenant, booking, giá, dịch vụ/kho, quyền hạn và audit trail

## 1. Mục tiêu

Khắc phục các lỗi có thể gây sai giá giữa khách sạn, hủy booking thất bại, không lưu được order mới hoặc sai tồn kho. Đồng thời chốt các quy tắc quyền hạn và tạo nền tảng truy vết thay đổi nghiệp vụ.

Không nằm trong phạm vi:

- Thay đổi giao diện ngoài phần cần thiết để thông báo lỗi/quyền.
- Thay đổi schema theo hướng tách database riêng cho mỗi khách sạn.
- Tối ưu hiệu năng báo cáo chuyên sâu hoặc tích hợp kế toán bên ngoài.

## 2. Nguyên tắc chung

- Mọi truy vấn model có `hotel_id` phải đi qua tenant scope hoặc lọc rõ `hotel_id`.
- Mọi mutation tài chính/kho/booking dùng transaction; lỗi phải rollback toàn bộ.
- Không tin dữ liệu số lượng, giá, room id hoặc booking id từ client.
- Mọi thay đổi nghiệp vụ dùng TDD: test đỏ → triển khai tối thiểu → refactor → full suite.
- Không sửa dữ liệu lịch sử im lặng; migration/backfill phải có script và kiểm tra riêng.

## 3. Hạng mục bắt buộc (P0)

### 3.1 Cô lập PriceRule theo khách sạn

**Hiện trạng:** `pricing_service.get_effective_room_prices()` tìm `PriceRule` theo loại phòng/ngày nhưng không lọc `hotel_id`.

**Yêu cầu:**

- Rule giá chỉ được áp dụng khi `PriceRule.hotel_id == room.hotel_id`.
- Nếu `room.hotel_id` không có, hàm không được áp dụng rule tenant bất kỳ.
- Giữ nguyên ưu tiên hiện tại: rule active, đúng loại phòng, đúng ngày, priority cao hơn, sau đó lọc thứ.

**Tiêu chí nghiệm thu:**

- Rule cùng loại phòng của hotel B không làm đổi giá hotel A.
- Rule của đúng hotel vẫn đổi giá và giữ `rule_name` đúng.
- Giá theo giờ vẫn lấy từ Room, không lấy từ PriceRule.

### 3.2 Sửa luồng hủy booking

**Hiện trạng:** nhánh nhận `booking_room_id`/`booking_id` gọi `.first()` sai vị trí sau `int()`, gây lỗi runtime.

**Yêu cầu:**

- Parse ID an toàn; ID sai kiểu trả `400`, không trả stack trace.
- Lấy booking/booking room bằng tenant scope.
- Hủy một `BookingRoom` chỉ ảnh hưởng phòng được chọn.
- Hủy theo `booking_id` ảnh hưởng các phòng chưa hủy trong booking đó.
- Không cho hủy phòng đã checkout; quy tắc cho phòng checked-in cần quyết định ở mục 7.
- Cọc, phí hủy, refund và Payment chỉ được tạo một lần cho cùng hành động; retry request không được nhân đôi tiền.

**Tiêu chí nghiệm thu:**

- Hủy một phòng đoàn không hủy phòng khác.
- Hủy toàn booking chuyển tất cả phòng hợp lệ sang cancelled.
- Không thể hủy booking/room tenant khác.
- Hủy lại cùng đối tượng có phản hồi rõ, không thêm Payment/refund.

### 3.3 Sửa lưu order mới và bảo toàn tenant

**Hiện trạng:** endpoint thêm order tạo `BookingService` mới thiếu `hotel_id` dù model bắt buộc trường này.

**Yêu cầu:**

- Mọi `BookingService` mới luôn có `hotel_id` từ phòng/booking tenant hiện tại.
- Kiểm tra request `items`: phải là danh sách không rỗng, `service_id` là int, `qty` là int dương.
- Service phải thuộc tenant hiện tại; item sai tenant hoặc không tồn tại làm toàn request thất bại và rollback.
- Món đã có cộng dồn quantity; không tạo dòng trùng cùng booking/phòng/service.
- Lưu thành công phải hiện trong lịch sử “Đã gọi”, preview checkout và hóa đơn.

**Tiêu chí nghiệm thu:**

- Order mới tạo đúng `hotel_id`, booking_id, room_id, giá snapshot.
- Order lặp cộng dồn quantity.
- Quantity âm/0, item rỗng, service khác tenant trả 400/404 và không thay đổi dữ liệu/kho.
- Order tenant A không thể đọc hoặc sửa tenant B.

## 4. Hạng mục độ an toàn cao (P1)

### 4.1 Chính sách tồn kho và transaction order

**Đề xuất mặc định:** chặn order nếu bất kỳ inventory item liên kết có tồn kho không đủ; không cho tồn kho âm.

**Yêu cầu:**

- `deduct_inventory`/`restore_inventory` nhận `hotel_id` và chỉ mutate inventory tenant đó.
- Validate toàn bộ items và tồn kho trước khi thêm `BookingService` hoặc trừ kho.
- Một order có nhiều món là atomic: một món lỗi thì không lưu món nào và không trừ kho nào.
- Nếu service không liên kết inventory, vẫn cho order và không cập nhật kho.
- Response lỗi nêu rõ món nào thiếu và số lượng hiện có.

**Tiêu chí nghiệm thu:**

- Không có quantity inventory âm sau order/rollback/update service.
- Cùng `service_id` ở tenant khác không bị thay đổi tồn kho.
- Update service quantity khôi phục/trừ lại kho chính xác.

### 4.2 Chống booking trùng khi có request đồng thời

**Yêu cầu:**

- Định nghĩa thống nhất overlap: khoảng `[check_in, check_out)`; điểm checkout của booking trước bằng checkin booking sau là hợp lệ.
- Khi tạo/sửa/chuyển phòng booking, kiểm tra overlap trong transaction.
- Khóa bản ghi Room hoặc dùng chiến lược phù hợp MySQL để hai request đồng thời không cùng giữ một phòng.
- Nếu conflict, trả `409` với thông điệp phòng/thời gian xung đột.

**Tiêu chí nghiệm thu:**

- Một booking overlap bị từ chối.
- Booking sát thời điểm checkout/checkin được chấp nhận.
- Hai request mô phỏng cạnh tranh không tạo hai active booking overlap.

### 4.3 Idempotency cho thao tác tiền và checkout

**Yêu cầu:**

- Checkout, group checkout, refund/hủy phải kiểm tra trạng thái trước khi tạo Payment.
- Client retry cùng request không được tạo nhiều Payment cùng loại cho cùng booking room/action.
- Response thành công trả `payment_id`/reference để client và log đối chiếu.
- Các phép tính dùng Decimal hoặc giá trị tiền nguyên nhất quán; không dùng float để quyết định số tiền cuối.

## 5. Phân quyền nghiệp vụ (P1)

### 5.1 Vai trò đề xuất

| Hành vi | Staff | Hotel admin | Master admin trong ngữ cảnh hotel |
|---|---|---|---|
| Xem sơ đồ phòng, Timeline, khách hàng | Có | Có | Có |
| Tạo/sửa booking, check-in | Có | Có | Có |
| Gọi dịch vụ | Có | Có | Có |
| Checkout, hoàn/hủy có tiền, chỉnh VAT/cọc | **Chờ quyết định** | Có | Có |
| Sửa giá phòng/rule giá | Không | Có | Có |
| Kho, dịch vụ, chi phí | **Chờ quyết định** | Có | Có |
| Quản lý nhân sự hotel | Không | Có | Có |
| Tạo/tạm ngưng hotel | Không | Không | Có |

### 5.2 Yêu cầu kỹ thuật

- Bổ sung decorator quyền theo capability, không chỉ kiểm tra `role == admin` rải rác.
- Endpoint mutation phải áp dụng capability ở backend, không chỉ ẩn nút UI.
- Response API không được redirect HTML khi thiếu quyền; trả `403` JSON cho API.
- Có test staff/admin/master cho từng nhóm endpoint nhạy cảm.

## 6. Audit trail (P2)

### 6.1 Phạm vi log

Ghi audit event cho:

- Tạo/sửa/hủy booking và thay phòng.
- Check-in/check-out, hoàn tiền, phí hủy, chỉnh cọc/VAT.
- Thêm/sửa/xóa dịch vụ và quantity gọi món.
- Thay đổi giá/rule giá, kho, chi phí.
- Tạo/reset/xóa user và thay đổi trạng thái hotel.

### 6.2 Dữ liệu event

- `hotel_id`, `actor_user_id`, thời gian, action, entity type/id.
- Snapshot before/after tối thiểu cho field thay đổi.
- Request/reference id khi action tạo Payment.
- Không ghi plaintext password, token hoặc dữ liệu nhạy cảm vượt nhu cầu audit.

Audit log chỉ append; Hotel admin xem log hotel mình, Master admin xem theo hotel context/toàn hệ thống theo quyền.

## 7. Quyết định cần bạn phê duyệt trước khi triển khai

1. **Staff có được checkout/hoàn-hủy có tiền không?** Đề xuất: Staff được checkout thường, Hotel admin bắt buộc cho refund, hủy có hoàn tiền, chỉnh VAT/cọc và group checkout.
2. **Khi thiếu kho:** đề xuất chặn toàn bộ order, không cho tồn âm.
3. **Hủy phòng checked-in:** đề xuất không dùng cancel; phải checkout hoặc luồng “hủy sau check-in” riêng có audit/refund.
4. **SĐT khách hàng:** đề xuất không unique cứng vì gia đình/công ty có thể dùng chung; khi trùng, UI yêu cầu chọn khách thay vì tự lấy bản ghi đầu tiên.
5. **Audit log:** triển khai ngay sau P1 hay để sau khi P0/P1 ổn định?

## 8. Thứ tự triển khai đề xuất

| Đợt | Phạm vi | Điều kiện hoàn tất |
|---|---|---|
| 1 — P0 | PriceRule tenant, hủy booking, order mới | Test unit/API/cross-tenant cho từng lỗi xanh |
| 2 — P1 | Kho atomic + tenant, validation order | Không âm kho, rollback toàn bộ khi có item lỗi |
| 3 — P1 | Role capability, idempotency checkout/refund | Ma trận quyền và retry tiền có test |
| 4 — P1 | Chống booking overlap/concurrency | Conflict 409 và test cạnh tranh |
| 5 — P2 | Audit trail, xử lý SĐT trùng | Truy vết được action nhạy cảm |

## 9. Kiểm tra trước khi bàn giao

- Chạy toàn bộ pytest, bao gồm test tenant isolation hiện có và test mới.
- Kiểm tra migration/backfill trên database local copy trước khi áp dụng môi trường dùng chung.
- Với thay đổi quyền/UI, kiểm tra bằng `bb-browser` cho Staff, Hotel admin và Master admin.
- Báo cáo rõ migration nào đã chạy, dữ liệu nào được backfill và hành vi cũ nào bị chặn theo chính sách đã duyệt.
