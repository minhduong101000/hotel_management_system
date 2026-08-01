# Kế hoạch TDD: Làm mới thị giác giao diện Hotel POS Pro

**Ngày:** 02-08-2026

**Spec nguồn:** `docs/superpowers/specs/2026-08-02-ui-visual-refresh-design.md`

**Trạng thái:** Sẵn sàng triển khai sau khi người dùng phê duyệt kế hoạch

## 1. Mục tiêu và baseline

Kế hoạch này triển khai đợt visual refresh **Hospitality Operations — Bright & Calm** trên nền UI hiện tại. Phạm vi chỉ gồm presentation, accessibility, feedback và hành vi giao diện đã được spec cho phép; không thay đổi nghiệp vụ, API contract, database, quyền hoặc tenant scope.

Baseline đã kiểm tra trước khi lập kế hoạch:

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_ui_shell_markup.py tests/test_accessibility_markup.py tests/test_frontdesk_ui_polish.py tests/test_admin_ui_polish.py tests/test_finance_ui_polish.py tests/test_operation_modal_ui.py tests/test_room_map_card_markup.py tests/test_timeline_operations_ui.py tests/test_warehouse_batch_ui.py tests/test_workflow_modal_markup.py -q
```

Kết quả: `38 passed`.

Các nền tảng đã có và phải được kế thừa:

- Application shell, sidebar, topbar, skip link và focus style.
- `PageHeader`, `FilterBar`, `StatusBadge`, `operation-modal` và các workflow modal.
- Modal focus management và một phần async button state.
- Room card renderer hiện tại, Timeline controls và các partial booking/checkout dùng chung.
- Các test accessibility, tenant, nghiệp vụ và bảo mật hiện có.

Kế hoạch này thay thế phần visual refresh còn lại trong `docs/superpowers/plans/2026-07-30-global-ui-polish-tdd.md`; không sửa hoặc xóa tài liệu cũ.

## 2. Nguyên tắc triển khai bắt buộc

- Không triển khai đồng loạt toàn bộ template trong một commit.
- Mỗi task dưới đây là một hạng mục độc lập: test đỏ → triển khai tối thiểu → refactor → test xanh → kiểm tra `bb-browser` → commit riêng.
- Không đổi ID, `name`, `data-*`, handler hoặc cấu trúc mà JavaScript/nghiệp vụ đang phụ thuộc nếu chưa có test bảo vệ.
- Không thêm route, API hoặc CTA nghiệp vụ mới chỉ để phục vụ empty state. CTA chỉ gọi hành vi đã tồn tại như làm mới, mở form tạo hoặc chuyển sang trang có sẵn.
- Không thêm JavaScript test runner trong đợt này. Hành vi client đơn giản được bảo vệ bằng source/markup test và kiểm tra thật bằng `bb-browser`; nếu xuất hiện logic client phức tạp cần unit test, phải xin phê duyệt trước.
- Chỉ dùng màu semantic từ spec. Mọi tone sáng hơn phải vẫn đạt contrast đã chốt.
- Dữ liệu dùng cho kiểm tra trực quan phải là fixture/seed local cô lập; không thao tác production.
- Không commit các file đang dở hoặc file untracked không thuộc đúng task.

## 3. Chu trình TDD dùng cho mọi task

### Bước 1 — Viết test đỏ

- Mở rộng test gần phạm vi nhất thay vì tạo test trùng lặp.
- Test route/rendered HTML khi yêu cầu liên quan template và quyền.
- Test source chỉ dùng cho CSS token, selector bắt buộc hoặc JavaScript markup không thể thực thi bằng Flask test client.
- Chạy đúng test vừa sửa và lưu bằng chứng test thất bại vì yêu cầu mới chưa được triển khai.

### Bước 2 — Triển khai tối thiểu

- Chỉ sửa file cần thiết cho task hiện tại.
- Dùng component/token chung; không sao chép style riêng sang template.
- Giữ nguyên API, route và nghiệp vụ.

### Bước 3 — Refactor và chạy test xanh

Chạy test mục tiêu trước:

```powershell
& '.\venv\Scripts\python.exe' -m pytest <test-files-của-task> -q
```

Sau đó chạy toàn bộ suite:

```powershell
& '.\venv\Scripts\python.exe' -m pytest -q
git diff --check
```

### Bước 4 — Kiểm tra bằng `bb-browser`

- Kiểm tra route đã thay đổi tại desktop 1440 hoặc 1920 px.
- Task shell/responsive kiểm tra thêm 1024 và 768 px; lượt regression cuối kiểm tra chống vỡ tại 375 px.
- Kiểm tra keyboard focus, hover/pressed/disabled/loading nếu có, empty/loading/error state, modal và console errors.
- Chụp screenshot trước/sau cho màn hình đại diện của task.

### Bước 5 — Commit riêng

- Chỉ stage file thuộc task.
- Commit message bằng tiếng Anh theo gợi ý trong từng task.
- Không bắt đầu task kế tiếp nếu task hiện tại chưa xanh và chưa hoàn tất kiểm tra trình duyệt.

## 4. Ma trận kiểm thử

| Loại kiểm tra | Công cụ | Trách nhiệm |
|---|---|---|
| Token/CSS/JS source | `pytest` + `pathlib` | Bảo vệ selector, token, reduced motion, helper và trạng thái button |
| Route/template | Flask test client | Bảo vệ quyền, tenant, page shell, label, accessible name và component markup |
| Nghiệp vụ liên quan | Test hiện có | Đảm bảo polish UI không đổi booking, checkout, kho, tài chính hoặc quyền |
| Hành vi/trực quan | `bb-browser` | Xác nhận kích thước, spacing, màu, keyboard, modal, chart và console |
| Toàn hệ thống | `pytest -q` | Phát hiện regression ngoài phạm vi task |

## 5. Task 1 — Nền visual token, button và component dùng chung (P0)

### Test đỏ

Mở rộng:

- `tests/test_ui_shell_markup.py`.
- `tests/test_accessibility_markup.py`.

Test cần khẳng định:

- `static/css/style.css` có đủ token màu mới: brand navy, action, action hover, info, surface tint, text và focus ring.
- Có spacing token `--space-1` đến `--space-6`.
- `--font-sans` dùng `Be Vietnam Pro`, `Noto Sans`, `sans-serif`.
- `.app-content .btn` là kích thước mặc định 44 px; `.btn-sm` là 36 px desktop và 44 px dưới 992 px; `.btn-lg` là 48 px.
- `.btn-icon` và `.modal .btn-close` có hit area 44 × 44 px.
- Button có gap icon/text, hover, active, disabled, focus-visible và loading/busy style.
- Có selector dùng chung cho `DataState`, KPI card, button group và tabular number.
- Motion 150–250 ms và có `prefers-reduced-motion`.

Chạy đỏ:

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_ui_shell_markup.py tests/test_accessibility_markup.py -q
```

