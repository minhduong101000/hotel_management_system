# Kế hoạch TDD: Chuẩn hóa modal vận hành

## Hạng mục 1 — Component modal chung cho thao tác ngắn

1. Viết test đỏ kiểm tra các trang Khách hàng, Dịch vụ, Giá, Kho, Chi phí dùng class `operation-modal`.
2. Thêm CSS token chung và gắn class vào modal ngắn, không thay API/JS.
3. Chạy test mục tiêu, `pytest -q`, kiểm tra `bb-browser` các modal đại diện.
4. Commit riêng.

## Hạng mục 2 — Booking lẻ và gọi dịch vụ

1. Viết test markup cho modal rộng, header/footer cố định và không mở modal lồng nhau.
2. Hợp nhất markup booking lẻ dùng chung cho Sơ đồ phòng và Timeline.
3. Kiểm tra tạo booking trước, vào ở ngay và gọi dịch vụ bằng `bb-browser`.
4. Commit riêng.

## Hạng mục 3 — Booking đoàn và checkout

1. Viết test đỏ cho layout fullscreen và CTA nghiệp vụ rõ ràng.
2. Hợp nhất booking đoàn, checkout phòng/đoàn, chi tiết hóa đơn thành luồng dùng chung.
3. Kiểm tra hủy, VAT, cọc, dời lịch và checkout bằng test + `bb-browser`.
4. Commit riêng.

## Hạng mục 4 — Regression/a11y

1. Kiểm tra focus, Escape, tab order, overflow ở desktop/tablet.
2. Chạy full suite, `git diff --check`, kiểm tra console bằng `bb-browser`.
3. Commit riêng.
