# Hướng dẫn đối soát dữ liệu nghiệp vụ

Command đối soát chỉ xử lý một khách sạn trong mỗi lần chạy. Luôn chạy
`dry-run`, lưu kết quả và để người phụ trách nghiệp vụ duyệt trước khi cân nhắc
`apply`.

## 1. Chạy dry-run

```powershell
.\venv\Scripts\python.exe -m flask --app app reconcile-business-data --hotel-slug central
```

Kết quả là JSON gồm:

- `issue_count`: tổng số sai lệch;
- `manual_review_count`: số sai lệch command không được phép tự sửa;
- `applied_count`: luôn bằng `0` ở dry-run;
- `issues`: rule, loại/id bản ghi, giá trị hiện tại, giá trị kỳ vọng và khả
  năng áp dụng tự động.

Không đưa kết quả chứa dữ liệu vận hành lên kênh công khai. Lưu báo cáo cùng
thời điểm chạy, phiên bản ứng dụng và thông tin backup để phục vụ phê duyệt.

## 2. Quy tắc được phép apply

Command chỉ tự sửa các giá trị có thể suy ra trực tiếp:

- trạng thái Booking cha từ toàn bộ BookingRoom;
- `Room.status` khi số BookingRoom `checked_in` là `0` hoặc `1`;
- `InventoryItem.quantity` từ tổng `quantity_available` của các lô.

Các sai lệch tiền, payment status, Payment thiếu operation, tenant link,
snapshot giá, allocation dịch vụ và phòng trùng luôn yêu cầu xử lý thủ công.
Command không tự đoán số tiền hoặc dựng lịch sử giả.

## 3. Điều kiện apply

Trước khi apply:

1. Dừng hoặc cô lập mutation của đúng tenant.
2. Tạo backup và kiểm tra khả năng restore.
3. Lưu, duyệt báo cáo dry-run.
4. Xác nhận phiên bản code/schema đang chạy.

Sau khi được phê duyệt:

```powershell
.\venv\Scripts\python.exe -m flask --app app reconcile-business-data `
  --hotel-slug central `
  --apply `
  --confirm-apply `
  --backup-acknowledged
```

Apply chạy trong một transaction theo tenant. Nếu một rule lỗi, toàn bộ thay
đổi của lần chạy được rollback. Chạy lại dry-run ngay sau apply; lưu cả báo cáo
trước và sau. Những issue còn `requires_manual_review=true` phải được xử lý qua
quy trình riêng có phê duyệt, không sửa trực tiếp bằng command này.
