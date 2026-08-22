# Spec: Cảnh báo vận hành qua Telegram

**Nguồn:** rà soát vận hành 22-08-2026. Hiện tại chủ khách sạn biết có sự cố bằng
cách lễ tân gọi điện — không có kênh nào khác.

**Chủ dự án đã chốt:**
- Kênh: **Telegram** (một bot, một đoạn chat).
- Có **tin tóm tắt mỗi sáng**, gửi vào cùng đoạn chat đó.
- **Không** thêm dịch vụ canh từ bên ngoài. Cả VPS tắt thì lễ tân thấy ngay và gọi;
  thứ đang vô hình là backup hỏng và đĩa đầy, và cả hai đều thấy được từ bên trong.

---

## 1. Vấn đề

Ba hỏng hóc hiện đang **im lặng hoàn toàn**:

| Hỏng gì | Hôm nay biết bằng cách nào | Hậu quả nếu không biết |
| --- | --- | --- |
| Container `web` chết và không tự dậy lại được | lễ tân gọi | quầy đứng |
| `db-backup` dump lỗi | không ai biết | phát hiện lúc cần khôi phục thì đã muộn |
| Đĩa đầy | không ai biết | MySQL ngừng ghi, quầy đứng, không rõ nguyên nhân |

Hai cái sau nguy hiểm hơn cái đầu: `web` chết thì có người phàn nàn trong vài phút,
còn backup hỏng có thể kéo dài hàng tháng mà không ai nhận ra.

`docker-compose.yml` đã có `healthcheck` cho `web` và `restart: unless-stopped`, nên
một cú sập đơn lẻ tự phục hồi. Giá trị của cảnh báo là biết khi nó **không** dậy lại
được, chứ không phải mỗi lần nó restart.

---

## 2. Phạm vi

**Trong phạm vi:** một container canh chừng chạy cùng stack, ba phép kiểm, gửi
Telegram khi đổi trạng thái, nhắc lại khi vẫn hỏng, và một tin tóm tắt mỗi sáng.

**Ngoài phạm vi (có chủ đích):**
- Dịch vụ canh từ bên ngoài / dead-man's-switch — chủ dự án đã loại.
- Prometheus, Grafana, log tập trung. Một khách sạn không cần.
- Cảnh báo lỗi 500 của ứng dụng. Cần móc vào Flask, để đợt sau.
- Gửi email. `MAIL_*` đã có trong `x-web-env` nhưng đợt này không dùng.

---

## 3. Kiến trúc

Một service mới `alerts` trong `docker-compose.yml`, dựng từ **chính
`docker/Dockerfile` đang có** — cùng image với `web`, nên có sẵn Python và
`services/time_service.py`. Không cần base image mới, không cần cài thêm gì.

Nó **không** kết nối cơ sở dữ liệu. `/healthz` đã kiểm hộ (`app.py:138-145` chạy
`SELECT 1` và trả 503 nếu hỏng), nên một phép gọi HTTP phủ được cả web lẫn db.

```
alerts (vòng lặp 5 phút)
  ├── GET http://web:8000/healthz        → trong mạng compose
  ├── đọc /backups (mount read-only)     → tuổi + kích thước + gzip
  ├── disk_usage(/backups)               → % đã dùng
  ├── so với trạng thái ở /state/alerts.json
  └── POST api.telegram.org/bot<TOKEN>/sendMessage
```

### 3.1 Tách lớp

| Tệp | Trách nhiệm | Kiểm thử |
| --- | --- | --- |
| `services/alert_service.py` | **Thuần**: chấm điểm từng phép kiểm, quyết định gửi gì, soạn câu chữ. Nhận `now` làm tham số, không gọi mạng, không đọc đĩa. | pytest phủ kín, không cần mạng |
| `services/telegram_service.py` | Gửi một tin. Mỏng. Cấu hình rỗng = không làm gì. | pytest với transport giả |
| `scripts/alert_watch.py` | Vòng lặp + I/O thật: HTTP, đọc thư mục, `disk_usage`, đọc/ghi tệp trạng thái. | kiểm tay qua `--once` |

Ranh giới đặt ở đó vì **toàn bộ phần dễ sai là phần quyết định**, và phần đó không
cần I/O nào để kiểm.

---

## 4. Ba phép kiểm

| Phép kiểm | Quan sát | Kêu khi |
| --- | --- | --- |
| `web` | `GET {ALERT_WEB_URL}` | thất bại **2 chu kỳ liên tiếp** (ngưỡng cấu hình được) |
| `backup` | tệp `*.sql.gz` mới nhất trong `/backups` | quá `26` tiếng, **hoặc** rỗng, **hoặc** gzip lỗi, **hoặc** thư mục không có tệp nào |
| `disk` | `shutil.disk_usage` trên phân vùng chứa `/backups` | đã dùng **đạt hoặc vượt** `85%` (`>=`) |

