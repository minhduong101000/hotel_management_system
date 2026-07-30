# Kế hoạch TDD: Củng cố tính toàn vẹn nghiệp vụ, bảo mật và production

**Ngày:** 30-07-2026

**Trạng thái:** Chờ phê duyệt để triển khai

**Spec nguồn:** `docs/superpowers/specs/2026-07-30-business-integrity-remediation-design.md`

**Phạm vi:** Stored XSS, CSRF, cấu hình production, Alembic/schema đa tenant, test database production, báo cáo, operation/payment, pricing, checkout lẻ/đoàn, kho/dịch vụ, dời/hủy lịch, trạng thái tổng hợp, reconciliation, accessibility và hiệu năng dashboard phòng.

## 1. Kết quả cần đạt

Kế hoạch này chuyển toàn bộ spec nguồn thành các lát cắt TDD độc lập. Mỗi hạng mục phải:

1. Có test tái hiện lỗi và thất bại vì đúng nguyên nhân trước khi sửa.
2. Có triển khai tối thiểu để test mới qua.
3. Được refactor trong khi giữ test xanh.
4. Chạy kiểm tra hồi quy phù hợp.
5. Kiểm tra `bb-browser` nếu có thay đổi UI.
6. Tạo một commit riêng bằng tiếng Anh, không chứa file dở dang hoặc thay đổi không liên quan.

Không triển khai công nợ, cổng thanh toán, hóa đơn điện tử, chuyển phòng sau check-in hoặc tự động sửa dữ liệu tài chính lịch sử.

## 2. Cổng phê duyệt trước khi viết code

### 2.1. Cổng G0 — quyết định nghiệp vụ

Trước mọi hạng mục ghi phụ thuộc G0, bắt đầu từ hạng mục 6, cần người phụ trách nghiệp vụ phê duyệt năm quyết định:

1. Checkout chỉ thành công khi số dư phải thu về `0`; không hỗ trợ công nợ trong luồng hiện tại.
2. Đêm ở quá dùng đơn giá snapshot của đêm cuối gần nhất.
3. Giữ `BookingService` với `quantity = 0` để bảo toàn lịch sử, không xóa cứng.
4. Expense đã void không vào P&L/sổ quỹ và không tự đảo tồn kho.
5. Reconciliation luôn chạy `dry-run` trước; chỉ `apply` khi có phê duyệt riêng.

Các giá trị trên là mặc định đề xuất trong spec, chưa được xem là quyết định đã duyệt chỉ vì plan đã được tạo.

### 2.2. Cổng G1 — môi trường MySQL dùng cho test

Trước hạng mục 3 cần một database MySQL dùng riêng cho test migration/integration. Biến môi trường đề xuất:

```powershell
$env:TEST_MYSQL_DATABASE_URL = "mysql+pymysql://<user>:<password>@<host>/<test_database>"
```

Database này không được trỏ vào production hoặc database có dữ liệu cần giữ. Test destructive chỉ được phép chạy sau khi fixture xác nhận tên database thuộc allowlist test.

### 2.3. Cổng G2 — dữ liệu lịch sử

Không chạy lệnh reconciliation ở chế độ `apply` trong quá trình triển khai. Hạng mục 13 chỉ xây command, test và tạo báo cáo `dry-run`; việc áp dụng lên dữ liệu thật cần một phê duyệt vận hành riêng.

## 3. Quy ước thực thi TDD

### 3.1. Chu kỳ bắt buộc cho mỗi hạng mục

```text
Kiểm tra worktree
  → viết test nhỏ nhất
  → chạy và lưu bằng chứng RED
  → triển khai tối thiểu
  → chạy test đích GREEN
  → refactor
  → chạy test liên quan + full regression
  → kiểm tra browser nếu có UI
  → kiểm tra diff
  → commit riêng
```

Không bắt đầu hạng mục kế tiếp khi hạng mục hiện tại chưa xanh và chưa có commit, trừ khi bị chặn và người dùng quyết định đổi phạm vi.

### 3.2. Lệnh chuẩn

```powershell
# Test đích
.\venv\Scripts\python.exe -m pytest <test-file> -q

# Toàn bộ test nhanh
.\venv\Scripts\python.exe -m pytest -q

# Kiểm tra Alembic head
.\venv\Scripts\python.exe -m flask --app app db heads

# Test MySQL được đánh dấu riêng
.\venv\Scripts\python.exe -m pytest -m mysql -q

# Kiểm tra thay đổi trước commit
git status --short
git diff --check
git diff -- <các-file-của-hạng-mục>
```

Không dùng `pytest.exe` trực tiếp nếu làm sai module path của project. Không stage các file untracked hoặc thay đổi sẵn có của người dùng ngoài hạng mục.

### 3.3. Ma trận kiểm thử

