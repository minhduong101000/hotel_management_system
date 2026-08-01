# Runbook triển khai bản củng cố production

Tài liệu này dùng cho bản phát hành có thay đổi bảo mật, Alembic, schema đa tenant
và tính toàn vẹn nghiệp vụ. Thực hiện trước trên một bản sao dữ liệu production đã
ẩn thông tin nhạy cảm. Không đưa secret, mật khẩu, chuỗi kết nối thật hoặc file
backup vào repository.

## 1. Biến môi trường bắt buộc

Khai báo secret bằng secret manager của môi trường chạy, không lưu trong source,
script deploy hoặc lịch sử shell dùng chung:

```powershell
$env:APP_ENV = "production"
$env:SECRET_KEY = "<random-secret-dai-it-nhat-32-ky-tu>"
$env:DATABASE_URL = "mysql+pymysql://<db_user>:<db_password>@<db_host>/<db_name>"
```

- `APP_ENV` phải là `production`.
- `SECRET_KEY` phải ngẫu nhiên, dài ít nhất 32 ký tự và khác mọi giá trị mẫu.
- `DATABASE_URL` phải dùng tài khoản ứng dụng có quyền tối thiểu cần thiết; không
  dùng tài khoản quản trị database.
- Các biến mail chỉ khai báo khi tính năng gửi mail được bật. Không để credential
  mẫu trong production.

Ứng dụng production sẽ từ chối khởi động nếu thiếu cấu hình bắt buộc, dùng secret
yếu hoặc bật `DEBUG`/`TESTING`. Không chạy `app.py` trực tiếp để phục vụ production;
dùng WSGI server hoặc runtime do nền tảng triển khai quản lý.

## 2. Kiểm tra trước triển khai

Ghi lại commit, thời gian phát hành, người duyệt, phiên bản MySQL và revision hiện
tại. Trên máy CI hoặc máy nghiệm thu, dùng database MySQL chuyên dụng có tên chứa
`test`; fixture integration sẽ xóa và tạo lại schema nên tuyệt đối không trỏ vào
production hoặc database cần giữ:

```powershell
$env:TEST_MYSQL_DATABASE_URL = "mysql+pymysql://<test_user>:<test_password>@<test_host>/<test_database>"
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\python.exe -m pytest -m mysql -q
.\venv\Scripts\python.exe -m flask --app app db heads
```

Điều kiện đi tiếp:

1. Hai lệnh test đều xanh trên cùng major version MySQL với production.
2. `db heads` chỉ trả đúng một head.
3. Không còn migration ngoài graph hoặc thay đổi code chưa được review.
4. Có cửa sổ bảo trì và cách dừng toàn bộ request ghi trong lúc nâng cấp.
5. Rehearsal trên bản sao dữ liệu không phát hiện trùng `(hotel_id, room_number)`
   hoặc lỗi preflight khác.

## 3. Backup và diễn tập restore

Trước khi deploy, dừng/cô lập request ghi rồi tạo backup nhất quán. Ví dụ với
MySQL, để công cụ hỏi mật khẩu thay vì ghi mật khẩu trên command line:

```powershell
mysqldump --single-transaction --routines --triggers -h <db_host> -u <db_user> -p <db_name> > <backup_path>
```

Không coi file backup là hợp lệ chỉ vì command thành công. Restore vào database
cô lập, kiểm tra bảng, số lượng bản ghi trọng yếu và đăng nhập bằng một tài khoản
nghiệm thu:

```powershell
mysql -h <restore_host> -u <restore_user> -p <restore_database> < <backup_path>
```

Ghi checksum, nơi lưu mã hóa, thời hạn lưu và kết quả diễn tập restore vào biên bản
phát hành. Chỉ tiếp tục khi người chịu trách nhiệm xác nhận có thể restore.

## 4. Nâng cấp Alembic

Chạy toàn bộ bước này trước trên database vừa restore. Khi tạo SQL offline trên
Windows, đặt UTF-8 để log migration tiếng Việt không làm command thất bại:

```powershell
$env:PYTHONIOENCODING = "utf-8"
.\venv\Scripts\python.exe -m flask --app app db current
.\venv\Scripts\python.exe -m flask --app app db heads
.\venv\Scripts\python.exe -m flask --app app db upgrade --sql
.\venv\Scripts\python.exe -m flask --app app db upgrade
.\venv\Scripts\python.exe -m flask --app app db current
```

Đọc SQL sinh ra và log preflight trước khi chạy `db upgrade` trên production. Nếu
migration dừng vì dữ liệu conflict, giữ ứng dụng cũ, không sửa trực tiếp để ép
migration chạy; lập danh sách conflict, xử lý qua quy trình có phê duyệt rồi diễn
tập lại từ một bản backup mới.

