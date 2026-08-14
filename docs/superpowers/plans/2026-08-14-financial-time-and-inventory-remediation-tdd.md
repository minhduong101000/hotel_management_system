# Kế hoạch TDD: Hoàn tiền nhập trực tiếp, thời gian báo cáo và kiểm thử kho

**Ngày:** 14-08-2026

**Trạng thái:** Sẵn sàng triển khai (chính sách nghiệp vụ đã chốt cùng ngày — xem G0)

**Spec nguồn:** `docs/superpowers/specs/2026-08-14-financial-time-and-inventory-remediation-design.md`

**Phạm vi:** Gỡ auto-refund, form hoàn tiền nhập trực tiếp có lưới an toàn, bút toán đảo, hai góc nhìn billing/sổ quỹ, time service UTC/Bangkok, `Booking.completed_at`, FEFO clock inject.

## 1. Kết quả cần đạt

Mỗi hạng mục: test đỏ vì đúng nguyên nhân → triển khai tối thiểu → refactor giữ xanh → chạy regression hạng mục → một commit riêng tiếng Anh. UI thay đổi phải kiểm `bb-browser` trước khi coi là xong. Không đụng: công nợ, cổng thanh toán, ngưỡng hạn mức phê duyệt, sửa dữ liệu tài chính lịch sử.

## 2. Cổng

### G0 — Chính sách nghiệp vụ (ĐÃ CHỐT 14-08-2026, không chờ gì thêm)

1. Lễ tân ngang quyền Admin: nhập hoàn + bút toán đảo, tất cả vào audit.
2. Nhập % kèm cơ sở tính (phần chưa sử dụng / toàn bộ hóa đơn) hoặc số tiền trực tiếp.
3. Trần cứng server-side: `tiền hoàn ≤ Σ Payment.amount của booking` (tổng ròng đang giữ).
4. Sửa sai bằng bút toán đảo, không sửa/xóa dòng cũ.
5. Bill khách lọc cặp refund/đảo đã triệt tiêu; sổ nội bộ giữ đủ.
6. Checkout/hủy không bao giờ tự sinh refund; hủy mặc định hoàn 0.

### G1 — MySQL test

`TEST_MYSQL_DATABASE_URL` đã hoạt động (12 test mysql xanh 14-08). Test migration mới bắt buộc chạy cả marker `mysql`.

## 3. Bối cảnh code đã khảo sát (14-08)

| Thứ | Vị trí | Ghi chú cho người thực thi |
|---|---|---|
| Auto-refund cần gỡ | `services/group_checkout_service.py:122-131` | nhánh `elif balance < 0: payment_service.record_refund(...)` |
| API hủy nhận tham số hoàn | `controllers/timeline_controller.py:860-1142` (`cancel_booking`) | đọc `is_force_majeure` (dòng 867), `refund_percent` (872–874); tính hoàn 1002–1015; ghi refund 1058–1070 |
| Hạ tầng Payment | `models/payment.py` | đã có `hotel_id`, `business_operation_id`, `component_key`, unique `(hotel_id, business_operation_id, component_key)` |
| Ghi tiền | `services/payment_service.py` | `record_refund` ghi số âm; `_create_payment` validate operation cùng hotel |
| Idempotency | `BusinessOperation` + `business_operation_service.replay_operation` | pattern dùng sẵn trong `cancel_booking` và checkout |
| Audit | `audit_service.record_event(...)` | pattern trong `group_checkout_service.py:164-182` |
| Báo cáo | `controllers/report_controller.py:31-140` | `datetime.now()`, `Booking.updated_at` (dòng 83–87), `func.date(finalized_time)` (101–116) |
| Billing khách | `controllers/billing_controller.py:68+` (`get_billing_detail`), 284–285 tính tổng từ `booking.payments` | chỗ áp bộ lọc cặp triệt tiêu |
| Migration head | `a2b3c4d5e6f7` | migration mới nối tiếp head này |
| FEFO | `services/inventory_batch_service.py:132-148`, `services/inventory_service.py:50-109` | `batches_for_consumption(item, on_date, lock)` đã nhận `on_date`; `deduct_inventory`/`validate_inventory` chưa truyền xuống |

