# Spec: CI hardening — Docker build và smoke trình duyệt

**Ngày:** 15-08-2026
**Trạng thái:** Chờ chủ dự án duyệt để thực thi
**Bối cảnh:** 19 file JS chưa từng chạy trong kiểm thử — hai bug URL 14-08 (nút add-room gọi sai blueprint, autofill khách 404) đều lọt vì test chỉ đọc chuỗi HTML/JS tĩnh. CI hiện cũng không build Docker image nên Dockerfile hỏng chỉ phát hiện lúc deploy.

## 1. Mục tiêu

1. **Mọi push đều build được image + boot được stack thật**: job CI build Docker image, dựng web+db+migrate bằng compose, chờ healthy, đánh smoke HTTP.
2. **JS chạy thật trong trình duyệt headless**: Playwright (Python) đi 4 luồng nghiệp vụ nhạy nhất, bắt lỗi console và request 404 — lớp lưới đúng cho loại bug "nút chết im lặng".
3. Giữ CI nhanh: hai job mới chạy song song với hai job test hiện có; tổng thời gian pipeline không vượt ~10 phút.

## 2. Thiết kế

### 2.1. Job `docker-smoke` (GitHub Actions)

- `docker compose -f docker-compose.yml build` (file base — đúng bản production).
- Tạo `.env` CI từ secrets giả định sẵn trong workflow (không phải secrets thật).
- `docker compose -f docker-compose.yml up -d db migrate web` (bỏ caddy/backup cho nhẹ), chờ web healthy ≤ 90s.
- Smoke: `/healthz` = 200; tạo hotel + admin bằng `flask create-hotel` trong container; GET `/central/login` = 200.

### 2.2. Bộ smoke trình duyệt `tests/browser/` (Playwright, marker `browser`)

Chạy với server thật (`flask run` nền + SQLite seed qua create_app? — KHÔNG: dùng chính compose stack của job docker-smoke để test môi trường thật). 4 kịch bản:

| # | Kịch bản | Bắt gì |
|---|---|---|
| B1 | Đăng nhập admin → thấy sơ đồ phòng | form login hoạt động, redirect đúng slug |
| B2 | Timeline: mở modal booking, autofill SĐT khách cũ | chính bug 404 autofill 14-08 |
| B3 | Chi tiết hóa đơn → mở modal Hoàn tiền → preview hiện 3 con số | refund.js + api() mapping |
| B4 | Modal sửa booking → nút "Thêm phòng vào đơn" gửi đúng URL | chính bug add-room 14-08 |

Mỗi kịch bản assert thêm 2 bất biến toàn cục: **không có lỗi console** và **không request nào trả 404/500** trong phiên — đây là lưới bắt "nút chết" tổng quát, không chỉ 4 luồng trên.

- Local: `pytest -m browser` với `BROWSER_BASE_URL` trỏ stack compose đang chạy; bỏ qua (skip) nếu thiếu biến — không làm chậm bộ test thường.
- CI: job docker-smoke chạy tiếp `pytest -m browser` sau khi stack healthy.

### 2.3. Dọn kèm (nhóm 5 cũ)

- `pytest.ini` thêm marker `browser`.
- requirements-dev: pin `playwright` + `pytest-playwright`.
- Cập nhật trạng thái các spec/plan cũ treo sai (plan kho 07-29 "chờ review" dù đã chạy...).

## 3. Ngoài phạm vi

- Coverage gate và lint (đợt riêng nếu muốn — tránh phình).
- Test JS unit thuần (không framework FE, không đáng đầu tư khi Playwright phủ hành vi).
- Sentry/monitoring (cần tài khoản dịch vụ).

## 4. Tiêu chí nghiệm thu

1. Push lên dev: 4 job CI (unit / mysql / docker-smoke / browser trong docker-smoke) đều xanh.
2. Cố tình làm hỏng Dockerfile trên nhánh thử → CI đỏ ở docker-smoke (chứng minh lưới có răng — kiểm local bằng cách build file hỏng, không cần push nhánh rác).
3. Tái diễn bug add-room cũ (revert tạm mapping trong main.js ở working tree) → B4 đỏ, console/404-guard bắt được; hoàn tác.
4. `pytest -m "not mysql and not browser"` local vẫn ~70s như cũ.
5. Playwright chạy local được trên stack compose hiện hành (hướng dẫn 3 lệnh trong plan).

## 5. Sau đợt này (lộ trình đề xuất, mỗi mục một spec riêng)

1. **Room-move** — đổi phòng cho khách đang ở: chuyển dịch vụ/cọc/lịch sử, nối luôn UI kéo-thả `update_timeline` đang chờ.
2. **Bảo trì theo lịch** — khoảng ngày + cảnh báo đụng booking, thay trạng thái vô thời hạn.
3. Monitoring (Sentry + uptime) khi có tài khoản.
