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

## 2. Quyền hiện tại

| Vai trò | Khu vực/chức năng chính |
|---|---|
| Staff | Lễ tân: Sơ đồ phòng, Timeline, khách hàng, hóa đơn; xem cấu hình phòng/giá, xem kho. Có thể thực hiện booking, check-in, gọi dịch vụ và checkout qua các luồng lễ tân. |
| Admin khách sạn | Toàn bộ chức năng Staff, cộng thêm doanh thu, chi phí, sổ quỹ, nhật ký, nhân sự; tạo/sửa phòng, bảo trì phòng, thay đổi kho. |
| Master Admin | Đăng nhập Master Console, tạo tenant và Admin đầu tiên, bật/tắt tenant, vào chế độ hỗ trợ tenant. |

Lưu ý: bảng trên là **ý nghĩa vận hành mong muốn và menu đang hiển thị**. Một số API hiện chỉ kiểm tra đăng nhập mà chưa kiểm tra đúng vai trò; các lệch này được liệt kê tại [mục 5](#5-các-điểm-cần-chỉnh-theo-hiện-trạng-mã-nguồn).

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
- Kéo/thả hoặc kéo giãn booking có API cập nhật lịch; thao tác dời lịch chính thức có bước kiểm tra phòng trống, lý do, tùy chọn giữ giá/áp dụng giá mới và chỉ Admin/Master Admin được gọi.
- Check-in, xem/in billing đoàn, gọi dịch vụ và checkout đoàn từ chi tiết booking.
- Hủy chỉ áp dụng với phòng `booked`; UI/API cũ hiện có tỷ lệ hoàn và cờ bất khả kháng, nhưng nghiệp vụ này sẽ được thay thế theo [spec xử lý bất khả kháng](superpowers/specs/2026-08-14-financial-time-and-inventory-remediation-design.md).

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
- Quy ước thời gian của báo cáo hiện cần chuẩn hóa theo UTC/Bangkok; hạng mục này nằm trong [spec remediation](superpowers/specs/2026-08-14-financial-time-and-inventory-remediation-design.md).

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
| P0 | Checkout đoàn hiện tự tạo refund khi cọc lớn hơn hóa đơn (`balance < 0`). Hủy phòng cũ cho client gửi trực tiếp `is_force_majeure` và `refund_percent`. | Không phù hợp chính sách đã thống nhất. Chỉ hoàn tiền qua case bất khả kháng được phê duyệt, có thể xảy ra sau khi khách đã ở một phần kỳ. Xem [spec remediation](superpowers/specs/2026-08-14-financial-time-and-inventory-remediation-design.md). |
| P0 | API tạo/sửa/xóa **dịch vụ** và tạo/sửa/xóa **luật giá** hiện chỉ yêu cầu đăng nhập, trong khi menu Dịch vụ bị ẩn với Staff. | Cần quyết định Staff có quyền sửa giá/dịch vụ hay không; nếu không, phải thêm kiểm tra server-side, không chỉ ẩn menu. |
| P1 | Timeline có nút/JS gọi `/api/bookings/add-room`, nhưng route này không xuất hiện trong URL map Flask. | Luồng thêm một phòng vào booking đã có hiện chưa hoạt động; cần hoặc triển khai endpoint + TDD, hoặc bỏ nút để tránh thao tác 404. |
| P1 | Cập nhật trực tiếp booking/timeline và hủy hiện chỉ kiểm tra đăng nhập, trong khi dời lịch có kiểm tra Admin/Master Admin riêng. | Cần thống nhất ma trận quyền cho sửa booking, kéo-thả timeline và hủy phòng. |
| P1 | Báo cáo dùng `Booking.updated_at` làm mốc completed và đang trộn mốc UTC từ database với giờ Bangkok của ứng dụng. | Có thể sai số booking hoàn tất quanh biên ngày. Spec remediation đề xuất `completed_at` và kỳ báo cáo chuyển sang UTC. |
| P2 | Test FEFO dùng hạn đã qua so với ngày chạy nên đỏ không ổn định. | Không đổi quy tắc FEFO; cần inject/fix ngày nghiệp vụ trong test để kiểm thử lô còn hạn/quá hạn xác định. |

## 6. Ngoài phạm vi hiện tại

- Chưa có luồng hoàn tiền bất khả kháng được phê duyệt và truy vết riêng; hiện mới có logic hủy/hoàn cũ cần thay thế.
- Chưa có lịch bảo trì theo khoảng thời gian, tự dời khách, sơ đồ tầng, tiện nghi, sức chứa hoặc nhập phòng hàng loạt.
- Chưa có danh mục `RoomType` riêng; loại phòng là chuỗi trên từng phòng.
- Chưa có cơ chế công nợ khách hàng trong checkout.
- Không có khu vực kho tổng toàn hệ thống; kho luôn thuộc từng tenant.

## 7. Nguồn kiểm kê

Tài liệu được tổng hợp trực tiếp từ các blueprint đã đăng ký trong `app.py`, URL map Flask, controller, template và JavaScript hiện có: lễ tân/phòng/booking, khách hàng, dịch vụ, kho, chi phí, billing, báo cáo, nhân sự, audit và Master Console. Mọi thay đổi nghiệp vụ tiếp theo nên cập nhật lại tài liệu này cùng test TDD tương ứng.
