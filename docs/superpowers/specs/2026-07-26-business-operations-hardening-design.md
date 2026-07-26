# Spec: Hoàn thiện nghiệp vụ vận hành và đối soát

**Ngày:** 26-07-2026  
**Trạng thái:** Đã phê duyệt triển khai theo thứ tự: idempotency thanh toán, audit log, rồi phân quyền và các hạng mục còn lại.  
**Phạm vi:** Thanh toán, phân quyền vận hành, đặt phòng đồng thời, audit log, khách hàng và độ chính xác báo cáo.

## 1. Bối cảnh và mục tiêu

Các đợt trước đã hoàn thiện cô lập tenant cho giá, order và kho; order trừ tồn theo từng khách sạn, không cho tồn âm, còn nhập bổ sung thực hiện ở trang Kho hàng. Phòng đã check-in chỉ checkout, không cancel trực tiếp.

Đợt này làm hệ thống an toàn khi nhiều nhân viên cùng thao tác và có thể đối soát được tiền/dữ liệu sau ca làm:

- Không ghi trùng Payment khi checkout hoặc hủy/refund bị gửi lại.
- Không tạo hai booking active chồng thời gian cho cùng một phòng.
- Quyền Staff/Hotel admin/Master admin rõ ràng và được kiểm tra tại backend.
- Có lịch sử ai đã thay đổi dữ liệu nhạy cảm.
- Không tự gắn sai khách khi trùng SĐT.
- Có test xác nhận báo cáo doanh thu/phòng dùng đúng quan hệ dữ liệu.

Không bao gồm trong đợt này:

- Tích hợp cổng thanh toán, hóa đơn điện tử hoặc kế toán bên thứ ba.
- Chính sách mức hoàn tiền/lý do hoàn cụ thể.
- Tách database riêng cho từng khách sạn.
- Thiết kế lại giao diện ngoài các thông báo/quyền cần thiết.

## 2. Quy tắc chung

- Mọi thay đổi phải theo TDD: test đỏ, triển khai tối thiểu, refactor, full suite.
- Mutation về tiền, booking, kho và quyền phải nằm trong transaction; lỗi phải rollback toàn bộ.
- Toàn bộ model có `hotel_id` luôn truy vấn/mutate trong tenant scope.
- API mutation trả JSON status rõ ràng: `400` dữ liệu sai, `403` thiếu quyền, `404` ngoài tenant/không tồn tại, `409` xung đột trạng thái hoặc nghiệp vụ.
- Không thay đổi dữ liệu local cũ hoặc migration schema khi chưa có migration/backfill được duyệt.

## 3. Idempotency cho checkout, hủy và Payment

### Hiện trạng đã kiểm tra

`Payment` hiện chỉ có index theo `(hotel_id, booking_id)`. `checkout_room()` gọi `record_room_payment()` cho các phần tiền phòng, dịch vụ và thuế; payment service tạo bản ghi mới cho mỗi lần gọi. Chưa có request/reference duy nhất để nhận diện thao tác lặp.

### Yêu cầu

- Mỗi thao tác tiền có `operation_key` hoặc bảng operation riêng, xác định tối thiểu: hotel, booking room/booking, loại thao tác và lần thao tác nghiệp vụ.
- Một checkout thành công chỉ tạo các Payment của checkout một lần, kể cả khi client gửi lại cùng request hoặc người dùng double-click.
- Hủy/refund chỉ ghi refund và phí hủy một lần.
- Nếu booking room đã `checked_out`, checkout lại trả `409` cùng reference của thao tác trước (nếu có), không ghi thêm Payment.
- Response thành công trả reference để UI/log đối chiếu.
- Dùng Decimal hoặc quy ước số tiền nguyên thống nhất cho các quyết định tiền cuối cùng.

### Tiêu chí nghiệm thu

- Hai request checkout giống nhau chỉ có một bộ Payment.
- Retry hủy/refund không tăng Payment/refund/cancellation fee.
- Payment tenant A không thể được đọc hoặc dùng để hoàn ở tenant B.

## 4. Chống chồng lịch booking khi thao tác đồng thời

### Hiện trạng đã kiểm tra

Code đã có `_has_room_time_conflict()` tại timeline và gọi khi tạo/sửa/move ở các luồng chính. Kiểm tra hiện ở tầng ứng dụng; chưa có chiến lược lock/transaction cho hai request đồng thời.

### Yêu cầu

- Chuẩn hóa overlap là khoảng `[check_in, check_out)`; checkout của đơn trước đúng bằng check-in của đơn sau là hợp lệ.
- Tạo booking, kéo timeline, đổi phòng và thêm phòng đoàn đều dùng cùng một helper kiểm tra.
- Với database production, khóa bản ghi Room hoặc áp dụng chiến lược transaction phù hợp dialect trước khi ghi BookingRoom active.
- Conflict trả `409` gồm số phòng và khoảng thời gian xung đột; không tạo booking nửa chừng.
- Test SQLite chỉ xác nhận logic; test tích hợp MySQL/PostgreSQL xác nhận lock nếu production dùng một trong các database đó.

### Tiêu chí nghiệm thu

- Không tồn tại hai `BookingRoom` active overlap trong cùng tenant/phòng.
- Hai request cạnh tranh chỉ có một request thành công.
- Không làm hỏng case nối tiếp checkout/check-in đúng thời điểm.

