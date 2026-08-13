# Spec: Dời lịch booking, giữ giá đã chốt

## 1. Mục tiêu

Cho phép Admin khách sạn dời lịch của booking chưa check-in sang ngày/phòng còn trống mà vẫn giữ nguyên giá đã xác nhận tại thời điểm đặt. Luồng này phục vụ trường hợp khách không thể đến đúng lịch và khách sạn đồng ý hỗ trợ đổi ngày.

Mục tiêu chính là bảo toàn cam kết giá với khách, đồng thời vẫn đảm bảo không trùng lịch phòng và có đầy đủ lịch sử truy vết.

## 2. Phạm vi

### Bao gồm

- Dời lịch booking/phòng ở trạng thái `booked`.
- Có thể đổi ngày check-in, check-out và phòng nếu phòng đích còn trống.
- Giữ nguyên snapshot tiền phòng đã chốt lúc tạo booking.
- Hiển thị giá hiện hành của lịch mới chỉ để tham khảo.
- Bắt buộc nhập lý do dời lịch.
- Ghi audit log lịch cũ/lịch mới, người thao tác, lý do và giá được giữ.
- Hiển thị lịch sử dời lịch trong chi tiết booking/hóa đơn.

### Không bao gồm

- Dời booking đã check-in, checkout hoặc hủy.
- Tự động áp dụng giá mới khi dời lịch.
- Cho Staff thao tác dời lịch nếu chưa có quyết định phân quyền mới.
- Thay đổi chính sách hoàn/hủy cọc.

## 3. Quy tắc nghiệp vụ đã chốt

1. Giá booking được chốt tại lúc tạo booking.
2. Dời lịch theo thỏa thuận giữ nguyên giá đã chốt, dù lịch mới rơi vào ngày lễ/cao điểm hoặc giá niêm yết đã thay đổi.
3. Giá hiện hành của lịch mới chỉ dùng để thông tin cho lễ tân, không dùng để tính hóa đơn.
4. Tiền phòng phải được lưu theo từng đêm; mỗi đêm được gắn với `business_date` là ngày bắt đầu đêm đó.
5. Rule ngày 02/09 áp dụng cho đêm từ giờ check-in chuẩn ngày 02/09 đến giờ checkout chuẩn ngày 03/09.
6. Phụ thu check-in sớm/checkout muộn phát sinh sau này tính dựa trên giá snapshot của đêm liên quan, không dựa trên rule giá mới.
7. Lịch mới phải không trùng booking active khác và không thuộc phòng bảo trì.
8. Dời lịch bắt buộc có lý do; không được dùng thao tác kéo-thả để tự lưu ngay.

## 4. Dữ liệu cần bổ sung

### 4.1 Snapshot giá booking

Tạo dữ liệu snapshot cho từng `BookingRoom`, tối thiểu gồm:

- `booking_room_id`
- `business_date`
- `room_price`
- `rule_name` (có thể rỗng nếu giá niêm yết)
- `source` (`base` hoặc `price_rule`)
- `created_at`

Snapshot được tạo khi booking được xác nhận. Tổng snapshot là nguồn dữ liệu tiền phòng khi checkout, thay vì tính lại rule hiện hành.

### 4.2 Lịch sử dời lịch

Tạo bản ghi mỗi lần dời lịch, gồm:

- `booking_room_id`
- Phòng cũ / phòng mới
- Check-in cũ / check-in mới
- Check-out cũ / check-out mới
- Lý do
- Người thao tác
- Tổng giá snapshot được giữ
- Thời điểm dời

Có thể triển khai bằng bảng riêng `booking_reschedules`; audit event vẫn cần tồn tại để có timeline hoạt động chung.

## 5. Tính giá theo từng đêm

### Quy ước

- Một đêm có `business_date` bằng ngày check-in của đêm đó.
- Giá đêm 02/09 lấy rule hiệu lực ngày 02/09, không lấy rule ngày 03/09.
- Booking 30/04–02/05 gồm hai đêm: 30/04 và 01/05; mỗi đêm tính rule riêng.