## 4. Hạng mục

### Hạng mục 1 — Gỡ auto-refund và tham số hoàn từ client

**Files:** `services/group_checkout_service.py`, `controllers/timeline_controller.py`, `tests/test_group_checkout.py`, `tests/test_booking_cancellation.py`, `static/js/timeline_manager.js` + template modal hủy (bỏ input % hoàn, cờ bất khả kháng).

**RED:**

1. `test_group_checkout_excess_deposit_returns_credit_without_refund` — checkout đoàn với cọc > hóa đơn: response `success=True`, `data.unrefunded_credit == <số dư>`, **không** tồn tại `Payment` `payment_type='refund'` của booking, trạng thái phòng vẫn chốt `checked_out`.
2. Sửa test hiện hữu `test_group_checkout_excess_deposit_creates_one_refund` (đang đòi hành vi cũ) thành kỳ vọng mới trên.
3. `test_cancel_booking_ignores_client_refund_parameters` — POST cancel với `refund_percent=100, is_force_majeure=True`: hủy thành công, `refund_amount == 0`, không có Payment refund, các field `cancellation_refund_percent == 0`; payload response không còn khóa `refund_percent`.

**GREEN:**

- `group_checkout_service.settle_group_checkout`: xóa nhánh `elif balance < 0`; thêm `"unrefunded_credit": format(_money(abs(min(balance, 0))), ".2f")` vào `result["data"]`; audit `after_data` thêm `unrefunded_credit`.
- `cancel_booking`: bỏ đọc `is_force_majeure`/`refund_percent_input`; đặt `refund_percent_effective = 0.0` cố định; bỏ khối `record_refund` (1058–1070); giữ nguyên bookkeeping phân bổ cọc (`room_deposit_original`, `room_deposit_amount = 0`, fee note) — tiền cọc giữ lại toàn bộ cho tới khi có người nhập hoàn qua hạng mục 2. Response thêm `data.unrefunded_credit = allocated_deposit`.
- UI: form hủy bỏ input %/cờ; hiển thị dòng "Không phát sinh hoàn tiền tự động — dùng nút Hoàn tiền nếu cần trả khách".

**Regression:** `pytest tests/test_group_checkout.py tests/test_booking_cancellation.py tests/test_booking_state_aggregation.py -q`

**Commit:** `feat: stop automatic refunds; cancellation no longer accepts client refund parameters`

### Hạng mục 2 — Migration + refund service (cơ sở tính, trần cứng, idempotency)

**Files:** migration mới (down_revision `a2b3c4d5e6f7`), `models/payment.py`, `services/refund_service.py` (mới), `tests/test_refund_service.py` (mới), `tests/integration/test_room_migration_mysql.py` (thêm head mới vào danh sách parametrize nếu file đang liệt kê revision).

**Migration:** thêm `payments.reverses_payment_id` `Integer` FK `payments.id`, nullable, `UniqueConstraint('reverses_payment_id', name='uq_payments_reverses_once')`. Không backfill.

**Interface `services/refund_service.py`:**

```python
class RefundError(ValueError): ...

ALLOWED_BASES = {"unused", "total"}

def refundable_cap(booking) -> Decimal:
    """Σ Payment.amount của booking (mọi dòng, kể cả refund/đảo) — tiền ròng đang giữ."""

def unused_value(booking_rooms, effective_at) -> Decimal:
    """Giá trị các đêm chưa ở từ effective_at đến check_out_expected,
    theo snapshot giá của từng BookingRoom (dùng breakdown snapshot nếu có,
    fallback price_snapshot × số đêm còn lại). Phòng cancelled/checked_out: 0."""

def quote_refund(*, booking, base, percent=None, amount=None, effective_at=None) -> dict:
    """Trả {'base_value', 'refund_amount', 'cap', 'already_refunded'} — dùng cho preview
    lẫn validate lúc tạo. Không mutation."""

def create_refund(*, booking, base, percent=None, amount=None, payment_method,
                  reason, effective_at=None, actor_user_id, client_key) -> Payment:
    """Idempotency: operation_key = f'refund:{booking.id}:{client_key}'.
    Validate: base hợp lệ; đúng một trong percent/amount; percent trong (0,100];
    reason.strip() khác rỗng; method thuộc ALLOWED_PAYMENT_METHODS;
    refund_amount > 0 và ≤ refundable_cap. Ghi Payment qua
    payment_service.record_refund(component_key='refund'), audit 'create_refund'
    (payload: base, percent, base_value, amount, actor)."""
```