Hai phép so sánh cố ý khác nhau: tuổi backup dùng `>` (đúng 26 tiếng chưa kêu),
đĩa dùng `>=` (đúng 85% đã kêu). Đĩa đầy là ngưỡng an toàn nên nghiêng về kêu
sớm; tuổi backup là nhịp sinh hoạt nên nghiêng về không kêu oan.

### 4.1 Vì sao `web` phải hỏng hai lần mới kêu

`web` có healthcheck 15 giây và `restart: unless-stopped`. Nó tự dậy lại sau khi
sập. Kêu ngay từ nhịp trượt đầu tiên nghĩa là gửi tin mỗi lần deploy và mỗi lần
restart — chủ dự án sẽ tắt thông báo trong vòng một tuần, và khi đó hệ thống cảnh
báo coi như không tồn tại. Ngưỡng 2 lọc đúng lớp nhiễu đó.

### 4.2 Vì sao backup phải kiểm nội dung, không chỉ kiểm tên tệp

`docker/backup.sh` chạy `mysqldump ... | gzip > "${file}"`. Shell tạo tệp **trước
khi** `mysqldump` chạy xong. Nếu dump chết giữa chừng — hết đĩa, mất kết nối db,
container bị giết — tệp vẫn nằm đó với đúng tên và đúng dấu thời gian, chỉ là rỗng
hoặc cụt. Chỉ nhìn tên và giờ là tự lừa mình đúng vào lúc cần tin nhất.

Nên phép kiểm gồm ba tầng: **có tệp** → **không rỗng** → **giải nén được tới byte
cuối**.

### 4.3 Không giải nén lại tệp cũ mỗi 5 phút

Kiểm gzip phải đọc hết tệp. Với bản dump lớn, làm việc đó mỗi 5 phút là phí I/O vô
ích. Trạng thái ghi nhớ `(tên, kích thước, mtime, gzip_ok)` của tệp đã kiểm; chỉ
kiểm lại khi bộ ba đầu thay đổi.

---

## 5. Chống làm phiền

Một bot kêu quá nhiều bị tắt thông báo, và bot bị tắt thông báo thì vô dụng y như
không có. Đây là phần quyết định hệ thống này sống hay chết.

Mỗi phép kiểm giữ **hai** trạng thái:

- `status` — vừa quan sát được. **Luôn** cập nhật.
- `notified_status` — trạng thái gần nhất đã **báo thành công** cho người dùng.

Gửi tin khi:
1. `status != notified_status` — đổi trạng thái (ổn→hỏng 🔴, hỏng→ổn 🟢), hoặc
2. `status` đang hỏng và đã quá `ALERT_REPEAT_HOURS` (mặc định 6) kể từ
   `last_notified_at` — nhắc lại để sự cố kéo dài không bị quên.

Đang hỏng mà chưa tới hạn nhắc: **im lặng**. Không có chuyện gửi mỗi 5 phút.

### 5.1 Chỉ ghi nhận sau khi gửi thành công

`notified_status` và `last_notified_at` **chỉ** được cập nhật khi Telegram trả về
thành công. `status` thì luôn cập nhật.

Đây là chỗ dễ sai nhất của toàn bộ thiết kế. Nếu ghi `notified_status` trước khi
gửi, thì một lần Telegram lỗi mạng sẽ khiến chu kỳ sau so ra "không đổi trạng
thái" — và cảnh báo đó **mất vĩnh viễn**. Hệ thống trông vẫn khoẻ mạnh trong khi
đã nuốt mất đúng cái tin quan trọng nhất.

Tách `status` khỏi `notified_status` làm việc thử lại thành hệ quả tự nhiên: chu
kỳ sau vẫn thấy lệch, vẫn gửi.

---

## 6. Tin tóm tắt mỗi sáng

Mỗi ngày một tin vào lúc `ALERT_SUMMARY_HOUR` (mặc định **7**) **giờ Việt Nam**,
gồm cả ba trạng thái:

```
☀️ Hotel POS — 22/08/2026
✅ Web: bình thường
✅ Backup: bản mới nhất 3 giờ trước (hotel-20260822-000102.sql.gz, 9.2 MB)
✅ Đĩa: đã dùng 42%
```

Mục đích không phải khoe mọi thứ đang ổn, mà là **chứng minh bot còn sống**. Không
có tin sáng = bot chết, token hỏng, hoặc container không chạy — và chủ dự án biết
điều đó ngay, thay vì tưởng "yên lặng nghĩa là ổn".

Điều kiện gửi: `business_now().hour >= ALERT_SUMMARY_HOUR` **và**
`last_summary_date != business_today()`. Nghĩa là nếu container tắt lúc 7h và bật
lại lúc 9h thì tin vẫn được gửi bù, không mất ngày.