### Công thức checkout

```text
Tổng giá snapshot các đêm
+ phụ thu sớm/muộn thực tế
+ dịch vụ
+ VAT (nếu chọn)
- cọc đã thu
= số tiền cần thu hoặc hoàn
```

## 5.1 Engine tính tiền phòng và checkout

### Mục tiêu

Engine phải tạo được breakdown có thể đối soát cho từng hóa đơn. Không được tính lại toàn bộ tiền phòng theo rule hiện hành nếu booking đã có snapshot giá.

### Thành phần hóa đơn

```text
Tiền phòng snapshot theo từng đêm / tiền thuê giờ
+ phụ thu check-in sớm / checkout muộn
+ dịch vụ đã dùng
+ VAT (nếu người dùng chọn áp dụng)
= tổng hóa đơn
- cọc đã thu
= số tiền còn thu
  hoặc số tiền cần hoàn
```

### A. Thuê theo ngày / qua đêm

1. Mỗi đêm được tính độc lập theo `business_date`.
2. `business_date` là ngày bắt đầu của đêm, theo giờ check-in chuẩn hiện tại là 14:00.
3. Giá của từng đêm lấy rule hiệu lực đúng ngày đó khi booking được tạo, sau đó được đóng băng vào snapshot.
4. Checkout dùng tổng snapshot tiền phòng, không dùng rule giá đã sửa sau này.
5. Khi Admin chủ động đổi lịch, snapshot vẫn giữ nguyên. Không sinh lại giá lễ/cao điểm của lịch mới.

Ví dụ:

```text
30/04 14:00 → 02/05 12:00
Đêm 30/04: Rule lễ 1.000.000đ
Đêm 01/05: Giá thường 500.000đ
Tiền phòng snapshot: 1.500.000đ
```

### B. Thuê theo giờ

1. Dùng giá block đầu, số giờ block đầu và giá mỗi giờ tiếp theo từ snapshot cấu hình phòng lúc check-in/booking.
2. Có 10 phút ân hạn theo logic hiện có.
3. Nếu tiền thuê giờ vượt giá qua đêm snapshot, tự chuyển sang cách tính qua đêm.
4. Rule giá đặc biệt trong giai đoạn hiện chỉ áp dụng giá qua đêm; không áp dụng giá giờ trừ khi có quyết định nghiệp vụ mới.

### C. Check-in sớm / checkout muộn

Áp dụng cho booking theo ngày/qua đêm; thuê giờ ngắn tiếp tục tính theo block giờ.

| Tổng thời gian sớm/muộn | Phụ thu |
|---|---:|
| Không quá 1 giờ | 0% |
| Trên 1 đến 4 giờ | 30% giá đêm snapshot |
| Trên 4 đến 6 giờ | 50% giá đêm snapshot |
| Trên 6 giờ | 100% giá đêm snapshot |

Quy tắc:

- Chỉ tính phần sớm ở đầu kỳ và phần muộn ở cuối kỳ.
- Không cộng phụ thu lặp lại cho các ngày ở giữa.
- Phụ thu check-in sớm dùng giá snapshot của đêm đầu.
- Phụ thu checkout muộn dùng giá snapshot của đêm cuối.
- Breakdown phải nêu số giờ, tỷ lệ và số tiền phụ thu.

### D. Dịch vụ, kho và VAT

- Mỗi dịch vụ tính `số lượng × đơn giá tại thời điểm gọi`; đơn giá phải được lưu trong `BookingService.price_at_booking`.
- Tăng số lượng dịch vụ trừ kho; giảm/xóa dòng dịch vụ hoàn kho theo logic hiện có.
- VAT chỉ cộng khi người dùng chọn trong checkout; breakdown phải hiển thị rõ mức VAT và số tiền.

### E. Cọc, hủy và hoàn tiền

