# P1 — Config + Docker + Vá bảo mật: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `git clone` + điền `.env` + `docker compose up` = hệ thống chạy trên máy trắng; 4 lỗ hổng bảo mật đã vá; bảng `users`/`service_orders` chữ thường qua migration đầu tiên.

**Architecture:** Giữ nguyên app module-level (factory là việc của P2). Config đọc từ `.env` qua `config.py` class-based. Compose 3 service: `web` (gunicorn :8000) + `db` (MySQL 8, volume mới, user riêng — bỏ hẳn root/123456 đã lộ) + `adminer` (profile dev). Migration baseline sinh từ model trên DB trống với tên bảng đã sửa. Mỗi fix bảo mật đi theo nhịp red→green bằng curl (chưa có pytest — P4).

**Tech Stack:** Flask 3.1.3, Flask-Migrate/Alembic, gunicorn, MySQL 8, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-08-14-p1-config-docker-security-design.md`

## Global Constraints

- Làm trên nhánh `dev`. Không sửa logic nghiệp vụ, không đổi tên class Python (P3), không đụng `models/__init__.py` (P2).
- Sau MỖI task: app vẫn đăng nhập được (mục 1 checklist smoke) trước khi commit.
- Secrets sinh bằng `openssl rand -hex 32` — không tự bịa chuỗi; không ghi secret thật vào bất kỳ file tracked nào (`.env` đã nằm trong `.gitignore`).
- Chuỗi kết nối cũ `root:123456@localhost/Hotel_Management_System` phải biến mất khỏi source sau Task 1; container `hotel-mysql-legacy` giữ ở trạng thái stopped làm rollback, không xóa trong P1.
- Commit message một dòng tiếng Anh + trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Config ra `.env` (config.py + .env + .env.example + app.py)

**Files:**
- Modify: `config.py` (đang rỗng 0 byte)
- Create: `.env` (không commit), `.env.example` (commit)
- Modify: `app.py:20-23` (bỏ 3 dòng config hardcode)

**Interfaces:**
- Produces: `get_config(name)` trả class config theo `FLASK_CONFIG` (`development`/`testing`/`production`); `TestConfig` dùng SQLite in-memory — P2/P4 dựa vào đây. Biến env chuẩn: `SECRET_KEY`, `DATABASE_URL`, `FLASK_CONFIG`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `MYSQL_*`.

- [ ] **Step 1: Viết `config.py`**

```python
import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


class BaseConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevConfig(BaseConfig):
    DEBUG = True


class TestConfig(BaseConfig):
    TESTING = True
    SECRET_KEY = 'test-secret-key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


class ProdConfig(BaseConfig):
    DEBUG = False


_config_map = {
    'development': DevConfig,
    'testing': TestConfig,
    'production': ProdConfig,
}


def get_config(name=None):
    name = name or os.environ.get('FLASK_CONFIG', 'development')
    if name == 'production':
        missing = [k for k in ('SECRET_KEY', 'DATABASE_URL') if not os.environ.get(k)]
        if missing:
            raise RuntimeError(f'Thiếu biến môi trường bắt buộc cho production: {missing}')
    return _config_map[name]
```

- [ ] **Step 2: Tạo `.env` (tạm thời vẫn trỏ DB legacy để app chạy tiếp; Task 4 sẽ đổi sang DB mới)**

```bash
SECRET=$(openssl rand -hex 32)
cat > .env <<EOF
FLASK_CONFIG=development
SECRET_KEY=$SECRET
DATABASE_URL=mysql+pymysql://root:123456@localhost:3306/Hotel_Management_System
EOF
```

- [ ] **Step 3: Tạo `.env.example` (commit — chỉ placeholder, không secret thật)**

```bash
cat > .env.example <<'EOF'
# Copy thành .env rồi điền giá trị thật. Sinh secret: openssl rand -hex 32
FLASK_CONFIG=development
SECRET_KEY=changeme-openssl-rand-hex-32
DATABASE_URL=mysql+pymysql://hotel:changeme@localhost:3306/hotel

# Cho container db (docker-compose)
MYSQL_ROOT_PASSWORD=changeme-root
MYSQL_DATABASE=hotel
MYSQL_USER=hotel
MYSQL_PASSWORD=changeme

