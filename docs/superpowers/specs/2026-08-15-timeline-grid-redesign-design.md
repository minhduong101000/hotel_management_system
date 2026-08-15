# Spec: Redesign màn Timeline theo bản thiết kế 15-08-2026

> **ĐÃ TRIỂN KHAI 15-08-2026** — nghiệm thu: 434 unit + 12 mysql + 4 browser
> xanh; screenshot đối chiếu mockup khớp; bỏ hẳn phụ thuộc unpkg vis-timeline.
> Bonus: sửa bug có sẵn /api/rooms/search (NameError) lộ ra khi nghiệm thu.

**Nguồn thiết kế:** file "Thiết kế lại timeline.zip" của chủ khách sạn (mockup
`Timeline phòng.dc.html`, 9 màn). **Nguyên tắc bất di bất dịch:** chỉ đổi lớp
hiển thị — giữ nguyên toàn bộ logic, endpoint, luồng thao tác, ID phần tử và
handler JS hiện có (test browser + test markup đang neo vào chúng).

## 1. Phạm vi

| Màn trong thiết kế | File hiện có | Việc |
| --- | --- | --- |
| Timeline (lưới phòng × ngày) | `templates/rooms/timeline.html`, `static/js/timeline_manager.js` | **Thay vis-timeline bằng lưới tự vẽ** |
| Đặt phòng | `templates/rooms/_booking_modal.html` | Restyle + tạm tính + chip giờ |
| Chi tiết booking (POS) | `#bookingDetailModal` trong timeline.html | Restyle |
| Sửa booking (bước trung gian) | `#editBookingModal` trong timeline.html | Restyle theo ngôn ngữ thiết kế |
| Thanh toán | `_checkout_modal.html` + `checkout.js` | Restyle + segmented phương thức |
| Đặt đoàn | `_group_booking_modal.html` | Restyle |
| Thanh toán đoàn | `_group_checkout_modal.html` | Restyle |
| Dời lịch | `#rescheduleModal` trong timeline.html | Restyle (field đã trùng thiết kế) |
| Quét QR CCCD | `_qr_scanner_modal.html` | Restyle |
| Trạng thái tải/rỗng/lỗi | `data-state` sẵn có | Restyle nhẹ |

Các partial modal dùng chung với trang Sơ đồ phòng → restyle áp dụng cho cả
hai nơi (nhất quán, đúng ý thiết kế).

## 2. Quyết định kiến trúc

### 2.1 Bỏ vis-timeline, tự vẽ lưới
- Xóa 2 thẻ CDN unpkg (css + js) — hết phụ thuộc mạng ngoài cho màn này, hết
  vụ XSS-filter/CSS-override đã phải vá bằng `!important`.
- `#visualization` giữ nguyên id + `class="d-none"` ban đầu (test
  `test_frontdesk_ui_polish` neo), trở thành mount-point của lưới.
- Render DOM bằng `document.createElement`; tên khách đổ qua `textContent`
  (không innerHTML với dữ liệu người dùng).
- Máy trạng thái `showTimelineState` (loading/empty/error/no-items) giữ nguyên.
- Vị trí thanh booking = % phút trong khoảng nhìn (`left/width`), kẹp vào mép;
  meta ("n đêm"/"n giờ") ẩn khi thanh < 8% bề rộng.
- Đường "bây giờ" đỏ đặt theo % trong header + từng hàng, đúng thiết kế.
- Nhóm hàng theo tầng: chỉ khi mọi `room_number` là số ≥ 3 chữ số và có ≥ 2
  tầng (tầng = bỏ 2 chữ số cuối). Ngược lại danh sách phẳng, không hàng nhóm.

### 2.2 Chế độ xem: hợp nhất hiện có + thiết kế
`Ngày` (24 cột giờ) · `3 ngày` · `Tuần` (7) · `2 tuần` (14) · `Tháng` (30).
Ba nút đầu giữ nguyên id (`timeline-view-day/3days/week`), thêm
`timeline-view-2weeks`, `timeline-view-month`. Cùng một công thức % phút cho
mọi chế độ. >14 ngày → header rút gọn (chỉ số ngày).

### 2.3 Tương tác giữ nguyên topology
- Click thanh booking → `openEditModal(booking_room_id, booking_id)` (như cũ).
- Click ô trống → `openCreateModal(room_id, thời_điểm_ô)`; ngày-mode truyền
  đúng giờ của cột, ngày-nhiều truyền 14:00 của ngày đó.
