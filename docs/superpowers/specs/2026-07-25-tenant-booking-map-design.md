# Thiết kế: Multi-tenant an toàn, booking và sơ đồ phòng

## Mục tiêu

Đảm bảo ứng dụng quản lý khách sạn đang phát triển local vận hành đúng giữa nhiều khách sạn, đồng thời biến Sơ đồ phòng thành màn hình thao tác nhanh dùng chung quy tắc booking và nhận phòng với Timeline.

## Phạm vi

Đợt này gồm: truy vấn dữ liệu theo tenant, nhận diện đúng dòng booking khi check-in, giao diện thao tác nhanh trên Sơ đồ phòng, một số thành phần giao diện dùng chung và test tự động. Không gồm bảo mật triển khai production, OTA, audit log, mở rộng vai trò, housekeeping, quản lý ca, hoặc tái cấu trúc toàn bộ controller.

## Quyết định đã chốt

### Cô lập tenant

- Bỏ global filter `Query.before_compile` theo hotel hiện tại. Nó bỏ qua các query có `LIMIT` hoặc `OFFSET`, nên những truy vấn như `.first()` có thể trả về dữ liệu chéo tenant.
- Thêm helper query tường minh nhận model và đọc `g.hotel_id`. Helper phải từ chối khi request không có tenant context và chỉ trả bản ghi có `hotel_id` của hotel hiện tại.
- Các endpoint lấy tài nguyên theo ID phải dùng helper này, bao gồm những endpoint chạm tới booking, booking-room, room, customer, payment, service, inventory, expense và price-rule.
- Bản ghi mới vẫn nhận `hotel_id` tự động trong `before_flush`; mỗi service cũng chỉ được tạo bản ghi sau khi tenant context đã tồn tại.
- Test phải tạo hai hotel và chứng minh người dùng của hotel A nhận phản hồi không tìm thấy khi truy cập room hoặc booking-room của hotel B.

### Quản lý khách sạn và tài khoản

- `Master admin` là tài khoản hệ thống có `is_super_admin=True` và không thuộc hotel cụ thể. Master admin được tạo/sửa/ngưng hoạt động hotel và tạo tài khoản admin đầu tiên cho từng hotel.
- `Hotel admin` và `staff` có đúng một `hotel_id`. Họ chỉ được đọc, tạo và sửa dữ liệu trong hotel đó; giao diện không có chức năng đổi hotel.
- Hotel admin được tạo tài khoản staff có cùng `hotel_id`; server không nhận `hotel_id` do staff gửi từ trình duyệt.
- Master admin được phép vào chế độ hỗ trợ một hotel, nhưng mọi màn hình phải hiển thị rõ tên hotel hiện tại trong header.
- Giữ `username` unique toàn hệ thống trong giai đoạn này. Mỗi hotel có đường dẫn login riêng `/<hotel_slug>/login`; đăng nhập bằng tài khoản không thuộc hotel trên URL phải bị chặn.
- Test xác nhận hotel admin và staff không thể đăng nhập hoặc gọi API của hotel khác; master admin vẫn có quyền vào tenant context đã chọn.

### Hợp đồng booking và nhận phòng

- Mọi thao tác booking theo phòng luôn định danh bản ghi bằng `booking_room_id`, không dùng riêng `booking_id` hoặc cách lấy “dòng booked đầu tiên của phòng”.
- `POST /api/rooms/checkin` nhận `{ "booking_room_id": integer }`. Server tự lấy room từ booking-room, không tin room number từ trình duyệt.
- Check-in thành công cần: booking-room thuộc tenant hiện tại, có trạng thái `booked`, phòng sạch/chưa có khách, và giờ nhận dự kiến không sớm hơn hiện tại quá ba giờ.
- Khi thành công: chuyển `BookingRoom.status` thành `checked_in`, gán `check_in_actual`, đặt room là `occupied`, và cập nhật booking cha sang `checked_in` khi phù hợp.
- Timeline và Sơ đồ phòng gọi cùng endpoint, nhận cùng validation message.

### Trải nghiệm Sơ đồ phòng

- Sơ đồ phòng vẫn là màn hình thao tác nhanh; Timeline là nơi lập lịch và sửa chi tiết.
- Phòng sạch, trống, không có booking active: mở menu nhỏ gồm `Đặt trước` và `Vào ở ngay`.
- Phòng sạch, trống, có booking sắp đến hoặc chờ nhận: hiển thị thông báo hoàn chỉnh thay badge cảnh báo hiện tại. Thông báo gồm tên khách, giờ nhận dự kiến, giờ trả dự kiến, tiền cọc và trạng thái.
- Bấm thông báo mở popover/menu nhỏ có `Nhận phòng` và `Xem chi tiết`. `Nhận phòng` gọi endpoint chung với đúng `booking_room_id`; `Xem chi tiết` dẫn đến chi tiết booking tương ứng trên Timeline.
- Phòng có booking tương lai vẫn có thể được đặt cho khoảng thời gian không chồng lấn. Thông báo không được khiến người dùng hiểu nhầm phòng đang có khách.

### Chuẩn hóa giao diện tối thiểu

- Tạo CSS class dùng chung cho status badge, menu thao tác nhỏ, modal footer, empty state và table header.
- Dùng một quy ước trạng thái: booked = warning, checked-in = primary, checked-out = neutral, cancelled = danger, dirty = warning, maintenance = secondary.
- Dùng JavaScript formatter chung cho VND và ngày giờ tiếng Việt tại Sơ đồ phòng và Timeline.
- Đợt này không chuyển đổi mọi bảng hiện có; chỉ tạo thành phần tái sử dụng và áp dụng cho Sơ đồ phòng, Timeline.

## Quy tắc TDD và kiểm chứng

- Mọi thay đổi hành vi bắt đầu bằng pytest test thất bại mô tả đúng kết quả quan sát được.
- Test suite dùng Flask application factory và SQLite tách biệt; không yêu cầu MySQL local và không làm thay đổi database phát triển.
- Mỗi task tuân thủ red → green → refactor; chạy focused test trước full relevant suite.
- Test phải bao phủ: tenant isolation, check-in đúng booking-room, validation check-in, state transition khi check-in thành công, và dữ liệu thông báo booking của API Sơ đồ phòng.
- Không coi là hoàn thành khi focused test và full test suite liên quan chưa pass.

## Phần để sau

- Secret production, CSRF, xử lý XSS ngoài phạm vi map/timeline, audit log, backup, CI, Docker, role chi tiết, ca thu ngân, housekeeping, bảo trì, export, và coverage cho module không liên quan.