### Triển khai tối thiểu

File chính:

- `static/css/style.css`.

Thực hiện:

- Bổ sung token theo spec và ánh xạ Bootstrap variables sang token mới.
- Chuẩn hóa `.btn` mặc định là size medium; override có kiểm soát cho `.btn-sm`, `.btn-lg`, `.btn-icon`.
- Tạo style trạng thái hover/active/focus/disabled/loading mà không làm layout shift.
- Refactor `PageHeader`, `FilterBar`, `DataState`, KPI card, table cell, card, modal và numeric style dùng token.
- Giữ alias cho token/class cũ đang được template dùng; chưa xóa selector cũ trong task này.

### Kiểm tra

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_ui_shell_markup.py tests/test_accessibility_markup.py tests/test_operation_modal_ui.py tests/test_workflow_modal_markup.py -q
& '.\venv\Scripts\python.exe' -m pytest -q
git diff --check
```

`bb-browser`:

- Sơ đồ phòng: toolbar/button/status badge.
- Timeline: nhóm điều hướng và chế độ xem.
- Kho: primary/secondary button và modal nhập vật tư.
- Tab keyboard qua button để xác nhận focus ring không bị cắt.

**Commit:** `style: standardize visual tokens and buttons`

**Điểm duyệt:** Sau task này, người dùng duyệt palette, button và spacing trên Sơ đồ phòng, Timeline và Kho trước khi áp dụng hàng loạt.

## 6. Task 2 — Làm mới trang đăng nhập khách sạn (P1)

### Test đỏ

Mở rộng:

- `tests/test_admin_ui_polish.py`.
- `tests/test_accessibility_markup.py`.

Test cần khẳng định:

- Login dùng class shell/card/header/footer mới và không còn inline color `#2980b9`.
- Submit button dùng size lớn, có busy state và status region.
- Password có button hiện/ẩn với accessible name, `aria-pressed` và hit area 44 px.
- Label, autocomplete, CSRF và error `role="alert"` hiện có không bị mất.
- Script login chỉ đổi `type` password và accessible state; không can thiệp submit/authentication.