- Cọc là khoản đã thu, tách khỏi tổng tiền phòng/dịch vụ.
- Checkout tính số còn phải thu từ tổng hóa đơn trừ cọc và các payment trước đó.
- Hủy phòng dùng chính sách phần trăm hoàn hiện có; bắt buộc lý do.
- Hóa đơn hủy phải hiển thị cọc gốc, tỷ lệ hoàn, phí giữ lại và số hoàn thực tế.
- Sổ quỹ ghi nhận cọc/hoàn là dòng tiền thực tế; hóa đơn thể hiện chúng là cấu phần của booking.

### F. Snapshot cần có

Ngoài snapshot từng đêm, lưu snapshot cấu hình thuê giờ tối thiểu:

- Giá block đầu.
- Số giờ block đầu.
- Giá giờ tiếp theo.
- Giá qua đêm tham chiếu.

Snapshot này đảm bảo Admin đổi giá phòng sau khi khách check-in không làm thay đổi hóa đơn đang mở.

## 5.2 Validation rule giá

- Rule có ngày trống phải thực sự áp dụng không giới hạn thời gian.
- Ngày kết thúc không được nhỏ hơn ngày bắt đầu.
- Giá rule phải lớn hơn 0.
- Không cho hai rule cùng loại phòng, cùng priority chồng thời gian nếu chưa có quy tắc phân giải rõ.
- Rule priority cao hơn thắng; cần có thứ tự phụ ổn định nếu nghiệp vụ cho phép overlap.
- UI rule đặc biệt chỉ hiển thị giá qua đêm cho đến khi có quyết định áp dụng giá giờ theo giai đoạn.

## 6. Thiết kế UI/UX

### 6.0 Timeline miễn phí, giữ `vis-timeline`

Không thay thư viện Timeline. Project tiếp tục dùng `vis-timeline` để tránh chi phí license và refactor sang React. Phần cần làm là redesign lớp giao diện và hành vi xung quanh timeline.

- Toolbar một hàng: điều hướng ngày, ngày đang xem, `Ngày / 3 ngày / Tuần`, filter và nút tạo booking.
- Legend chỉ giữ trạng thái vận hành chính: Đặt trước, Chờ nhận, Đang ở, Quá giờ trả, Bảo trì.
- Cột phòng hiển thị số phòng, loại phòng, giá cơ bản và trạng thái ngắn gọn.
- Thanh booking chỉ hiển thị tên khách, thời gian và trạng thái; không nhồi toàn bộ thông tin.
- Click booking mở quick panel bên phải trước khi mở modal nghiệp vụ.
- Kéo-thả/resize không tự lưu: phải mở modal xác nhận dời lịch giữ giá.
- Có skeleton/loading state khi timeline thay đổi ngày hoặc filter.
- Dùng icon Font Awesome đang có; không dùng emoji làm icon cấu trúc.

Mục tiêu visual: dashboard nội bộ desktop/tablet, mật độ cao nhưng không dày chữ, trạng thái không chỉ dựa vào màu và tất cả action có focus/feedback rõ ràng.

### 6.1 Điểm vào

Trong menu nhanh của thẻ booking trên Timeline và chi tiết booking:

- Xem chi tiết
- Dời lịch
- Hủy phòng

Không tự lưu thao tác kéo-thả. Nếu vẫn giữ kéo-thả cho tiện thao tác, nó chỉ mở modal Dời lịch với dữ liệu mới đã chọn.

### 6.2 Modal “Dời lịch – giữ giá đã chốt”

Hiển thị ba khu vực:

1. **Thông tin booking**: mã booking, khách, phòng, trạng thái.
2. **Lịch cũ / lịch mới**: ngày giờ, phòng mới, kiểm tra phòng trống.
3. **Trạng thái giá**:
   - Badge `Giữ giá đã chốt`.
   - Tổng giá snapshot.
   - Giá hiện hành lịch mới để tham khảo.
   - Chênh lệch, nếu có.

Trường bắt buộc: lý do dời lịch.

Nút:

- Hủy.
- Kiểm tra phòng trống.
- Xác nhận dời lịch (chỉ bật sau khi lịch hợp lệ).