- Filter giữ `<select id="timeline-status-filter">` (native, a11y), thêm 2
  option `hourly`, `group`; `getFilteredTimelineItems` mở rộng tương ứng.
- Kéo-thả dời lịch: **ngoài phạm vi** (backlog room-move); bỏ câu hint kéo-thả.

### 2.4 Thẻ thống kê (4 chip đầu trang) — tính phía client
Từ `timelineData` đã tải (API trả toàn bộ booking chưa hoàn tất):
- **Lấp đầy**: số phòng distinct có item `checked_in` / tổng phòng (%).
- **Nhận hôm nay**: item `booked|pending` có ngày bắt đầu = hôm nay (giờ máy
  lễ tân = giờ VN, nhất quán với cách thanh hiển thị).
- **Trả hôm nay**: item `checked_in` có ngày kết thúc = hôm nay.
- **Quá giờ**: item có `is_overstay` (server tính sẵn).

### 2.5 API bổ sung field cấu trúc (không phá vỡ)
`GET /api/bookings/timeline`:
- groups += `room_type`;
- items += `customer_name`, `rental_type`, `room_count`, `is_overstay`.
`content`/`className` giữ nguyên cho tương thích. Có pytest khóa các key mới.

### 2.6 Màu trạng thái (token trong style.css)
| Trạng thái | Sọc/bar | Nền | Chữ |
| --- | --- | --- | --- |
| Đặt trước (daily booked/pending) | `#2563eb` | `#eff6ff` | `#1d4ed8` |
| Đang ở (daily checked_in) | `#0f766e` | `#f0fdfa` | `#0f766e` |
| Theo giờ (hourly) | `#7c3aed` | `#f5f3ff` | `#6d28d9` |
| Đặt đoàn (`is_group`) | `#15803d` | `#f0fdf4` | `#15803d` |
| Quá giờ (`is_overstay`) | `#dc2626` | `#fef2f2` | `#b91c1c` |
Kiểu thanh: nền nhạt + sọc trái 3px màu trạng thái ("Nền nhạt" của thiết kế).
Ưu tiên phân loại: overstay > group > hourly > daily.

### 2.7 Modal
- Skeleton Bootstrap giữ nguyên (Modal API, focus helper, aria đã test).
- Thêm class thiết kế (`pos-modal`, `pos-section-label`, `pos-summary-box`,
  `pos-chip`…) + CSS trong style.css: bo 16px, header trắng chữ đậm (bỏ
  `bg-primary text-white`), nút teal `--color-action`, section label uppercase.
- Đặt phòng: thêm cột "Tạm tính" (dữ liệu từ quote API sẵn có của
  `calculateQuickDeposit`), chip thời lượng giờ 2h/4h/6h điền `bk-hourly-out`.
  Chip "Chưa biết" (thuê giờ mở) **ngoài phạm vi** — cần backend + chính sách giá.
- Thanh toán: segmented Tiền mặt/Chuyển khoản/Thẻ → `payload.payment_method`
  (`cash|banking|credit_card` — server đã nhận sẵn). Mặc định Tiền mặt.
- Mọi ID, label-for, aria-*, `data-modal-initial-focus` giữ đúng như test khóa.

### 2.8 Font & token
- `--font-sans` đã trỏ 'Be Vietnam Pro' → nạp thật font qua Google Fonts link
  trong `base.html` (app đã dùng CDN bootstrap/font-awesome, nhất quán).
- Token màu đã có đủ trong `:root` style.css từ đợt PROMAX — dùng lại.
- Xóa block CSS vis-* cũ (hết tác dụng khi bỏ vis).

## 3. Ngoài phạm vi (ghi rõ để không trôi)
1. Kéo-thả thanh booking để dời lịch (đi cùng backlog room-move).
2. Thuê giờ không chốt giờ ra ("Chưa biết") — cần backend.
3. Redesign sidebar/chrome toàn app (thiết kế chỉ mô tả lại, đã gần đúng).
4. Prop "Nền đậm" của thanh (thiết kế mặc định nền nhạt).

## 4. Tiêu chí nghiệm thu
1. Toàn bộ unit suite xanh (kể cả markup/accessibility/ui-regression).
2. Browser suite (B1–B4 + guard console/4xx) xanh trên stack Docker rebuild.
3. Không còn request tới unpkg trên trang timeline.
4. Screenshot lưới + modal đối chiếu mockup: layout, màu, khoảng cách khớp.
5. Click ô trống tạo booking đúng phòng/ngày; click thanh mở đúng modal cũ.
