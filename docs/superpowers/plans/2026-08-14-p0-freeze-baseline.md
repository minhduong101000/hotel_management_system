# P0 — Đóng băng hiện trạng: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tạo điểm quay về an toàn (tag `v0-legacy`, requirements đã pin) và định nghĩa đo được cho "không hỏng" (checklist smoke đã đi tay một lượt) trước khi bắt đầu refactor.

**Architecture:** Không có thay đổi code — P0 chỉ dựng lại môi trường chạy (venv + MySQL container, vì máy hiện tại không còn cả hai), ghi lại trạng thái, và cắm mốc. Bốn task tuần tự; tag nằm cuối cùng để nó bao trùm cả requirements đã pin và checklist (vẫn zero thay đổi code app).

**Tech Stack:** Python 3.12 (Homebrew), venv, MySQL 8 (Docker container tạm), Flask app hiện có chạy bằng `python app.py`.

**Spec:** `docs/superpowers/specs/2026-08-14-p0-freeze-baseline-design.md`

## Global Constraints

- **CẤM sửa mọi file code app**: `app.py`, `controllers/`, `models/`, `templates/`, `static/`, `extensions.py`, `config.py`. Nếu app không boot được vì xung đột version, DỪNG LẠI và báo cáo — không vá code.
- Chỉ được tạo/sửa: `requirements.txt`, `requirements-dev.txt`, `docs/smoke-checklist.md`, git tag.
- Python bắt buộc: `/opt/homebrew/bin/python3.12` (python3 hệ thống là 3.9.6 — không dùng).
- MySQL container phải khớp **nguyên văn** chuỗi kết nối hardcode tại `app.py:22`: `mysql+pymysql://root:123456@localhost/Hotel_Management_System` (user `root`, mật khẩu `123456`, db `Hotel_Management_System`, port 3306).
- Commit message: một dòng ngắn tiếng Anh + trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Dựng môi trường chạy được (venv + MySQL container + app boot)

**Files:**
- Create: `venv/` (đã có trong `.gitignore` — không commit)
- Không sửa file nào trong repo.

**Interfaces:**
- Consumes: `requirements.txt` hiện tại (7 tên gói trần), `app.py:22` (chuỗi kết nối DB).
- Produces: venv tại `venv/` có app boot được — Task 2 freeze từ venv này; container MySQL `hotel-mysql-legacy` — Task 3 đi checklist trên đó.

- [ ] **Step 1: Tạo venv bằng Python 3.12**

```bash
cd /Users/duongnguyen1010/code/Python/hotel_management_system
/opt/homebrew/bin/python3.12 -m venv venv
venv/bin/python --version
```
Expected: `Python 3.12.x`

- [ ] **Step 2: Cài 7 gói từ requirements.txt hiện tại**

```bash
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
```
Expected: `Successfully installed Flask-x.y.z Flask-Login-... Flask-Migrate-... Flask-SQLAlchemy-... PyMySQL-... email-validator-... python-dotenv-...` (kèm gói phụ thuộc). Nếu pip báo lỗi resolve → DỪNG, báo cáo.

- [ ] **Step 3: Dựng MySQL 8 container khớp chuỗi kết nối hardcode**

```bash
docker run -d --name hotel-mysql-legacy \
  -e MYSQL_ROOT_PASSWORD=123456 \
  -e MYSQL_DATABASE=Hotel_Management_System \
  -p 3306:3306 \
  mysql:8
```
Expected: in ra container id. Nếu báo trùng tên: `docker rm -f hotel-mysql-legacy` rồi chạy lại. Nếu port 3306 bận: `lsof -i :3306` xem tiến trình nào chiếm, báo cáo trước khi xử lý.

- [ ] **Step 4: Chờ MySQL healthy**

```bash
until docker exec hotel-mysql-legacy mysqladmin ping -uroot -p123456 --silent 2>/dev/null; do sleep 2; done; echo READY
```
Expected: `READY` trong vòng ~30 giây.

- [ ] **Step 5: Boot app và tạo schema**

```bash
venv/bin/python app.py > /tmp/hotel-app.log 2>&1 &
sleep 3
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/login
curl -s http://127.0.0.1:5000/init-db
```
Expected: dòng đầu `200`; dòng hai là message init thành công (route `/init-db` tạo bảng + seed admin — sẽ bị xóa ở P1, P0 dùng nguyên trạng). Nếu `python app.py` chết ngay → đọc `/tmp/hotel-app.log`; lỗi import/version → DỪNG, báo cáo (Global Constraint: không vá code).

- [ ] **Step 6: Xác nhận bảng đã tạo trong MySQL**

```bash
docker exec hotel-mysql-legacy mysql -uroot -p123456 -e "SHOW TABLES" Hotel_Management_System
```
Expected: danh sách có `Users`, `rooms`, `bookings`, `booking_rooms`, `booking_services`, `services`, `customers`, `payments`, `price_rules` (tên `Users` viết hoa là hiện trạng — P1 mới đổi).

