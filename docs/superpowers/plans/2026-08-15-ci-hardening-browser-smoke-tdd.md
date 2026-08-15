# Kế hoạch TDD: CI hardening — Docker build và smoke trình duyệt

**Ngày:** 15-08-2026 · **Spec nguồn:** `2026-08-15-ci-hardening-browser-smoke-design.md` · **Trạng thái:** Chờ duyệt

Nguyên tắc RED của đợt này: với lưới kiểm thử, "RED" = chứng minh lưới BẮT ĐƯỢC lỗi đã biết (tái diễn bug cũ trong working tree → test đỏ → hoàn tác), không phải viết code sai mới.

## HM1 — Hạ tầng Playwright + 2 bất biến toàn cục

**Files:** `requirements-dev.txt` (+playwright, pytest-playwright — pin sau khi cài), `pytest.ini` (+marker `browser`), `tests/browser/conftest.py` (mới), `tests/browser/test_smoke_flows.py` (mới, B1 trước).

`tests/browser/conftest.py`:
- Fixture `base_url`: đọc `BROWSER_BASE_URL`; thiếu → `pytest.skip` cả module (bộ test thường không chậm đi).
- Fixture `admin_page`: đăng nhập bằng `BROWSER_ADMIN_USER/PASSWORD` (mặc định đọc `.env` local), trả page đã ở sơ đồ phòng.
- Fixture `guarded_page` (bất biến toàn cục): gắn listener `console` (level error) và `response` (status ≥ 400 với path `/api/` hoặc `.js`); cuối test assert hai danh sách rỗng — đây là lưới "nút chết im lặng".

Bước:
1. `venv/bin/pip install playwright pytest-playwright && venv/bin/playwright install chromium` → pin vào requirements-dev.
2. Viết B1 (login → thấy `#room-map` container). Chạy với stack compose local: `BROWSER_BASE_URL=http://127.0.0.1:8000 venv/bin/python -m pytest -m browser -q` → xanh.
3. RED-proof: đổi tạm password → B1 đỏ đúng thông điệp; hoàn tác.

Commit: `test: playwright harness with console and 404 guards`

## HM2 — Ba kịch bản nghiệp vụ B2–B4

**Files:** `tests/browser/test_smoke_flows.py`.

- B2 autofill: mở timeline → modal tạo booking → gõ SĐT khách có sẵn (seed qua API trước bằng `requests` trong fixture) → chờ tên tự điền; guard 404 bắt fetch sai prefix.
- B3 refund: seed booking + cọc qua API (pattern giống smoke 14-08) → billing → chi tiết → nút Hoàn tiền → assert 3 con số ngữ cảnh có nội dung ≠ "—".
- B4 add-room: mở modal sửa booking trên timeline → gọi `addRoomToExistingBooking` qua nút → nhập số phòng trống (dialog prompt: dùng `page.on('dialog')`) → chờ alert thành công; guard 404 bắt sai blueprint.
- RED-proof cho B4: revert tạm dòng `'/api/bookings/add-room'` trong main.js → B4 đỏ vì guard 404; hoàn tác (đây là tái diễn nguyên văn bug 14-08).

Commit: `test: browser smoke for autofill, refund modal and add-room flows`

## HM3 — Job CI docker-smoke

**Files:** `.github/workflows/tests.yml` (job mới `docker-smoke`).

Job steps:
1. checkout; tạo `.env` CI (openssl rand tại chỗ; `SESSION_COOKIE_SECURE=false`; `DOMAIN=` trống).
2. `docker compose -f docker-compose.yml build`
3. `docker compose -f docker-compose.yml up -d db migrate web` + vòng chờ web healthy ≤ 90s (`docker inspect`).
4. `docker compose exec -T web flask create-hotel --name CI --slug central --admin-username admin --admin-password <pw-ci-12+>`
5. curl `/healthz` = 200, `curl http://127.0.0.1:8000/central/login` = 200 — LƯU Ý: base không publish 8000 → dùng `docker compose exec web python -c urllib` hoặc thêm `--publish` qua override CI riêng (`docker-compose.ci.yml` mở 127.0.0.1:8000).
6. setup-python + pip install dev + `playwright install --with-deps chromium` + `BROWSER_BASE_URL=http://127.0.0.1:8000 pytest -m browser -q`.
7. `docker compose logs web --tail 50` khi fail (step `if: failure()`).

Nghiệm thu có răng: build với Dockerfile hỏng cục bộ (thêm lệnh sai tạm) → bước build fail local; hoàn tác.

Commit: `ci: build image, boot compose stack and run browser smoke on every push`

## HM4 — Dọn trạng thái docs treo + nghiệm thu tổng

1. Sửa trạng thái các plan/spec cũ ghi "chờ" dù đã chạy (kho 07-29, room-config 08-02...) — một commit docs.
2. Chạy tiêu chí spec mục 4 (1–5). Push, xem run Actions đầu tiên có 4 job xanh (bạn xác nhận trên tab Actions hoặc cài `gh` để mình tự xem).

## Ước tính & rủi ro

- ~nửa ngày. Rủi ro chính: chờ stack trong CI chậm (mysql image pull) — dùng cache layer GHA mặc định, chấp nhận job ~4-6 phút; Playwright trên macOS local cần `playwright install` một lần (~120MB).
- Dialog `prompt()` của add-room là API cổ — nếu Playwright xử lý phập phù, đổi UI sang modal nhỏ (ghi chú trong plan, chỉ làm nếu vướng).