| Lớp | Mục đích | Khi chạy |
|---|---|---|
| SQLite in-memory + `db.create_all()` | Unit/API nhanh, phản hồi ngắn | Mỗi vòng RED/GREEN |
| Alembic graph/schema | Một head, metadata và migration nhất quán | Hạng mục 2–5 và full regression |
| MySQL integration | Unique constraint, transaction, row lock, kiểu dữ liệu | Hạng mục 3, 7–13 |
| `bb-browser` desktop | XSS runtime, keyboard, focus, modal, lỗi/loading, console | Mọi hạng mục có UI |

SQLite không được dùng làm bằng chứng duy nhất cho hành vi migration, constraint hoặc `with_for_update()`.

## 4. Thứ tự phụ thuộc

```text
Stored XSS ───────────────────────────────────────────────┐
                                                        │
Alembic merge → Room tenant constraint → MySQL harness ─┼→ Operation/Payment
                                                        │         │
Production config → CSRF foundation ────────────────────┤         ├→ Pricing quote
                                                        │         │       │
Report isolation/void ──────────────────────────────────┤         │       ├→ Checkout lẻ
                                                        │         │       └→ Checkout đoàn
Kho nền tảng ───────────────────────────────────────────┤         │
Dời lịch/state ─────────────────────────────────────────┤         │
                                                        │         └→ Reconciliation
Accessibility + query budget ───────────────────────────┴→ Nghiệm thu cuối
```

Pricing quote nền tảng được thực hiện trước checkout vì checkout phải dùng quote do server tính. Phần overstay được hoàn thiện trong cùng nhánh pricing sau khi G0 được duyệt.

## 5. Hạng mục 1 — Chặn Stored XSS ở danh sách khách hàng

**Ưu tiên:** P0

**Phụ thuộc:** Không
**Commit:** `fix: prevent stored XSS in customer list`

### Test đỏ

Tạo `tests/test_customer_render_security.py`:

- Seed customer có `name`, `phone`, `email`, `address` chứa payload HTML/event handler.
- Khẳng định trang không nhúng dữ liệu customer vào inline JavaScript.
- Kiểm tra source `static/js/customer.js` không gán dữ liệu customer không tin cậy vào `innerHTML`.
- Kiểm tra nút sửa/xóa không tạo inline `onclick` chứa dữ liệu customer.
- API vẫn trả nguyên dữ liệu dưới dạng JSON để frontend render bằng text, không “lọc” làm mất dữ liệu gốc.

Chạy:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_customer_render_security.py -q
```

RED mong đợi: test chỉ ra `innerHTML`/inline handler hiện tại trong `static/js/customer.js`.

### Triển khai tối thiểu

Sửa:

- `static/js/customer.js`
- `templates/customers/index.html` nếu cần container/template an toàn

Yêu cầu:

- Tạo node bằng `createElement`, gán nội dung bằng `textContent`.
- Gắn ID bằng `dataset`; đăng ký action bằng `addEventListener` hoặc event delegation.
- Không chèn dữ liệu customer vào HTML string, selector hoặc inline event handler.
- Không coi validation server là cơ chế chống XSS; dữ liệu vẫn phải được output-encode tại sink.

### GREEN và kiểm tra browser

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_customer_render_security.py tests/test_audit_log.py tests/test_frontdesk_ui_polish.py -q
.\venv\Scripts\python.exe -m pytest -q
```

Với `bb-browser` ở desktop:

1. Tạo/mở bản ghi chứa `onerror=window.reviewXss=123` và thẻ HTML.
2. Xác nhận danh sách hiển thị payload như text.
3. Xác nhận `window.reviewXss` không được tạo.
4. Thử sửa/xóa đúng bản ghi.
5. Xác nhận console không có lỗi.

## 6. Hạng mục 2 — Hợp nhất hai Alembic head

**Ưu tiên:** P1

**Phụ thuộc:** Không
**Commit:** `chore: merge alembic revision heads`

### Test đỏ

Tạo `tests/test_migration_graph.py` dùng Alembic `ScriptDirectory`:

- `get_heads()` phải trả đúng một revision.
- Head duy nhất phải chứa lịch sử của cả `a6b0c4d8e1f3` và `c8d2e3f4a5b6`.
- Không revision nào bị orphan.

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_migration_graph.py -q
```

RED mong đợi: nhận hai head hiện hữu.

### Triển khai tối thiểu

Tạo merge revision trong `migrations/versions/`:

- `down_revision = ('a6b0c4d8e1f3', 'c8d2e3f4a5b6')`.
- `upgrade()` và `downgrade()` không thay đổi schema.
- Không sửa lịch sử các revision đã tồn tại.

### GREEN

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_migration_graph.py -q
.\venv\Scripts\python.exe -m flask --app app db heads
.\venv\Scripts\python.exe -m flask --app app db upgrade --sql
```

Nghiệm thu: đúng một head; SQL offline được tạo mà không còn lỗi “Multiple head revisions”.

## 7. Hạng mục 3 — Đồng bộ unique số phòng theo tenant

**Ưu tiên:** P1