# Tài khoản admin đầu tiên (flask seed-admin)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme-strong-password
EOF
```

- [ ] **Step 4: Sửa `app.py` — thay 3 dòng hardcode (20–23) bằng config module**

Thay:
```python
app = Flask(__name__)
app.config['SECRET_KEY'] = 'luxury-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:123456@localhost/Hotel_Management_System'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
```
bằng:
```python
from config import get_config

app = Flask(__name__)
app.config.from_object(get_config())
```

- [ ] **Step 5: Verify — restart app, đăng nhập OK, secret sạch**

```bash
pkill -f "python app.py"; sleep 1
venv/bin/python app.py > /tmp/hotel-app.log 2>&1 &
sleep 3
curl -s -o /dev/null -w "login page: %{http_code}\n" http://127.0.0.1:5000/login
curl -s -D - -o /dev/null -d "username=admin&password=123456" http://127.0.0.1:5000/login | grep -i location
grep -rn "luxury-secret-key\|root:123456" --include="*.py" . && echo "FAIL: còn secret" || echo "PASS: source sạch secret"
```
Expected: `login page: 200`; `Location: /dashboard/room-map`; `PASS`.

- [ ] **Step 6: Commit**

```bash
git add config.py .env.example app.py
git commit -m "Externalize config to .env via class-based config.py"
```
(kèm trailer — xem Global Constraints; `.env` KHÔNG được vào commit: `git status` phải sạch sau add.)

---

### Task 2: Bốn vá bảo mật

**Files:**
- Modify: `controllers/auth_controller.py:19-23` (xóa backdoor)
- Modify: `app.py:49-58` (xóa route `/init-db`, thêm CLI `seed-admin`)
- Modify: `controllers/customer_controller.py` (6 route thêm `@login_required`)
- Modify: `.env` (thêm `ADMIN_USERNAME`/`ADMIN_PASSWORD`)

**Interfaces:**
- Produces: lệnh `flask seed-admin` (idempotent — chạy lại không tạo trùng) đọc `ADMIN_USERNAME`/`ADMIN_PASSWORD` từ env; Task 5 gọi nó trong entrypoint container.

- [ ] **Step 1: RED — chứng minh 3 lỗ hổng đang mở**

```bash
curl -s -o /dev/null -w "init-db: %{http_code}\n" http://127.0.0.1:5000/init-db          # 200 = đang mở
curl -s -o /dev/null -w "customers no-auth: %{http_code}\n" http://127.0.0.1:5000/api/customers  # 200 = đang hở
grep -n "admin' and password == '123456'" controllers/auth_controller.py                  # thấy dòng = backdoor còn
```

- [ ] **Step 2: Xóa backdoor** — trong `controllers/auth_controller.py` xóa nguyên khối:

```python
        # Demo login nhanh (nếu chưa có DB thật)
        if username == 'admin' and password == '123456':
            dummy_user = User(id=1, username='admin', role='admin')
            login_user(dummy_user)
            return redirect(url_for('room.map_view'))
```

- [ ] **Step 3: Bỏ `/init-db`, thêm CLI `seed-admin`** — trong `app.py` thay nguyên hàm `init_db()` (dòng 49–58, cả decorator) bằng:

```python
@app.cli.command('seed-admin')
def seed_admin():
    """Tạo tài khoản admin đầu tiên từ ADMIN_USERNAME / ADMIN_PASSWORD trong env."""
    import os
    username = os.environ.get('ADMIN_USERNAME', 'admin')
    password = os.environ.get('ADMIN_PASSWORD')
    if not password:
        raise SystemExit('ADMIN_PASSWORD chưa được đặt trong env')
    with app.app_context():
        if User.query.filter_by(username=username).first():
            print(f'User "{username}" đã tồn tại — bỏ qua.')
            return
        db.session.add(User(username=username,
                            password_hash=generate_password_hash(password),
                            role='admin'))
        db.session.commit()
        print(f'Đã tạo admin "{username}".')