### Triển khai tối thiểu

File dự kiến:

- `templates/auth/login.html`.
- `static/css/style.css`.
- `static/js/login.js` nếu cần tách hành vi hiện/ẩn mật khẩu.

Thực hiện:

- Bỏ inline style/màu legacy; dùng navy/teal và token chung.
- Dùng card rộng 420–460 px ở desktop; giữ layout cân đối tại 1920 px và không vỡ ở 375 px.
- Dùng button 48 px, loading state khi submit và show/hide password.
- Dự trữ vùng alert để hạn chế layout jump.

### Kiểm tra

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_admin_ui_polish.py tests/test_accessibility_markup.py tests/test_csrf_protection.py tests/test_smoke.py -q
& '.\venv\Scripts\python.exe' -m pytest -q
git diff --check
```

`bb-browser`:

- Login 1920 px và 375 px.
- Tab qua username, password, toggle, remember và submit.
- Toggle password cập nhật icon/accessible state.
- Thử validation rỗng, đăng nhập sai và đăng nhập đúng; không có console error.

**Commit:** `style: refresh hotel login experience`

## 7. Task 3 — Polish sidebar và topbar (P1)

### Test đỏ

Mở rộng `tests/test_ui_shell_markup.py` để yêu cầu:

- Brand có cách xem đầy đủ tên khách sạn khi bị cắt (`title` hoặc accessible description).
- Nav giữ đủ icon + text, group heading và `aria-current`.
- User area có accessible account trigger/menu hoặc logout action rõ; không mất route logout hiện có.
- Mobile/tablet sidebar toggle có accessible name, expanded state và đóng được bằng Escape/nhấp ngoài nếu triển khai drawer.
- Không thêm accordion nhóm menu trong task này; ba nhóm hiện có chỉ được polish thị giác để tránh mở rộng hành vi không cần thiết.

### Triển khai tối thiểu

File dự kiến:

- `templates/layouts/base.html`.
- `static/css/style.css`.
- `static/js/main.js`.

Thực hiện:

- Chuẩn hóa khoảng cách icon/text, active state, group spacing và logout separation.
- Thêm tooltip/native title cho hotel name bị ellipsis.
- Giảm lặp thông tin topbar; chuyển user area thành account menu bằng Bootstrap nếu không làm tăng phụ thuộc.
- Hoàn thiện drawer behavior ở dưới 992 px, focus/escape và backdrop nếu cần.

### Kiểm tra

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_ui_shell_markup.py tests/test_ui_regression.py tests/test_master_access.py -q
& '.\venv\Scripts\python.exe' -m pytest -q
git diff --check
```

`bb-browser`: Sơ đồ phòng và Kho tại 1920/1024/768 px; active route, brand tooltip, account menu, sidebar toggle, Escape và console.

**Commit:** `style: polish application navigation shell`

## 8. Task 4 — Sơ đồ phòng và room card sáng, dễ quét (P1)

### Test đỏ

Mở rộng:

- `tests/test_room_map_card_markup.py`.
- `tests/test_frontdesk_ui_polish.py`.

Test cần khẳng định:

- Toolbar dùng button group/size chung và giữ filter/status IDs hiện tại.
- Room card có status label và style rail/tint; không truyền đạt trạng thái chỉ bằng màu.
- Card vẫn chỉ hiển thị booking gần nhất và giữ toàn bộ click/keyboard/checkout guards hiện có.
- Empty state có icon, title, description và action `Làm mới` gọi hành vi đã tồn tại; không tạo route cấu hình phòng mới.
- Loading/error/empty dùng `DataState`, không dùng một dòng `<i>Không tìm thấy phòng nào</i>`.
- Không quay lại renderer HTML không an toàn.

### Triển khai tối thiểu

File dự kiến:

- `templates/rooms/map.html`.
- `static/js/room.js`.
- `static/css/style.css`.

Thực hiện:

- Nhóm filter, refresh và status summary theo spacing token.
- Chuyển card sang surface/tint + status rail/badge; danger chỉ cho quá giờ/lỗi.
- Tạo loading/empty/error state có kích thước ổn định và retry dùng `fetchRooms()` hiện có.
- Không thay dữ liệu booking, API hoặc handler order/check-in/checkout.

