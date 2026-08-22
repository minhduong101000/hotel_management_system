# Runbook: Khôi phục dữ liệu từ bản sao lưu

**Đã diễn tập thật ngày 22-08-2026 và thành công** — xem mục "Kết quả diễn tập"
ở cuối. Các bước dưới đây là đúng những lệnh đã chạy, không phải lý thuyết.

---

## Bản sao lưu nằm ở đâu

Container `db-backup` chạy `mysqldump` mỗi ngày một lần, nén gzip, ghi vào thư
mục `backups/` ở gốc repo. Giữ lại **14 ngày** (`BACKUP_RETENTION_DAYS`), quá hạn
thì tự xoá.

```bash
ls -lt backups/*.sql.gz | head
```

Tệp mới nhất nằm trên cùng. Tên có dạng `hotel-YYYYMMDD-HHMMSS.sql.gz`, giờ trong
tên là **giờ UTC** (container chạy UTC), tức trễ 7 tiếng so với giờ Việt Nam.

---

## Trước khi khôi phục: đọc đoạn này

Khôi phục là thao tác **ghi đè**. Nếu khôi phục thẳng vào cơ sở dữ liệu đang chạy
thì mọi thứ phát sinh sau thời điểm bản sao lưu đó sẽ **mất vĩnh viễn** — mọi
booking, mọi khoản thu, mọi thay đổi.

Nên thứ tự luôn là:

1. **Sao lưu ngay cái đang có trước đã**, kể cả khi nó đang hỏng. Hỏng vẫn còn
   hơn không có.
2. Khôi phục vào **cơ sở dữ liệu tạm** rồi đối chiếu.
3. Chỉ khi đã chắc mới đổi sang dùng nó.

---

## Cách 1 — Kiểm tra một bản sao lưu (an toàn, không đụng dữ liệu thật)

Dùng khi muốn biết bản sao lưu có dùng được không, hoặc muốn xem lại dữ liệu cũ.
**Không ảnh hưởng gì tới hệ thống đang chạy.**

```bash
set -a; source .env; set +a
NEWEST=$(ls -t backups/*.sql.gz | head -1)
echo "Sẽ khôi phục: $NEWEST"

# Tạo một cơ sở dữ liệu tạm, tên riêng, không đụng cái thật
docker compose exec -T db sh -c \
  "mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -e 'DROP DATABASE IF EXISTS restore_drill; CREATE DATABASE restore_drill CHARACTER SET utf8mb4;'"

# Đổ bản sao lưu vào đó
gzip -dc "$NEWEST" | docker compose exec -T db sh -c \
  "mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" restore_drill"
echo "mã thoát: $?"     # PHẢI là 0
```

Rồi đối chiếu với hệ thống đang chạy:

```bash
set -a; source .env; set +a
docker compose exec -T db sh -c "mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -N -B -e \"
SELECT 'khoi_phuc' src, COUNT(DISTINCT b.id) so_don, IFNULL(SUM(p.amount),0) tong_tien
  FROM restore_drill.bookings b
  LEFT JOIN restore_drill.payments p ON p.booking_id=b.id
UNION ALL
SELECT 'dang_chay', COUNT(DISTINCT b.id), IFNULL(SUM(p.amount),0)
  FROM \\\`\$MYSQL_DATABASE\\\`.bookings b
  LEFT JOIN \\\`\$MYSQL_DATABASE\\\`.payments p ON p.booking_id=b.id;\""
```

Xong thì dọn:

```bash
docker compose exec -T db sh -c \
  "mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -e 'DROP DATABASE IF EXISTS restore_drill;'"
```

---

## Cách 2 — Khôi phục thật (khi dữ liệu đang chạy đã hỏng)

> **Dừng lại một nhịp.** Mọi thứ phát sinh sau thời điểm bản sao lưu sẽ mất.
> Nếu chưa chắc chắn, làm Cách 1 trước.

**Bước 1 — cứu lấy hiện trạng trước đã.** Kể cả khi nó đang hỏng.

```bash
docker compose run --rm -e ONE_SHOT=1 db-backup
ls -lt backups/*.sql.gz | head -2
```

**Bước 2 — dừng ứng dụng**, để không ai ghi thêm trong lúc khôi phục.

