# Kế hoạch TDD: Chuẩn hóa giao diện web Hotel POS Pro

**Ngày:** 26-07-2026  
**Spec nguồn:** `docs/superpowers/specs/2026-07-26-web-ui-ux-redesign-design.md`  
**Trạng thái:** ĐÃ TRIỂN KHAI (cập nhật trạng thái 15-08-2026 — tính năng đã vận hành, xem business-operations-guide.md)

## 1. Phạm vi và nguyên tắc triển khai

- Thứ tự ưu tiên: desktop/tablet nội bộ → mobile tối thiểu chống vỡ layout → mobile tối ưu đầy đủ ở đợt sau.
- Đợt 1 chỉ làm P0: khung giao diện, sơ đồ phòng và Timeline. Các màn hình CRUD/báo cáo/Master Console được làm ở các đợt tiếp theo.
- Không sửa quy tắc nghiệp vụ, API hay quyền truy cập trừ khi kiểm tra cho thấy UI hiện tại không thể thực hiện hành vi đã có.
- Mỗi task tuân thủ: viết test đỏ → chạy test xác nhận đỏ → triển khai tối thiểu → refactor → chạy lại test liên quan và toàn bộ suite.
- Dùng `ui-ux-pro-max` khi quyết định UI. Trước mỗi đợt tạo/chỉnh trang mới, đọc design system đã lưu và phần override của trang nếu có.
- Sau mỗi task có thay đổi UI, kiểm tra bằng `bb-browser` ở desktop 1440 px; các task responsive kiểm tra thêm 1024 px và 768 px. Ghi rõ nếu công cụ không khả dụng.

## 2. Chiến lược test

Project hiện có `pytest`/Flask test client và chưa có JavaScript test runner. Kế hoạch không tự thêm Node/Vitest/Playwright khi chưa được phê duyệt.

| Loại kiểm tra | Công cụ | Mục đích |
|---|---|---|
| Route/template | `pytest` + Flask test client | Đảm bảo trang trả về đúng shell, quyền và thành phần HTML chính |
| API dữ liệu | `pytest` + fixture booking | Đảm bảo UI có đủ dữ liệu để biểu diễn, không đổi tenant scope |
| Regression markup/CSS/JS | `pytest` đọc source | Ngăn renderer cũ, selector/token bắt buộc hoặc markup không truy cập được quay lại |
| Hành vi/trực quan | `bb-browser` | Xác nhận luồng thật, trạng thái card, modal, desktop/tablet và console error |

Test source không thay thế test JavaScript đơn vị. Nếu sau này cần kiểm tra logic client phức tạp hơn (lọc lịch, state modal, loading), cần bạn duyệt riêng việc thêm test runner.

## 3. Đợt 0 — Chốt design system và baseline

### Task 0.1: Lưu design system của project

**File tạo mới:**

- `design-system/hotel-pos-pro/MASTER.md`

**Thực hiện:**

1. Kiểm tra `design-system/hotel-pos-pro/MASTER.md` chưa tồn tại.
2. Dùng `ui-ux-pro-max` với truy vấn `internal hotel management operations dashboard dense calm efficient`, density 8, và `--persist --output-dir` trỏ về root project.
3. Đọc lại file đã tạo, đối chiếu token/colors và quy tắc dashboard với spec.

**Kiểm tra:**

- Không ghi đè MASTER.md nếu file đã được người dùng hoặc agent khác tạo.
- Không yêu cầu test chức năng vì chỉ tạo tài liệu định hướng.

### Task 0.2: Chụp baseline không thay đổi dữ liệu

**Không sửa code.**

Mở bằng `bb-browser` với phiên admin local:

- Sơ đồ phòng.
- Timeline.
- Khách hàng.
- Nhân sự.
- Master Console.

Lưu screenshot baseline và console errors. Nếu một trang phụ thuộc dữ liệu local chưa tải được, ghi lại URL và lỗi cụ thể, không tự seed/sửa dữ liệu production-like.

## 4. Đợt 1 — Nền UI và layout chung (P0)

### Task 1.1: Viết regression test cho shell chung

**Test đỏ trước:** tạo `tests/test_ui_shell_markup.py`.

Test cần khẳng định:

- `GET /<hotel_slug>/rooms/dashboard/room-map` khi đã đăng nhập trả `200` và có `main`/sidebar/app content.
- `templates/layouts/base.html` có thẻ `meta name="viewport"`.
- Layout có nơi hiển thị tên khách sạn hiện tại và banner hỗ trợ cho Master admin khi đang ở tenant.
- `static/css/style.css` định nghĩa token semantic tối thiểu cho primary, surface, background, border, success, warning, danger.
- CSS có breakpoint chung cho sidebar/app content ở màn hình dưới desktop.