### Kiểm tra

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_room_map_card_markup.py tests/test_room_notices.py tests/test_room_dashboard_query_budget.py tests/test_checkin.py tests/test_order_submission.py tests/test_order_history.py -q
& '.\venv\Scripts\python.exe' -m pytest -q
git diff --check
```

`bb-browser`:

- Trạng thái không có phòng, loading/error giả lập an toàn và room grid có dữ liệu local.
- Kiểm tra available/booked/occupied/hourly/overdue/dirty nếu fixture có đủ.
- Mở room card, order modal, booking info và checkout đến bước xác nhận; không thay đổi dữ liệu nếu chưa được phép.
- Keyboard Enter/Space trên card và console errors.

**Commit:** `style: refresh room map visual hierarchy`

## 9. Task 5 — Timeline toolbar và data states (P1)

### Test đỏ

Mở rộng:

- `tests/test_timeline_operations_ui.py`.
- `tests/test_frontdesk_ui_polish.py`.

Test cần khẳng định:

- Toolbar có ba nhóm: range navigation, view mode, filter/actions.
- Button giữ đủ ID/handler hiện tại và dùng button system chung.
- Active view có `aria-pressed` hoặc semantic state tương đương, không phụ thuộc màu duy nhất.
- Có ba data state phân biệt: chưa có phòng, không có booking theo filter, lỗi tải dữ liệu.
- Legend có text/icon và style nhẹ, không dùng gradient/rực làm tín hiệu duy nhất.
- `showTimelineState` và filter/view functions hiện có vẫn được gọi.

### Triển khai tối thiểu

File dự kiến:

- `templates/rooms/timeline.html`.
- `static/js/timeline_manager.js`.
- `static/css/style.css`.

Thực hiện:

- Chuẩn hóa button height/gap, group và active state.
- Refactor empty/error/loading state không làm thay đổi API Timeline.
- Làm legend gọn và bảo toàn màu trạng thái nghiệp vụ.
- Giữ nguyên các modal partial và ID được workflow script dùng.

### Kiểm tra

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_timeline_operations_ui.py tests/test_booking_reschedule_ui.py tests/test_workflow_modal_markup.py tests/test_booking_overlap.py tests/test_booking_state_aggregation.py -q
& '.\venv\Scripts\python.exe' -m pytest -q
git diff --check
```

`bb-browser`: Timeline tại 1920/1024 px; ngày/3 ngày/tuần, previous/today/next, status filter, đặt đoàn, empty/error states, keyboard và console.

**Commit:** `style: improve timeline controls and states`

## 10. Task 6 — Khách hàng và hóa đơn cũ (P1)

### Test đỏ

Mở rộng:

- `tests/test_frontdesk_ui_polish.py`.
- `tests/test_accessibility_markup.py`.
- `tests/test_customer_render_security.py`.

Test cần khẳng định:

- Hai trang dùng cùng page header, filter/table shell và DataState.
- Search/filter button có đúng cấp bậc; create customer là primary CTA duy nhất ở header.
- Customer row action dùng `.btn-icon`, có accessible name và tooltip; không quay lại `innerHTML` với dữ liệu khách hàng.
- Billing filter input có label liên kết; empty/loading/error nằm trong table container.
- Cột tiền và số lượng dùng class canh phải/tabular.

### Triển khai tối thiểu

File dự kiến:

- `templates/customers/index.html`.
- `static/js/customer.js`.
- `templates/billing/index.html`.
- `static/css/style.css`.

Thực hiện:

- Chuẩn hóa spacing của search/filter/action.
- Dùng button/icon system chung và giữ renderer customer an toàn bằng DOM API.
- Bổ sung DataState cho loading/empty/error của hai bảng.
- Không thay customer/billing endpoint hoặc dữ liệu hiển thị.

