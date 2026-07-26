# Thiết kế: Master admin và quản trị riêng từng khách sạn

## Mục tiêu

Hoàn thiện mô hình quản trị nhiều khách sạn: một Master admin quản lý các khách sạn và tạo tài khoản admin ban đầu; mỗi Hotel admin và staff chỉ thấy, tạo và quản lý dữ liệu thuộc đúng một khách sạn.

## Phạm vi

Đợt này gồm:

- Trang quản trị Master admin cho danh sách và trạng thái khách sạn.
- Tạo khách sạn cùng tài khoản Hotel admin đầu tiên.
- Quản lý staff/admin trong phạm vi một khách sạn.
- Cô lập tenant cho toàn bộ thao tác quản lý user theo ID.
- Hiển thị rõ khách sạn context khi Master admin hỗ trợ một khách sạn.
- Test TDD cho role, tenant isolation và luồng tạo hotel/admin.

Không gồm dashboard tổng hợp doanh thu, mô hình một user thuộc nhiều hotel, phân quyền chi tiết hơn admin/staff, reset mật khẩu qua email, audit log, hoặc tự đăng ký khách sạn.

## Vai trò và quyền hạn

| Vai trò | `is_super_admin` | `hotel_id` | Quyền |
| --- | --- | --- | --- |
| Master admin | `True` | `NULL` | Quản lý khách sạn; tạo Hotel admin; vào context bất kỳ hotel để hỗ trợ. |
| Hotel admin | `False` | Bắt buộc | Quản lý nhân viên/admin trong chính hotel; vận hành nghiệp vụ của hotel. |
| Staff | `False` | Bắt buộc | Chỉ vận hành nghiệp vụ được cấp; không quản lý tài khoản. |

- `username` tiếp tục unique toàn hệ thống.
- Một User không-master có đúng một `hotel_id`; không có nút đổi hotel.
- Master admin không được tạo booking hoặc dữ liệu nghiệp vụ ngoài tenant URL đã chọn. Khi vào `/<hotel_slug>/...`, mọi query dữ liệu nghiệp vụ vẫn phải scope bằng `g.hotel_id`.

## Kiến trúc và route

### Master admin console

- Route: `/master` — Master Console dashboard; đây là trang mặc định sau khi Master admin đăng nhập.
- Route: `/master/hotels` — danh sách hotel, trạng thái active/inactive, số phòng và số user thuộc hotel.
- Route: `/master/hotels/create` (`POST`) — tạo hotel và Hotel admin đầu tiên trong cùng một transaction.
- Route: `/master/hotels/<int:hotel_id>/toggle-active` (`POST`) — đổi trạng thái hoạt động; không xóa hotel và không xóa dữ liệu.
- Route: `/master/hotels/<int:hotel_id>/enter` (`GET`) — redirect tới `/<hotel_slug>/rooms/dashboard/room-map`; header luôn hiển thị tên hotel context.
- Chỉ `is_super_admin=True` truy cập các route `/master/*`; user khác nhận HTTP 403.

### Master Console dashboard

- Hiển thị tổng quan toàn hệ thống, không hiển thị bảng booking/khách trộn lẫn của nhiều hotel.
- Thẻ chỉ số gồm: tổng hotel, hotel đang hoạt động, hotel tạm ngưng, tổng số phòng, tổng phòng đang có khách và tổng booking được tạo trong ngày hiện tại.
- Danh sách “Hotel cần chú ý” gồm hotel tạm ngưng và hotel không có Hotel admin; nếu không có dữ liệu, hiển thị empty state rõ ràng.
- Bảng hotel hiển thị: tên, slug, trạng thái, số phòng, số user, Hotel admin đầu tiên, ngày tạo và thao tác.
- Mỗi dòng có `Vào quản lý`, `Tạm ngưng/Kích hoạt`; chỉ Master admin được thấy các action này.
- `Vào quản lý` không trộn dữ liệu với hotel khác: Master admin chuyển sang đúng URL tenant của hotel đã chọn và header hiển thị `Đang hỗ trợ: <tên hotel>`.
- Header trong Master Console có nhãn `Master Console`; không dùng menu vận hành của một hotel cụ thể.

### Quản trị user trong hotel