*(Task này không có commit — không file tracked nào thay đổi.)*

---

### Task 2: Pin requirements.txt + tạo requirements-dev.txt

**Files:**
- Modify: `requirements.txt` (7 tên trần → freeze đầy đủ có `==`)
- Create: `requirements-dev.txt`

**Interfaces:**
- Consumes: venv Task 1 (đã xác nhận boot được).
- Produces: `requirements.txt` pin cứng — mọi giai đoạn sau (Dockerfile P1, CI tương lai) cài từ file này; `requirements-dev.txt` — P4 bổ sung gói test vào đây.

- [ ] **Step 1: Freeze TRƯỚC khi cài bất kỳ gói dev nào** (thứ tự bắt buộc — freeze sau khi cài pytest sẽ lẫn gói dev vào requirements chính)

```bash
venv/bin/pip freeze > requirements.txt
cat requirements.txt
```
Expected: ~10–15 dòng, mỗi dòng dạng `Gói==x.y.z`, có đủ Flask, Flask-SQLAlchemy, Flask-Login, Flask-Migrate, PyMySQL, python-dotenv, email-validator.

- [ ] **Step 2: Verify cài sạch trong venv mới tinh**

```bash
VERIFY_DIR=$(mktemp -d)
/opt/homebrew/bin/python3.12 -m venv "$VERIFY_DIR/venv"
"$VERIFY_DIR/venv/bin/pip" install -q -r requirements.txt && echo INSTALL-OK
rm -rf "$VERIFY_DIR"
```
Expected: `INSTALL-OK`

- [ ] **Step 3: Cài pytest và sinh requirements-dev.txt**

```bash
venv/bin/pip install pytest
echo "-r requirements.txt" > requirements-dev.txt
venv/bin/pip freeze | grep -i "^pytest==" >> requirements-dev.txt
cat requirements-dev.txt
```
Expected:
```
-r requirements.txt
pytest==8.x.y
```

- [ ] **Step 4: Commit**