**RED (mỗi test một hành vi):**

1. `test_refund_base_unused_math` — booking 5 đêm 400k đã thu 2.000k, effective sau 2 đêm: `unused_value == 1_200_000`; percent 50 → refund 600k.
2. `test_refund_base_total_math` — base total, percent 50 → 1.000k.
3. `test_refund_amount_direct_entry` — nhập `amount=350_000` không cần percent.
4. `test_refund_hard_cap_blocks_over_collected` — đã thu 500k, đã hoàn 300k → nhập 300k nữa bị `RefundError`; không Payment mới, không audit.
5. `test_refund_requires_reason_and_method` — thiếu một trong hai → lỗi, không mutation.
6. `test_refund_idempotent_retry_returns_same_payment` — cùng `client_key` gọi 2 lần → 1 Payment.
7. `test_refund_tenant_isolation` — booking hotel B với actor hotel A → lỗi, không mutation (dùng pattern `tenant_query`).
8. `test_refund_staff_and_admin_equal` — service không phân biệt role (đối chứng ở API hạng mục 4).

**Regression:** `pytest tests/test_refund_service.py -q` + `pytest -m mysql` (migration mới upgrade từ head cũ và từ DB trống).

**Commit:** `feat: refund service with base selection, hard cap and idempotency`

### Hạng mục 3 — Bút toán đảo và hai góc nhìn dữ liệu

**Files:** `services/refund_service.py`, `services/payment_service.py` (helper `effective_payments`), `controllers/billing_controller.py`, `controllers/cashier_controller.py` (đánh dấu cặp, không lọc), `tests/test_refund_reversal.py` (mới), `tests/test_billing_views.py` (mới hoặc gộp file billing test hiện có).

**Interface:**

```python
def reverse_refund(*, payment, reason, actor_user_id, client_key) -> Payment:
    """Chỉ nhận dòng payment_type='refund' chưa bị đảo (tra unique reverses_payment_id).
    Tạo Payment dương payment_type='refund_reversal', reverses_payment_id=payment.id,
    cùng booking/hotel; idempotency 'refund_reversal:{payment.id}:{client_key}';
    audit 'reverse_refund'."""

def effective_payments(booking) -> list[Payment]:
    """Các dòng còn hiệu lực cho bill khách: loại bỏ dòng refund đã bị đảo
    và mọi dòng refund_reversal."""
```

**RED:**

1. `test_reverse_refund_creates_linked_positive_line` — đảo đúng số tiền, đúng liên kết.
2. `test_reverse_refund_twice_rejected` — đảo lần 2 lỗi, không mutation (kể cả race: constraint DB chặn — thêm ca marker `mysql`).
3. `test_reverse_only_refund_lines` — đảo dòng `deposit` → lỗi.
4. `test_billing_detail_hides_cancelled_refund_pair` — chuỗi hoàn sai 350k → đảo → hoàn đúng 35k: `get_billing_detail` và trang in chỉ chứa dòng 35k; tổng ròng đúng.
5. `test_cashier_ledger_keeps_all_lines` — sổ quỹ trả đủ 3 dòng, cặp sai/đảo có nhãn (`is_reversed`/`reverses_payment_id` trong payload).
6. `test_report_cashflow_counts_pairs_both_ways` — `total_cash_in`/`total_cash_out` gồm cả hai chiều nên net khớp két.

**GREEN:** billing dùng `effective_payments`; các phép tổng ở `billing_controller.py:284-285` đổi sang danh sách hiệu lực; cashier thêm cờ hiển thị; `Payment.to_dict` thêm `reverses_payment_id`.