**Phụ thuộc:** Hạng mục 2, G1
**Commit:** `fix: scope room numbers by hotel`

### Test đỏ

Tạo:

- `tests/test_room_schema_constraints.py`
- `tests/integration/test_room_migration_mysql.py`
- marker `mysql` trong `pytest.ini`

Ca test:

- Metadata model có named unique constraint `(hotel_id, room_number)`.
- Hai khách sạn được phép cùng có phòng `101`.
- Một khách sạn không được có hai phòng `101`.
- Schema dựng bằng Alembic có constraint giống metadata.
- Upgrade từ database trống chạy thành công.
- Upgrade từ từng head cũ đến head mới chạy thành công.
- Preflight phát hiện duplicate trong cùng khách sạn và dừng với thông báo có thể xử lý, không âm thầm xóa dữ liệu.

RED mong đợi: model chưa có constraint; migration hiện vẫn giữ global unique `room_number`.

### Triển khai tối thiểu

Sửa:

- `models/room.py`
- migration mới sau merge head
- fixture migration/MySQL mới trong `tests/integration/`

Migration phải:

1. Kiểm tra duplicate `(hotel_id, room_number)`.
2. Dừng an toàn nếu có conflict.
3. Drop global unique/index cũ theo tên được inspect thực tế.
4. Tạo named unique constraint mới.
5. Có downgrade đối xứng và cảnh báo rõ nếu dữ liệu đa tenant không thể quay lại global unique.

### GREEN

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_room_schema_constraints.py tests/test_tenant_isolation.py -q
.\venv\Scripts\python.exe -m pytest -m mysql tests/integration/test_room_migration_mysql.py -q
.\venv\Scripts\python.exe -m pytest -q
```

Không đánh dấu hoàn tất nếu chưa chạy được MySQL; phải ghi rõ blocker môi trường.

## 8. Hạng mục 4 — Cấu hình production fail-closed

**Ưu tiên:** P1

**Phụ thuộc:** Không
**Commit:** `fix: enforce secure production configuration`

### Test đỏ

Tạo `tests/test_production_config.py`:

- Production thiếu `SECRET_KEY` phải từ chối khởi động.
- Production thiếu `DATABASE_URL` phải từ chối khởi động.
- Từ chối secret/credential mặc định đã biết.
- Production không bật debug.
- Import hoặc chạy entrypoint không gọi `db.create_all()`, ALTER ad-hoc, backfill hay tạo user mặc định.
- Development/testing vẫn có cấu hình tường minh và test suite không phụ thuộc MySQL máy cá nhân.
- Seed development chỉ chạy qua CLI rõ ràng và không ghi mật khẩu cố định.

RED mong đợi: `config.py` fallback secret/database; `app.py` seed `admin123`/`staff123`, gọi `db.create_all()` và `debug=True`.

### Triển khai tối thiểu

Sửa:

- `config.py`
- `app.py`
- thêm module CLI phù hợp, ví dụ `commands/development.py`
- `requirements.txt` hoặc tài liệu env nếu cần

Yêu cầu:

- Tách `DevelopmentConfig`, `TestingConfig`, `ProductionConfig`.
- Validate production config trước khi kết nối database.
- Startup production chỉ khởi tạo app; schema đi qua Alembic.
- Seed/reconcile là command chủ động, yêu cầu tham số/secret hợp lệ.
- Không log credential hoặc password.

### GREEN

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_production_config.py tests/test_smoke.py -q
.\venv\Scripts\python.exe -m pytest -q
```

## 9. Hạng mục 5 — Nền tảng CSRF cho form và JSON API

**Ưu tiên:** P1

**Phụ thuộc:** Hạng mục 4
**Commit:** `feat: add CSRF protection`

### Test đỏ

Tạo `tests/test_csrf_protection.py`:

- Form mutation thiếu/sai token bị chặn.
- JSON `POST`, `PUT`, `PATCH`, `DELETE` thiếu/sai token bị chặn.
- Token từ session khác bị chặn.
- Token hợp lệ cho phép request cùng-origin.
- Lỗi API trả JSON ổn định; form nhận response phù hợp.
- Login và các mutation chính có token trong markup/header.
- `GET`, `HEAD`, `OPTIONS` không bị chặn.

TestingConfig có thể tắt CSRF cho test cũ, nhưng test file này phải tạo app với CSRF bật. Không được “pass” bằng cách miễn trừ hàng loạt blueprint.

### Triển khai tối thiểu

Sửa:

- `requirements.txt` thêm `Flask-WTF`
- `extensions.py`
- `app.py`
- `templates/layouts/base.html`
- các form đăng nhập/master login
- `static/js/main.js` tạo wrapper fetch dùng chung
- chuyển các mutation frontend sang wrapper, ưu tiên customer/staff/checkout/warehouse trước rồi bao phủ toàn bộ

API error contract tối thiểu:

