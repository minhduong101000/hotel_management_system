# Sổ tay nghiệp vụ hiện có của Hotel POS Pro

**Cập nhật theo mã nguồn:** 14-08-2026
**Phạm vi:** Chức năng đã được đăng ký trong ứng dụng hiện tại trên nhánh `dev`.
**Cách đọc:** “Có” nghĩa là đã có route/controller tương ứng. Các mục “Cần chỉnh” nêu rõ phần đã phát hiện lệch nghiệp vụ hoặc không nhất quán, không khẳng định đó là tính năng đã hoàn thành.

## 1. Mô hình vận hành tổng quát

Hệ thống là phần mềm vận hành khách sạn theo từng tenant. Mỗi khách sạn có `slug` riêng và phần lớn màn hình chạy dưới dạng:

```text
/<hotel_slug>/...
```

Ví dụ tenant `central` có Sơ đồ phòng tại `/central/rooms/dashboard/room-map`.

Chuỗi dữ liệu nghiệp vụ chính:

```text
Khách hàng
  └─ Booking (đơn đặt)
       ├─ BookingRoom (từng phòng trong đơn)
       │    ├─ BookingService (dịch vụ đã dùng)
       │    └─ Payment (cọc, thanh toán, hoàn tiền)
       └─ BusinessOperation + AuditEvent (chống xử lý lặp và truy vết)

Dịch vụ ↔ Vật tư kho ↔ Lô hàng ↔ Biến động kho / phân bổ theo lô
```

Mọi thao tác tenant phải giới hạn theo `hotel_id`. Master Admin có khu vực quản trị riêng để tạo, ngừng hoạt động và vào hỗ trợ từng khách sạn.

### 1.1. Trạng thái nghiệp vụ quan trọng

| Đối tượng | Trạng thái/ý nghĩa |
|---|---|
| Phòng thực tế | `available` (sẵn sàng), `occupied` (có khách), `maintenance` (bảo trì). Song song có trạng thái vệ sinh `cleaned`/`dirty`. |
| Phòng trong đơn (`BookingRoom`) | `booked` → `checked_in` → `checked_out`; hoặc `booked` → `cancelled`. |
| Đơn (`Booking`) | Được suy ra từ các phòng con: `confirmed`, `checked_in`, `completed`, `cancelled`… |
| Thanh toán | Cọc, tiền phòng, tiền dịch vụ, thuế, thanh toán gộp, phí hủy và hoàn tiền được lưu thành `Payment`. |
| Lô kho | Lô còn dùng được, đã hết, quá hạn; khi khách gọi dịch vụ, tồn được phân bổ theo lô. |

## 2. Chức năng theo từng role

Trong code hiện có, quyền được quyết định bằng hai thuộc tính riêng:

- `role`: `staff` hoặc `admin`.
- `is_super_admin`: cờ quyền toàn hệ thống của Master Admin.

`admin_required` chỉ chấp nhận `role == admin`; trong khi `room_structure_required` và `booking_reschedule_required` chấp nhận cả Admin lẫn Master Admin. Vì vậy quyền của Master khi vào tenant không hoàn toàn giống quyền Admin. Bảng dưới mô tả **quyền backend thực tế**, không chỉ menu.

