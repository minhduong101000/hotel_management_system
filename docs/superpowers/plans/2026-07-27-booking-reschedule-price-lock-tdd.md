# Plan TDD: Engine tính tiền, snapshot giá và dời lịch giữ giá

## Nguyên tắc thực hiện

- Mỗi bước chức năng phải bắt đầu bằng test thất bại.
- Triển khai tối thiểu để test qua, sau đó refactor.
- Không thay đổi hành vi ngoài spec đã duyệt.
- Sau mỗi lát cắt độc lập: chạy test liên quan, `git diff --check`, commit tiếng Anh riêng.
- Mọi thay đổi UI phải kiểm tra desktop bằng `bb-browser` trước khi báo hoàn tất.

## Giai đoạn 0 — Khảo sát và cố định hành vi hiện tại

### 0.1 Lập test regression cho engine hiện có

**Test đỏ cần viết**

- Thuê giờ trong block đầu và trong 10 phút ân hạn.
- Thuê giờ vượt block đầu.
- Thuê giờ vượt giá đêm và chuyển sang tính đêm.
- Check-in sớm/check-out muộn ở các mốc 1h, 4h, 6h.
- Booking nhiều ngày không sinh phụ thu hàng trăm giờ.

**Triển khai**

- Chỉ sửa test fixture hoặc bug đã chứng minh bằng test.
- Không thay đổi công thức trước khi regression suite bảo vệ được hành vi cần giữ.

**Kiểm tra**

```powershell
& 'C:\tmp\hotel-management-tdd-venv\Scripts\python.exe' -m pytest -q tests/test_pricing_*.py
```

## Giai đoạn 1 — Chuẩn hóa rule giá theo ngày

### 1.1 Rule ngày trống

**Test đỏ**

- Rule có cả `start_date` và `end_date` trống áp dụng mọi ngày.
- Rule chỉ có `start_date` áp dụng từ ngày đó trở đi.
- Rule chỉ có `end_date` áp dụng đến hết ngày đó.

**Triển khai tối thiểu**

- Thay điều kiện query cứng bằng điều kiện nullable đúng nghĩa.

### 1.2 Validation rule

**Test đỏ**

- Không lưu khi `end_date < start_date`.
- Không lưu khi giá qua đêm `<= 0`.
- Không lưu rule chồng khoảng ngày, cùng loại phòng và cùng priority.
- Rule priority cao hơn được chọn khi overlap được nghiệp vụ cho phép.

**Triển khai tối thiểu**

- Validation ở controller/service trước khi commit.
- Trả lỗi API rõ ràng để UI hiển thị cạnh field phù hợp.

### 1.3 Dọn UI rule giá

**Test đỏ**

- Markup modal rule không còn trường giá giờ đặc biệt.
- UI hiển thị rõ “Rule hiện chỉ áp dụng giá qua đêm”.

**Triển khai**

- Bỏ field giá giờ không được model/service sử dụng.
- Kiểm tra bằng `bb-browser` ở desktop.

## Giai đoạn 2 — Tính giá từng đêm

### 2.1 Tách helper tạo danh sách đêm

**Test đỏ**

- Khoảng 02/09 14:00 → 03/09 12:00 tạo một `business_date` là 02/09.
- Khoảng 30/04 14:00 → 02/05 12:00 tạo các đêm 30/04, 01/05.
- Một kỳ dưới một đêm vẫn có tối thiểu một đơn vị giá khi là thuê theo ngày.

**Triển khai tối thiểu**

- Tạo helper thuần, không truy cập DB, trả danh sách `business_date`.

### 2.2 Tính breakdown giá từng đêm

**Test đỏ**

- Giá lễ 30/04 và giá thường 01/05 được cộng đúng theo từng đêm.
- Rule theo thứ chỉ áp dụng đúng business date.
- Breakdown có ngày, tên rule/giá niêm yết, số tiền từng đêm và tổng.

**Triển khai tối thiểu**

- Tạo helper lấy giá cho từng `business_date`.
- Thay phép nhân `nights × một mức giá` bằng tổng breakdown từng đêm.

### 2.3 Bảo toàn phụ thu

**Test đỏ**

- Check-in sớm tính theo giá đêm đầu.
- Checkout muộn tính theo giá đêm cuối.
- Booking qua giai đoạn giá khác nhau không nhân phụ thu theo từng đêm.
- Thuê giờ ngắn không bị áp quy tắc phụ thu qua đêm.

**Triển khai tối thiểu**

- Đưa giá đêm đầu/cuối từ breakdown vào helper phụ thu.

## Giai đoạn 3 — Lưu snapshot giá

### 3.1 Migration và model snapshot

**Test đỏ**

- Tạo booking theo ngày sinh snapshot cho từng đêm.
- Snapshot chứa business date, giá, source và rule name.
- Tạo booking thuê giờ sinh snapshot cấu hình block giờ.

**Triển khai tối thiểu**

- Thêm model/table snapshot và migration Alembic.
- Tạo service tạo snapshot trong transaction tạo booking đơn và booking đoàn.

### 3.2 Checkout dùng snapshot

**Test đỏ**