**Triển khai tối thiểu:**

- Sửa `templates/layouts/base.html`.
- Chuẩn hóa token ở đầu `static/css/style.css`.
- Bổ sung selector layout desktop/tablet; không thay đổi URL, route hoặc logic login.

**Refactor:**

- Gom các style layout lặp lại, bỏ magic number không cần thiết.
- Không xóa class cũ đang được template khác dùng trước khi đã tìm kiếm toàn project.

**Kiểm tra sau khi xanh:**

```powershell
& 'C:\tmp\hotel-management-tdd-venv\Scripts\python.exe' -m pytest tests/test_ui_shell_markup.py -q
& 'C:\tmp\hotel-management-tdd-venv\Scripts\python.exe' -m pytest -q
```

`bb-browser`: kiểm tra 1440 px và 1024 px ở sơ đồ phòng, sidebar/menu, scroll nội dung, focus cơ bản và console errors.

### Task 1.2: Chuẩn hóa component CSS nền

**Test đỏ trước:** mở rộng `tests/test_ui_shell_markup.py` để yêu cầu các selector dùng chung:

- `.page-header`, `.filter-bar`, `.status-badge`, `.data-state`, `.confirm-modal` hoặc tên cuối cùng đã chốt khi triển khai.
- Các selector có focus visible cho link/button/input.
- Không có `body { overflow: hidden; }` khiến content page không thể cuộn nếu không có vùng cuộn thay thế rõ ràng.

**Triển khai tối thiểu:**

- Thêm component CSS chung vào `static/css/style.css`.
- Chỉ áp dụng ngay cho Sơ đồ phòng và Timeline; không đổi đồng loạt mọi template trong task này.

**Kiểm tra sau khi xanh:**

- Chạy test task 1.1 và suite đầy đủ.
- `bb-browser`: keyboard tab qua sidebar, filter, action chính; không có focus mất dấu hoặc màn hình tràn ngang tại 1024 px.

## 5. Đợt 2 — Sơ đồ phòng (P0)

### Task 2.1: Bảo vệ dữ liệu thông báo booking

**Test đỏ trước:** mở rộng `tests/test_room_notices.py` bằng fixture một phòng có ít nhất ba booking sắp nhận.

Test cần khẳng định API sơ đồ phòng:

- Vẫn trả đủ notices thuộc đúng room và đúng tenant, theo thứ tự giờ check-in tăng dần.
- Không cắt dữ liệu API xuống một booking; sơ đồ phòng chỉ chọn booking gần nhất để hiển thị, còn Timeline cần dữ liệu lịch đầy đủ.

**Triển khai tối thiểu:**

- Chỉ sửa backend nếu test phát hiện API đang không đảm bảo thứ tự/dữ liệu.
- Không thay đổi schema hoặc API contract không cần thiết.

**Kiểm tra sau khi xanh:**

- Chạy `tests/test_room_notices.py` và `tests/test_tenant_isolation.py`.

### Task 2.2: Chỉ báo booking gần nhất và bỏ renderer chết

**Test đỏ trước:** cập nhật `tests/test_room_map_card_markup.py` để khẳng định:

- `renderRoomCard` chỉ lấy notice gần nhất để render chỉ báo booking.
- Card không render tên khách, danh sách booking, số lượng lịch, chuỗi UI `+N lịch khác`, popover hay modal lịch mở rộng.
- Card có nhãn trạng thái chữ và CTA `Xem thông tin` duy nhất cho booking sắp nhận.
- Popup/modal gọn của CTA phải nhận đúng `booking_room_id`, tên khách, giờ nhận, SĐT và tiền cọc của booking gần nhất; không hiển thị booking khác.
- `renderGrid` không còn `return` làm renderer cũ ở dưới trở thành unreachable; không còn `cardHtml`/`col.innerHTML = cardHtml` của renderer cũ.
- Nội dung tên khách/booking được gán qua DOM API thay vì nội suy HTML cho card mới.

**Triển khai tối thiểu:**

- Sửa `static/js/room.js`: giữ một renderer card duy nhất, chọn `room.notices[0]` sau khi đảm bảo thứ tự theo thời điểm; CTA mở popup/modal gọn thông tin booking gần nhất.
- Sửa `static/css/style.css`: card đồng chiều cao, body không chứa danh sách booking, popup/modal gọn và thông tin dễ quét.
- Giữ tất cả trạng thái và endpoint check-in/check-out hiện có.

**Refactor:**