| Nhóm chức năng | Staff | Admin khách sạn | Master Admin |
|---|---|---|---|
| Đăng nhập vào tenant, xem Sơ đồ phòng/Timeline/Hóa đơn | Có | Có | Có khi vào tenant hỗ trợ |
| Tạo booking lẻ/đoàn, check-in, gọi/sửa dịch vụ trong booking, checkout lẻ/đoàn, dọn phòng | Có | Có | Có khi vào tenant hỗ trợ |
| Khách hàng: tìm, thêm, sửa, xóa | Có | Có | Có khi vào tenant hỗ trợ |
| Timeline: tạo, sửa trực tiếp, kéo-thả, hủy booking | Có trong hiện trạng API | Có | Có khi vào tenant hỗ trợ |
| Dời lịch có kiểm tra phòng trống và lý do | Không, trả `403` | Có | Có |
| Xem cấu hình phòng và giá mặc định | Có | Có | Có |
| Thêm/sửa phòng, bật/tắt bảo trì | Không, trả `403` | Có | Có |
| Giá đặc biệt qua đêm: xem/thêm/sửa/xóa | Có trong hiện trạng API | Có | Có khi vào tenant hỗ trợ |
| Dịch vụ/minibar: xem/thêm/sửa/xóa | Có trong hiện trạng API, dù menu bị ẩn | Có | Có khi vào tenant hỗ trợ |
| Kho: xem vật tư/lô/lịch sử | Có | Có | Có khi vào tenant hỗ trợ |
| Kho: tạo/sửa/xóa vật tư, nhập, hủy hàng, điều chỉnh | Không | Có | Chỉ có nếu tài khoản Master đồng thời có `role=admin` |
| Chi phí, doanh thu, sổ quỹ, nhật ký hoạt động, nhân sự | Không | Có | Chỉ có nếu tài khoản Master đồng thời có `role=admin` |
| Master Console: tạo tenant, tạo Admin đầu tiên, bật/tắt tenant, vào hỗ trợ | Không | Không | Có |

