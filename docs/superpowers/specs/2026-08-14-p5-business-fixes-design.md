# Spec P5 — Sửa nghiệp vụ tiền & booking

**Trạng thái:** ⬜ Chưa làm · **Ước tính:** kéo dài (làm theo lát, mỗi lát một PR) · **Phụ thuộc:** P4

## Mục tiêu

Sửa 9 lỗi nghiệp vụ đã xác định, theo đúng chu trình TDD: các test `xfail` viết sẵn ở P4 là danh sách việc — sửa đến đâu gỡ dấu `xfail` đến đó. **Tiến độ P5 = số `xfail` còn lại giảm về 0.** Đồng thời rút logic khỏi controller vào tầng `services/`.

## Danh sách lỗi — thứ tự đề xuất

Nhóm theo lát dọc, mỗi lát tự đứng được và có thể release riêng:

### Lát 1 — Dòng tiền (quan trọng nhất)

1. **Ghi sổ `Payment` khi checkout** (SDD 6.4, D3): mỗi lần thu tiền là một dòng append-only (`deposit`/`settlement`/`refund`). Bảng đã có, chưa từng được ghi.
2. **Cập nhật `booking.total_amount` + `payment_status`** trong cùng transaction với checkout — hiện đứng yên ở giá trị khởi tạo.
3. **Chuyển toàn bộ tính tiền sang `Decimal`** (SDD D4): helper `common/money.py`, sửa `pricing.py` + mọi chỗ cộng tiền; thống nhất cột DB về `DECIMAL(15,2)` bằng migration.

### Lát 2 — Toàn vẹn đặt phòng

4. **Sửa `group_create`**: đang truyền kwargs không tồn tại vào model (`booking_date`, `deposit`, `rental_type`, `price`) → crash. Viết lại trên `services/booking.py`.
5. **Chống double-booking** (SDD 4.3): kiểm tra chồng lấn trong transaction có `SELECT … FOR UPDATE`; test bằng marker `mysql`.
6. **`service_orders.room_id` NOT NULL** + mọi thao tác dịch vụ lọc theo `booking_id + room_id` (SDD 6.5) — sửa lỗi xóa dịch vụ cả đoàn khi sửa một phòng.

### Lát 3 — Giá & quyền

7. **PriceRule NULL date** (SDD 6.1): rule không có ngày áp quanh năm — gỡ `xfail` ca test tương ứng.
8. **Phân quyền** (`common/decorators.py` → `@role_required('admin')`): áp cho nhóm giá, dịch vụ, cấu hình; ẩn menu theo role trong template.
9. **Chuẩn hóa cập nhật trạng thái `Booking` tổng** từ trạng thái các `BookingRoom` con (SDD 4.4): checkout phòng cuối cùng → booking `completed`.

## Quy tắc làm việc

- Mỗi lát: gỡ `xfail` → chạy đỏ → sửa ở tầng `services/` → chạy xanh → đi tay checklist smoke phần liên quan → cập nhật SDD (gỡ nhãn `[Đích]` các mục đã thành hiện thực).
- Không sửa hai lát trong cùng một PR.
- Controller chỉ còn: parse request → gọi service → trả response.

## Tiêu chí nghiệm thu (toàn phase)

- [ ] 0 test `xfail` còn lại trong bộ test.
- [ ] Checkout một phòng tạo đúng 1 dòng `payments`; tổng `payments` của booking khớp `total_amount`.
- [ ] Hai request đặt trùng phòng đồng thời: đúng 1 thành công.
- [ ] Tài khoản `staff` bị chặn khỏi API quản lý giá (403).
- [ ] SDD không còn mục nào lệch với code trong các phần 4–7.

## Ngoài phạm vi

- 5 màn hình dữ liệu cứng (thu ngân, kho, giao ca, báo cáo, cấu hình) → Backlog trong README sổ tổng.