```json
{
  "success": false,
  "error_code": "csrf_failed",
  "msg": "Phiên thao tác không hợp lệ hoặc đã hết hạn."
}
```

### GREEN và browser

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_csrf_protection.py tests/test_smoke.py tests/test_master_access.py -q
.\venv\Scripts\python.exe -m pytest -q
```

Với `bb-browser`: login, tạo/sửa/xóa customer và một mutation staff/checkout; xác nhận request hợp lệ chạy được, token thiếu bị chặn, lỗi hết phiên dễ hiểu, console sạch.

## 10. Hạng mục 6 — Cô lập tenant và loại Expense void khỏi báo cáo

**Ưu tiên:** P0

**Phụ thuộc:** G0 cho chính sách void
**Commit:** `fix: isolate tenant financial reports`

### Test đỏ

Mở rộng/tạo:

- `tests/test_report_room_revenue.py`
- `tests/test_report_financial_isolation.py`
- `tests/test_expense_void_record.py`
- `tests/test_cashier_report.py`

Ca test:

- Revenue, expense, profit và cashier chỉ dùng dữ liệu `current_hotel_id`.
- Expense `is_voided=True` không vào P&L hoặc sổ quỹ.
- Khoảng ngày áp dụng nhất quán theo timezone nghiệp vụ.
- Occupancy tính theo số room-night khả dụng, không đếm số booking.
- Booking nhiều phòng nối đúng `BookingRoom.room_id`.
- Không rò rỉ tên khách, phòng hoặc amount của khách sạn khác.

RED mong đợi: các aggregate còn thiếu tenant/void filter hoặc công thức occupancy hiện tại khác invariant.

### Triển khai tối thiểu

Sửa:

- `controllers/report_controller.py`
- `controllers/cashier_controller.py`
- helper query/report mới trong `services/` nếu cần
- template report chỉ khi contract response thay đổi

Mọi aggregate phải bắt đầu từ tenant scope tường minh; không lọc sau khi đã aggregate.

### GREEN và browser

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_report_room_revenue.py tests/test_report_financial_isolation.py tests/test_cashier_report.py tests/test_expense_void_record.py -q
.\venv\Scripts\python.exe -m pytest -q
```

Nếu UI đổi, dùng `bb-browser` kiểm tra filter ngày, empty state, số revenue/expense/profit/occupancy và console.

## 11. Hạng mục 7 — Nền tảng BusinessOperation, Payment và transaction

**Ưu tiên:** P0

**Phụ thuộc:** Hạng mục 2–3, G1
**Commit:** `feat: link payments to business operations`

### Test đỏ

Tạo:

- `tests/test_business_operation_results.py`
- `tests/test_payment_operation_linkage.py`
- `tests/integration/test_operation_concurrency_mysql.py`

Ca test:

- `Payment.hotel_id` luôn bắt buộc và khớp tenant của booking/operation.
- Payment do mutation tạo có liên kết tới `BusinessOperation`.
- Mỗi operation có component key ổn định; unique trong tenant.
- Operation hoàn tất lưu result snapshot đủ để retry trả cùng kết quả.
- Hai request đồng thời cùng idempotency key chỉ tạo một operation/một bộ payment.
- Exception giữa transaction rollback cả state, payment, inventory và operation chưa hoàn tất.
- Tiền dùng `Decimal`, không dùng float cho phép tính ghi sổ.

### Triển khai tối thiểu

Sửa:

- `models/business_operation.py`
- `models/payment.py`
- `services/payment_service.py`
- thêm `services/business_operation_service.py`
- migration mới sau room constraint

Schema dự kiến:

- `business_operations.result_snapshot`
- `business_operations.request_fingerprint`
- `payments.business_operation_id`
- `payments.component_key`
- named unique/index theo `(hotel_id, business_operation_id, component_key)`

Không đặt `commit()` trong helper thấp; transaction do service use-case sở hữu.