Các dòng “Có trong hiện trạng API” là **quyền đang bị nới quá rộng**, không phải khuyến nghị nghiệp vụ. Cần chốt và áp dụng server-side theo [mục 5](#5-các-điểm-cần-chỉnh-theo-hiện-trạng-mã-nguồn).

### 2.1. Staff lễ tân

Staff là vai trò vận hành ca trực. Các thao tác nên sử dụng trong ca:

1. Xem phòng trống/đang ở/cần dọn trên **Sơ đồ phòng** và xem lịch trên **Timeline**.
2. Tạo booking lẻ hoặc đoàn, nhận cọc đúng mức 50%/100%, sau đó check-in khách đến.
3. Cập nhật hồ sơ khách, gọi minibar/dịch vụ và điều chỉnh số lượng trước checkout.
4. Xem quote checkout, xác nhận thanh toán, in/xem hóa đơn cũ và đánh dấu đã dọn phòng.
5. Xem tồn, lô và lịch sử kho để phục vụ vận hành, nhưng không tự nhập/hủy/điều chỉnh kho.
6. Xem cấu hình phòng/giá để tư vấn khách, nhưng không thay đổi cấu trúc phòng.

Staff không được dùng khu vực chi phí, báo cáo doanh thu, sổ quỹ, nhật ký hoạt động hay quản trị nhân sự. Theo nghiệp vụ cần chốt, Staff cũng không nên có quyền sửa danh mục dịch vụ/giá, hủy booking tùy ý hoặc kéo-thả lịch trực tiếp; backend hiện chưa chặn triệt để các thao tác này.

### 2.2. Admin khách sạn

Admin chịu trách nhiệm vận hành và kiểm soát dữ liệu trong **một tenant**:

1. Có toàn bộ tác vụ lễ tân của Staff.
2. Quản lý cấu trúc phòng: thêm/sửa phòng, giá mặc định theo giờ/ngày, bật/tắt bảo trì.
3. Quản lý danh mục dịch vụ/minibar, giá đặc biệt qua đêm và kiểm tra các ảnh hưởng trước khi áp dụng.
4. Quản lý kho: vật tư, lô nhập, hạn dùng, hủy hàng và điều chỉnh tồn có lý do.
5. Ghi nhận/hủy ghi nhận chi phí; đồng bộ chi phí sang kho và dịch vụ khi cần.
6. Xem báo cáo doanh thu, sổ quỹ, hóa đơn và nhật ký để đối soát ca/ngày.
7. Tạo, đặt lại mật khẩu và xóa tài khoản trong tenant; không thể xóa chính mình hoặc Admin cuối cùng.
8. Dời lịch booking với lý do, kiểm tra phòng trống và lựa chọn giữ giá/áp giá mới.

Admin không quản lý tenant khác và không có quyền tạo/tạm dừng khách sạn ở Master Console.

### 2.3. Master Admin

Master Admin chịu trách nhiệm cấp hệ thống:

1. Đăng nhập **Master Console** để xem số lượng khách sạn/phòng/booking toàn hệ thống.
2. Tạo tenant mới kèm tài khoản Admin đầu tiên.
3. Bật hoặc tạm ngưng hoạt động tenant.
4. Vào một tenant ở chế độ hỗ trợ; banner giao diện thông báo đang hỗ trợ khách sạn nào.
5. Trong tenant, có thể dùng các route chỉ cần đăng nhập, quản lý cấu trúc phòng và dời lịch vì hai decorator này chấp nhận `is_super_admin`.

Đã xử lý 14-08: `admin_required` chấp nhận cả `is_super_admin` — Master vào tenant hỗ trợ dùng được đầy đủ kho, chi phí, doanh thu, sổ quỹ, audit và nhân sự mà không cần kiêm `role = admin`.

## 3. Bản đồ màn hình và thao tác

### 3.1. Đăng nhập tenant

**URL:** `/<hotel_slug>/login`
**Dành cho:** Staff, Admin khách sạn và Master Admin khi vào tenant.

- Đăng nhập bằng tài khoản thuộc đúng khách sạn; Master Admin cũng có thể vào tenant.
- Có tùy chọn ghi nhớ phiên đăng nhập.
- Khi thành công, chuyển về Sơ đồ phòng của tenant.
- Đăng xuất tại `/<hotel_slug>/logout`.

### 3.2. Sơ đồ phòng

**URL:** `/<hotel_slug>/rooms/dashboard/room-map`
**Dành cho:** người dùng đã đăng nhập.
**Mục đích:** màn hình lễ tân vận hành tức thời.

| Thao tác | Công dụng/qui tắc hiện có |
|---|---|
| Lọc trạng thái | Xem toàn bộ, phòng trống, đang có khách hoặc bảo trì; màn hình hiển thị thêm số phòng sẵn sàng, có khách, cần dọn. |
| Tạo booking lẻ | Chọn phòng, nhập khách, chọn thuê ngày hoặc thuê giờ, tính báo giá server-side, rồi chọn cọc đúng 50% hoặc 100% trước khi tạo. Giá được snapshot tại booking. |
| Đặt đoàn | Chọn nhiều phòng theo khoảng ngày, kiểm tra trống, tính tổng và cọc 50%/100%; cọc được phân bổ cho từng phòng theo giá snapshot. |
| Check-in | Chỉ nhận phòng từ `booked`; sau đó BookingRoom thành `checked_in`, phòng vật lý thành `occupied`. |
| Gọi dịch vụ | Chọn dịch vụ cho phòng đang ở; hệ thống ghi dòng dịch vụ và trừ tồn kho theo lô nếu dịch vụ được quản lý tồn. |
| Điều chỉnh dịch vụ | Tăng/giảm số lượng trước checkout; giảm số lượng hoàn tồn về đúng lô đã phân bổ. |
| Checkout lẻ | Xem báo giá mới, tùy chọn VAT 8%, áp dụng cọc khi đủ điều kiện, chọn phương thức thanh toán và xác nhận. Server kiểm tra quote còn hiệu lực, trạng thái phòng và chống xử lý lặp. |
| Xác nhận dọn phòng | Sau checkout, đánh dấu phòng đã dọn để trở thành sẵn sàng. |

### 3.3. Timeline đặt phòng

**URL:** `/<hotel_slug>/rooms/timeline-view`
**Dành cho:** người dùng đã đăng nhập.
**Mục đích:** xem lịch phòng theo trục thời gian và thao tác booking chi tiết.

- Xem booking theo từng phòng, theo trạng thái và khoảng thời gian.
- Tạo booking từ vị trí trên timeline; có thuê ngày/giờ, thông tin khách, tiền cọc và báo giá.
- Mở chi tiết để sửa thông tin khách, thời gian, phòng, ghi chú và dịch vụ.
- API cập nhật lịch kéo-thả (`update_timeline`) đã sẵn sàng phía server nhưng UI chưa nối (ghi nhận 14-08 — dự kiến làm cùng đợt room-move); thao tác dời lịch chính thức có bước kiểm tra phòng trống, lý do, tùy chọn giữ giá/áp dụng giá mới và chỉ Admin/Master Admin được gọi.
- Check-in, xem/in billing đoàn, gọi dịch vụ và checkout đoàn từ chi tiết booking.
- Hủy chỉ áp dụng với phòng `booked`; hủy luôn hoàn 0 đ và không còn nhận tỷ lệ hoàn từ client (14-08).
- **Hoàn tiền** là thao tác riêng từ chi tiết hóa đơn: nhập % theo *phần chưa sử dụng* hoặc *toàn bộ hóa đơn* (hoặc số tiền), server hiển thị Đã thu / Giá trị cơ sở / Đã hoàn và chặn cứng không vượt tiền đang giữ; nhập sai sửa bằng **bút toán đảo** — bill khách chỉ hiện dòng hiệu lực, sổ quỹ giữ đủ.

### 3.4. Khách hàng

**URL:** `/<hotel_slug>/customers/customers`
**Dành cho:** người dùng đã đăng nhập.

- Tìm tối đa 100 khách theo tên, số điện thoại hoặc CCCD.
- Thêm, sửa và xóa thông tin tên, điện thoại, email, CCCD, địa chỉ.
- Booking dùng số điện thoại để tìm/tái sử dụng khách hàng đã có.
- Sửa/xóa khách hàng có audit event; dữ liệu được tách theo tenant.

### 3.5. Hóa đơn cũ

**URL:** `/<hotel_slug>/billing/billing`
**Dành cho:** người dùng đã đăng nhập.

- Lọc và xem danh sách booking/phòng đã có dữ liệu billing.
- Mở chi tiết: khách, phòng, khoảng ở, loại thuê, dịch vụ, VAT, tổng tiền, cọc, tiền thanh toán cuối.
- Hiển thị thông tin hủy nếu phòng đã hủy.
- In hóa đơn từ giao diện trình duyệt.

### 3.6. Cấu hình phòng và giá mặc định

**URL:** `/<hotel_slug>/rooms/settings`
**Dành cho:** mọi người dùng đã đăng nhập để xem; Admin/Master Admin để sửa cấu trúc.

- Xem danh sách phòng, loại phòng, trạng thái vận hành, số booking còn hiệu lực và bộ giá mặc định.
- Tìm/lọc theo số phòng, loại phòng và trạng thái.
- Admin/Master Admin có thể thêm phòng, sửa số phòng/loại phòng/bộ giá mặc định và bật/tắt bảo trì.
- Bộ giá mặc định gồm giá qua đêm, giá block đầu, số giờ block đầu và giá giờ tiếp theo.
- Không xóa cứng phòng; không tự dời/hủy booking khi chuyển phòng sang bảo trì.

### 3.7. Giá đặc biệt qua đêm

**URL:** `/<hotel_slug>/prices/admin/price-manager`
**Dành cho:** người dùng đã đăng nhập trong hiện trạng code.

- Tạo, sửa, xóa luật giá theo tên sự kiện, loại phòng, khoảng ngày, thứ trong tuần và độ ưu tiên.
- Khi nhiều luật khớp, luật ưu tiên cao hơn được áp dụng.
- Luật chỉ ghi đè **giá qua đêm**; giá theo giờ vẫn dùng giá mặc định từng phòng.
- Booking mới lấy giá hiệu lực để snapshot; booking cũ không đổi giá theo cấu hình mới.

### 3.8. Danh mục dịch vụ và minibar

**URL:** `/<hotel_slug>/services/services`
**Dành cho:** menu chỉ hiển thị Admin; controller hiện yêu cầu đăng nhập.

- Quản lý tên và đơn giá dịch vụ/minibar.
- Thêm, sửa, xóa dịch vụ; mỗi thao tác được ghi audit.
- Dịch vụ có thể liên kết với vật tư kho để tự trừ tồn khi khách gọi.

### 3.9. Kho hàng theo lô

**URL:** `/<hotel_slug>/warehouse/warehouse`
**Dành cho:** tất cả người dùng xem; Admin thay đổi dữ liệu.

| Thao tác | Công dụng |
|---|---|
| Danh sách vật tư | Xem mã, đơn vị, tồn tổng, ngưỡng cảnh báo, dịch vụ liên kết và trạng thái. |
| Thêm/sửa vật tư | Admin tạo/sửa mã, tên, đơn vị, ngưỡng, giá nhập tham chiếu, liên kết dịch vụ. Vật tư mới có tồn tạo lô nhập đầu. |
| Nhập thêm | Admin tạo một lô mới có số lượng, ngày nhập, hạn dùng tùy chọn và đơn giá. |
| Xem lô/lịch sử | Xem số lượng còn lại, hạn dùng, nguồn nhập và biến động của từng lô. |
| Hủy hàng | Admin giảm đúng lô với lý do: quá hạn, hư hỏng, thất thoát hoặc kiểm kê. |
| Điều chỉnh tồn | Admin tăng/giảm đúng lô, bắt buộc lý do; không cho tồn âm. |

Khi dịch vụ có liên kết vật tư, hệ thống ưu tiên xuất theo FEFO: lô còn hạn gần nhất trước, lô không hạn dùng sau; hàng quá hạn không được dùng.

### 3.10. Chi phí

**URL:** `/<hotel_slug>/expenses/expenses`
**Dành cho:** Admin.

- Thêm, lọc theo ngày/nhóm chi phí và xem tổng chi không gồm khoản void.
- Nhóm hiện có: điện nước, lương, mua sắm, sửa chữa, khác.
- Có thể đồng bộ chi phí sang kho: tạo/cập nhật vật tư, tạo lô nhập; tùy chọn đồng bộ thêm dịch vụ/minibar.
- Khoản chi chưa đồng bộ kho có thể xóa.
- Khoản chi đã đồng bộ kho không xóa trực tiếp; Admin dùng **Hủy ghi nhận chi phí** với lý do. Void loại khoản chi khỏi báo cáo nhưng **không** tự đảo tồn kho, vì hàng có thể đã được sử dụng.

### 3.11. Báo cáo doanh thu

**URL:** `/<hotel_slug>/reports/reports/revenue`
**Dành cho:** Admin.

- Chọn hôm nay, tuần, tháng hoặc khoảng tùy chỉnh.
- Xem doanh thu hóa đơn phòng, thực thu ròng, tổng chi không gồm void và lợi nhuận dự tính.
- Biểu đồ doanh thu/chi phí, tỷ lệ lấp đầy theo ngày, top phòng theo doanh thu và số booking hoàn tất.
- Báo cáo chỉ lấy dữ liệu tenant hiện tại.
- Kỳ báo cáo chọn theo ngày Việt Nam (Asia/Bangkok) và truy vấn theo cửa sổ UTC tương ứng; số booking hoàn tất đếm theo `completed_at` (14-08).

### 3.12. Thu ngân / Sổ quỹ

**URL:** `/<hotel_slug>/cashier/reports/cashier`
**Dành cho:** Admin.

- Đối soát theo hôm nay/tuần/tháng hoặc khoảng ngày.
- Tổng hợp thu vào, hoàn tiền, chi vận hành và dư thực tế.
- Liệt kê giao dịch cọc, tiền phòng, dịch vụ, VAT, thanh toán đoàn, phí hủy và hoàn tiền.
- In phiếu cọc của booking từ danh sách hoặc bằng Booking ID.

### 3.13. Cấu hình và nhân sự

**URL:** `/<hotel_slug>/staff/`
**Dành cho:** Admin.

- Tạo tài khoản Staff hoặc Admin trong tenant hiện tại.
- Đặt lại mật khẩu người dùng khác.
- Xóa tài khoản; không được xóa chính mình và không được xóa Admin cuối cùng của khách sạn.
- Tạo, đổi mật khẩu và xóa đều được ghi audit.

### 3.14. Nhật ký hoạt động

**URL:** `/<hotel_slug>/activity-log/`
**Dành cho:** Admin.

- Theo dõi hành động vận hành: phòng, booking, dịch vụ, kho, giá, chi phí và nhân sự.
- Lọc theo thời gian, nhóm nghiệp vụ, mã hành động hoặc loại đối tượng.
- Mỗi bản ghi lưu người thực hiện, thời gian, dữ liệu trước/sau khi phù hợp.
- Có phân trang, tối đa 100 bản ghi/trang ở API (giao diện mặc định 25).

### 3.15. Master Console

**URL:** `/master/login`, `/master`
**Dành cho:** Master Admin.

- Đăng nhập khu vực toàn hệ thống riêng với tenant.
- Xem tổng số khách sạn, phòng, phòng đang có khách và booking tạo hôm nay.
- Tạo khách sạn mới kèm tài khoản Admin đầu tiên.
- Bật/tắt hoạt động khách sạn.
- Vào màn hình vận hành của một tenant ở chế độ hỗ trợ.

## 4. Luồng vận hành đề xuất cho nhân viên

### 4.1. Một booking lẻ tiêu chuẩn

1. Vào **Sơ đồ phòng**, lọc phòng sẵn sàng.
2. Chọn phòng, nhập/tìm khách, chọn thuê ngày hoặc thuê giờ.
3. Tính báo giá, chọn cọc 50% hoặc 100%, tạo booking.
4. Đến giờ nhận: xác nhận **check-in**.
5. Trong thời gian ở: gọi/cập nhật dịch vụ; tồn kho được giảm nếu có quản lý kho.
6. Khi trả: mở checkout, kiểm tra báo giá/VAT/dịch vụ/cọc, chọn phương thức thanh toán và xác nhận.
7. Dọn phòng, rồi đánh dấu **đã dọn** để đưa phòng về sẵn sàng.

### 4.2. Booking đoàn

1. Từ Sơ đồ phòng hoặc Timeline, tìm/chọn nhiều phòng cùng kỳ ở.
2. Tạo một Booking chứa nhiều BookingRoom, ghi nhận cọc đoàn và phân bổ cọc theo từng phòng.
3. Check-in/checkout theo từng phòng hoặc dùng checkout đoàn cho các phòng đang ở.
4. Hệ thống tổng hợp trạng thái Booking cha từ trạng thái từng phòng.

### 4.3. Nhập hàng và bán minibar

1. Admin tạo dịch vụ/minibar nếu chưa có.
2. Tạo vật tư kho và liên kết với dịch vụ, hoặc tạo chi phí rồi đồng bộ chi phí sang kho/dịch vụ.
3. Khi khách gọi dịch vụ, hệ thống kiểm tra đủ tồn còn dùng được, trừ theo lô và lưu phân bổ.
4. Khi giảm/hủy dịch vụ trước checkout, hệ thống hoàn vào đúng lô đã xuất.
5. Hàng quá hạn/hỏng/thất thoát chỉ giảm khi Admin tạo phiếu hủy hàng; không tự động giảm số thực tế.

### 4.4. Đối soát cuối ngày

1. Admin xem **Sổ quỹ** để so sánh thu, hoàn và chi theo kỳ.
2. Xem **Chi phí** để xác nhận các khoản void đã bị loại khỏi tổng.
3. Xem **Báo cáo doanh thu** để theo dõi doanh thu phòng, lấp đầy và top phòng.
4. Khi cần truy nguyên thao tác, lọc **Nhật ký hoạt động** theo booking/phòng/người dùng.

## 5. Các điểm cần chỉnh theo hiện trạng mã nguồn

| Ưu tiên | Phát hiện | Tác động/nghiệp vụ cần chốt |
|---|---|---|
| ~~P0~~ ĐÃ XỬ LÝ 14-08 | ~~Checkout đoàn tự tạo refund; hủy phòng cho client gửi `refund_percent`~~ | Đã thay bằng luồng hoàn tiền nhập trực tiếp có lưới an toàn (form Hoàn tiền, trần cứng server-side, bút toán đảo). Xem [spec remediation](superpowers/specs/2026-08-14-financial-time-and-inventory-remediation-design.md). |
| ~~P0~~ ĐÃ XỬ LÝ 14-08 | ~~API sửa dịch vụ/luật giá chỉ cần đăng nhập~~ | Đã chốt: Staff XEM được giá/dịch vụ (tư vấn khách) nhưng mọi thao tác thêm/sửa/xóa là Admin-only, chặn server-side (`admin_required`, 403 JSON). |
| ~~P1~~ ĐÃ XỬ LÝ 14-08 | ~~Nút add-room gọi route không tồn tại~~ | Endpoint `/api/bookings/add-room` đã triển khai thật (chống trùng lịch, snapshot giá, audit); nút Timeline hoạt động. |
| ~~P1~~ ĐÃ CHỐT 14-08 | ~~Ma trận quyền booking chưa thống nhất~~ | Nguyên tắc đã chốt: **vận hành quầy = Staff** (tạo/sửa booking, kéo-thả, hủy có lý do, hoàn tiền), **cấu hình = Admin** (giá, dịch vụ, cấu trúc phòng); dời lịch giữ Admin/Master như thiết kế. API hết phiên trả 401 JSON. |
| ~~P1~~ ĐÃ XỬ LÝ 14-08 | ~~Báo cáo dùng `updated_at` + trộn UTC/giờ ứng dụng~~ | Đã có `Booking.completed_at` + time service (UTC + ngày nghiệp vụ Asia/Bangkok); báo cáo/sổ quỹ lọc theo cửa sổ UTC của kỳ Bangkok. |
| ~~P2~~ ĐÃ XỬ LÝ 14-08 | ~~Test FEFO đỏ theo lịch~~ | `deduct/validate_inventory` nhận `as_of_date` inject được; thiếu tồn không ghi partial; regression lô hết hạn/không hạn bổ sung. |

## 6. Ngoài phạm vi hiện tại

- Chưa có luồng hoàn tiền bất khả kháng được phê duyệt và truy vết riêng; hiện mới có logic hủy/hoàn cũ cần thay thế.
- Chưa có lịch bảo trì theo khoảng thời gian, tự dời khách, sơ đồ tầng, tiện nghi, sức chứa hoặc nhập phòng hàng loạt.
- Chưa có danh mục `RoomType` riêng; loại phòng là chuỗi trên từng phòng.
- Chưa có cơ chế công nợ khách hàng trong checkout.
- Không có khu vực kho tổng toàn hệ thống; kho luôn thuộc từng tenant.

## 7. Nguồn kiểm kê

Tài liệu được tổng hợp trực tiếp từ các blueprint đã đăng ký trong `app.py`, URL map Flask, controller, template và JavaScript hiện có: lễ tân/phòng/booking, khách hàng, dịch vụ, kho, chi phí, billing, báo cáo, nhân sự, audit và Master Console. Mọi thay đổi nghiệp vụ tiếp theo nên cập nhật lại tài liệu này cùng test TDD tương ứng.