## 5. Phân quyền nghiệp vụ

### Quyết định đã chốt

- Staff được checkout.
- Phòng đã check-in chỉ checkout, không cancel.
- Mức hoàn tiền, lý do hoàn và thẩm quyền refund chi tiết sẽ chốt sau.

### Yêu cầu kỹ thuật

- Tạo decorator capability dùng lại, thay cho việc chỉ dựa vào `login_required` hoặc `admin_required` rải rác.
- Backend trả JSON `403` cho API, không redirect HTML.
- UI chỉ ẩn/khóa thao tác theo capability như hỗ trợ trải nghiệm; backend vẫn là lớp quyết định.

### Ma trận quyền cần chốt trước khi triển khai phần refund

| Hành vi | Staff | Hotel admin | Master admin trong tenant context |
|---|---:|---:|---:|
| Booking, check-in, gọi món, checkout | Có | Có | Có |
| Nhập thêm kho | Có | Có | Có |
| Sửa/xóa item kho, dịch vụ, giá | Có | Có | Có |
| Hủy booking trước check-in | Có | Có | Có |
| Refund/phí hủy, VAT, cọc, checkout đoàn | Có, bắt buộc lý do | Có, bắt buộc lý do | Có, bắt buộc lý do |
| Chi phí, nhân sự, cấu hình hotel | Không | Có | Có |
| Quản lý danh sách hotel | Không | Không | Có |

### Tiêu chí nghiệm thu

- Có test Staff/Hotel admin/Master admin cho từng capability.
- Thiếu quyền không làm mutation dù gọi API trực tiếp.
- Staff vẫn checkout được như quyết định đã chốt.

## 6. Audit log

### Yêu cầu

Tạo audit event append-only cho các hành động:

- Tạo/sửa/hủy booking, đổi phòng, check-in/check-out.
- Gọi/sửa/xóa dịch vụ trên bill; nhập/sửa/xóa kho.
- Checkout, refund, phí hủy, cọc, VAT.
- Sửa giá/rule giá, chi phí, user và trạng thái hotel.

Mỗi event có: `hotel_id`, `actor_user_id`, thời gian, action, entity type/id, request/operation reference và snapshot before/after tối thiểu. Không ghi password, token hoặc bí mật vào snapshot.

Hotel admin chỉ xem log hotel mình; Master admin xem theo hotel context hoặc toàn hệ thống tùy capability.

### Tiêu chí nghiệm thu

- Mỗi mutation nhạy cảm tạo đúng một event cùng transaction.
- Event tenant A không xuất hiện ở tenant B.
- Retry idempotent không tạo audit event thanh toán trùng.

## 7. Khách hàng trùng SĐT

### Hiện trạng đã kiểm tra

Luồng tạo booking đang dùng `tenant_query(Customer).filter_by(phone=phone).first()`. SĐT không có unique constraint, vì vậy có thể tự chọn nhầm bản ghi đầu tiên khi nhiều khách dùng chung số.

### Yêu cầu

- Không đặt unique cứng cho SĐT.
- API tìm khách theo SĐT trả danh sách ứng viên trong tenant hiện tại.
- Khi có nhiều ứng viên, UI bắt buộc lễ tân chọn khách hoặc tạo khách mới; không tự lấy `.first()`.
- CCCD vẫn tuân theo unique theo hotel hiện có.

## 8. Xác nhận số liệu báo cáo

### Hiện trạng cần kiểm chứng bằng test

Trong `report_controller.py` có truy vấn join viết `Room.id == BookingRoom.id`. Cần viết test dữ liệu nhiều phòng trước để xác nhận báo cáo theo phòng/doanh thu có dùng đúng quan hệ `Room.id == BookingRoom.room_id`.

### Yêu cầu

- Viết test đỏ cho báo cáo theo phòng với ID BookingRoom khác ID Room.
- Sửa join tối thiểu nếu test chứng minh sai.
- Mọi tổng doanh thu/báo cáo lọc theo tenant và không tính booking active vào doanh thu đã hoàn tất.

## 9. Thứ tự triển khai

1. Idempotency checkout/refund và test Payment.
2. Audit log nền tảng, áp dụng trước cho checkout/refund, hủy phòng, kho, giá và xóa dữ liệu.
3. Chống overlap/concurrency booking.
4. Triển khai phân quyền backend/UI theo chính sách đã chốt.
5. Chống tự gắn khách trùng SĐT.
6. Test/sửa báo cáo theo phòng.

## 10. Điểm cần bạn xác nhận

Trước khi triển khai phân quyền/refund, cần chốt:

1. **Đã chốt:** Staff được nhập thêm kho.
2. **Đã chốt:** Staff được sửa/xóa item kho, dịch vụ và giá.
3. **Đã chốt:** Staff được hủy booking trước check-in.
4. **Đã chốt:** tất cả vai trò vận hành được refund; bắt buộc nhập lý do. Cơ chế `refund_percent` hiện có tiếp tục là cơ sở tính số tiền hoàn; không đặt giới hạn % mới trong đợt này.
5. **Đã chốt:** triển khai audit log ngay sau idempotency để các thao tác tiền và vận hành mới đều có dấu vết.