### GREEN

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_business_operation_results.py tests/test_payment_operation_linkage.py tests/test_checkout_idempotency.py tests/test_booking_cancellation.py -q
.\venv\Scripts\python.exe -m pytest -m mysql tests/integration/test_operation_concurrency_mysql.py -q
.\venv\Scripts\python.exe -m pytest -q
```

## 12. Hạng mục 8 — PriceQuote duy nhất, cọc và overstay snapshot

**Ưu tiên:** P0/P1

**Phụ thuộc:** Hạng mục 7, G0
**Commit:** `feat: unify booking price quotes`

### Test đỏ

Mở rộng/tạo:

- `tests/test_pricing_quote.py`
- `tests/test_pricing_nightly_breakdown.py`
- `tests/test_pricing_tenant_scope.py`
- `tests/test_booking_deposit_rules.py`
- `tests/test_checkout_quote_staleness.py`

Ca test:

- Booking create, preview, deposit validation và checkout gọi cùng PriceQuote service.
- Quote có room lines, service lines, tax, deposit, total, balance, currency và fingerprint/version.
- Giá theo đêm dùng đúng business date và tenant.
- Booking hiện hữu ưu tiên snapshot, không đổi theo rule mới.
- Ở quá ngày nối thêm breakdown `overstay_extension` bằng giá snapshot đêm cuối.
- Cọc tối đa/đề xuất được tính từ quote server.
- Confirm với quote cũ trả `409 quote_stale` và quote mới; không mutation.

### Triển khai tối thiểu

Sửa:

- `services/pricing_service.py`
- thêm value object/service `services/booking_quote_service.py`
- `controllers/booking_controller.py`
- `controllers/room_controller.py`
- model/migration snapshot nếu schema hiện tại chưa đủ
- frontend booking/checkout chỉ hiển thị output server

Giữ lớp tương thích mỏng cho call site cũ trong lúc refactor, sau đó xóa khi mọi call site đã chuyển và test xanh.

### GREEN và browser

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_pricing_quote.py tests/test_pricing_nightly_breakdown.py tests/test_pricing_tenant_scope.py tests/test_booking_deposit_rules.py tests/test_checkout_quote_staleness.py -q
.\venv\Scripts\python.exe -m pytest -q
```

Với `bb-browser`: tạo booking thường/đoàn, thay ngày và VAT, kiểm tra tiền cọc; mở stale quote và xác nhận UI bắt buộc tải lại trước khi thanh toán.

## 13. Hạng mục 9 — Checkout lẻ server-authoritative và idempotent

**Ưu tiên:** P0

**Phụ thuộc:** Hạng mục 7–8, G0
**Commit:** `fix: enforce authoritative room checkout`

### Test đỏ

Mở rộng:

- `tests/test_checkout_idempotency.py`
- tạo `tests/test_checkout_settlement.py`
- tạo `tests/test_checkout_state_guards.py`
- tạo `tests/integration/test_checkout_concurrency_mysql.py`

Ca test:

- Chỉ `BookingRoom.checked_in` được checkout.
- Client không thể quyết định amount bằng cách sửa payload.
- Confirm dùng quote reference/fingerprint và tính lại trên server.
- Thiếu tiền bị chặn; đủ tiền tạo settlement đúng số.
- Cọc dư tạo Payment loại `refund`, không giả làm `room_payment`.
- Retry cùng key trả result snapshot, không tạo payment/audit/inventory lần hai.
- Hai request đồng thời chỉ một request mutation.
- Lỗi giữa chừng rollback toàn bộ.
- Room, BookingRoom, Booking và payment status đạt state sau cùng nhất quán.

### Triển khai tối thiểu

Sửa:

- checkout endpoint trong `controllers/room_controller.py` hoặc blueprint thực tế
- `services/business_operation_service.py`
- `services/payment_service.py`
- thêm `services/booking_state_service.py`
- `static/js/checkout.js`
- `templates/rooms/_checkout_modal.html`

Client chỉ gửi:

- `booking_room_id`
- `quote_reference`
- `include_tax`
- `payment_method`
- `idempotency_key`

Không nhận `amount` client làm nguồn ghi sổ.

### GREEN và browser

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_checkout_idempotency.py tests/test_checkout_settlement.py tests/test_checkout_state_guards.py tests/test_audit_log.py -q
.\venv\Scripts\python.exe -m pytest -m mysql tests/integration/test_checkout_concurrency_mysql.py -q
.\venv\Scripts\python.exe -m pytest -q
```

Với `bb-browser`: preview → confirm; thử double-click; thử quote stale; thử phòng chưa check-in; kiểm tra loading, lỗi, focus và console.

## 14. Hạng mục 10 — Checkout đoàn đúng trạng thái và tổng tiền

**Ưu tiên:** P0

**Phụ thuộc:** Hạng mục 9
**Commit:** `fix: make group checkout atomic and idempotent`

### Test đỏ

Tạo `tests/test_group_checkout.py` và `tests/integration/test_group_checkout_concurrency_mysql.py`:

- Chặn toàn bộ nếu còn phòng `booked`; response liệt kê phòng chưa nhận.
- Chỉ checkout tập phòng `checked_in`; không sửa phòng đã kết thúc.
- Grand total lấy từ tất cả room/service/tax/refund component hợp lệ.
- Retry không ghi `Booking.total_amount` về `0`.
- Payment component không lặp.
- Booking cha chỉ completed theo aggregate rule.
- Hai request đồng thời cho cùng booking chỉ tạo một kết quả.
- Lỗi một phòng rollback toàn đoàn.

### Triển khai tối thiểu

Sửa:

- group checkout endpoint trong controller hiện hữu
- `services/booking_quote_service.py`
- `services/business_operation_service.py`
- `services/booking_state_service.py`
- `static/js/checkout.js`
- `templates/rooms/_group_checkout_modal.html`

Lock booking và các BookingRoom theo thứ tự ID ổn định để giảm deadlock.

### GREEN và browser

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_group_checkout.py tests/test_checkout_idempotency.py tests/test_pricing_nightly_breakdown.py tests/test_audit_log.py -q
.\venv\Scripts\python.exe -m pytest -m mysql tests/integration/test_group_checkout_concurrency_mysql.py -q
.\venv\Scripts\python.exe -m pytest -q
```

