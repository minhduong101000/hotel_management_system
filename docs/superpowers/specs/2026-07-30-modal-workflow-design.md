# Spec: Chuẩn hóa modal và luồng thao tác vận hành

## Mục tiêu

- Giảm modal chồng modal, làm rõ hành động chính và tránh nhét luồng nghiệp vụ dài vào hộp thoại nhỏ.
- Giữ nguyên API, dữ liệu, phân quyền, tính tiền và nghiệp vụ hiện có.
- Đồng nhất desktop/tablet: header, body có thể cuộn, footer cố định, nút Hủy và CTA rõ nghĩa.

## Phân loại

### Modal thao tác ngắn — giữ modal vừa

- Khách hàng, dịch vụ, giá sự kiện.
- Nhập kho, điều chỉnh tồn, hủy hàng.
- Quét QR CCCD, xác nhận check-in, dời lịch.

Các modal này có tối đa một thực thể và một hành động ghi dữ liệu. Chúng dùng component CSS chung `operation-modal`.

### Luồng phức tạp — dùng modal rộng/toàn màn hình

- Gọi dịch vụ: modal rộng hai cột, giữ ngữ cảnh phòng và danh sách món.
- Đặt phòng lẻ: modal rộng, chia nhóm Khách / Thời gian / Hành động cuối.
- Đặt đoàn: fullscreen desktop/tablet; chia bước Thời gian & phòng trống, Trưởng đoàn, Cọc & ghi chú.
- Checkout phòng/đoàn và chi tiết hóa đơn: fullscreen, phần tổng tiền và CTA cố định ở cuối.

### Không mở thêm modal

- Lịch sử biến động lô hàng hiển thị trong panel lô hàng hiện hữu.
- Thông tin khách từ sơ đồ phòng chỉ đọc: chuyển thành side panel ở đợt sau; chưa bỏ modal khi chưa có panel thay thế.

## Hợp nhất nguồn giao diện

- Booking lẻ, booking đoàn, checkout phòng và checkout đoàn hiện bị copy ở Sơ đồ phòng và Timeline.
- Mục tiêu: mỗi luồng chỉ có một template/markup nguồn dùng chung; hai trang chỉ gọi đúng hàm mở luồng.
- Không triển khai song song modal mới khi bản sao cũ còn được gọi.

## Quy ước component modal

- `operation-modal`: modal ngắn; width 520px, header có icon + tiêu đề + mô tả, body có label/helper text, footer cố định.
- `operation-modal--danger`: dùng cho hủy hàng/chi phí; CTA mô tả hành động nguy hiểm.
- `operation-modal--wide`: dùng cho gọi dịch vụ/booking lẻ.
- `operation-modal--fullscreen`: dùng cho booking đoàn, checkout, chi tiết hóa đơn.
- Không dùng backdrop `static` trừ camera QR hoặc khi có dữ liệu chưa lưu cần xác nhận thoát.

## Tiêu chí nghiệm thu

- Các modal thao tác ngắn có spacing, focus, CTA và trạng thái màu thống nhất.
- Booking/checkout không bị chồng modal; trở về đúng luồng cha khi hoàn tất/hủy.
- Sơ đồ phòng và Timeline không còn hai bản markup riêng cho cùng một nghiệp vụ.
- Kiểm tra desktop bằng `bb-browser`, không có lỗi console; full test xanh.
