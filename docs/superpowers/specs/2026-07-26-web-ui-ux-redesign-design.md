# Spec: Chuẩn hóa giao diện web Hotel POS Pro

**Ngày:** 26-07-2026  
**Trạng thái:** Chờ phê duyệt để triển khai  
**Phạm vi:** Giao diện web nội bộ cho Master admin, Hotel admin và Staff

## 1. Bối cảnh và mục tiêu

Hệ thống là công cụ vận hành khách sạn nội bộ. Giao diện cần ưu tiên tốc độ quét thông tin, thao tác ít bước và tính nhất quán giữa các màn hình, thay vì phong cách trang giới thiệu.

Mục tiêu của đợt này:

- Chuẩn hóa layout, màu sắc, kiểu card, bảng, form, modal và trạng thái tải/rỗng/lỗi.
- Làm lại sơ đồ phòng để vẫn gọn khi một phòng có nhiều booking sắp đến.
- Tách rõ trải nghiệm Master Console và không gian vận hành của từng khách sạn.
- Cải thiện khả năng truy cập cơ bản: nhãn nút, focus, tương phản, phản hồi thao tác.
- Ưu tiên desktop/tablet nội bộ; không để layout vỡ ở màn hình nhỏ nhưng chưa tối ưu mobile đầy đủ trong đợt này.

Không nằm trong phạm vi:

- Thay đổi quy tắc nghiệp vụ booking, check-in/check-out, giá, kho hoặc báo cáo.
- Bổ sung dark mode, animation phức tạp hoặc thay framework giao diện.
- Thay đổi API trừ khi cần thiết để biểu diễn dữ liệu UI đã có.

## 2. Hướng thiết kế được chọn

### 2.1 Phong cách

- Kiểu giao diện: **dashboard vận hành mật độ cao**.
- Tông chính: navy/trung tính sáng; màu xanh dương cho điều hướng và hành động chính.
- Màu trạng thái chỉ dùng cho nghiệp vụ và luôn đi kèm nhãn chữ hoặc biểu tượng.
- Khoảng cách theo thang 4/8 px; nội dung dày vừa phải, không nén chữ dưới 12 px.
- Dùng một bộ Font Awesome hiện có trong project; không thêm emoji làm icon thao tác.

### 2.2 Token dùng chung

| Vai trò | Giá trị đề xuất | Cách dùng |
|---|---:|---|
| Primary | `#1E3A8A` | Điều hướng, nút chính, focus ring |
| Secondary | `#3B82F6` | Liên kết, hành động phụ đang chọn |
| Accent | `#A16207` | Cảnh báo cần chú ý nhưng chưa lỗi |
| Success | `#059669` | Sẵn sàng, hoàn tất |
| Warning | `#D97706` | Phòng đang ở/theo giờ, cần theo dõi |
| Danger | `#DC2626` | Quá giờ, xóa, lỗi, hủy |
| Surface | `#FFFFFF` | Card, bảng, modal |
| Background | `#F8FAFC` | Nền ứng dụng |
| Border | `#E2E8F0` | Đường phân tách và viền input |

Token phải nằm trong CSS chung; không thêm màu hex tùy tiện trong từng template, trừ màu dữ liệu biểu đồ đã được phê duyệt.

## 3. Khung giao diện chung

### 3.1 Desktop

- Sidebar trái cố định chứa logo/tên khách sạn, nhóm menu và tài khoản hiện tại.
- Thanh trang trên cùng hiển thị tiêu đề trang, ngữ cảnh khách sạn và tối đa hai hành động chính.
- Nội dung dùng `main-area` cuộn độc lập; sidebar không làm mất khả năng cuộn danh sách menu.
- Mỗi trang dùng cùng thứ tự: tiêu đề → thanh lọc/tác vụ → chỉ số tóm tắt (nếu cần) → nội dung chính.

### 3.2 Responsive

- Bổ sung `meta viewport` cho layout chung và Master templates.
- Ở dưới 992 px, sidebar chuyển sang menu thu gọn có nút mở/đóng; không để sidebar 240 px chiếm cố định màn hình. Đây là mức hỗ trợ tối thiểu cho tablet/màn hình hẹp, không phải phạm vi tối ưu mobile đầy đủ.
- Bảng rộng nằm trong vùng cuộn ngang có chỉ báo; không làm tràn toàn trang.
- Modal có chiều cao tối đa theo viewport; vùng danh sách bên trong tự cuộn.