Với `bb-browser`: đoàn có phòng booked phải bị chặn và nêu phòng; đoàn hợp lệ hiển thị từng thành phần, grand total, refund/balance; double-click không nhân đôi.

## 15. Hạng mục 11 — Toàn vẹn kho theo lô và hóa đơn dịch vụ bất biến

**Ưu tiên:** P1

**Phụ thuộc:** G0

**Commit A:** `fix: keep inventory receipt totals consistent`
**Commit B:** `fix: preserve service batch allocations`

Hạng mục này gồm hai lát cắt độc lập; mỗi lát cắt phải hoàn tất và commit trước khi chuyển tiếp.

### 11A. Receipt vật tư mới không cộng đôi

Test đỏ trong:

- `tests/test_inventory_batches.py`
- `tests/test_expense_inventory_sync.py`

Ca test:

- Tạo vật tư mới từ expense chỉ tăng tổng tồn đúng một lần.
- `InventoryItem.quantity` bằng tổng `InventoryBatch.quantity_available`.
- Retry expense sync không tạo batch/movement thứ hai.
- Expense void không tự đảo kho theo G0.

Triển khai trong `controllers/expense_controller.py`, `services/inventory_batch_service.py` và helper liên quan.

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_inventory_batches.py tests/test_expense_inventory_sync.py tests/test_expense_void_record.py -q
.\venv\Scripts\python.exe -m pytest -q
```

### 11B. Delta allocation, hoàn đúng lô và khóa sau checkout

Test đỏ trong:

- `tests/test_inventory_batch_allocations.py`
- `tests/test_order_submission.py`
- `tests/test_order_history.py`
- `tests/integration/test_inventory_concurrency_mysql.py`

Ca test:

- Tăng quantity cấp thêm theo FEFO.
- Giảm quantity hoàn đúng các batch allocation ban đầu.
- Về `0` vẫn giữ dòng lịch sử và allocations phù hợp.
- Không sửa/xóa dịch vụ của room đã checkout.
- Không để tổng tồn âm khi hai request đồng thời.
- Transaction lỗi không để movement và quantity lệch nhau.

Triển khai trong `services/inventory_service.py`, `services/inventory_batch_service.py`, order endpoints và model allocation nếu cần.

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_inventory_batch_allocations.py tests/test_order_submission.py tests/test_order_history.py -q
.\venv\Scripts\python.exe -m pytest -m mysql tests/integration/test_inventory_concurrency_mysql.py -q
.\venv\Scripts\python.exe -m pytest -q
```

Nếu UI order/warehouse đổi, kiểm tra `bb-browser` cho add/increase/decrease/remove, finalized lock, lỗi thiếu tồn và console.

## 16. Hạng mục 12 — Phân quyền dời lịch, mutation Timeline và state tổng hợp

**Ưu tiên:** P1

**Phụ thuộc:** Hạng mục 7, G0

**Commit A:** `fix: enforce reschedule capabilities`
**Commit B:** `fix: centralize booking state transitions`

### 12A. Dời lịch chỉ qua capability được phép

Test đỏ:

- Mở rộng `tests/test_booking_reschedule.py`
- Mở rộng `tests/test_booking_reschedule_ui.py`
- Mở rộng `tests/test_timeline_operations_ui.py`

Ca test:

- Staff bị từ chối ở API dời lịch kể cả gọi trực tiếp.
- Admin được phép dời booking chưa check-in.
- Booking đã check-in/checked-out/cancelled không dời bằng luồng này.
- Drag/drop Timeline không gọi mutation generic có thể đổi giá trị hóa đơn.
- UI ẩn/disable action theo capability nhưng server vẫn là nơi quyết định cuối.

Triển khai capability decorator/service trong controller và đổi Timeline sang endpoint chuyên biệt hoặc read-only đối với state cấm.

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_booking_reschedule.py tests/test_booking_reschedule_ui.py tests/test_timeline_operations_ui.py tests/test_staff_permissions.py -q
.\venv\Scripts\python.exe -m pytest -q
```

Kiểm tra `bb-browser` bằng cả tài khoản Staff và Admin; keyboard, feedback lỗi và console.

### 12B. Một state transition service

Test đỏ:

- `tests/test_booking_state_aggregation.py`
- mở rộng `tests/test_booking_cancellation.py`
- mở rộng `tests/test_checkin.py`
- mở rộng test checkout

Ca test:

- Booking `cancelled` chỉ khi mọi phòng cancelled.
- Booking `completed` khi mọi phòng kết thúc và ít nhất một phòng checked_out.
- Mixed booked/checked_in/checked_out/cancelled có kết quả xác định.
- Room status đồng bộ với BookingRoom active.
- Cancellation operation key dùng đúng namespace/entity, không va chạm ID booking và booking-room.
- Mọi transition bất hợp lệ bị chặn trước mutation.

Triển khai `services/booking_state_service.py` và chuyển check-in, checkout, cancel, reschedule sang service này.

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_booking_state_aggregation.py tests/test_booking_cancellation.py tests/test_checkin.py tests/test_checkout_state_guards.py -q
.\venv\Scripts\python.exe -m pytest -q
```