### 6.3 Hiển thị sau khi dời

Trong chi tiết booking/hóa đơn:

- Giá đã chốt.
- Lịch gốc.
- Lịch hiện tại.
- Danh sách lần dời, lý do, người thao tác và thời gian.

Thông báo thành công:

`Đã dời lịch sang [ngày mới]. Giá đã chốt [số tiền] được giữ nguyên.`

### 6.4 Tiêu chí UI Timeline

- Không phát sinh scroll ngang ngoài vùng Timeline cần thiết.
- Toolbar và quick panel không che nội dung Timeline.
- Quick panel có action theo trạng thái booking, không hiển thị nút vô hiệu không rõ lý do.
- Hiển thị loading/error/empty state rõ ràng.
- Kiểm tra trực quan bằng `bb-browser` ở desktop sau implementation.

## 7. API dự kiến

### Kiểm tra lịch mới

`POST /<hotel_slug>/timeline/api/bookings/reschedule/availability`

Input: `booking_room_id`, `room_id`, `check_in`, `check_out`.

Output: phòng có thể dời hay không, lý do từ chối, giá snapshot được giữ, giá hiện hành tham khảo.

### Xác nhận dời lịch

`POST /<hotel_slug>/timeline/api/bookings/reschedule`

Input: `booking_room_id`, `room_id`, `check_in`, `check_out`, `reason`.

Xử lý trong một transaction:

1. Lock booking room và phòng đích.
2. Kiểm tra tenant, trạng thái booking, lý do, phòng bảo trì và trùng lịch.
3. Lưu lịch sử dời lịch.
4. Cập nhật lịch/phòng hiện tại.
5. Giữ nguyên snapshot giá.
6. Ghi audit `reschedule_booking_keep_price`.

## 8. Audit log

Action: `reschedule_booking_keep_price`.

`before_data` gồm phòng/lịch cũ và tổng giá snapshot.

`after_data` gồm phòng/lịch mới, lý do, tổng giá snapshot và giá hiện hành tham khảo.

Không lưu mật khẩu, dữ liệu nhạy cảm không cần thiết hoặc giá mới như một khoản phải thu.

## 9. TDD và tiêu chí nghiệm thu

Viết test đỏ trước từng thay đổi. Tối thiểu cần có:

- Booking đi qua nhiều đêm/lễ tính đúng giá từng đêm.
- Rule ngày 02/09 áp dụng đúng đêm 02/09 → 03/09.
- Dời lịch từ ngày thường sang ngày lễ vẫn giữ snapshot giá ban đầu.
- Dời lịch sang phòng bận/bảo trì bị từ chối.
- Dời booking checked-in, checked-out hoặc cancelled bị từ chối.
- Lý do trống bị từ chối.
- Tenant khác không thể dời booking.
- Audit chứa lịch cũ, lịch mới, lý do và actor.
- UI modal có badge giữ giá, cảnh báo chênh lệch và không có nút tự tính lại giá.

Sau implementation phải chạy test phù hợp, toàn bộ test hồi quy và kiểm tra desktop bằng `bb-browser`.

## 10. Điểm cần xác nhận trước implementation

## 11. Quyết định đã chốt sau review

- Admin được đổi sang phòng khác khi dời lịch.
- Không giới hạn số lần dời lịch.
- Tiền cọc giữ nguyên khi dời lịch.
- Admin chọn rõ `Giữ giá đã chốt` hoặc `Áp dụng giá mới`; mặc định giữ giá. Nếu áp dụng giá mới, hệ thống tạo snapshot mới và audit lựa chọn này.

- Admin có được phép chủ động đổi phòng đồng thời với dời lịch không, hay chỉ đổi ngày?
- Có giới hạn số lần dời lịch không?
- Có cần giữ tiền cọc nguyên trạng hay cho phép điều chỉnh cọc thủ công sau khi dời lịch?
- Có cần cho phép một luồng riêng “dời lịch và áp dụng giá mới” sau này không?
