# Spec P0 — Đóng băng hiện trạng

**Trạng thái:** ⬜ Chưa làm · **Ước tính:** 0,5 ngày · **Phụ thuộc:** không

## Mục tiêu

Trước khi sửa bất cứ thứ gì, phải có (1) một điểm quay về an toàn và (2) một định nghĩa đo được cho hai chữ "không hỏng". Hiện tại chưa có cả hai.

## Việc cần làm

1. **Dựng lại môi trường chạy** (phát hiện khi khảo sát 14/08: máy hiện tại không còn venv nào có Flask, MySQL local không chạy): tạo `venv/` bằng Python 3.12, cài 7 gói, dựng MySQL 8 tạm bằng Docker container khớp chuỗi kết nối hardcode trong `app.py`, xác nhận app boot được.
2. **Pin dependencies:** `pip freeze` từ venv vừa xác nhận chạy được, ghi đè `requirements.txt` với version cụ thể (`Flask==x.y.z`…). File hiện tại chỉ có 7 tên gói trần — build lại không tái lập được.
3. **Tách requirements dev:** tạo `requirements-dev.txt` (ban đầu rỗng hoặc chỉ chứa `pytest` — P4 sẽ bổ sung).
4. **Tag git:** `git tag v0-legacy` tại commit hiện hành, push tag nếu có remote.
5. **Checklist smoke thủ công:** tạo `docs/smoke-checklist.md` liệt kê các màn hình / API **đang chạy được** (đăng nhập, sơ đồ phòng, timeline, đặt phòng lẻ, check-in, gọi dịch vụ, preview checkout, checkout, CRUD khách hàng, CRUD dịch vụ, quản lý giá). Với mỗi mục ghi: thao tác → kết quả mong đợi.
6. **Ghi rõ những cái đang hỏng sẵn** vào cuối checklist (ví dụ: đặt đoàn `group_create` crash, tiền checkout không được lưu) — để sau này không nhầm là hỏng do refactor.

## Tiêu chí nghiệm thu

- [ ] `requirements.txt` có version pin cho 100% gói; `pip install -r requirements.txt` trong venv mới cài được sạch.
- [ ] Tag `v0-legacy` tồn tại và checkout được.
- [ ] `docs/smoke-checklist.md` có ≥ 10 mục chạy-được và mục "hỏng sẵn" riêng.

## Ngoài phạm vi

- Không sửa bất kỳ dòng code nào.
- Không nâng cấp version gói nào — pin đúng version đang chạy.