`last_summary_date` cũng chỉ cập nhật **sau khi gửi thành công**, theo đúng nguyên
tắc mục 5.1.

---

## 7. Hợp đồng thời gian

Đợt 22-08 vừa gỡ `db.func.now()` khỏi `models/` để `time_service` là nguồn duy
nhất. Thiết kế này giữ nguyên nguyên tắc đó:

- **Tuổi backup**: `mtime` của tệp là dấu thời gian POSIX (epoch), **không phụ
  thuộc múi giờ**. Đổi sang UTC-naive rồi so với `time_service.utc_now_naive()`.
- **Giờ gửi tin sáng và ngày của tin**: `time_service.business_now()` và
  `time_service.business_today()` — 7 giờ sáng nghĩa là 7 giờ sáng Việt Nam, kể cả
  khi container chạy UTC.

Cần thêm một hàm vào `services/time_service.py`:

```python
def utc_naive_from_timestamp(timestamp: float) -> datetime:
    """Đổi dấu thời gian POSIX sang UTC-naive.

    Dùng cho mtime của tệp. Không đi qua giờ máy, nên đúng bất kể container đặt
    TZ gì — chính là điều `datetime.fromtimestamp()` trần KHÔNG đảm bảo.
    """
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)
```

Đặt ở `time_service` chứ không ở `alert_service` để giữ đúng "một nguồn duy nhất",
và để lưới `tests/test_no_ambient_now.py` vẫn bao được.

---

## 8. Cấu hình

Tất cả qua biến môi trường, thêm vào `.env.example` với giá trị rỗng/mặc định.

| Biến | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | *(rỗng)* | Rỗng = **tắt hẳn**, không cố gửi gì |
| `TELEGRAM_CHAT_ID` | *(rỗng)* | Rỗng = tắt hẳn |
| `ALERT_INTERVAL_SECONDS` | `300` | Chu kỳ vòng lặp |
| `ALERT_WEB_URL` | `http://web:8000/healthz` | Trong mạng compose |
| `ALERT_WEB_FAIL_THRESHOLD` | `2` | Số chu kỳ hỏng liên tiếp mới kêu |
| `ALERT_BACKUP_DIR` | `/backups` | Mount read-only |
| `ALERT_BACKUP_MAX_AGE_HOURS` | `26` | Cho lịch dump hằng ngày |
| `ALERT_DISK_THRESHOLD_PERCENT` | `85` | |
| `ALERT_REPEAT_HOURS` | `6` | Nhắc lại khi vẫn hỏng |
| `ALERT_SUMMARY_HOUR` | `7` | Giờ Việt Nam |
| `ALERT_STATE_FILE` | `/state/alerts.json` | Volume riêng, sống qua restart |

**Rỗng = tắt** là mặc định có chủ đích: máy local và CI không có token nên sẽ không
bao giờ cố gọi ra Internet, và cũng không cần thêm cờ bật/tắt riêng.

`ALERT_BACKUP_MAX_AGE_HOURS` để cấu hình chứ không ghi cứng, vì nó phải đi theo
`BACKUP_INTERVAL_SECONDS` của `docker/backup.sh`. Ghi cứng thì đổi tần suất dump sẽ
khiến cảnh báo kêu oan mỗi ngày, và kêu oan thì bị tắt.

---

## 9. Khai báo trong docker-compose

```yaml
  alerts:
    build:
      context: .
      dockerfile: docker/Dockerfile
    command: ["python", "-m", "scripts.alert_watch"]
    environment:
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:-}
      TELEGRAM_CHAT_ID: ${TELEGRAM_CHAT_ID:-}
      ALERT_INTERVAL_SECONDS: ${ALERT_INTERVAL_SECONDS:-300}
      # ... các biến còn lại theo bảng mục 8
    volumes:
      - ./backups:/backups:ro
      - alert_state:/state
    depends_on:
      web:
        condition: service_started
    restart: unless-stopped
    logging: *default-logging
```

Hai chi tiết cố ý:

- **`condition: service_started`, KHÔNG phải `service_healthy`.** Nếu chờ `web`
  khoẻ mới khởi động, thì đúng vào lúc `web` hỏng ngay từ đầu — ca đáng báo nhất —
  bộ canh sẽ không bao giờ chạy để mà báo.
- **`./backups:/backups:ro`.** Bộ canh chỉ đọc. Nó không được phép xoá hay sửa
  bản sao lưu; việc dọn theo hạn là của `db-backup`.
- `/state` là volume có tên, không phải bind mount, để trạng thái sống qua
  `docker compose down` mà không rơi vào repo.

---

## 10. Chạy tay

```bash
docker compose run --rm alerts python -m scripts.alert_watch --test-message
docker compose run --rm alerts python -m scripts.alert_watch --once
```

