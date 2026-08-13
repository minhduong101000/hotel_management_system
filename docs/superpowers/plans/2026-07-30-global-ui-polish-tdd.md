# Kế hoạch TDD: Polish giao diện toàn web

**Phạm vi:** Desktop/tablet cho hệ thống vận hành nội bộ. Giữ nguyên API và nghiệp vụ hiện có; chỉ chuẩn hóa cấu trúc, khả năng thao tác và hiển thị.

## Mục tiêu chung

- Một ngôn ngữ giao diện dashboard nhất quán: navy làm màu điều hướng, nền sáng, CTA rõ ràng, trạng thái semantic.
- Mọi trang có cùng nhịp: tiêu đề + mô tả ngắn, hành động chính, filter, nội dung dữ liệu, empty/loading/error state.
- Không dùng màu đơn lẻ để biểu đạt trạng thái; có nhãn chữ/icon nhất quán.
- Nút, input, bảng, modal và feedback có kích thước/spacing/focus state đồng bộ.
- Không đổi luồng đặt phòng, tính tiền, kho, phân quyền hoặc tenant scope.

## Quy ước kiểm thử cho mọi hạng mục

1. Viết test markup hoặc endpoint liên quan trước, chạy đỏ.
2. Triển khai UI tối thiểu, refactor CSS dùng token chung.
3. Chạy test hạng mục và full `pytest -q`.
4. Dùng `bb-browser` desktop để kiểm tra page thay đổi, modal/filter/empty state và console.
5. Commit tiếng Anh riêng sau một hạng mục hoàn chỉnh.

## Hạng mục 1 — Shared shell và design tokens

**Hiện trạng:** Đã hoàn thành commit `901ffeb`.

- Sidebar/topbar, token màu, button/input/table/card cơ bản.
- Bổ sung test shell để chống mất topbar và focus state.

## Hạng mục 2 — Trang vận hành lễ tân

**Trang:** Sơ đồ phòng, Timeline, Khách hàng, Hóa đơn cũ.

- Chuẩn hóa page header, toolbar, filter và action chính.
- Sơ đồ phòng: giữ mật độ phòng; trạng thái phòng, notice và CTA phải đọc được ngay.
- Timeline: toolbar 3 tầng gọn hơn, legend/filters không lấn vùng lịch, trạng thái trống/lỗi rõ.
- Khách hàng và hóa đơn: bảng responsive, cột số tiền canh phải/tabular, action overflow gọn.
- Modal booking/check-in/checkout: nhóm trường theo luồng nghiệp vụ, error cạnh input, footer action rõ primary/destructive.

**TDD:** `tests/test_room_map_card_markup.py`, `test_timeline_operations_ui.py`, `test_ui_regression.py`; thêm test markup cho header/action của khách hàng/hóa đơn.

## Hạng mục 3 — Dịch vụ, kho và giá

**Trang:** Dịch vụ/Minibar, Kho hàng, Quản lý giá phòng.

- Chuẩn hóa bảng quản trị có filter bar, empty state, bulk-safe action và feedback không phụ thuộc alert.
- Kho: hoàn thiện trạng thái lô/hạn dùng, lịch sử và action destructive tách biệt.
- Giá phòng: tổ chức rule theo thẻ/timeline thời gian, làm rõ trạng thái đang áp dụng và phạm vi ngày.
- Mọi modal có focus, label, helper text, loading state cho submit.

**TDD:** mở rộng `test_warehouse_batch_ui.py`; thêm `test_service_ui.py`, `test_price_manager_ui.py` theo markup thực tế.

## Hạng mục 4 — Tài chính, báo cáo và audit

**Trang:** Doanh thu, Sổ quỹ, Chi phí, Nhật ký hoạt động.

- KPI đầu trang theo cùng một component: nhãn, giá trị, kỳ lọc, màu semantic.
- Bảng tài chính có tổng, filter bar, cột tiền canh phải và trạng thái không dữ liệu.
- Chi phí: hiển thị rõ “đã hủy ghi nhận”, lý do và action an toàn.
- Audit: filter/pagination giữ nguyên dữ liệu, badge nhóm nhất quán.

**TDD:** giữ `test_activity_log.py`, `test_audit_log.py`, thêm kiểm tra markup KPI/filter/void label.

## Hạng mục 5 — Nhân sự, Master Console và xác thực

**Trang:** Cấu hình & Nhân sự, Master dashboard/login, login khách sạn.

- Tách rõ khu vực Master Console với brand/badge ngữ cảnh khách sạn.
- Form nhân sự và login có label/error/feedback chuẩn; action nguy hiểm tách khỏi action thông thường.
- Bảng khách sạn/nhân sự dùng cùng component desktop/tablet.

**TDD:** mở rộng `test_master_access.py`, `test_hotel_user_management.py`, `test_staff_permissions.py` với markup cần thiết.

## Hạng mục 6 — Responsive, accessibility và regression cuối

- Kiểm tra 1024px, 1280px, 1440px bằng bb-browser; 768px cho tablet.
- Kiểm tra keyboard focus, aria-label cho icon-only button, contrast, form error, loading/empty state.
- Rà không có horizontal scroll, modal bị che, bảng vỡ cột hoặc console error mới.
- Chạy full suite, `git diff --check`, commit hạng mục cuối.

## Thứ tự triển khai đề xuất

1. Lễ tân (giá trị vận hành cao nhất).
2. Dịch vụ/kho/giá.
3. Tài chính/audit.
4. Nhân sự/Master/auth.
5. Responsive/accessibility sweep.

## Ngoài phạm vi

- Thiết kế mobile-first hoàn chỉnh hoặc app mobile.
- Thay framework Bootstrap/Font Awesome.
- Đổi nghiệp vụ, API hoặc cấu trúc database chỉ để phục vụ giao diện.
