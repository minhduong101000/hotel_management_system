# Kế hoạch TDD: Production hardening

**Ngày:** 15-08-2026 · **Spec nguồn:** `2026-08-15-production-hardening-design.md`

Phần app (healthz, logging, cookie env) đi chu kỳ RED→GREEN pytest; phần hạ tầng (compose/Dockerfile/Caddy/backup) nghiệm thu bằng lệnh sống theo spec mục 3 — mỗi hạng mục một commit.

## HM1 — `/healthz` + logging app (pytest)

**Files:** `app.py`, `services/notification_service.py`, `config.py` (SESSION_COOKIE_SECURE từ env), `tests/test_health_and_logging.py` (mới).

RED:
1. `test_healthz_ok` — GET `/healthz` không đăng nhập → 200 `{"status":"ok"}`.
2. `test_healthz_reports_db_failure` — monkeypatch `db.session.execute` raise → 503 `{"status":"degraded"}`.
3. `test_notification_logs_instead_of_print` — caplog bắt `Hotel ... has no email` ở level INFO/WARNING.
4. `test_session_cookie_secure_env_override` — tạo app production với `SESSION_COOKIE_SECURE=false` trong env → config False; không đặt → True.

GREEN: route trong `create_app` (trước tenant preprocessor, path không chứa slug); `logging.basicConfig(level=INFO)` khi không TESTING; notification dùng `current_app.logger`; ProdConfig đọc env bool.

Commit: `feat: healthz endpoint, structured logging, configurable secure cookie`

## HM2 — Gunicorn conf, non-root, compose hardening + override dev

**Files:** `docker/gunicorn.conf.py` (mới), `docker/Dockerfile`, `docker-compose.yml`, `docker-compose.override.yml` (mới, commit — dev mặc định), `.env.example` (+`DOMAIN`, `WEB_CONCURRENCY`, `BACKUP_RETENTION_DAYS`, `SESSION_COOKIE_SECURE`, MAIL_*).

- Dockerfile: user `app`, `CMD gunicorn -c docker/gunicorn.conf.py app:app` (bỏ migrate khỏi CMD).
- compose base: service `migrate` one-shot; web `depends_on` migrate completed + db healthy; web healthcheck bằng `python -c urllib /healthz`; `restart: unless-stopped` toàn bộ; bỏ ports db; web KHÔNG publish (chỉ expose nội bộ); MAIL_* passthrough; logging json-file 10m×5.
- override dev: web `127.0.0.1:8000:8000`, db `127.0.0.1:3306:3306`, adminer bật thường.

Nghiệm thu: `docker compose config -q`; up sạch → `docker inspect` web healthy; `whoami` ≠ root; từ host `nc 3306` fail khi chạy `--no-override` (dùng `docker compose -f docker-compose.yml config | grep -A2 ports`).

Commit: `feat: hardened compose topology with one-shot migrations and non-root gunicorn`

## HM3 — Caddy reverse proxy

**Files:** `docker/Caddyfile` (mới), `docker-compose.yml` (service caddy, ports 80/443, volume caddy_data), `.env` + `.env.example` (`DOMAIN`).

Caddyfile: nếu `{$DOMAIN}` đặt → site `{$DOMAIN}` auto-TLS; mặc định fallback `:80` reverse_proxy web:8000. Nghiệm thu local: `curl -H 'Host: localhost' http://127.0.0.1/central/login` → 200 qua proxy.

Commit: `feat: caddy reverse proxy with optional auto-TLS`

## HM4 — Backup sidecar + runbook

**Files:** `docker/backup.sh` (mới), `docker-compose.yml` (service `db-backup`), `docs/production-remediation-runbook.md` (mục backup/restore + secret rotation), `.gitignore` (+`backups/`).

`backup.sh`: vòng lặp `mysqldump --single-transaction --routines hotel | gzip > /backups/hotel-$(date +%Y%m%d-%H%M).sql.gz`; `find /backups -name 'hotel-*.sql.gz' -mtime +$RETENTION -delete`; sleep 86400. Nghiệm thu: chạy 1 vòng tay (`docker compose run --rm db-backup one-shot`), kiểm file + gunzip đọc được, tạo file mtime cũ giả để kiểm retention.

Commit: `feat: daily database backup sidecar with retention` + `docs: backup restore drill and secret rotation runbook`

## HM5 — Nghiệm thu tổng

Toàn bộ 7 tiêu chí spec mục 3 + full regression hai bộ test + push. Cập nhật spec → ĐÃ TRIỂN KHAI.