- `--test-message` gửi một tin thử. Dùng lúc cài để xác nhận token và `chat_id`
  đúng **trước khi** tin tưởng hệ thống. Không đọc, không ghi tệp trạng thái.
- `--once` chạy đúng một chu kỳ rồi thoát, theo đúng quy ước `ONE_SHOT=1` mà
  `docker/backup.sh` đã dùng.

---

## 11. Việc chủ dự án phải làm tay

1. Nhắn `/newbot` cho **@BotFather** trên Telegram, đặt tên, nhận token.
2. Nhắn một câu bất kỳ cho bot vừa tạo (hoặc thêm bot vào group rồi nhắn).
3. Mở `https://api.telegram.org/bot<TOKEN>/getUpdates`, lấy `chat_id`.
4. Điền `TELEGRAM_BOT_TOKEN` và `TELEGRAM_CHAT_ID` vào `.env` trên VPS.
5. `docker compose up -d alerts`, rồi chạy `--test-message` để xác nhận.

Sẽ viết thành runbook `docs/runbooks/telegram-alerts.md` trong lúc triển khai.

**Khuyến nghị kèm theo (một dòng `.env`, không phải việc code):** đặt
`BACKUP_RETENTION_DAYS=90`. Hiện đang chạy mặc định 14, nghĩa là khả năng quay
ngược thời gian chỉ có 14 ngày — hỏng dữ liệu phát hiện sau 3 tuần thì mọi bản còn
sống đều đã mang sẵn cái hỏng. Bản dump hiện chỉ 9KB nên 90 bản vẫn không đáng kể.

---

## 12. Bảo mật

- Token nằm trong `.env`, **không** commit. `.env.example` chỉ có khoá rỗng.
- Không bao giờ ghi token ra log, kể cả khi gửi lỗi. Thông báo lỗi chỉ được nêu mã
  HTTP, không nêu URL đầy đủ (URL Telegram **chứa** token).
- Nội dung tin nhắn không chứa dữ liệu khách, chỉ trạng thái vận hành.
- Bộ canh mount `/backups` **read-only**.

---

## 13. Kiểm chứng

### 13.1 Phần thuần (`services/alert_service.py`)

- `web`: dưới ngưỡng → ổn; đạt ngưỡng → hỏng.
- `backup`: thư mục rỗng → hỏng; tệp 0 byte → hỏng; gzip lỗi → hỏng; quá tuổi →
  hỏng; tệp tốt và mới → ổn.
- `backup`: **đúng biên** — đúng bằng `max_age_hours` thì chưa kêu, quá một phút
  thì kêu.
- `disk`: dưới ngưỡng → ổn; đúng ngưỡng và trên ngưỡng → hỏng.
- Chuyển trạng thái: ổn→hỏng gửi 🔴; hỏng→ổn gửi 🟢; hỏng→hỏng chưa tới hạn nhắc →
  **không gửi gì**; hỏng→hỏng đã quá hạn nhắc → gửi lại.
- **Gửi thất bại thì chu kỳ sau phải gửi lại** — dựng trạng thái với
  `status='fail'`, `notified_status='ok'` và khẳng định vẫn sinh ra tin. Đây là
  test quan trọng nhất của mục 5.1.
- Tin sáng: chưa tới giờ → không gửi; tới giờ và chưa gửi hôm nay → gửi; đã gửi
  hôm nay → không gửi; tắt lúc 7h bật lại lúc 9h → vẫn gửi bù.
- Tin sáng dùng **giờ nghiệp vụ**: chạy test dưới cả `TZ=UTC` lẫn
  `TZ=Asia/Ho_Chi_Minh`, kết quả phải giống nhau.

### 13.2 Phần gửi (`services/telegram_service.py`)

- Cấu hình rỗng → không gọi mạng, trả về "đã tắt".
- Cấu hình đủ → POST đúng URL và payload (dùng transport giả).
- Telegram trả lỗi → trả về thất bại, **không** ném ngoại lệ làm chết vòng lặp.
- Thông báo lỗi **không** chứa token.

### 13.3 Khai báo hạ tầng

- `docker-compose.yml` có service `alerts`, mount `/backups` read-only, dùng
  `condition: service_started`.
- `.env.example` có đủ khoá của bảng mục 8.

### 13.4 Kiểm tay khi triển khai

1. `--test-message` → tin tới Telegram.
2. Dừng `web` (`docker compose stop web`), chờ 2 chu kỳ → nhận tin 🔴. Bật lại →
   nhận tin 🟢.
3. `touch -d '3 days ago'` lên tệp backup mới nhất trong một thư mục thử → nhận
   tin backup quá hạn.
4. Ghi một tệp rỗng `.sql.gz` mới nhất → nhận tin "backup rỗng/hỏng".