## 17. Hạng mục 13 — Reconciliation có dry-run và apply được bảo vệ

**Ưu tiên:** P1

**Phụ thuộc:** Hạng mục 7–12, G0, G2
**Commit:** `feat: add business data reconciliation command`

### Test đỏ

Tạo `tests/test_reconciliation_command.py`:

- Mặc định chỉ dry-run và không commit.
- Báo theo tenant: room constraint conflict, aggregate state lệch, payment thiếu operation, inventory total lệch batch, allocation thiếu, snapshot thiếu.
- Output không lộ dữ liệu tenant khác hoặc secret.
- `--apply` yêu cầu cờ xác nhận rõ, tenant đích và backup acknowledgement.
- Lỗi một rule rollback apply của tenant đó.
- Rule tài chính không tự đoán số tiền; đánh dấu cần xử lý thủ công khi không đủ bằng chứng.
- Chạy lại sau apply an toàn phải idempotent.

### Triển khai tối thiểu

Thêm:

- `commands/reconcile.py`
- các rule nhỏ trong `services/reconciliation/`
- đăng ký Flask CLI trong app factory
- tài liệu vận hành ngắn trong `docs/`

Không nhúng reconciliation vào Alembic migration hoặc startup app.

### GREEN

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_reconciliation_command.py -q
.\venv\Scripts\python.exe -m pytest -q
```

Chỉ chạy command trên fixture/test database ở chế độ dry-run. Không chạy `--apply` trên dữ liệu người dùng trong hạng mục này.

## 18. Hạng mục 14 — Accessibility nền tảng cho form/modal/action

**Ưu tiên:** P2

**Phụ thuộc:** Hạng mục 1, 5, 9–10
**Commit:** `fix: improve workflow accessibility`

Thiết kế theo `ui-ux-pro-max`: accessible name rõ nghĩa, focus nhìn thấy được, thứ tự Tab theo thị giác, lỗi gần trường và có vùng thông báo, nút loading giữ nhãn dễ hiểu, touch target tối thiểu phù hợp.

### Test đỏ

Tạo/mở rộng:

- `tests/test_accessibility_markup.py`
- `tests/test_workflow_modal_markup.py`
- `tests/test_ui_shell_markup.py`
- `tests/test_customer_render_security.py`

Ca test:

- Label login dùng `for` khớp `id`.
- Modal có `aria-labelledby`, close button có accessible name.
- Icon-only customer actions có `aria-label` chứa action và đối tượng.
- Error container có `role="alert"` hoặc `aria-live` phù hợp.
- Loading button có disabled/busy state, không chỉ đổi icon.
- Shared styles có `:focus-visible` rõ ràng và không xóa outline vô điều kiện.
- Modal đóng trả focus về trigger.

### Triển khai tối thiểu

Sửa:

- `templates/auth/login.html`
- `templates/rooms/_booking_modal.html`
- các partial checkout/group checkout liên quan
- `templates/customers/index.html`
- `static/js/customer.js`, `static/js/checkout.js`, modal helper dùng chung
- shared CSS hiện hữu

### GREEN và browser

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_accessibility_markup.py tests/test_workflow_modal_markup.py tests/test_ui_shell_markup.py tests/test_customer_render_security.py -q
.\venv\Scripts\python.exe -m pytest -q
```

Checklist `bb-browser` desktop:

1. Tab từ trigger vào modal theo thứ tự thị giác.
2. Focus được nhìn thấy ở mọi control.
3. Escape đóng modal đúng lúc và focus về trigger.
4. Close icon có tên trong accessibility tree.
5. Lỗi validation được announce và focus tới vùng cần sửa.
6. Double-submit bị chặn; nút loading có tên rõ.
7. Customer edit/delete dùng keyboard được.
8. Console không có lỗi.

Không tuyên bố UI đã kiểm tra nếu `bb-browser` không khả dụng; ghi rõ phần chưa kiểm chứng.

## 19. Hạng mục 15 — Loại N+1 và khóa query budget dashboard

**Ưu tiên:** P2

**Phụ thuộc:** Hạng mục 8
**Commit:** `perf: bound room dashboard queries`

### Test đỏ

Tạo `tests/test_room_dashboard_query_budget.py` dùng SQLAlchemy event counter:

- Với 4 phòng, endpoint dashboard/API phòng dùng tối đa 5 SQL statements.
- Với 40 phòng vẫn dùng tối đa cùng budget.
- Giá effective, active/upcoming booking và service count giữ nguyên payload.
- Query vẫn tenant-scoped.
- Không lazy-load thêm khi serialize response.

RED mong đợi: số query tăng theo số phòng vì lookup `PriceRule` và `count()` riêng từng phòng.

### Triển khai tối thiểu

Sửa:

- `services/pricing_service.py`: bulk load rules một lần và tính effective price trong memory theo room/type/date.
- `controllers/room_controller.py`: aggregate service count bằng một grouped query; eager-load quan hệ cần serialize.

Không cache xuyên tenant/request ở bước này.

### GREEN

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_room_dashboard_query_budget.py tests/test_pricing_tenant_scope.py tests/test_room_notices.py tests/test_room_map_card_markup.py -q
.\venv\Scripts\python.exe -m pytest -q
```

Với `bb-browser`: mở room map có dữ liệu đủ trạng thái; so payload/giá/count với trước thay đổi và kiểm tra console.

## 20. Hạng mục 16 — Nghiệm thu tích hợp và tài liệu vận hành

**Ưu tiên:** Bắt buộc

**Phụ thuộc:** Tất cả hạng mục được duyệt
**Commit:** `docs: add production remediation runbook`

### Kiểm tra tự động

```powershell
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\python.exe -m pytest -m mysql -q
.\venv\Scripts\python.exe -m flask --app app db heads
.\venv\Scripts\python.exe -m flask --app app db upgrade --sql
git diff --check
git status --short
```

### Kiểm tra migration

Trên database test riêng:

1. Upgrade từ database trống đến head.
2. Upgrade từ mỗi head cũ đến head.
3. Kiểm tra schema room/payment/operation bằng inspector.
4. Downgrade một revision mới rồi upgrade lại khi downgrade an toàn.
5. Chạy preflight trên fixture có conflict và xác nhận dừng an toàn.

### Kiểm tra browser end-to-end

Với `bb-browser` desktop:

1. Login và CSRF.
2. Customer payload XSS.
3. Booking + cọc + quote.
4. Check-in.
5. Gọi dịch vụ và thay quantity.
6. Checkout lẻ thành công, retry/double-click.
7. Checkout đoàn bị chặn và thành công.
8. Dời lịch bằng Admin, bị chặn bằng Staff.
9. Report tenant/void/occupancy.
10. Keyboard/focus/accessibility tree và console.

### Runbook

Tạo tài liệu tiếng Việt mô tả:

- Biến môi trường production bắt buộc.
- Quy trình backup → Alembic upgrade → smoke test → rollback.
- Cách chạy MySQL integration test.
- Cách chạy reconciliation dry-run và đọc kết quả.
- Không ghi secret/credential thật vào repository.

## 21. Điều kiện dừng và báo blocker

Dừng hạng mục hiện tại, không tự mở rộng phạm vi, khi:

- G0 chưa được duyệt nhưng test/implementation phụ thuộc trực tiếp vào quyết định nghiệp vụ.
- Không có MySQL test database cho hành vi chỉ MySQL mới chứng minh được.
- Migration preflight phát hiện dữ liệu conflict.
- Worktree có thay đổi người dùng chồng lên đúng file cần sửa và không thể tách an toàn.
- Cần thay đổi API contract ngoài spec hoặc hỗ trợ công nợ/chuyển phòng sau check-in.
- `bb-browser` không khả dụng cho thay đổi UI.

Báo blocker phải nêu: hạng mục, bằng chứng, phần đã kiểm tra, phần chưa thể kiểm tra và quyết định cần người dùng cung cấp. Không trình bày phần dở dang như đã hoàn tất.

## 22. Definition of Done toàn chương trình

- Payload Stored XSS không thực thi.
- Mutation form/API có CSRF và lỗi ổn định.
- Production thiếu cấu hình bắt buộc phải fail-closed; startup không seed/schema/debug.
- Alembic chỉ có một head.
- Model, Alembic và MySQL cùng enforce unique `(hotel_id, room_number)`.
- Test migration/MySQL bổ sung cho constraint, lock và transaction.
- Báo cáo không lẫn tenant và loại Expense void đúng chính sách.
- Payment truy vết được về operation/component; retry trả cùng result.
- Pricing, deposit, preview và checkout dùng một nguồn server.
- Checkout lẻ/đoàn đúng state, tiền, refund, idempotency và transaction.
- Tổng tồn bằng tổng lô; hoàn đúng allocation; dịch vụ finalized bất biến.
- Dời lịch đúng capability; state tổng hợp nhất quán.
- Reconciliation mặc định dry-run và không tự sửa tài chính.
- Accessibility markup và luồng keyboard/modal đạt checklist.
- Dashboard đáp ứng query budget cố định với 4 và 40 phòng.
- Mỗi hạng mục có bằng chứng RED/GREEN, full regression, kiểm tra browser khi cần và commit riêng.