- Giữ route hiện có `/<hotel_slug>/staff/` làm màn hình quản lý user của Hotel admin.
- Danh sách chỉ chứa `User.hotel_id == g.hotel_id`; không hiển thị Master admin hay user hotel khác.
- Hotel admin tạo user với `hotel_id=g.hotel_id` gán tường minh trên server, bỏ phụ thuộc vào `before_flush`.
- Hotel admin chỉ tạo role `staff` hoặc `admin` trong chính hotel, không thể gửi `is_super_admin=True` hay `hotel_id` khác qua form/API.
- Reset password và delete user phải dùng lookup tenant-scoped; ID thuộc hotel khác trả 404.
- Không cho Hotel admin xóa chính mình, xóa Master admin, hoặc xóa admin cuối cùng của hotel.
- Khi hotel inactive, user thuộc hotel đó không đăng nhập được; Master admin vẫn vào console `/master/*`.

### Authentication và context

- Login tenant giữ đường dẫn `/<hotel_slug>/login`.
- User thường đăng nhập sai hotel URL nhận redirect về login cùng URL và message lỗi; session không được tạo.
- Master admin có login riêng tại `/master/login`, hoặc dùng một login chung không yêu cầu `hotel_slug`; sau khi thành công redirect tới `/master`.
- Không cho Master admin login qua URL hotel như user thường, để tránh nhầm context. Việc hỗ trợ hotel chỉ bắt đầu từ `/master/hotels/<hotel_id>/enter`.
- `load_current_hotel` kiểm tra `is_active` cho tenant route. Master admin context chỉ được tạo sau route `enter` hoặc qua URL hotel được redirect từ `enter`.

## Dữ liệu và transaction

Tạo hotel dùng một transaction:

1. Validate `name`, `slug`, `admin_username`, `admin_password`.
2. Kiểm tra `slug` và `admin_username` chưa tồn tại.
3. Tạo `Hotel(is_active=True)`.
4. Tạo `User(role='admin', hotel_id=hotel.id, is_super_admin=False)` và hash password.
5. Commit một lần; lỗi validation hoặc database rollback toàn bộ, không để hotel không có admin.

Không thay đổi schema vì `Hotel`, `User.hotel_id` và `User.is_super_admin` đã tồn tại. Chỉ thêm migration nếu kiểm tra database thực tế cho thấy constraint/index không khớp model.

## Giao diện

- Master Console có layout riêng, gồm sidebar/nav dành cho quản trị hệ thống và không dùng menu vận hành của hotel.
- Trang `/master` có dashboard chỉ số, danh sách Hotel cần chú ý và bảng hotel rút gọn với action `Vào quản lý`.
- Master console dùng bảng: Tên hotel, slug, trạng thái, số phòng, số user, ngày tạo, thao tác.
- Nút thao tác: `Vào quản lý`, `Tạm ngưng/Kích hoạt`; tạm ngưng cần modal xác nhận và nêu rõ user hotel sẽ không đăng nhập được.
- Form tạo hotel gồm thông tin hotel và khối “Tài khoản Hotel admin đầu tiên”.
- Header trong tenant context hiển thị rõ tên hotel; với Master admin thêm nhãn `Đang hỗ trợ` và nút quay về `/master/hotels`.
- Hotel admin chỉ thấy quản lý nhân viên thuộc hotel hiện tại; không thấy selector hoặc dữ liệu hotel khác.

## TDD bắt buộc

- Mỗi endpoint/hành vi mới bắt đầu bằng pytest test thất bại sử dụng SQLite test database.
- Test tối thiểu:
  - Master admin vào được `/master/hotels`; Hotel admin/staff nhận 403.
  - Master admin vào `/master` thấy chỉ số được tính trên tất cả hotel; Hotel admin/staff nhận 403.
  - Master Console không trả booking/khách chi tiết của nhiều hotel trong cùng payload.
  - Master tạo hotel thành công có đúng một Hotel admin với `hotel_id` đúng và mật khẩu được hash.
  - Username/slug trùng rollback, không tạo hotel hoặc user dở dang.
  - Hotel admin chỉ thấy user của chính hotel.
  - Hotel admin không reset password/xóa user thuộc hotel khác; trả 404.
  - Hotel admin không tạo super admin, không gán hotel khác và không xóa admin cuối cùng.
  - Hotel inactive chặn login của user hotel đó.
  - Master dùng `enter` vào hotel A chỉ đọc dữ liệu tenant A; không có data leak hotel B.

## Tiêu chí hoàn thành

- Có màn hình Master admin quản lý hotel và tạo admin đầu tiên.
- Toàn bộ user management lookup/list query theo `hotel_id`.
- Không có endpoint `/master/*` truy cập được bởi Hotel admin/staff.
- Tất cả test mới và test hiện có pass trong Python environment hoạt động.
- Không thay đổi hoặc xóa dữ liệu phát triển local trong quá trình test.