Sau upgrade, dùng schema inspector hoặc `SHOW CREATE TABLE` để xác nhận tối thiểu:

- `rooms` unique theo `(hotel_id, room_number)`, không unique `room_number` toàn hệ
  thống;
- bảng/cột operation và liên kết payment tồn tại đúng migration;
- revision hiện tại bằng head duy nhất;
- ứng dụng production khởi động mà không seed dữ liệu hay bật debug.

## 5. Smoke test sau triển khai

Trên staging đã migrate, chạy đầy đủ; trên production chỉ dùng dữ liệu nghiệm thu
được phê duyệt và tránh tạo giao dịch tài chính giả:

1. Đăng nhập đúng tenant; request POST không có CSRF token bị từ chối với lỗi ổn
   định, còn form/API hợp lệ hoạt động.
2. Mở danh sách khách có chuỗi kiểm thử XSS và xác nhận chuỗi chỉ hiển thị dạng text,
   không tạo node HTML và không có JavaScript chạy.
3. Xác nhận hai khách sạn có thể cùng số phòng, nhưng một khách sạn không thể có hai
   phòng trùng số.
4. Tạo quote đặt phòng, chọn cọc 50%/100%, đặt phòng, check-in và kiểm tra trạng thái
   Booking/BookingRoom/Room đồng bộ.
5. Gọi dịch vụ, đổi quantity và kiểm tra tồn kho/lô; lỗi phải rollback toàn request.
6. Checkout lẻ và đoàn trên staging; double-click/retry chỉ tạo một operation và
   một kết quả tài chính.
7. Admin dời lịch được, Staff bị chặn theo capability; lịch sử và audit event đúng.
8. So sánh báo cáo doanh thu, công suất, sổ quỹ và expense void theo từng tenant.
9. Kiểm tra desktop bằng `bb-browser`: keyboard/focus modal, accessible name của nút
   icon, trạng thái loading/error và console không có lỗi.

Nếu một bước thất bại, ngừng mở traffic, lưu log/request ID và chuyển sang mục
rollback. Không tiếp tục với giả định dữ liệu sẽ tự đồng bộ.

## 6. Rollback

Ưu tiên restore backup đã diễn tập thay vì downgrade Alembic mù quáng:

1. Dừng toàn bộ request ghi và lưu thời điểm bắt đầu sự cố.
2. Nếu chưa chạy migration và chưa có mutation mới, rollback application về commit
   cũ rồi chạy smoke test tương thích.
3. Nếu schema hoặc dữ liệu đã đổi, chỉ chạy `db downgrade <revision>` khi revision
   đó đã được rehearsal với đúng loại dữ liệu và được xác nhận không làm mất dữ
   liệu. Migration unique số phòng có thể chủ động từ chối downgrade khi nhiều
   khách sạn dùng cùng số phòng.
4. Khi downgrade không được chứng minh an toàn, tạo database mới từ backup, xác
   minh revision/schema, đổi kết nối theo quy trình hạ tầng rồi khởi động lại bản
   ứng dụng cũ.
5. Chạy smoke test đọc, đối chiếu operation/payment/inventory và chạy reconciliation
   dry-run. Chỉ mở traffic sau khi người phụ trách nghiệp vụ xác nhận.

Không ghi đè database lỗi cho đến khi đã lưu đủ log và bản sao phục vụ điều tra.

## 7. Đối soát dữ liệu

Mỗi lần chỉ đối soát một tenant và luôn chạy dry-run trước:

```powershell
.\venv\Scripts\python.exe -m flask --app app reconcile-business-data --hotel-slug <hotel_slug>
```

Lưu JSON output cùng commit/revision và backup tương ứng. Các issue có
`requires_manual_review=true` không được tự sửa. Chỉ sau khi báo cáo được duyệt,
tenant đã dừng mutation và backup đã được kiểm chứng mới dùng apply:

```powershell
.\venv\Scripts\python.exe -m flask --app app reconcile-business-data `
  --hotel-slug <hotel_slug> `
  --apply `
  --confirm-apply `
  --backup-acknowledged
```

Chạy lại dry-run ngay sau apply và lưu báo cáo trước/sau. Quy tắc sửa tự động, cách
đọc từng loại issue và điều kiện phê duyệt nằm tại
`docs/reconciliation-runbook.md`.

## 8. Biên bản nghiệm thu

Biên bản phát hành phải chứa commit, Alembic revision trước/sau, kết quả unit/MySQL
test, checksum backup, kết quả restore rehearsal, smoke test, reconciliation dry-run,
người phê duyệt và mọi bước chưa thể kiểm chứng. Không đính kèm secret, cookie phiên,
dữ liệu khách hàng nguyên bản hoặc chuỗi kết nối thật.