```bash
git add requirements.txt requirements-dev.txt
git commit -m "Pin dependencies from verified running env

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Checklist smoke — viết file và đi tay một lượt

**Files:**
- Create: `docs/smoke-checklist.md`

**Interfaces:**
- Consumes: app đang chạy từ Task 1 (http://127.0.0.1:5000).
- Produces: `docs/smoke-checklist.md` — mọi giai đoạn P1–P5 nghiệm thu bằng cách đi lại file này; cột "Kết quả baseline" là mốc so sánh.

- [ ] **Step 1: Tạo file với nội dung sau (nguyên văn)**

````markdown
# Checklist Smoke — Baseline v0-legacy (14/08/2026)

Định nghĩa đo được cho "không hỏng" trong suốt refactor P1–P5. Sau mỗi giai
đoạn, đi lại checklist: mọi mục ✅ ở baseline phải giữ nguyên ✅. Mục ❌ ghi
chú lý do. KHÔNG sửa cột "Kết quả baseline" sau khi đã chốt.

Môi trường baseline: venv Python 3.12 + MySQL 8 (container
`hotel-mysql-legacy`) + `venv/bin/python app.py` → http://127.0.0.1:5000

## Chuẩn bị dữ liệu (một lần, sau /init-db)

1. `GET /init-db` — tạo bảng + tài khoản admin (mật khẩu seed: xem handler
   `/init-db` trong `app.py`).
2. Đăng nhập admin, tạo: ≥2 phòng (1 Standard, 1 Deluxe, có giá đêm + giá
   giờ), ≥2 dịch vụ (VD: Nước suối 10.000đ, Giặt ủi 50.000đ), ≥1 khách hàng.

## Các mục phải chạy được

| #  | Thao tác | Mong đợi | Kết quả baseline |
|----|----------|----------|------------------|
| 1  | `GET /login`, đăng nhập tài khoản admin seed | Về dashboard, có session | |
| 2  | `GET /dashboard/room-map` | Lưới phòng đúng số phòng đã tạo | |
| 3  | `GET /api/rooms` (đã đăng nhập) | JSON phòng + thống kê trống/có khách | |
| 4  | `GET /timeline-view` | Timeline Vis.js render nhóm phòng | |
| 5  | Tìm phòng trống (`POST /api/rooms/search`, ngày mai→mốt) | JSON phòng trống gom theo loại, kèm giá | |
| 6  | Đặt phòng lẻ từ timeline (`POST /api/bookings/create`) | Booking mới hiện trên timeline | |
| 7  | Check-in phòng vừa đặt (`POST /api/rooms/checkin`) | Phòng chuyển "Có khách" trên sơ đồ | |
| 8  | Gọi 1 dịch vụ cho phòng đang ở (`POST /api/orders/add`) | Dịch vụ hiện trong chi tiết phòng | |
| 9  | Preview checkout (`POST /api/rooms/preview_checkout`) | Hóa đơn: tiền phòng + dịch vụ, có breakdown | |
| 10 | Checkout (`POST /api/rooms/checkout`) | Phòng về "Trống + chờ dọn" | |
| 11 | Xác nhận dọn (`POST /api/rooms/clean`) | Phòng về "Trống, sạch" | |
| 12 | `GET /customers` + thêm/sửa/xóa khách, tìm theo SĐT | CRUD + tìm kiếm hoạt động | |
| 13 | `GET /services` + thêm/sửa/xóa dịch vụ | CRUD hoạt động | |
| 14 | `GET /admin/price-manager` + tạo luật giá cuối tuần | Rule lưu và hiện trong danh sách | |
| 15 | `GET /logout` rồi mở lại `/dashboard/room-map` | Bị đưa về trang login | |

## Hỏng sẵn từ trước refactor — KHÔNG phải lỗi do refactor

| #  | Hiện tượng | Nguyên nhân đã biết |
|----|-----------|---------------------|
| B1 | Đặt đoàn (`POST /api/bookings/group_create`) trả 500 | truyền kwargs không tồn tại vào model (Spec P5 lát 2) |
| B2 | Sau checkout: bảng `payments` trống, `total_amount` không đổi | tiền không được ghi sổ (SDD 6.4, Spec P5 lát 1) |
| B3 | Sửa dịch vụ 1 phòng trong đoàn xóa dịch vụ mọi phòng cùng đơn | xóa theo `booking_id` thiếu `room_id` (SDD 6.5) |
| B4 | PriceRule không điền ngày không bao giờ được áp | so sánh NULL (SDD 6.1) |
| B5 | `/api/customers` gọi được KHÔNG cần đăng nhập | thiếu `@login_required` (Spec P1 vá) |
| B6 | Đăng nhập `admin/123456` vào được dù DB không có user này | backdoor trong auth controller (Spec P1 vá) |
| B7 | Hết session: nút gọi API im lặng, màn hình trống | fetch nhận 302→HTML thay vì 401 (Spec P3 sửa) |
| B8 | `/billing`, `/warehouse`, `/staff/shifts`, `/reports/revenue`, `/settings` | màn hình dữ liệu cứng (Backlog) |
````

- [ ] **Step 2: Đi tay checklist trên app đang chạy**

Mở http://127.0.0.1:5000 bằng trình duyệt, làm phần "Chuẩn bị dữ liệu", rồi đi lần lượt mục 1→15, điền cột "Kết quả baseline" bằng ✅ (kèm ghi chú nếu có điểm lạ) hoặc ❌ + hiện tượng. Với B1–B6: thử nhanh để xác nhận đúng là hỏng/hở như mô tả, sửa mô tả nếu thực tế khác.

- [ ] **Step 3: Verify checklist đạt tiêu chí spec**

```bash
grep -c "✅" docs/smoke-checklist.md
```
Expected: ≥ 10. Nếu < 10 mục chạy được → hiện trạng tệ hơn dự kiến: DỪNG, báo cáo danh sách ❌ trước khi tiếp tục.

- [ ] **Step 4: Commit**

```bash
git add docs/smoke-checklist.md
git commit -m "Add baseline smoke checklist (walked on v0-legacy)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Tag v0-legacy và push

**Files:** không — chỉ tag.

**Interfaces:**
- Consumes: các commit Task 2 + Task 3 (tag đặt cuối để bao trùm requirements đã pin và checklist — vẫn zero thay đổi code app, đúng tinh thần "đóng băng").
- Produces: tag `v0-legacy` — điểm `git checkout v0-legacy` quay về trạng thái trước refactor cho mọi giai đoạn sau.

- [ ] **Step 1: Tạo annotated tag**

```bash
git tag -a v0-legacy -m "Frozen baseline before refactor P1-P5: unpinned code + pinned deps + walked smoke checklist"
git tag -l v0-legacy
```
Expected: in ra `v0-legacy`

- [ ] **Step 2: Push tag lên origin**

```bash
git push origin v0-legacy
```
Expected: `* [new tag] v0-legacy -> v0-legacy`

- [ ] **Step 3: Verify checkout được**

```bash
git checkout v0-legacy --detach 2>&1 | head -2; git checkout main 2>&1 | head -1
```
Expected: detach rồi quay lại `main` không lỗi.

---

## Dọn dẹp & bàn giao sang P1

- **Giữ nguyên** container `hotel-mysql-legacy` và `venv/` — dùng tiếp làm môi trường dev cho tới khi P1 thay bằng `docker compose`. Muốn tắt tạm: `docker stop hotel-mysql-legacy`; bật lại: `docker start hotel-mysql-legacy`.
- Tắt app: `kill %1` hoặc `pkill -f "python app.py"`.
- Cập nhật `docs/superpowers/specs/README.md`: dòng P0 → ✅ Xong, kèm ngày.
