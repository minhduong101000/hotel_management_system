# Spec P3 — Tổ chức lại thư mục

**Trạng thái:** ⬜ Chưa làm · **Ước tính:** 2 ngày · **Phụ thuộc:** P2 (bắt buộc smoke test đang xanh)

## Mục tiêu

Gom code vào package `app/` và tách `controllers/` (12 file đang trộn HTML + JSON + logic) thành ba tầng có quy tắc phụ thuộc một chiều: `views/api → services → models`. Cây thư mục đích: SDD mục 3.3.

## Việc cần làm

### 1. Dời file — kỷ luật hai commit

- **Commit A:** chỉ `git mv`, không sửa một ký tự nội dung nào — để git nhận diện rename, diff đọc được, revert được.
- **Commit B:** sửa toàn bộ import theo vị trí mới.
- Sau mỗi commit: chạy smoke test, phải xanh mới đi tiếp.

### 2. Tách ba tầng

- `app/api/` — blueprint trả JSON (booking, room, customer, price, timeline, service).
- `app/views/` — blueprint trả HTML (auth, dashboard, billing, report, setting).
- `app/services/` — logic thuần, **cấm import Flask**. `controllers/pricing_service.py` → `app/services/pricing.py` (nó vốn là service nằm nhầm chỗ). Tạo khung `booking.py`, `billing.py`, `room.py` — P3 chỉ dời logic đã tách sẵn được, việc rút ruột controller còn lại để P5.

### 3. Xử lý lỗi tập trung

- `app/common/errors.py`: error handler chung — log server-side, client nhận message chung. Xóa ~12 chỗ `jsonify({'msg': str(e)})` đang rò lỗi hệ thống.
- Handler 401 cho API (SDD mục 3.2): request từ blueprint `api*` chưa đăng nhập nhận `401 JSON` thay vì 302 redirect HTML — sửa bug JS chết âm thầm khi hết session.

### 4. Đổi tên class + CSRF

- Đổi class `BookingService` → `ServiceOrder` (bảng đã đổi tên ở P1) — sửa mọi chỗ dùng.
- Bật `CSRFProtect` toàn cục; thêm meta tag token vào layout, JS gửi header `X-CSRFToken` (một chỗ sửa chung trong helper fetch nếu có, hoặc từng file JS).

## Tiêu chí nghiệm thu

- [ ] Cây thư mục khớp SDD mục 3.3; `controllers/` không còn tồn tại.
- [ ] `grep -r "import flask" app/services/` (và `from flask`) không có kết quả.
- [ ] Commit A là pure-rename (git hiển thị `renamed:` cho mọi file).
- [ ] Smoke test xanh; đi tay checklist smoke P0 trên bản Docker.
- [ ] Hết session mà gọi API → nhận 401 JSON; truy cập trang HTML → redirect login.
- [ ] POST không kèm CSRF token bị chặn; các form/fetch hiện có vẫn hoạt động.

## Ngoài phạm vi

- Không sửa logic nghiệp vụ, không sửa 9 lỗi tiền/booking (P5).
- Không đụng nội dung template ngoài phần thêm CSRF meta tag.
