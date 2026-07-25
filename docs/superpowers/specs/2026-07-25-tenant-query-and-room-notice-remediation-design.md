# Thiết kế khắc phục: Tenant query và thông báo booking trên Sơ đồ phòng

## Mục tiêu

Khôi phục cô lập dữ liệu tuyệt đối giữa các khách sạn sau refactor tenant query, đồng thời hoàn thiện dữ liệu và giao diện thông báo booking trên Sơ đồ phòng theo thiết kế đã chốt.

## Phạm vi

Spec chỉ xử lý bốn vấn đề đã xác minh trong review:

1. Không dùng `.get()` trên `tenant_query(...)`.
2. Đảm bảo các endpoint thao tác dữ liệu theo tenant không còn query trực tiếp bỏ qua `hotel_id`.
3. Hoàn chỉnh contract API và UI của thông báo booking trên Sơ đồ phòng.
4. Loại bỏ XSS khi render dữ liệu booking/khách trong thông báo này.

Không bao gồm: CSRF toàn hệ thống, audit log, role mới, refactor controller quy mô lớn, chuẩn hóa toàn bộ giao diện, OTA, backup, hoặc tính năng nghiệp vụ mới.

## Quyết định kỹ thuật

### 1. Quy tắc truy vấn tenant

- `tenant_query(Model)` chỉ dùng cho truy vấn danh sách hoặc query tiếp theo bằng `filter`, `filter_by`, `first`, `all`, `count`, `one_or_none`.
- Không gọi `.get()` sau `tenant_query(Model)`. SQLAlchemy không cho phép `Query.get()` khi query đã có điều kiện `hotel_id`.
- Khi cần bản ghi bắt buộc tồn tại, dùng `tenant_get_or_404(Model, record_id)`.
- Khi bản ghi có thể không tồn tại, dùng `tenant_query(Model).filter(Model.id == record_id).first()`.
- Không dùng `Model.query`, `Model.query.get`, `Model.query.get_or_404`, hoặc `db.session.query(Model)` cho model có `hotel_id` trong controller/service chạy trong tenant request, trừ truy vấn không thuộc tenant context được ghi chú rõ ràng.
- Các model phải được rà trong phạm vi controller/service: `Room`, `Booking`, `BookingRoom`, `Customer`, `Service`, `Payment`, `InventoryItem`, `Expense`, `PriceRule`.

### 2. Hành vi khi truy cập chéo tenant

- Mọi endpoint lấy, sửa hoặc xóa tài nguyên theo ID phải trả 404 nếu ID tồn tại nhưng thuộc khách sạn khác.
- Không trả dữ liệu chi tiết, không sửa dữ liệu và không trả lỗi 500 trong trường hợp này.
- Master admin chỉ truy cập dữ liệu tenant thông qua URL tenant context đã chọn; các query vẫn phải có `hotel_id` của URL đó.

### 3. Contract thông báo booking của Sơ đồ phòng

- API `GET /<hotel_slug>/rooms/api/rooms` trả `notices` cho từng phòng.
- Mỗi notice có đúng các trường:

```json
{
  "booking_room_id": 12,
  "type": "upcoming",
  "status": "booked",
  "guest_name": "Nguyễn Văn A",
  "check_in_expected": "2026-07-25T14:00",
  "check_out_expected": "2026-07-26T12:00",
  "deposit": 500000
}
```

- `type` chỉ là `upcoming` khi giờ nhận nằm trong 24 giờ tới, hoặc `waiting` khi đã quá giờ nhận mà booking vẫn là `booked`.
- Notice không xuất hiện cho booking thuộc khách sạn khác, đã hủy hoặc đã checkout.
- Phòng có nhiều booking hợp lệ có thể có nhiều notice, sắp theo `check_in_expected` tăng dần.

### 4. Giao diện thao tác nhanh

- Thẻ phòng chỉ hiển thị tóm tắt: trạng thái, tên khách, giờ nhận và trạng thái cọc.
- Bấm notice mở menu/popover nhỏ, không nhét toàn bộ thao tác trực tiếp vào card.
- Popover có hai action: `Nhận phòng` và `Xem chi tiết`.
- `Nhận phòng` gửi duy nhất `{ "booking_room_id": number }` tới endpoint check-in chung.
- `Xem chi tiết` mở đúng booking-room trên Timeline bằng `booking_room_id`.
- Phòng trống không có notice có menu riêng: `Đặt trước` và `Vào ở ngay`.

### 5. An toàn khi render UI

- Không đưa `guest_name`, thời gian hoặc bất kỳ dữ liệu API nào vào `innerHTML` bằng template string.
- JavaScript tạo element bằng DOM API và gán nội dung động qua `textContent`.
- `booking_room_id` phải được kiểm tra là số nguyên dương trước khi dùng để gọi API hoặc tạo URL.

## Yêu cầu TDD

- Mỗi hành vi dưới đây bắt đầu bằng test pytest thất bại.
- Test dùng SQLite tách biệt từ `tests/conftest.py`; không dùng MySQL local.
- Test tối thiểu:
  - Mỗi endpoint theo ID của room/booking/customer/service/kho/chi phí/giá trả 404 khi ID thuộc hotel khác.
  - Các endpoint Timeline đã refactor không trả 500 do `.get()` trên `tenant_query`.
  - Một room trả notice đầy đủ trường, đúng tenant, đúng thứ tự.
  - Notice không lọt booking của hotel khác.
  - Check-in từ notice chỉ cập nhật booking-room được chọn.
  - Giá trị khách có HTML như `<img src=x onerror=alert(1)>` được hiển thị dưới dạng text, không tạo DOM element từ chuỗi đó.
- Sau mỗi task: chạy focused test; khi hoàn tất: chạy toàn bộ `python -m pytest -v` trong môi trường Python hoạt động.

## Tiêu chí hoàn thành

- Không còn kết quả từ `rg -n "tenant_query\\([^\\)]*\\)\\.get\\(" controllers services`.
- Không còn truy vấn trực tiếp không có scope tenant với các model tenant-owned trong controller/service tenant request.
- Tất cả test mới và test hiện có pass trong environment có thể chạy pytest.
- Sơ đồ phòng hiển thị notice đủ thông tin, có popover thao tác nhanh, và không render dữ liệu khách bằng `innerHTML`.