```
(`db.create_all()` bị bỏ hẳn — tạo schema từ nay là việc của migration, Task 4.)

- [ ] **Step 4: Chặn nhóm customers** — trong `controllers/customer_controller.py`: thêm `from flask_login import login_required` vào đầu file, và thêm `@login_required` dưới decorator route của cả 6 hàm: `index`, `get_customers`, `add_customer`, `update_customer`, `delete_customer` (route PUT và DELETE riêng biệt).

- [ ] **Step 5: Thêm creds admin vào `.env`**

```bash
ADMINPW=$(openssl rand -hex 16)
printf "ADMIN_USERNAME=admin\nADMIN_PASSWORD=%s\n" "$ADMINPW" >> .env
echo "Ghi lại mật khẩu admin dev: $ADMINPW"
```

- [ ] **Step 6: GREEN — restart app, cả 3 lỗ đã đóng, login thật vẫn OK**

```bash
pkill -f "python app.py"; sleep 1
venv/bin/python app.py > /tmp/hotel-app.log 2>&1 & sleep 3
curl -s -o /dev/null -w "init-db: %{http_code}\n" http://127.0.0.1:5000/init-db          # Expected: 404
curl -s -o /dev/null -w "customers no-auth: %{http_code}\n" http://127.0.0.1:5000/api/customers  # Expected: 302
curl -s -D - -o /dev/null -d "username=admin&password=123456" http://127.0.0.1:5000/login | grep -ic "location: /dashboard" || echo "backdoor CLOSED"
curl -s -D - -o /dev/null -d "username=admin&password=123456" http://127.0.0.1:5000/login | grep -i "^HTTP"
```
Lưu ý: admin seed cũ trong DB legacy vẫn có mật khẩu `123456` (do `/init-db` cũ tạo) — dòng cuối vẫn có thể redirect thành công qua **đường DB thật**; điều đó chấp nhận được ở task này. Tiêu chí "admin/123456 bị từ chối" nghiệm thu trên **DB mới** (Task 4–5) nơi admin dùng `ADMIN_PASSWORD` ngẫu nhiên.

- [ ] **Step 7: Commit** — `git add controllers/auth_controller.py app.py controllers/customer_controller.py` + commit message `security: remove login backdoor and /init-db, require login on customers API`.

---

### Task 3: Dockerfile + docker-compose + gunicorn

**Files:**
- Create: `docker/Dockerfile`, `docker-compose.yml`
- Modify: `requirements.txt` (thêm gunicorn pinned)

**Interfaces:**
- Consumes: `.env` các biến `MYSQL_*`, `SECRET_KEY`, `ADMIN_*`.
- Produces: service `db` healthy trên cổng 3306 (Task 4 migrate vào đây); service `web` :8000 chạy `flask db upgrade && flask seed-admin && gunicorn` (Task 5 nghiệm thu).

- [ ] **Step 1: Pin gunicorn**

```bash
venv/bin/pip install gunicorn
venv/bin/pip freeze | grep -i "^gunicorn==" >> requirements.txt
tail -1 requirements.txt
```

- [ ] **Step 2: Viết `docker/Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV FLASK_APP=app.py FLASK_CONFIG=production
EXPOSE 8000
CMD ["sh", "-c", "flask db upgrade && flask seed-admin && gunicorn -b 0.0.0.0:8000 -w 2 app:app"]
```

- [ ] **Step 3: Viết `docker-compose.yml`**

```yaml
services:
  web:
    build:
      context: .
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    environment:
      FLASK_CONFIG: production
      SECRET_KEY: ${SECRET_KEY}
      DATABASE_URL: mysql+pymysql://${MYSQL_USER}:${MYSQL_PASSWORD}@db:3306/${MYSQL_DATABASE}
      ADMIN_USERNAME: ${ADMIN_USERNAME}
      ADMIN_PASSWORD: ${ADMIN_PASSWORD}
    depends_on:
      db:
        condition: service_healthy

  db:
    image: mysql:8
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    ports:
      - "3306:3306"
    volumes:
      - dbdata:/var/lib/mysql
    healthcheck:
      test: ["CMD-SHELL", "mysqladmin ping -h localhost -u$$MYSQL_USER -p$$MYSQL_PASSWORD --silent"]
      interval: 5s
      timeout: 3s
      retries: 30

  adminer:
    image: adminer
    ports:
      - "8080:8080"
    profiles: ["dev"]