## 4. Đặc tả theo màn hình

### 4.1 Sơ đồ phòng — Ưu tiên P0

Mỗi card phòng dùng đúng cấu trúc:

1. Header: số phòng, loại phòng, icon trạng thái.
2. Nội dung: nhãn trạng thái, thông tin chính của khách hoặc giá phòng.
3. Thông báo booking: một chỉ báo gọn về booking sắp nhận gần nhất của chính phòng đó.
4. Footer: một hành động chính và badge trạng thái có chữ.

Quy tắc booking:

- Nếu có ít nhất một booking: card chỉ hiện chỉ báo `Có khách sắp đến · HH:mm` và CTA `Xem thông tin`; không hiển thị tên khách hoặc danh sách booking trong card.
- CTA `Xem thông tin` mở một popup/modal gọn cho **booking sắp nhận gần nhất**, gồm tên khách, giờ nhận, SĐT, tiền cọc và CTA `Nhận phòng`.
- Nếu có thêm booking sau đó: không hiển thị số lượng, danh sách, `+N lịch khác`, popover hoặc modal lịch mở rộng tại sơ đồ phòng.
- Người dùng xem toàn bộ lịch booking và thực hiện thao tác theo booking khác tại màn hình Timeline.
- Chỉ CTA `Nhận phòng` trong popup/modal mới mở xác nhận check-in; card không tự chọn hay check-in ngầm booking.
- Nếu phòng đang có khách, không hiển thị toàn bộ lịch tương lai trong thân card; Timeline là nơi xem lịch tương lai đầy đủ.

Các trạng thái chuẩn: `Sẵn sàng`, `Chờ nhận`, `Đang ở`, `Theo giờ`, `Quá giờ`, `Cần dọn`, `Bảo trì`.

### 4.2 Timeline — Ưu tiên P0

- Đồng bộ header với sơ đồ phòng: tiêu đề, bộ lọc/ngày, hành động `Đặt đoàn` và `Làm mới`.
- Giữ timeline là vùng trọng tâm; tách các thao tác tạo/sửa/check-in/check-out vào modal có footer nhất quán.
- Modal booking chỉ có một CTA chính theo trạng thái hiện tại; thao tác phụ là nút outline.
- Modal hóa đơn/chi tiết booking có vùng nội dung cuộn, footer cố định, tổng tiền luôn dễ thấy.

### 4.3 Khách hàng, hóa đơn, kho, dịch vụ, giá phòng — Ưu tiên P1

- Dùng chung component trang danh sách: tiêu đề, nút tạo mới, bộ lọc, bảng, phân trang hoặc số kết quả, empty state và loading state.
- Các nút icon-only bắt buộc có `aria-label` và tooltip: sửa, xóa, xem chi tiết, nhập kho, gỡ liên kết.
- Nút phá hủy dùng màu danger và mở modal xác nhận thống nhất thay cho `confirm()` của trình duyệt.
- Form có label nhìn thấy được, dấu bắt buộc, trợ giúp định dạng, lỗi ngay cạnh trường và trạng thái đang lưu.

### 4.4 Báo cáo doanh thu, chi phí, sổ quỹ — Ưu tiên P1

- Thanh lọc ngày dùng cùng cấu trúc trên mọi báo cáo.
- KPI dùng card cùng kích thước, cùng kiểu icon và định dạng tiền VNĐ.
- Bảng số liệu căn phải cho tiền/số lượng, căn trái cho tên; hàng được highlight khi hover.
- Màu biểu đồ/trạng thái không là phương tiện duy nhất để truyền đạt ý nghĩa.

### 4.5 Cấu hình và nhân sự — Ưu tiên P1

- Chuyển trang hiện tại sang layout Bootstrap/card chung, loại bỏ phần lớn CSS inline.
- Form tạo tài khoản và danh sách nhân sự xếp dọc ở màn hình nhỏ, cạnh nhau ở desktop rộng.
- Reset mật khẩu là modal riêng có xác nhận; không nhập mật khẩu mới trực tiếp trong một ô của bảng.
- Hiển thị role bằng badge chuẩn `Admin`/`Staff`, không dùng màu tùy ý.

### 4.6 Master Console — Ưu tiên P1