### Kiểm tra

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_frontdesk_ui_polish.py tests/test_accessibility_markup.py tests/test_customer_render_security.py tests/test_customer_phone_matching.py tests/test_csrf_protection.py -q
& '.\venv\Scripts\python.exe' -m pytest -q
git diff --check
```

`bb-browser`: customer search, empty/result table, modal tạo/sửa đến validation; billing filter, empty/detail modal; keyboard và console.

**Commit:** `style: unify front desk data tables`

## 11. Task 7 — Kho hàng và modal kho (P1)

### Test đỏ

Mở rộng:

- `tests/test_warehouse_batch_ui.py`.
- `tests/test_operation_modal_ui.py`.
- `tests/test_accessibility_markup.py`.

Test cần khẳng định:

- KPI hạn dùng/tồn kho dùng KPI component/surface tint chung.
- Empty state `Kho chưa có vật tư` có CTA mở form `Thêm vật tư` hiện có.
- Mọi `btn-close` trong warehouse có `aria-label`.
- Mọi label của modal thêm/sửa/restock/dispose/adjust có `for` trỏ đúng ID.
- Neutral create/edit modal dùng header teal; destructive modal dùng danger; warning chỉ dùng đúng nghĩa.
- Submit buttons có busy/status region và không cho double submit.

### Triển khai tối thiểu

File dự kiến:

- `templates/warehouse/index.html`.
- `static/css/style.css`.
- Chỉ sửa JavaScript trong template hoặc tách file nếu cần để quản lý busy/DataState; không đổi API.

Thực hiện:

- Chuẩn hóa KPI, table, empty/loading/error và action buttons.
- Hoàn thiện label/accessible name/helper text của modal.
- Áp dụng async button state cho save/restock/dispose/adjust.
- Giữ nguyên batch, expiry, disposal, adjustment và service linkage behavior.

### Kiểm tra

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_warehouse_batch_ui.py tests/test_inventory_batches.py tests/test_inventory_adjustments.py tests/test_inventory_batch_allocations.py tests/test_expense_inventory_sync.py tests/test_accessibility_markup.py -q
& '.\venv\Scripts\python.exe' -m pytest -q
git diff --check
```

`bb-browser`: empty/table state, add/edit, restock, batch list, dispose và adjust đến bước xác nhận; focus restore, accessible tree và console.

**Commit:** `style: polish warehouse workflows`

## 12. Task 8 — Dịch vụ và quản lý giá phòng (P2)

### Test đỏ

Mở rộng `tests/test_frontdesk_ui_polish.py` và `tests/test_operation_modal_ui.py`; tạo `tests/test_service_price_ui.py` chỉ nếu các yêu cầu sau không phù hợp hai file hiện có:

- Service và price pages dùng cùng page header/table/card/action system.
- Add service/add rule là primary CTA duy nhất.
- Icon-only edit/delete có accessible name và hit area chuẩn.
- Modal có label liên kết, close label, helper/error/status region và busy submit.
- Inline raw color/size thuộc component chính được chuyển sang token/class chung.
- Không thay pricing rule calculation hoặc service/inventory linkage.

### Triển khai tối thiểu

File dự kiến:

- `templates/services/index.html`.
- `static/js/service_manager.js`.
- `templates/admin/price_manager.html`.
- `static/js/price_manager.js`.
- `static/css/style.css`.

Thực hiện:

- Chuẩn hóa list/rule card, action buttons, DataState và modal.
- Giữ màu semantic cho ngày cuối tuần/ưu tiên nhưng thêm text/badge rõ.
- Loại bỏ inline presentation trong phạm vi component đang sửa.

### Kiểm tra

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_frontdesk_ui_polish.py tests/test_operation_modal_ui.py tests/test_pricing_quote.py tests/test_pricing_tenant_scope.py tests/test_inventory_batch_allocations.py tests/test_csrf_protection.py -q
& '.\venv\Scripts\python.exe' -m pytest -q
git diff --check
```

`bb-browser`: service empty/table/modal; price list/rule modal/edit/delete đến bước xác nhận; keyboard và console.

**Commit:** `style: unify service and pricing management`

## 13. Task 9 — Doanh thu, sổ quỹ và chi phí (P2)

### Test đỏ

Mở rộng:

- `tests/test_finance_ui_polish.py`.
- `tests/test_accessibility_markup.py`.

Test cần khẳng định:

- Ba trang dùng cùng filter/action/KPI/table component.
- Revenue script có nhánh kiểm tra dữ liệu trước khi khởi tạo Chart.js.
- Empty revenue không dựng canvas/trục giả; có DataState và retry dùng API hiện có.
- Chart có accessible summary hoặc bảng/text fallback; legend/label không phụ thuộc màu.
- Tiền và số lượng dùng canh phải/tabular; kỳ dữ liệu hiển thị rõ.
- Expense/cashier empty/loading/error và destructive action có semantic button đúng.
- Không yêu cầu API mới cho delta/KPI nếu dữ liệu hiện có không cung cấp.

### Triển khai tối thiểu

File dự kiến:

- `templates/reports/revenue.html`.
- `templates/reports/cashier.html`.
- `templates/reports/expenses.html`.
- `static/css/style.css`.

Thực hiện:

- Chuẩn hóa filter bar, KPI card và table shell.
- Chỉ khởi tạo/update chart khi có dữ liệu; destroy chart cũ đúng cách khi đổi kỳ.
- Bổ sung empty/error/retry và text summary cho chart.
- Giảm gradient/rực; dùng surface tint và semantic foreground đạt contrast.

### Kiểm tra

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_finance_ui_polish.py tests/test_cashier_report.py tests/test_report_financial_isolation.py tests/test_report_room_revenue.py tests/test_expense_voiding.py tests/test_expense_void_record.py tests/test_accessibility_markup.py -q
& '.\venv\Scripts\python.exe' -m pytest -q
git diff --check
```