**Commit:** `feat: refund reversal with clean customer bill and full internal ledger`

### Hạng mục 4 — API + UI form hoàn tiền

**Files:** `controllers/booking_controller.py` (hoặc `controllers/refund_controller.py` mới đăng ký prefix tenant), `static/js/refund.js` (mới), template modal trong chi tiết booking/billing/checkout, `tests/test_refund_api.py`, `tests/test_refund_ui_markup.py`.

**API:**

| Method | Endpoint | Vai trò |
|---|---|---|
| POST | `/api/refunds/preview` | Trả `base_value / cap / already_refunded / refund_amount` từ `quote_refund` — nguồn của 3 con số ngữ cảnh |
| POST | `/api/refunds` | Tạo refund; body: `booking_id, base, percent hoặc amount, payment_method, reason, effective_at?, client_key` |
| POST | `/api/refunds/<payment_id>/reverse` | Bút toán đảo; body: `reason, client_key` |

Cả ba: `@login_required` (staff = admin, KHÔNG `admin_required`), tenant scope qua `tenant_query`, lỗi trả JSON (400/403/404/409), CSRF theo cơ chế hiện hành.

**RED:**

1. API preview trả đúng 3 con số; server tính lại lúc POST (gửi percent khác preview vẫn đúng công thức server).
2. POST vượt trần → 400 + `error_code='refund_exceeds_cap'`, không mutation — gọi thẳng API không qua UI.
3. Staff gọi được cả 3 endpoint (đối chứng chính sách); tenant khác → 404/403 nhất quán.
4. Markup: form có label liên kết, 3 con số ngữ cảnh render từ preview, khu lỗi `role="alert"`, nút xác nhận chứa số tiền quy đổi; bill in không có cặp triệt tiêu (DOM test).
5. Checkout lẻ/đoàn có `unrefunded_credit > 0` → response/DOM chứa lối tắt mở form hoàn.

**GREEN + bàn giao UI:** kiểm desktop `bb-browser`: nhập hoàn cơ sở A/B, nhập sai → đảo → nhập lại, in bill khách sạch, Escape/focus trả về trigger, console sạch, không tràn ngang.

**Commit:** `feat: refund entry UI with context guardrails and reversal flow`

### Hạng mục 5 — Time service, completed_at và báo cáo theo kỳ UTC

**Files:** `services/time_service.py` (mới), migration mới (`bookings.completed_at` + backfill), `services/booking_state_service.py`, `services/payment_service.py` (`_now` → `time_service.utc_now`), `services/reporting_service.py`, `controllers/report_controller.py`, `config.py` (`BUSINESS_TIMEZONE`), `tests/test_time_service.py`, `tests/test_report_period_utc.py`, cập nhật `tests/test_report_financial_isolation.py` nếu đụng fixture.

**Interface:**

```python
# services/time_service.py
BUSINESS_TIMEZONE = ZoneInfo(current_app.config.get("BUSINESS_TIMEZONE", "Asia/Bangkok"))
def utc_now() -> datetime            # aware UTC; điểm monkeypatch duy nhất của test
def business_now() -> datetime       # utc_now() đổi sang business tz
def business_today() -> date
def business_period_to_utc(start_date, end_date) -> tuple[datetime, datetime]  # [start_utc, end_utc)
def to_business_date(utc_dt) -> date # cho gom nhóm chart
```

Cột legacy naive: lưu `utc_now().replace(tzinfo=None)`; helper đọc gắn UTC.

**RED:**

1. `test_period_today_at_0030_bangkok_includes_late_utc_yesterday` — monkeypatch `utc_now` về `2026-08-13T17:30Z` (= 00:30 Bangkok 14-08): Payment/BookingRoom chốt lúc `17:05Z` được đếm vào "hôm nay".
2. `test_period_today_at_2330_bangkok_excludes_next_day` — biên trên.
3. `test_completed_at_set_once_by_state_service` — booking chuyển `completed` → set; sửa note ngày khác không đổi; report đếm theo `completed_at`, không theo `updated_at`.
4. `test_chart_groups_by_bangkok_date` — hai mốc UTC cùng ngày Bangkok nhưng khác ngày UTC nằm cùng cột chart (gom bằng `to_business_date` trong Python, bỏ `func.date`).
5. Migration test (marker `mysql`): backfill `completed_at = MAX(check_out_actual)`; booking completed thiếu mốc giữ `NULL` và không xuất hiện trong kỳ nào.