- Dùng layout riêng nhưng cùng token màu, typography và component cơ bản với ứng dụng khách sạn.
- Dashboard gồm: KPI tổng số khách sạn, đang hoạt động, tạm ngưng; bảng khách sạn; tìm kiếm; trạng thái; hành động `Vào quản lý` và `Kích hoạt/Tạm ngưng`.
- Form tạo khách sạn mở bằng modal hoặc drawer, có label và kiểm tra lỗi tại trường.
- Khi Master admin vào hỗ trợ một khách sạn, thanh banner trong app phải nêu rõ tên khách sạn và có đường quay lại Master Console.

## 5. Component dùng chung bắt buộc

- `PageHeader`: tiêu đề, mô tả ngắn tùy chọn, action chính/phụ.
- `FilterBar`: bộ lọc, tìm kiếm, khoảng ngày và nút áp dụng/xóa lọc.
- `StatusBadge`: icon nhỏ + nhãn + màu semantic.
- `DataTable`: header, empty state, loading state, lỗi tải lại, cuộn ngang khi cần.
- `ActionMenu`: nhóm thao tác phụ, không để nhiều nút icon rời rạc trong bảng.
- `ConfirmModal`: cảnh báo rõ đối tượng/hậu quả; không dùng `window.confirm()` cho thao tác nghiệp vụ.
- `AsyncButton`: trạng thái thường/đang xử lý/thành công/thất bại, ngăn bấm lặp.

## 6. Yêu cầu khả năng truy cập và phản hồi

- Tương phản chữ tối thiểu WCAG AA; focus keyboard phải nhìn thấy được.
- Mọi input có label; placeholder không là label duy nhất.
- Mọi button chỉ có icon phải có `aria-label`; ảnh logo có `alt` phù hợp.
- Thông báo lỗi/success phải dùng vùng có thể được screen reader thông báo (`role="alert"` hoặc `aria-live`).
- Tất cả thao tác lưu/tạo/xóa/check-in/check-out hiển thị trạng thái đang xử lý và kết quả.
- Animation, nếu có, 150–300 ms và tôn trọng `prefers-reduced-motion`.

## 7. Thứ tự triển khai đề xuất

| Đợt | Phạm vi | Kết quả mong đợi |
|---|---|---|
| 1 — P0 | Token CSS, layout chung, sơ đồ phòng, timeline | Hai màn hình lễ tân nhất quán, booking nhiều vẫn gọn |
| 2 — P1 | Component danh sách/form, khách hàng, hóa đơn, kho, dịch vụ, giá | Các màn hình CRUD cùng trải nghiệm |
| 3 — P1 | Báo cáo, nhân sự, Master Console | Trang quản trị và báo cáo đồng bộ |
| 4 — Sau | Tối ưu mobile đầy đủ, dark mode, animation, refactor JS toàn diện | Cải thiện chất lượng không chặn vận hành |

## 8. Tiêu chí nghiệm thu UI

- Không còn hai renderer/card style cùng tồn tại ở sơ đồ phòng.
- Card phòng chỉ hiển thị chỉ báo của booking sắp nhận gần nhất; popup/modal gọn xem chi tiết booking đó, còn Timeline là đường xem lịch đầy đủ.
- Mọi trang trong phạm vi dùng token và component chung; trang nhân sự không còn là ngoại lệ về layout.
- Không có button icon-only thiếu nhãn truy cập tại các trang đã sửa.
- Desktop 1440 px được kiểm tra trực quan bằng `bb-browser` cho từng luồng thay đổi.
- Khi bổ sung responsive, kiểm tra tối thiểu 375 px, 768 px, 1024 px và 1440 px.
- Toàn bộ thay đổi chức năng hoặc bug được triển khai theo TDD: test thất bại → triển khai tối thiểu → refactor → chạy lại test.

## 9. Quyết định đã chốt và rủi ro trước khi triển khai

- Ưu tiên desktop/tablet nội bộ trong đợt này; tối ưu mobile đầy đủ để sau.
- Sơ đồ phòng chỉ hiển thị chỉ báo booking sắp nhận gần nhất của mỗi phòng. CTA `Xem thông tin` mở chi tiết booking đó; không có danh sách booking mở rộng tại card. Timeline là nơi xem lịch đầy đủ.
- Việc thay `confirm()` bằng modal xác nhận làm thay đổi trải nghiệm, nhưng không đổi nghiệp vụ; chỉ thực hiện sau khi được phê duyệt theo từng đợt.