`bb-browser`:

- Revenue empty và có dữ liệu; đổi kỳ, custom range, chart, summary và top rooms.
- Cashier filter/table/print form đến validation.
- Expense filter, add và void đến bước xác nhận.
- Dừng Chart animation trước khi screenshot nếu công cụ capture bị timeout; không thay behavior production.

**Commit:** `style: refresh financial dashboards`

## 14. Task 10 — Nhân sự, audit và Master Console (P2)

### Test đỏ

Mở rộng:

- `tests/test_admin_ui_polish.py`.
- `tests/test_accessibility_markup.py`.
- `tests/test_master_access.py`.
- `tests/test_hotel_user_management.py`.

Test cần khẳng định:

- Staff form/table dùng button, spacing, card và DataState chung.
- Reset password/save dùng primary/secondary đúng cấp; delete user tách thành danger action có accessible name.
- Audit filter/table/details dùng shared component và empty/error state.
- Master dashboard/login dùng cùng typography/radius/input/button principles nhưng giữ stylesheet/context riêng.
- Master login có password toggle/accessibility tương đương hotel login nếu triển khai trong task này.
- Không thay quyền Master/Hotel admin/Staff hoặc rule admin cuối cùng.

### Triển khai tối thiểu

File dự kiến:

- `templates/staff/index.html`.
- `templates/audit/index.html`.
- `templates/master/base.html`.
- `templates/master/dashboard.html`.
- `templates/master/login.html`.
- `static/css/master.css`.
- `static/css/style.css`.

Thực hiện:

- Chuẩn hóa form/table/action và feedback.
- Tách destructive action về đúng nhóm/semantic.
- Làm Master Console sáng và nhất quán nhưng giữ nhận diện ngữ cảnh Master.
- Refactor template Master đang viết một dòng thành markup dễ bảo trì, không đổi form action/CSRF.

