# Spec: Production hardening

**Ngày:** 15-08-2026
**Trạng thái:** Đã chốt phạm vi (chủ dự án duyệt nhóm việc 14-08)
**Nguồn:** 12 phát hiện của audit ops 14-08.
**Không bao gồm:** giám sát/alert bên ngoài (Sentry/uptime — cần tài khoản dịch vụ, để đợt sau), CDN, multi-replica thật sự (single-node compose).

## 1. Kết quả cần đạt

`docker compose up -d` trên server trắng cho ra hệ thống: HTTPS qua reverse proxy, tự khởi động lại khi crash/reboot, MySQL không lộ cổng, container không chạy root, có log truy cập + log app persist qua rotation, backup DB tự động hằng ngày có retention, web có healthcheck thật, migration chạy một lần tách khỏi web. Dev giữ nguyên thói quen cũ nhờ `docker-compose.override.yml` (compose tự nạp): cổng nội bộ 127.0.0.1, adminer bật.

## 2. Thiết kế

| # | Hạng mục | Thiết kế |
|---|---|---|
| 1 | `/healthz` | Route công khai không tenant/không auth: `SELECT 1` vào DB, trả `{"status":"ok"}` 200 hoặc 503; dùng cho compose healthcheck (python urllib — slim image không có curl) và uptime check sau này |
| 2 | Logging | `create_app`: cấu hình `logging` INFO ra stdout (trừ TESTING); `notification_service` bỏ `print` dùng logger; compose: json-file driver `max-size=10m, max-file=5` |
| 3 | Gunicorn | `docker/gunicorn.conf.py`: `workers` từ env `WEB_CONCURRENCY` (mặc định 2), `timeout=60`, `accesslog='-'`, `max_requests=1000` + jitter 50 |
| 4 | Non-root | Dockerfile tạo user `app`, `USER app` |
| 5 | Migration tách | Service `migrate` one-shot (`flask db upgrade`), `web` `depends_on: migrate: service_completed_successfully` — hết race khi scale, web boot là phục vụ ngay |
| 6 | Restart | `restart: unless-stopped` cho web/db/proxy/backup |
| 7 | Đóng 3306 | Bỏ `ports` của db ở file base; override dev publish `127.0.0.1:3306` |
| 8 | HTTPS | Service `caddy` reverse proxy → web:8000; `DOMAIN` trong `.env`: có domain thật → auto-TLS Let's Encrypt, không có → `:80` + cảnh báo. `SESSION_COOKIE_SECURE` đọc từ env (mặc định production = true); triển khai LAN thuần HTTP phải chủ động đặt `SESSION_COOKIE_SECURE=false` — không còn hỏng login âm thầm |
| 9 | MAIL_* | Compose truyền `MAIL_SERVER/PORT/USE_TLS/USERNAME/PASSWORD/DEFAULT_SENDER` vào web |
| 10 | Backup | Service `db-backup` (image mysql:8): vòng lặp mỗi 24h `mysqldump --single-transaction` toàn bộ db `hotel` → volume bind `./backups/hotel-YYYYmmdd-HHMM.sql.gz`, xóa bản > `BACKUP_RETENTION_DAYS` (mặc định 14) |
| 11 | Secret rotation | Bổ sung mục vào `docs/production-remediation-runbook.md`: quy trình xoay SECRET_KEY (hệ quả: đăng xuất toàn bộ phiên), xoay MYSQL_PASSWORD, lịch khuyến nghị + diễn tập restore backup |

## 3. Tiêu chí nghiệm thu

1. `GET /healthz` → 200 khi DB sống; compose `docker inspect` web = healthy.
2. `docker compose config` hợp lệ; up từ trạng thái sạch: migrate chạy xong → web healthy → proxy phục vụ.
3. Từ host: cổng 3306 và 8000 KHÔNG mở ở file base (chỉ proxy 80/443); override dev vẫn cho 127.0.0.1.
4. `docker compose exec web whoami` ≠ root.
5. Chạy tay một vòng backup: file `.sql.gz` xuất hiện, giải nén đọc được schema; file cũ hơn retention bị xóa.
6. Log: gunicorn access log xuất hiện trong `docker compose logs web`; app log qua logger (không print).
7. Full regression 434 test hiện có xanh (đổi hạ tầng không đổi hành vi app, trừ route `/healthz` mới có test riêng).
