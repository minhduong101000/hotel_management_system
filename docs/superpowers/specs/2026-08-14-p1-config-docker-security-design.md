# Spec P1 — Config ra ngoài + Docker + Vá bảo mật

**Trạng thái:** ⬜ Chưa làm · **Ước tính:** 2 ngày · **Phụ thuộc:** P0

## Mục tiêu

`git clone` + điền `.env` + `docker compose up` = hệ thống chạy trên máy trắng. Đồng thời vá 4 lỗ hổng bảo mật nằm đúng trong các file phải sửa ở bước này — làm chung để không mở file hai lần.

## Bối cảnh

- `config.py` đang **rỗng 0 byte**; mật khẩu MySQL và `SECRET_KEY` hardcode trong `app.py` và đã nằm trong lịch sử git.
- `python-dotenv` và `Flask-Migrate` đã có trong requirements nhưng **chưa được dùng** (chưa có `migrations/`).
- Chi tiết thiết kế: SDD mục 7 (bảo mật) và mục 8 (triển khai).

## Việc cần làm

### 1. Config class-based

- `config.py`: `BaseConfig` / `DevConfig` / `TestConfig` / `ProdConfig`, đọc từ env qua `python-dotenv`.
- `ProdConfig` **không có default** cho `SECRET_KEY` và `DATABASE_URL` — thiếu là fail sớm lúc boot, không chạy với giá trị rỗng.
- Tạo `.env.example` (commit) và `.env` (đã ignore sẵn trong `.gitignore`).
- Biến môi trường: theo bảng SDD mục 8.2.

### 2. Docker

- `docker/Dockerfile`: Python slim, cài từ `requirements.txt` (đã pin ở P0), chạy gunicorn.
- `docker-compose.yml`: services `web` + `db` (MySQL 8, named volume `dbdata`, healthcheck `mysqladmin ping`) + `adminer` (chỉ profile dev).
- `web` chờ `db` healthy (`depends_on: condition: service_healthy`); entrypoint chạy `flask db upgrade` trước khi start gunicorn.
- DB user riêng cho app — **không dùng root**.

### 3. Migration đầu tiên

- `flask db init` + migration baseline từ model hiện có.
- **Trong cùng migration:** đổi tên bảng `Users` → `users` (bẫy case-sensitivity Linux — SDD D5) và `booking_services` → `service_orders` (SDD D6, chỉ đổi tên bảng; đổi tên class Python để sang P3).
- Trên DB dev đang có dữ liệu: `flask db stamp head` sau khi đổi tên tay, hoặc chấp nhận dựng DB mới trong Docker (dữ liệu hiện tại là dữ liệu test).

### 4. Bốn vá bảo mật

1. Xóa backdoor đăng nhập `admin/123456` trong `auth_controller.py`.
2. Bỏ route `/init-db`; thay bằng lệnh CLI `flask seed-admin` (đọc mật khẩu admin đầu tiên từ env hoặc prompt).
3. Đưa `SECRET_KEY` + DB credentials ra `.env`.
4. Thêm `@login_required` cho toàn bộ nhóm API customers đang hở.

## Tiêu chí nghiệm thu

- [ ] Trên máy chưa từng cài project: clone → copy `.env.example` thành `.env`, điền giá trị → `docker compose up` → đăng nhập được và đi hết checklist smoke P0 (các mục chạy-được).
- [ ] `grep` không còn secret nào trong source (mật khẩu, SECRET_KEY).
- [ ] Đăng nhập `admin/123456` (không có trong DB) bị từ chối.
- [ ] `GET /init-db` trả 404.
- [ ] Gọi API customers khi chưa đăng nhập bị chặn.
- [ ] Bảng trong MySQL container tên `users`, `service_orders` (chữ thường).

## Ngoài phạm vi

- Không đổi cấu trúc thư mục, không đổi tên class Python (P3).
- Không thêm CSRF (P3 — đi cùng đợt sửa hàng loạt template/JS).
- CI/CD, backup tự động → Backlog.