- Xóa hẳn code renderer cũ sau khi renderer mới đã thay thế.
- Đặt helper format trạng thái/thời gian và action card gần renderer, tránh logic rải rác.

**Kiểm tra sau khi xanh:**

```powershell
& 'C:\tmp\hotel-management-tdd-venv\Scripts\python.exe' -m pytest tests/test_room_notices.py tests/test_room_map_card_markup.py -q
& 'C:\tmp\hotel-management-tdd-venv\Scripts\python.exe' -m pytest -q
```

`bb-browser` ở 1440 px:

- Phòng có 0, 1, 2 và trên 2 booking vẫn chỉ có một chỉ báo/CTA booking gần nhất.
- Card không cao bất thường, không có scrollbar booking, tên khách hoặc danh sách booking trực tiếp trong card.
- CTA `Xem thông tin` mở đúng booking gần nhất; CTA `Nhận phòng` trong popup/modal mới mở xác nhận.
- Không còn JavaScript error trong console.

### Task 2.3: Làm rõ popup thông tin và thao tác check-in

**Test đỏ trước:** bổ sung test route/API vào `tests/test_checkin.py` cho trường hợp booking room id truyền từ UI là số hợp lệ và thuộc tenant; giữ test từ chối booking thuộc tenant khác.

**Triển khai tối thiểu:**

- Ở `static/js/room.js`, popup thông tin dùng booking gần nhất và chuyển giá trị hidden input sang số trước khi gọi check-in; không gọi API khi giá trị rỗng/không hợp lệ.
- Điều chỉnh text/action card để CTA chính là `Xem thông tin`; CTA `Nhận phòng` chỉ nằm trong popup/modal.

**Kiểm tra sau khi xanh:**

- Chạy `tests/test_checkin.py`, test room map, test tenant isolation và suite đầy đủ.
- `bb-browser`: mở popup thông tin từ card, xác nhận hiển thị đúng dữ liệu booking gần nhất; xác nhận luồng check-in trên dữ liệu local chỉ khi dữ liệu test an toàn và được phép thay đổi; nếu không, chỉ kiểm tra đến modal và ghi rõ giới hạn.

## 6. Đợt 3 — Timeline (P0)

### Task 3.1: Regression test cấu trúc trang Timeline

**Test đỏ trước:** tạo `tests/test_timeline_ui_markup.py`.

Test yêu cầu:

- Route timeline của tenant đã đăng nhập trả `200` và có timeline container, page header, action `Đặt đoàn` và `Làm mới`.
- Không làm mất các modal/ID mà `timeline_manager.js`, `checkout.js`, `group_booking.js` đang phụ thuộc.
- Template dùng class component chung thay vì thêm style inline mới cho page header.

**Triển khai tối thiểu:**

- Sửa `templates/rooms/timeline.html` áp dụng `PageHeader`/`FilterBar` đã có.
- Chỉ di chuyển CSS presentation cần thiết sang stylesheet; không đổi ID hoặc handler trong cùng task.

**Kiểm tra sau khi xanh:**

- Chạy test mới, `tests/test_ui_regression.py`, toàn bộ pytest.
- `bb-browser`: timeline hiển thị, mở modal đặt đoàn, mở modal booking, refresh; không JS error.

### Task 3.2: Chuẩn hóa modal Timeline

**Test đỏ trước:** mở rộng `tests/test_timeline_ui_markup.py` để yêu cầu:

- Modal có heading/label và CTA chính/phụ rõ ràng.
- Vùng nội dung dài có wrapper cuộn; footer action còn nhìn thấy được.
- Nút icon-only trong modal có `aria-label` hoặc text/tooltip.

**Triển khai tối thiểu:**

- Sửa markup/CSS cho modal booking, chi tiết booking và hóa đơn trong `templates/rooms/timeline.html`.
- Giữ nguyên endpoint và các ID JavaScript đã kiểm tra ở task 3.1.

**Kiểm tra sau khi xanh:**

- Chạy test task 3.1–3.2 và toàn bộ suite.
- `bb-browser` 1440/1024 px: modal có nội dung dài, modal hóa đơn, tab dịch vụ/phòng, keyboard close/focus và console error.

## 7. Đợt 4 — Danh sách và form dùng chung (P1)

Thực hiện lần lượt Khách hàng → Kho → Dịch vụ → Giá phòng → Hóa đơn.

Với mỗi trang, lặp TDD sau:

1. Viết test route trả `200` với tenant hợp lệ và template có `PageHeader`, `FilterBar`/tìm kiếm, data state, action tạo mới.
2. Viết test markup đảm bảo nút icon-only có `aria-label`, input có `label`, form có vùng lỗi/thông báo.
3. Triển khai tối thiểu template/CSS/JS của đúng trang.
4. Chạy test file mới + test tenant liên quan + toàn bộ pytest.
5. Dùng `bb-browser` kiểm tra tải danh sách, empty/loading/error, mở form, thao tác tạo/sửa/xóa đến bước xác nhận an toàn.

**File dự kiến:**

- `tests/test_customers_ui_markup.py`, `templates/customers/index.html`, `static/js/customer.js`.
- `tests/test_warehouse_ui_markup.py`, `templates/warehouse/index.html`.
- `tests/test_services_ui_markup.py`, `templates/services/index.html`, `static/js/service_manager.js`.
- `tests/test_price_manager_ui_markup.py`, `templates/admin/price_manager.html`, `static/js/price_manager.js`.
- `tests/test_billing_ui_markup.py`, `templates/billing/index.html`.

Không thay `confirm()` trên toàn hệ thống trong đợt này; chỉ thay ở trang đang được xử lý và có test/kiểm tra UI tương ứng.

## 8. Đợt 5 — Báo cáo, nhân sự và Master Console (P1)

### Task 5.1: Báo cáo

**Test đỏ trước:** `tests/test_reports_ui_markup.py` kiểm tra route theo tenant/quyền admin, bộ lọc ngày có label, KPI/bảng có data state.

**File thực hiện:**

- `templates/reports/revenue.html`
- `templates/reports/expenses.html`
- `templates/reports/cashier.html`
- `templates/reports/index.html`

**Kiểm tra:** pytest theo test mới + quyền/tenant, sau đó `bb-browser` 1440 px với các khoảng ngày.

### Task 5.2: Nhân sự

**Test đỏ trước:** mở rộng `tests/test_hotel_user_management.py` và tạo `tests/test_staff_ui_markup.py`.

Test đảm bảo layout card/form/bảng mới vẫn giữ:

- Chỉ user đúng tenant được hiển thị/chỉnh sửa.
- Không thể xóa admin cuối cùng.
- Form tạo/reset password có label và luồng xác nhận.

**File thực hiện:** `templates/staff/index.html`, `static/css/style.css`; chỉ sửa controller nếu test chức năng hiện có phát hiện thiếu dữ liệu UI.

### Task 5.3: Master Console

**Test đỏ trước:** mở rộng `tests/test_master_access.py` và `tests/test_master_hotel_creation.py`, thêm `tests/test_master_ui_markup.py`.

Test đảm bảo:

- Chỉ master admin vào Master Console.
- KPI, bảng khách sạn, tìm kiếm/form tạo, action vào quản lý và trạng thái có mặt trong template.
- Hotel admin không thấy/chạm được route Master.

**File thực hiện:**

- `templates/master/base.html`
- `templates/master/dashboard.html`
- `templates/master/login.html`
- `static/css/style.css` hoặc stylesheet Master riêng nếu cần

**Kiểm tra:** pytest test master + toàn bộ suite; `bb-browser` login Master, tạo form ở trạng thái validation (không submit tạo dữ liệu nếu chưa được phép), vào hỗ trợ hotel và quay về Master Console.

## 9. Quy trình kiểm tra cuối mỗi đợt

1. Chạy test file thay đổi trước, sau đó full suite:

```powershell
& 'C:\tmp\hotel-management-tdd-venv\Scripts\python.exe' -m pytest -q
```

2. Dùng `bb-browser` mở các route đã thay đổi ở desktop 1440 px, xem snapshot/screenshot, kiểm tra console errors.
3. Với layout chung hoặc responsive, kiểm tra 1024 px và 768 px; không tuyên bố mobile tối ưu đầy đủ.
4. Đối chiếu checklist accessibility: nhãn, focus, tương phản, trạng thái loading/error, action phá hủy có xác nhận.
5. Báo cáo riêng: test đã chạy, luồng browser đã kiểm chứng, dữ liệu local nào không thể thao tác vì tránh thay đổi trạng thái.

## 10. Điểm dừng cần phê duyệt

- Sau Đợt 2: duyệt trực quan sơ đồ phòng và xác nhận chỉ báo/popup booking gần nhất là đủ cho lễ tân.
- Sau Đợt 3: duyệt Timeline và modal, trước khi chuẩn hóa hàng loạt trang CRUD.
- Trước khi thêm JavaScript test runner hoặc thay đổi API/schema: cần phê duyệt riêng.
- Trước khi thay thế toàn bộ `confirm()` còn lại bằng modal: cần phê duyệt theo đợt vì đây là thay đổi trải nghiệm rộng.