**GREEN:** `resolve_report_period` nhận ngày Bangkok rồi trả cặp UTC; `completed_bookings` lọc `completed_at`; `daily_revenue` bỏ `func.date`, trả mốc thô rồi gom bằng Python; write path tài chính thay `datetime.now()` bằng `time_service.utc_now()` (chỉ trong các file thuộc phạm vi spec — không sweep toàn repo đợt này).

**Commit:** tách 2 — `feat: central time service and completed_at migration` rồi `fix: revenue report uses business-timezone periods and completed_at`

### Hạng mục 6 — FEFO clock inject + regression kho

**Files:** `services/inventory_service.py`, `services/inventory_batch_service.py`, `tests/test_inventory_batch_allocations.py`, `tests/test_inventory_batches.py`.

**GREEN thiết kế:** `validate_inventory(..., as_of_date=None)` và `deduct_inventory(..., as_of_date=None)` truyền xuống `available_quantity`/`batches_for_consumption`; mặc định `time_service.business_today()`.

**RED:**

1. Viết lại 2 test FEFO 14-08 (đang dùng ngày tương đối) sang ngày cố định: `as_of_date=date(2026, 7, 1)`, lô hết hạn 01-08 và 01-09 → khẳng định `[(early, 2), (later, 1)]` chạy đúng ở mọi ngày thực.
2. `test_expired_batch_never_consumed_or_allocated` — as_of sau hạn lô 1: chỉ lô 2 được dùng; không movement/allocation nào trỏ lô 1.
3. `test_no_expiry_batch_consumed_last`.
4. `test_insufficient_stock_writes_no_partial_movement` — thiếu tồn: `InsufficientInventoryError`, đếm movement/allocation trước sau bằng nhau (hiện `deduct_inventory` mutate dần rồi mới raise — GREEN phải validate đủ trước khi ghi hoặc để transaction rollback trọn; chọn validate-trước, ghi rõ trong code).
5. Giữ nguyên các test hoàn kho theo allocation hiện có.

**Commit:** `feat: injectable business date for inventory FEFO with expiry regressions`

### Hạng mục 7 — Regression toàn phần và cập nhật tài liệu

1. `pytest -m "not mysql" -q` và `pytest -m mysql -q` — toàn bộ xanh (369 + 12 + test mới).
2. Migration kiểm từ DB trống và DB có dữ liệu mẫu (compose): `flask db upgrade` sạch cả hai.
3. Đi tay các mục smoke liên quan trên compose: checkout đoàn dư cọc, hủy, hoàn, in bill.
4. Cập nhật `docs/business-operations-guide.md` (mục 5: dòng P0 hoàn tiền → đã xử lý; mục 3.3 mô tả luồng hoàn mới) và chỉ mục specs.
5. Commit `docs: refresh business guide after refund/time/inventory remediation` + push `dev`.

## 5. Rủi ro đã lường

- **`unused_value` với thuê giờ:** breakdown snapshot chủ yếu phục vụ thuê ngày; với `rental_type='hourly'` lấy phần chưa dùng = 0 (đã ở là tính trọn block) — ghi thành quy tắc trong docstring + một test riêng.
- **`func.now()` default của model:** `Payment.created_at` default DB; hạng mục 5 truyền `created_at=utc_now()` tường minh từ service nên default chỉ còn là fallback — không đổi schema đợt này.
- **Đổi kỳ vọng test cũ:** chỉ 1 test bị thay chủ đích (`excess_deposit_creates_one_refund`); mọi thay đổi kỳ vọng khác phải dừng lại và đối chiếu spec trước khi sửa.
