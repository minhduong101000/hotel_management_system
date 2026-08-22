# Runbook: Cảnh báo vận hành qua Telegram

## Cài lần đầu

1. Mở Telegram, nhắn `/newbot` cho **@BotFather**. Đặt tên bot. Nhận token dạng
   `123456789:AAH...`.
2. Nhắn một câu bất kỳ cho bot vừa tạo. (Muốn cả nhóm cùng nhận thì thêm bot vào
   group rồi nhắn trong group.)
3. Mở `https://api.telegram.org/bot<TOKEN>/getUpdates`, tìm `"chat":{"id":...}`.
   Group thì `id` là số âm — giữ nguyên dấu trừ.
4. Điền vào `.env` trên VPS:
   ```
   TELEGRAM_BOT_TOKEN=123456789:AAH...
   TELEGRAM_CHAT_ID=-1001234567890
   ```
5. `docker compose up -d alerts`
6. Xác nhận đường dây thông trước khi tin tưởng nó:
   ```bash
   docker compose run --rm alerts python -m scripts.alert_watch --test-message
   ```
   Không thấy tin thì xem log: `docker compose logs alerts`.
7. `--test-message` KHÔNG đọc/ghi trạng thái, nên nó không chứng minh được là
   volume `/state` thật sự ghi được — nếu quyền sai, mọi chu kỳ sau đó âm thầm
   chạy lại từ trạng thái rỗng (không ngưỡng dồn lỗi web, báo lại mỗi 5 phút
   cho backup/đĩa, spam tin sáng cả ngày) mà bước 6 vẫn xanh. Chạy thêm một chu
   kỳ thật rồi soi trạng thái đã ghi:
   ```bash
   docker compose run --rm alerts python -m scripts.alert_watch --once
   docker compose run --rm alerts sh -c 'ls -l /state && cat /state/alerts.json'
   ```
   Phải thấy `alerts.json` tồn tại, chứa cả ba mục `web`/`backup`/`disk`.

## Nâng cấp từ bản cũ — đọc trước khi deploy lại

Một bản dựng trước đây tạo volume `/state` **thuộc root**, trong khi container
chạy bằng người dùng `app`. Docker chỉ gán quyền từ image khi volume **còn
rỗng**, nên `docker compose build && up -d` **không sửa** một volume đã tồn tại.

Hậu quả nếu bỏ qua: bộ canh chạy, log không có gì bất thường với người không để
ý, nhưng nó **không ghi được trạng thái**. Khi đó cảnh báo web chết **không bao
giờ kêu** (bộ đếm luôn về 0), còn tin sáng gửi lại mỗi 5 phút.

Nếu máy đã từng chạy bộ canh trước ngày 22-08-2026, xoá volume trạng thái một
lần rồi dựng lại:

```bash
docker compose stop alerts
docker volume rm hotel_management_system_alert_state
docker compose up -d alerts
```

Mất lịch sử chống trùng lặp là chuyện nhỏ — cùng lắm nhận lại một tin cho mỗi
sự cố đang mở.

**Sau MỌI lần nâng cấp**, chạy lại bước 7 ở trên. Nó là bước duy nhất chứng minh
trạng thái ghi được; `--test-message` không đụng tới trạng thái nên vẫn báo thành
công kể cả khi mọi thứ đang hỏng.

Dấu hiệu trong log khi trúng lỗi này:

```
[alerts] ghi trạng thái lỗi: Permission denied — /state/alerts.json
```

## Ba thứ nó canh

| Canh gì | Kêu khi |
| --- | --- |
| Web + DB | `/healthz` hỏng 2 chu kỳ liên tiếp (~10 phút, với cấu hình mặc định) |
| Backup | chưa có bản sao lưu nào, tệp mới nhất rỗng, giải nén lỗi, hoặc đã quá 26 giờ |
| Đĩa | đã dùng ≥ 85% (đo trên ổ chứa thư mục `backups`) |

Chỉ báo khi **đổi trạng thái**, và nhắc lại mỗi 6 giờ nếu vẫn hỏng. Đang hỏng
mà chưa tới hạn nhắc thì im lặng — không có chuyện kêu mỗi 5 phút.

Các con số trên (2 chu kỳ, 26 giờ, 85%, 6 giờ) là giá trị mặc định trong
`.env.example` (`ALERT_WEB_FAIL_THRESHOLD`, `ALERT_BACKUP_MAX_AGE_HOURS`,
`ALERT_DISK_THRESHOLD_PERCENT`, `ALERT_REPEAT_HOURS`) — chỉnh trực tiếp trong
`.env` trên VPS nếu cần khác đi, rồi `docker compose up -d alerts` để áp dụng.

## Tin sáng

07:00 mỗi ngày theo giờ nghiệp vụ của hệ thống (múi giờ `Asia/Bangkok`,
UTC+7 — cùng giờ với Việt Nam), kể cả khi mọi thứ bình thường. Đổi giờ bằng
`ALERT_SUMMARY_HOUR` trong `.env`.

**Không có tin sáng nghĩa là bộ canh đã chết** — container tắt, token hỏng, hoặc
VPS ngừng chạy. Đó là toàn bộ mục đích của tin này: yên lặng không còn đồng
nghĩa với ổn.

## Khi nhận được cảnh báo

**🔴 Web:** `docker compose ps` xem `web` còn sống không.
`docker compose logs --tail=100 web`. Thường là restart lỗi hoặc db không lên.

**🔴 Backup:** `docker compose logs --tail=50 db-backup`. Nếu tệp rỗng hoặc hỏng
thì chạy tay một vòng:
`docker compose run --rm -e ONE_SHOT=1 db-backup`.

**🔴 Đĩa:** `df -h`, rồi `du -sh backups/*`. Giảm `BACKUP_RETENTION_DAYS` nếu
bản sao lưu chiếm quá nhiều, hoặc dọn log docker.

Khi vấn đề đã xử lý xong, bộ canh tự nhận ra ở chu kỳ kiểm kế tiếp (tối đa
`ALERT_INTERVAL_SECONDS`, mặc định 5 phút) và gửi tin 🟢 báo đã trở lại bình
thường — không cần làm gì thêm để "tắt" cảnh báo đỏ.

## Tắt tạm

Bỏ trống `TELEGRAM_BOT_TOKEN` trong `.env` rồi `docker compose up -d alerts`.
Bộ canh vẫn chạy, vẫn ghi trạng thái, chỉ không gửi gì.
