# Spec: Chuẩn hóa ma trận quyền và thêm phòng vào đơn

**Ngày:** 14-08-2026
**Trạng thái:** Đã chốt nghiệp vụ (chủ dự án, 14-08): staff KHÔNG được sửa dịch vụ/luật giá; nút "thêm phòng vào đơn" làm thật.
**Phạm vi:** 4 lỗ quyền trong sổ tay nghiệp vụ mục 5 + endpoint add-room còn thiếu ruột + `load_dotenv`.
**Không bao gồm:** đổi quyền các thao tác vận hành quầy (tạo booking, check-in/out, hủy có lý do, dịch vụ trong đơn — staff giữ nguyên quyền); ngưỡng phê duyệt; công nợ.

## 1. Ma trận quyền chuẩn (nguyên tắc: cấu hình = Admin, vận hành = Staff)

| Nhóm | Staff | Admin | Master trong tenant |
|---|---:|---:|---:|
| Vận hành quầy (booking, check-in/out, hủy, dịch vụ trong đơn, hoàn tiền, khách hàng) | Có | Có | Có |
| **Xem** danh mục dịch vụ (`GET /api/services` — modal order cần) | Có | Có | Có |
| **Sửa** danh mục dịch vụ (POST/PUT/DELETE) | **Không — 403** | Có | **Có (sửa mới)** |
| Luật giá: trang + toàn bộ API price-manager | **Không — 403** | Có | **Có (sửa mới)** |
| Khu `admin_required` hiện hữu (kho ghi, chi phí, doanh thu, sổ quỹ, audit, nhân sự) | Không | Có | **Có (sửa mới — trước bị khóa oan)** |

- `admin_required` viết lại theo hình mẫu `room_structure_required`: chấp nhận `role == 'admin'` **hoặc** `is_super_admin`; request API/JSON trả `403` JSON `error_code='forbidden'`, request HTML giữ flash + redirect.
- Hết phiên đăng nhập: request có path chứa `/api/` nhận **`401` JSON `error_code='unauthenticated'`** thay vì 302 HTML (sửa gốc bug "nút bấm im lặng"); request HTML giữ redirect về login.

## 2. Thêm phòng vào đơn (add-room)

`POST /<slug>/timeline/api/bookings/add-room` — JS `addRoomToExistingBooking()` đã gọi sẵn endpoint này.

- Input: `booking_id`, `room_number`, `check_in`, `check_out` (`%Y-%m-%dT%H:%M`).
- Điều kiện: booking thuộc tenant và đang `confirmed`/`checked_in` (đơn `cancelled`/`completed` từ chối); phòng thuộc tenant, không `maintenance`, không trùng lịch active (dùng `_has_active_booking_conflict` như create_booking, khóa hàng phòng).
- Tạo `BookingRoom` `status='booked'`, `rental_type='daily'`, snapshot giá như create_booking (`price_snapshot` + `price_breakdown_snapshot` từ `get_nightly_price_breakdown`); `room_deposit_amount = 0` — phòng thêm không thu cọc qua luồng này, tiền tính khi checkout.
- Gọi `aggregate_booking_state`, ghi audit `add_room_to_booking` (booking code, phòng, khoảng ở), commit. Trùng lịch tự chặn double-click.
- Quyền: staff dùng được (vận hành quầy).

## 3. Vá phụ

- `config.py` thêm `load_dotenv()` — `python app.py`/script trần đọc được `.env` như Flask CLI, hết rơi nhầm SQLite.

## 4. Tiêu chí nghiệm thu

1. Staff `POST/PUT/DELETE /api/services` và mọi API price-manager → `403` JSON; `GET /api/services` vẫn `200`.
2. Master Admin trong tenant gọi được API kho/chi phí/sổ quỹ/audit/nhân sự (trước 302 oan).
3. Chưa đăng nhập gọi API bất kỳ (`/api/`) → `401` JSON; mở trang HTML → redirect login (không đổi).
4. Add-room: thành công thêm phòng vào đơn có sẵn với snapshot giá đủ từng đêm + audit; trùng lịch → 409; đơn đã hủy/hoàn tất → từ chối; phòng tenant khác → 404; staff làm được.
5. `python -c "from app import app"` với `.env` trỏ MySQL kết nối đúng MySQL.
6. Full regression (416 test hiện có + test mới) xanh cả hai bộ.