- Sau khi tạo booking, sửa base price/rule giá rồi checkout vẫn dùng giá snapshot.
- Dịch vụ, VAT, cọc và phụ thu vẫn được cộng/trừ đúng.
- Booking dữ liệu cũ chưa có snapshot có fallback an toàn và được đánh dấu rõ.

**Triển khai tối thiểu**

- Checkout đơn/đoàn ưu tiên snapshot, chỉ fallback engine cũ khi cần.

## Giai đoạn 4 — Dời lịch giữ giá

### 4.1 Model và migration lịch sử dời lịch

**Test đỏ**

- Lưu lịch cũ/lịch mới, phòng cũ/phòng mới, lý do, actor, tổng snapshot.

**Triển khai tối thiểu**

- Tạo `BookingReschedule` và migration.

### 4.2 API kiểm tra lịch mới

**Test đỏ**

- Chấp nhận phòng trống trong tenant đúng.
- Từ chối phòng bận, phòng bảo trì, thời gian đảo ngược và tenant khác.
- Trả giá snapshot giữ nguyên và giá hiện hành tham khảo.

**Triển khai tối thiểu**

- Endpoint availability dùng kiểm tra overlap hiện có, loại trừ booking room đang dời.

### 4.3 API xác nhận dời lịch

**Test đỏ**

- Dời `booked` thành công, giữ nguyên snapshot.
- Từ chối booking `checked_in`, `checked_out`, `cancelled`.
- Từ chối lý do trống.
- Lock phòng/booking để tránh dời đồng thời.
- Ghi `BookingReschedule` và audit `reschedule_booking_keep_price` đúng before/after.

**Triển khai tối thiểu**

- Xử lý trong một transaction.
- Không gọi logic tính lại snapshot.

## Giai đoạn 5 — UI/UX dời lịch

### 5.0 Redesign Timeline với `vis-timeline`

**Test đỏ**

- Markup có toolbar gồm điều hướng ngày, chế độ xem và filter trạng thái.
- Markup có vùng loading/skeleton và empty state.
- Booking item chỉ chứa thông tin ngắn gọn theo spec.
- Click booking mở quick panel có action phù hợp trạng thái.

**Triển khai tối thiểu**

- Giữ `vis-timeline`; không thêm thư viện trả phí hoặc rewrite React.
- Refactor toolbar/legend/cột phòng/booking template theo token design system hiện có.
- Dùng Font Awesome nhất quán, label rõ ràng và focus state.

**Kiểm tra bắt buộc**

- Dùng `bb-browser` ở desktop để kiểm tra toolbar, timeline, quick panel, loading state và không có JavaScript error.
- Chụp/quan sát trạng thái có booking, không có booking, booking chờ nhận và booking quá giờ.

### 5.1 Modal và điểm vào

**Test đỏ**

- Timeline/chi tiết booking có nút “Dời lịch”.
- Modal có lịch cũ, lịch mới, chọn phòng, lý do bắt buộc, badge “Giữ giá đã chốt”.
- Không có nút tự áp giá hiện hành.

**Triển khai tối thiểu**

- Kéo thả Timeline chỉ mở modal; không tự lưu thay đổi.

### 5.2 Kiểm tra phòng và xác nhận

**Test đỏ**

- Nút xác nhận bị khóa trước khi kiểm tra lịch hợp lệ.
- Hiển thị giá hiện hành chỉ để tham khảo và chênh lệch rõ ràng.
- Thành công hiển thị thông báo giữ giá.
- Lỗi API hiển thị gần trường liên quan.

**Kiểm tra trực quan bắt buộc**

- `bb-browser` ở desktop: mở modal, lịch trống, lịch trùng, dời thành công.
- Kiểm tra console không có JavaScript error.

## Giai đoạn 6 — Hóa đơn, lịch sử và audit

### 6.1 Chi tiết hóa đơn

**Test đỏ**

- Hóa đơn hiển thị breakdown từng đêm snapshot.
- Hóa đơn sau dời hiển thị lịch gốc, lịch hiện tại, giá giữ nguyên.
- Phụ thu hiển thị riêng với tỷ lệ và số tiền.

### 6.2 Nhật ký hoạt động

**Test đỏ**

- Event dời lịch hiển thị nhãn tiếng Việt, actor, lịch cũ/mới và lý do.

## Giai đoạn 7 — Kiểm tra cuối

- Chạy test mới theo từng nhóm.
- Chạy toàn bộ test suite.
- Chạy migration local bằng `flask --app app db upgrade`.
- Kiểm tra UI bằng `bb-browser` cho Timeline, modal dời lịch, preview checkout, checkout và hóa đơn cũ.
- Xác nhận `git status` chỉ chứa các thay đổi thuộc scope.

## Điểm dừng cần xác nhận

Trước Giai đoạn 4 cần xác nhận:

1. Admin có được đổi phòng đồng thời khi dời lịch không?
2. Có giới hạn số lần dời lịch không?
3. Tiền cọc có giữ nguyên hoàn toàn hay cần quy trình điều chỉnh riêng?
4. Có cần luồng riêng “dời lịch và áp dụng giá mới” trong tương lai không?