### Kiểm tra

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_admin_ui_polish.py tests/test_activity_log.py tests/test_audit_log.py tests/test_master_access.py tests/test_master_hotel_creation.py tests/test_hotel_user_management.py tests/test_staff_permissions.py tests/test_accessibility_markup.py -q
& '.\venv\Scripts\python.exe' -m pytest -q
git diff --check
```

`bb-browser`: Staff form/table/reset/delete đến xác nhận; audit filter/details; Master login/dashboard/support hotel/return to Master; keyboard và console.

**Commit:** `style: polish administration interfaces`

## 15. Task 11 — Accessibility, responsive và regression cuối (P2)

### Test đỏ

Mở rộng:

- `tests/test_accessibility_markup.py`.
- `tests/test_ui_shell_markup.py`.
- `tests/test_ui_regression.py`.

Thêm kiểm tra có phạm vi rõ:

- Tất cả `btn-close` trong các template đã sửa có accessible name.
- Icon-only action trong các trang đã sửa có `aria-label` hoặc accessible text.
- Label quan trọng liên kết đúng input.
- CSS có breakpoint 375/768/992/1440 phù hợp, input 16 px ở viewport nhỏ, table wrapper và no-page-overflow rules.
- Focus-visible, reduced motion, disabled/loading và 44 px touch target không bị regression.
- Không còn màu legacy/inline style đã được task trước thay thế trong phạm vi component chính.

Không viết regex quét toàn project nếu gây false positive với Jinja; dùng danh sách template/control cụ thể để test có ý nghĩa.

### Triển khai tối thiểu

File dự kiến:

- `static/css/style.css`.
- `static/css/master.css`.
- Các template đã nằm trong phạm vi task 1–10 nếu sweep phát hiện thiếu sót.

Thực hiện:

- Chỉ sửa regression/accessibility/responsive còn lại; không redesign mới ở task cuối.
- Gom media query và alias selector sau khi mọi trang đã chuyển sang component mới.
- Chỉ xóa selector cũ sau khi `rg` xác nhận không còn consumer.

### Kiểm tra tự động

```powershell
& '.\venv\Scripts\python.exe' -m pytest tests/test_accessibility_markup.py tests/test_ui_shell_markup.py tests/test_ui_regression.py -q
& '.\venv\Scripts\python.exe' -m pytest -q
git diff --check
```

### Ma trận `bb-browser` cuối

| Viewport | Màn hình bắt buộc |
|---:|---|
| 1920 px | Login, Sơ đồ phòng, Timeline, Doanh thu, Kho/modal |
| 1440 px | Khách hàng, Hóa đơn, Dịch vụ, Giá, Chi phí, Staff |
| 1024 px | Sidebar/topbar, Sơ đồ phòng, Timeline, bảng và modal rộng |
| 768 px | Sidebar drawer, toolbar wrap, bảng scroll, modal |
| 375 px | Login và kiểm tra chống vỡ/tràn ngang của shell cơ bản |

Với mỗi màn hình:

- `snap` kiểm tra accessibility tree.
- `screenshot` kiểm tra khoảng cách, màu và hierarchy.
- `errors` và `console` phải không có lỗi mới.
- Tab keyboard qua các hành động chính; Escape đóng menu/modal phù hợp.
- Kiểm tra empty và populated state khi dữ liệu local cho phép.

**Commit:** `test: complete UI accessibility regression sweep`

## 16. Thứ tự commit dự kiến

1. `style: standardize visual tokens and buttons`
2. `style: refresh hotel login experience`
3. `style: polish application navigation shell`
4. `style: refresh room map visual hierarchy`
5. `style: improve timeline controls and states`
6. `style: unify front desk data tables`
7. `style: polish warehouse workflows`
8. `style: unify service and pricing management`
9. `style: refresh financial dashboards`
10. `style: polish administration interfaces`
11. `test: complete UI accessibility regression sweep`

## 17. Điều kiện dừng và điểm cần xin xác nhận

- Dừng sau Task 1 để người dùng duyệt trực quan palette, button và spacing trước khi áp dụng hàng loạt.
- Nếu empty-state CTA cần route hoặc quyền chưa tồn tại, không tự thêm chức năng; xin xác nhận.
- Nếu cần thêm API để có trend/delta KPI, giữ UI hiện tại và xin xác nhận thay đổi backend riêng.
- Nếu JavaScript behavior mới vượt khả năng kiểm chứng hợp lý bằng source test + `bb-browser`, xin phép thêm test runner trước khi triển khai.
- Nếu fixture local không đủ trạng thái populated để kiểm tra trực quan, tạo fixture/seed test cô lập trong task tương ứng; không tự sửa dữ liệu production-like.
- Nếu CSS global làm vỡ trang ngoài task, revert phần selector quá rộng trong chính task đó; không để regression sang task sau.

## 18. Định nghĩa hoàn tất toàn bộ kế hoạch

- Cả 11 task đã hoàn thành, mỗi task có test đỏ được ghi nhận, test xanh, `bb-browser` và commit riêng.
- Full `pytest -q` xanh sau task cuối.
- `git diff --check` xanh; không stage/commit file ngoài phạm vi.
- Các button cùng vai trò có cùng màu, kích thước và state; primary 44 px, icon-only 44 × 44 px, button group gap tối thiểu 8 px.
- Login, shell, Sơ đồ phòng, Timeline, bảng CRUD, Kho, báo cáo và quản trị dùng cùng visual language.
- Empty/loading/error state hoàn chỉnh; revenue không dựng chart/trục giả khi rỗng.
- Accessibility và responsive đạt tiêu chí trong spec; không có JavaScript error mới.
- Không đổi nghiệp vụ, API contract, quyền hoặc tenant isolation.
