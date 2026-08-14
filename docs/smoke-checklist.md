# Checklist Smoke — Baseline v0-legacy (14/08/2026)

Định nghĩa đo được cho "không hỏng" trong suốt refactor P1–P5. Sau mỗi giai
đoạn, đi lại checklist: mọi mục ✅ ở baseline phải giữ nguyên ✅. Mục ❌ ghi
chú lý do. KHÔNG sửa cột "Kết quả baseline" sau khi đã chốt.

Môi trường baseline: venv Python 3.12 + MySQL 8 (container
`hotel-mysql-legacy`) + `venv/bin/python app.py` → http://127.0.0.1:5000
Baseline đi ngày 14/08/2026 qua HTTP (curl + cookie session), phòng 101/201,
dịch vụ id 1–2, khách 0901234567.

## Chuẩn bị dữ liệu (một lần, sau /init-db)

1. `GET /init-db` — tạo bảng + tài khoản admin (`admin`, mật khẩu seed trong
   handler `/init-db` của `app.py`).
2. Đăng nhập admin, tạo: ≥2 phòng (1 Standard, 1 Deluxe, có giá đêm + giá
   giờ), ≥2 dịch vụ (VD: Nước suối 10.000đ, Giặt ủi 50.000đ), ≥1 khách hàng.
   Ghi chú baseline: không có màn hình/API tạo phòng — phòng thêm bằng SQL
   trực tiếp vào bảng `rooms`.

## Các mục phải chạy được

| #  | Thao tác | Mong đợi | Kết quả baseline |
|----|----------|----------|------------------|
| 1  | `GET /login`, đăng nhập tài khoản admin seed | Về dashboard, có session | ✅ 302 → `/dashboard/room-map` |
| 2  | `GET /dashboard/room-map` | Lưới phòng đúng số phòng đã tạo | ✅ 200 |
| 3  | `GET /api/rooms` (đã đăng nhập) | JSON phòng + thống kê trống/có khách | ✅ đủ 2 phòng, giá, trạng thái |
| 4  | `GET /timeline-view` | Timeline Vis.js render nhóm phòng | ✅ 200 |
| 5  | Tìm phòng trống (`POST /api/rooms/search`, ngày mai→mốt) | JSON phòng trống gom theo loại, kèm giá | ✅ gom Standard/Deluxe, kèm giá + rule |
| 6  | Đặt phòng lẻ từ timeline (`POST /api/bookings/create`) | Booking mới hiện trên timeline | ✅ tạo `BK-260814-6DN3` |
| 7  | Check-in phòng vừa đặt (`POST /api/rooms/checkin`) | Phòng chuyển "Có khách" trên sơ đồ | ✅ "Check-in thành công cho Nguyen Van A" |
| 8  | Gọi 1 dịch vụ cho phòng đang ở (`POST /api/orders/add`) | Dịch vụ hiện trong chi tiết phòng | ✅ (đường ghi này có `room_id` đúng) |
| 9  | Preview checkout (`POST /api/rooms/preview_checkout`) | Hóa đơn: tiền phòng + dịch vụ, có breakdown | ✅ 1 đêm 500k + phụ thu sớm 2,8h (30%) 150k + DV 20k − cọc 200k = 470k |
| 10 | Checkout (`POST /api/rooms/checkout`) | Phòng về "Trống + chờ dọn" | ✅ (nhưng tiền không được ghi sổ — xem B2) |
| 11 | Xác nhận dọn (`POST /api/rooms/clean`) | Phòng về "Trống, sạch" | ✅ available/cleaned |
| 12 | `GET /customers` + thêm/sửa/xóa khách, tìm theo SĐT | CRUD + tìm kiếm hoạt động | ✅ add/search(q=SĐT)/update/delete đều OK |
| 13 | `GET /services` + thêm/sửa/xóa dịch vụ | CRUD hoạt động | ✅ add/update/delete đều OK |
| 14 | `GET /admin/price-manager` + tạo luật giá cuối tuần | Rule lưu và hiện trong danh sách | ✅ rule CÓ ngày + days_of_week [5,6] áp đúng: search CN ra 600.000 "Cuoi tuan" |
| 15 | `GET /logout` rồi mở lại `/dashboard/room-map` | Bị đưa về trang login | ✅ 302 → `/login?next=...` |

## Hỏng sẵn từ trước refactor — KHÔNG phải lỗi do refactor

Tất cả xác minh ngày 14/08/2026 trên baseline (live = chạy thật; code = đọc nguồn).

| #  | Hiện tượng | Xác minh | Nguyên nhân đã biết |
|----|-----------|----------|---------------------|
| B1 | Đặt đoàn (`POST /api/bookings/group_create`) thất bại | live: `"Lỗi hệ thống: 'booking_date' is an invalid keyword argument for Booking"` | kwargs không tồn tại trên model (Spec P5 lát 2) |
| B2 | Sau checkout: tiền biến mất | live: `payments` 0 dòng, `total_amount=0.00`, booking kẹt `checked_in` sau khi đã trả phòng | không ghi sổ + gán vào thuộc tính không phải cột (SDD 6.4, Spec P5 lát 1) |
| B3 | Sửa dịch vụ 1 phòng trong đoàn xóa dịch vụ mọi phòng cùng đơn | code: `update_services` xóa theo `booking_id` (booking_controller.py:434); `update_service_quantity` cũng thiếu `room_id` | thiếu lọc `room_id` (SDD 6.5) |
| B4 | PriceRule không điền ngày không bao giờ được áp | live: rule không ngày priority 10 giá 999.999 bị bỏ qua, search vẫn ra rule thường 600.000 | so sánh NULL (SDD 6.1) |
| B5 | `/api/customers` gọi được KHÔNG cần đăng nhập | live: 200 không cookie | thiếu `@login_required` (Spec P1 vá) |
| B6 | Backdoor đăng nhập `admin/123456` trong code | code: auth_controller.py:20–23 (runtime không phân biệt được vì admin seed trùng đúng mật khẩu này) | backdoor demo (Spec P1 vá) |
| B7 | Hết session: nút gọi API im lặng, màn hình trống | live: `GET /api/rooms` sau logout → 302 HTML thay vì 401 JSON | login_view áp cho cả API (Spec P3 sửa) |
| B8 | `/billing`, `/warehouse`, `/staff/shifts`, `/reports/revenue`, `/settings` | live: cả 5 trả 200 nhưng nội dung tĩnh | màn hình dữ liệu cứng (Backlog) |