volumes:
  dbdata:
```

- [ ] **Step 4: Thêm creds DB mới vào `.env` và nhường cổng 3306**

```bash
DBPW=$(openssl rand -hex 16); ROOTPW=$(openssl rand -hex 16)
cat >> .env <<EOF
MYSQL_ROOT_PASSWORD=$ROOTPW
MYSQL_DATABASE=hotel
MYSQL_USER=hotel
MYSQL_PASSWORD=$DBPW
EOF
pkill -f "python app.py"
docker stop hotel-mysql-legacy
```

- [ ] **Step 5: Lên `db` mới, chờ healthy**

```bash
docker compose up -d db
until [ "$(docker inspect -f '{{.State.Health.Status}}' $(docker compose ps -q db))" = "healthy" ]; do sleep 2; done; echo DB-HEALTHY
```

- [ ] **Step 6: Commit** — `git add docker/Dockerfile docker-compose.yml requirements.txt` + message `feat: dockerize with compose (web, db, adminer) and pinned gunicorn`.

---

### Task 4: Đổi tên bảng + Flask-Migrate baseline trên DB mới

**Files:**
- Modify: `models/user.py:6` (`'Users'` → `'users'`), `models/booking_service.py:6` (`'booking_services'` → `'service_orders'`)
- Modify: `extensions.py` (thêm `migrate`), `app.py` (init migrate)
- Modify: `.env` (DATABASE_URL trỏ DB mới)
- Create: `migrations/` (flask db init + baseline)

**Interfaces:**
- Consumes: DB `hotel` trống, healthy từ Task 3.
- Produces: `migrations/versions/<rev>_baseline_schema.py` — nguồn sự thật về schema từ nay; container web chạy `flask db upgrade` dựa vào nó. Bảng: `users`, `service_orders` (+7 bảng cũ giữ tên).

- [ ] **Step 1: Sửa 2 `__tablename__`** — `models/user.py` dòng 6 thành `__tablename__ = 'users'`; `models/booking_service.py` dòng 6 thành `__tablename__ = 'service_orders'`. (Đã xác minh 14/08: không FK/chuỗi nào tham chiếu `'Users.id'` hay `'booking_services.*'` — rename tự đóng gói.)

- [ ] **Step 2: Đăng ký Flask-Migrate** — `extensions.py` thêm:

```python
from flask_migrate import Migrate
migrate = Migrate()
```
và trong `app.py`, cạnh `db.init_app(app)`:
```python
from extensions import db, login_manager, migrate
...
migrate.init_app(app, db)
```

- [ ] **Step 3: Trỏ `.env` sang DB mới** — sửa dòng `DATABASE_URL` trong `.env` thành:

```
DATABASE_URL=mysql+pymysql://hotel:<MYSQL_PASSWORD trong .env>@localhost:3306/hotel
```

- [ ] **Step 4: Sinh baseline migration trên DB trống và chạy**

```bash
export FLASK_APP=app.py
venv/bin/flask db init
venv/bin/flask db migrate -m "baseline schema"
grep -E "create_table|'users'|'service_orders'" migrations/versions/*_baseline_schema.py | head -12
venv/bin/flask db upgrade
venv/bin/flask seed-admin
```
Expected: migrate log liệt kê 9 bảng; grep thấy `'users'` và `'service_orders'`; upgrade OK; seed in `Đã tạo admin "admin"`.

- [ ] **Step 5: Verify tên bảng chữ thường trong MySQL (Linux container = case-sensitive)**

```bash
docker compose exec db mysql -uhotel -p$(grep '^MYSQL_PASSWORD=' .env | cut -d= -f2) hotel -e "SHOW TABLES"
```
Expected: 9 bảng, có `users` và `service_orders`, KHÔNG có `Users`/`booking_services`.

- [ ] **Step 6: Boot venv-app trên DB mới + reseed dữ liệu mẫu, login bằng admin mới**

```bash
venv/bin/python app.py > /tmp/hotel-app.log 2>&1 & sleep 3
docker compose exec db mysql -uhotel -p$(grep '^MYSQL_PASSWORD=' .env | cut -d= -f2) hotel -e "
INSERT INTO rooms (room_number, room_type, price_per_night, price_initial_block, initial_hours, price_next_hour, status, clean_status)
VALUES ('101','Standard',500000,100000,2,50000,'available','cleaned'),
       ('201','Deluxe',800000,150000,2,80000,'available','cleaned')"
ADMINPW=$(grep '^ADMIN_PASSWORD=' .env | cut -d= -f2)
curl -s -D - -o /dev/null -d "username=admin&password=$ADMINPW" http://127.0.0.1:5000/login | grep -i location
```
Expected: `Location: /dashboard/room-map`.

- [ ] **Step 7: Commit** — `git add models/user.py models/booking_service.py extensions.py app.py migrations/` + message `feat: Flask-Migrate baseline; rename tables to users/service_orders`.

---

### Task 5: Nghiệm thu toàn phase trên compose

**Files:**
- Modify: `docs/superpowers/specs/README.md` (P1 → ✅ khi xong)

- [ ] **Step 1: Dừng app venv, build và lên full stack**

```bash
pkill -f "python app.py"
docker compose up -d --build web
docker compose logs web --tail 5
```
Expected: log có `flask db upgrade` chạy sạch, seed-admin báo tồn tại/tạo, gunicorn `Listening at: http://0.0.0.0:8000`.

- [ ] **Step 2: Đi 6 tiêu chí nghiệm thu của spec trên http://127.0.0.1:8000**

```bash
B=http://127.0.0.1:8000
ADMINPW=$(grep '^ADMIN_PASSWORD=' .env | cut -d= -f2)
JAR=$(mktemp)
echo -n "1. login admin thật: "; curl -s -c $JAR -D - -o /dev/null -d "username=admin&password=$ADMINPW" $B/login | grep -i location
echo -n "2. secret trong source: "; grep -rn "luxury-secret-key\|root:123456\|123456@localhost" --include="*.py" . | grep -v venv && echo FAIL || echo PASS
echo -n "3. admin/123456: "; curl -s -D - -o /dev/null -d "username=admin&password=123456" $B/login | grep -ic "location: /dashboard" || echo "REJECTED (PASS)"
echo -n "4. /init-db: "; curl -s -o /dev/null -w "%{http_code}\n" $B/init-db
echo -n "5. customers no-auth: "; curl -s -o /dev/null -w "%{http_code}\n" $B/api/customers
echo "6. tables:"; docker compose exec db mysql -uhotel -p$(grep '^MYSQL_PASSWORD=' .env | cut -d= -f2) hotel -e "SHOW TABLES"
```
Expected: 1 → `/dashboard/room-map`; 2 → PASS; 3 → REJECTED; 4 → 404; 5 → 302; 6 → `users`+`service_orders` chữ thường.

- [ ] **Step 3: Đi lại 15 mục checklist smoke trên :8000** (login bằng `ADMIN_PASSWORD` mới; seed lại dịch vụ/khách qua API như baseline). Mọi mục ✅ baseline phải giữ ✅. Ghi chú thay đổi CHỦ ĐÍCH: B5 (customers cần login) và B6 (backdoor) nay đã FIXED — cập nhật hai dòng đó trong `docs/smoke-checklist.md` phần B, đánh dấu `FIXED P1 (14/08/2026)` thay vì sửa mô tả gốc.

- [ ] **Step 4: Cập nhật README sổ tổng + commit cuối**

```bash
# đổi dòng P1 thành: ✅ Xong <ngày>
git add docs/
git commit -m "Mark P1 done: verified 6 acceptance criteria on compose stack"
```

---

## Dọn dẹp & bàn giao sang P2

- `hotel-mysql-legacy` để STOPPED (rollback khi cần: `docker start hotel-mysql-legacy` + đổi `DATABASE_URL` về chuỗi cũ). Xóa hẳn sau khi P2 ổn định.
- Dev hằng ngày: `docker compose up -d db` + `venv/bin/python app.py` (config `development`), hoặc full stack `docker compose up -d --build`.
- P2 sẽ đổi gunicorn target từ `app:app` sang `wsgi:app` — một dòng trong Dockerfile.