```bash
docker compose stop web
```

**Bước 3 — khôi phục.**

```bash
set -a; source .env; set +a
CHON=backups/hotel-XXXXXXXX-XXXXXX.sql.gz     # điền tên tệp muốn dùng

gzip -dc "$CHON" | docker compose exec -T db sh -c \
  "mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" \"\$MYSQL_DATABASE\""
echo "mã thoát: $?"     # PHẢI là 0. Khác 0 thì DỪNG, đừng bật web lên.
```

**Bước 4 — kiểm tra trước khi mở cửa lại.**

```bash
set -a; source .env; set +a
docker compose exec -T db sh -c "mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -N -B -e \"
SELECT CONCAT('phien ban migration: ', version_num) FROM \\\`\$MYSQL_DATABASE\\\`.alembic_version;
SELECT CONCAT('so don: ', COUNT(*)) FROM \\\`\$MYSQL_DATABASE\\\`.bookings;
SELECT CONCAT('so khoan thu: ', COUNT(*)) FROM \\\`\$MYSQL_DATABASE\\\`.payments;\""
```

**Bước 5 — bật lại và xác nhận.**

```bash
docker compose start web
sleep 8
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/healthz    # phải là 200
```

Nếu `phien ban migration` khác với mã migration mới nhất của code đang chạy, chạy
thêm:

```bash
docker compose run --rm migrate
```

---

## Khi bộ canh báo backup có vấn đề

Cảnh báo Telegram 🔴 về backup nghĩa là một trong bốn: chưa có tệp nào, tệp mới
nhất rỗng, giải nén lỗi, hoặc đã quá 26 giờ.

```bash
docker compose logs --tail=50 db-backup      # xem nó báo gì
ls -lh backups/ | tail -5                    # tệp mới nhất bao nhiêu byte
gzip -t backups/hotel-XXXXXXXX-XXXXXX.sql.gz # còn giải nén được không
docker compose run --rm -e ONE_SHOT=1 db-backup   # chạy tay một vòng
```

Tệp mới nhất **rỗng hoặc cụt** là dấu hiệu `mysqldump` chết giữa chừng — shell
tạo tệp trước khi dump chạy xong, nên tên và giờ vẫn đúng dù bên trong không có
gì. Đó là lý do bộ canh kiểm cả nội dung chứ không chỉ kiểm tên.

---

## Kết quả diễn tập 22-08-2026

Khôi phục `backups/hotel-20260821-172425.sql.gz` (12 KB) vào một cơ sở dữ liệu
tạm rồi đối chiếu với hệ thống đang chạy:

| Hạng mục | Bản khôi phục | Đang chạy |
| --- | --- | --- |
| Mã thoát `mysql` | 0 | — |
| Số bảng | 19 | 19 |
| Khoá ngoại | 40 | 40 |
| Phiên bản migration | `d0e1f2a3b4c5` | `d0e1f2a3b4c5` |
| `users` / `customers` / `rooms` | 2 / 3 / 3 | 2 / 3 / 3 |
| `bookings` / `booking_rooms` | 52 / 67 | 52 / 67 |
| `payments` / `audit_events` | 55 / 71 | 55 / 71 |
| Truy vấn nghiệp vụ (đơn + tổng thu) | 52 đơn, 13.465.000 đ | 52 đơn, 13.465.000 đ |

Khớp tuyệt đối, kể cả khoá ngoại và phiên bản migration — nghĩa là ứng dụng chạy
được thẳng trên bản khôi phục mà không cần vá gì thêm.

**Nên diễn tập lại** sau mỗi lần đổi cấu trúc dữ liệu lớn, hoặc mỗi quý. Bản sao
lưu chưa từng khôi phục thử chỉ là một lời phỏng đoán.

---

## Một dòng nên sửa trong `.env`

```
BACKUP_RETENTION_DAYS=90
```

Đang chạy mặc định **14 ngày**, nghĩa là toàn bộ khả năng quay ngược thời gian
chỉ có hai tuần. Hỏng dữ liệu phát hiện sau ba tuần thì mọi bản còn sống đều đã
mang sẵn cái hỏng. Bản dump hiện 12 KB, nên 90 bản vẫn không đáng kể về dung
lượng.
