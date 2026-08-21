# Đường đi của tiền cọc — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ghi đúng phương thức khách trả tiền cọc, và buộc lễ tân khai rõ mục đích khi giảm cọc để tiền không rời két mà sổ ghi là "đính chính".

**Architecture:** Một helper chuẩn hoá phương thức trong `payment_service` được ba nơi ghi cọc dùng chung; ba modal thêm nhóm nút chọn dùng lại lớp CSS `pos-method-btn` sẵn có của màn thanh toán. Việc giảm cọc thêm một trường `deposit_change_type` bắt buộc, chặn ở **cả hai tầng** — giao diện khoá nút Lưu, máy chủ trả 400 nếu bị gọi thẳng.

**Tech Stack:** Flask, SQLAlchemy, pytest (marker `mysql`/`browser`), JS thuần (không framework, không bundler), Bootstrap 5.

**Spec:** `docs/superpowers/specs/2026-08-21-deposit-money-trail-design.md`

## Global Constraints

- Ba giá trị phương thức hợp lệ, **đúng như màn thanh toán đang dùng**: `cash`, `banking`, `credit_card`. Nhãn: "Tiền mặt", "Chuyển khoản", "Thẻ". Mặc định `cash`.
- **Không thêm `qr_code`** (quyết định có chủ đích trong spec mục 2.1).
- Giá trị lạ → **quy về `cash`, không ném lỗi** (nhãn kế toán, không phải điều kiện an toàn).
- `deposit_change_type` nhận đúng hai giá trị: `correction` | `returned_to_guest`.
- Khi máy chủ từ chối, **không được đổi bất kỳ dữ liệu nào** trước lúc trả lỗi.
- **Không sửa hồi tố** 49 khoản cọc cũ. **Không cần migration** (`payments.payment_method` là `String(50)`).
- Không dùng `datetime.now()` — có lưới chặn `tests/test_no_ambient_now.py`. Dùng `time_service`.
- Test chạy bằng `venv/bin/python -m pytest` (KHÔNG dùng `python` hệ thống).
- Commit tiếng Anh, dòng cuối: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

## File Structure

**Sửa**

| File | Trách nhiệm trong đợt này |
| --- | --- |
| `services/payment_service.py` | Thêm `DEPOSIT_PAYMENT_METHODS` + `normalize_payment_method` |
| `controllers/timeline_controller.py` | Nhận `deposit_payment_method` ở tạo booking và nộp thêm cọc; cổng `deposit_change_type` khi giảm cọc |
| `controllers/booking_controller.py` | Nhận `deposit_payment_method` ở đặt đoàn |
| `templates/rooms/_booking_modal.html` | Nhóm nút chọn phương thức + input ẩn `bk-deposit-method` |
| `templates/rooms/_group_booking_modal.html` | Nhóm nút chọn + input ẩn `group-deposit-method` |
| `templates/rooms/timeline.html` | Nhóm nút chọn + `edit-deposit-method`; hai lựa chọn mục đích; id cho nút Lưu |
| `static/js/main.js` | `setDepositPaymentMethod(method, button, inputId)` |
| `static/js/timeline_manager.js` | Gửi 2 trường mới; logic bật/tắt nút Lưu theo mục đích |
| `static/js/room.js` | Gửi `deposit_payment_method` (bản `submitFullBooking` **thứ hai**) |
| `static/js/group_booking.js` | Gửi `deposit_payment_method` |
| `tests/test_accessibility_markup.py` | Thêm 2 id radio vào danh sách cứng |
| `tests/test_deposit_adjustment.py` | Test cổng `deposit_change_type` |

**Tạo**

| File | Trách nhiệm |
| --- | --- |
| `tests/test_deposit_payment_method.py` | Khoá việc ghi đúng phương thức ở cả ba luồng |

**Bẫy đã biết — đọc trước khi làm:**

1. **Có HAI hàm `submitFullBooking`** — `static/js/timeline_manager.js` (trang Timeline) và `static/js/room.js` (trang Sơ đồ phòng). Sửa một cái thì luồng kia vẫn ghi tiền mặt.
2. `tests/test_accessibility_markup.py` dùng **danh sách id cứng**, không quét tự động. Thêm control mới mà quên khai báo thì markup đúng nhưng test không canh được.
3. `saveBookingChangesFromDetail` (modal chi tiết booking) cũng gửi `deposit`, đọc từ `<input type="hidden" id="bd-deposit">` được nạp lại đúng giá trị cũ — nên nó **không bao giờ** kích hoạt nhánh giảm cọc. Không cần đụng tới.

---

## Task 1: Helper chuẩn hoá phương thức thanh toán

**Files:**
- Modify: `services/payment_service.py`
- Test: `tests/test_deposit_payment_method.py` (tạo mới)

**Interfaces:**
- Produces: `payment_service.DEPOSIT_PAYMENT_METHODS` (tuple), `payment_service.normalize_payment_method(value, *, default="cash") -> str`

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/test_deposit_payment_method.py`:

```python
"""Tiền cọc phải ghi đúng phương thức khách trả (spec 21-08-2026).

Trước đợt này cả ba nơi ghi cọc đều cứng hoá 'cash': dữ liệu sản phẩm cho thấy
49/49 khoản cọc mang nhãn tiền mặt, kể cả khoản khách chuyển khoản — cuối ca
đếm két sẽ thiếu đúng những khoản đó.
"""

from extensions import db
from models import Payment
from services import payment_service


def test_normalize_accepts_the_three_supported_methods():
    for method in ("cash", "banking", "credit_card"):
        assert payment_service.normalize_payment_method(method) == method


def test_normalize_is_forgiving_about_case_and_spacing():
    assert payment_service.normalize_payment_method("  Banking ") == "banking"
    assert payment_service.normalize_payment_method("CREDIT_CARD") == "credit_card"


def test_normalize_falls_back_to_cash_instead_of_raising():
    """Đây là nhãn kế toán, không phải điều kiện an toàn: một lỗi gõ không được
    làm hỏng thao tác của lễ tân."""
    for value in ("bitcoin", "", None, 123):
        assert payment_service.normalize_payment_method(value) == "cash"
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_deposit_payment_method.py -v`
Expected: FAIL — `AttributeError: module 'services.payment_service' has no attribute 'normalize_payment_method'`

- [ ] **Step 3: Thêm helper vào `services/payment_service.py`**

Đặt ngay sau `_to_decimal_amount` (khoảng dòng 18), trước `_now`:

```python
DEPOSIT_PAYMENT_METHODS = ("cash", "banking", "credit_card")


def normalize_payment_method(value, *, default: str = "cash") -> str:
    """Chuẩn hoá phương thức thanh toán do client gửi lên.

    Giá trị lạ bị quy về mặc định thay vì ném lỗi: đây là nhãn kế toán, không
    phải điều kiện an toàn — chặn cứng sẽ làm hỏng thao tác của lễ tân vì một
    lỗi gõ, trong khi hậu quả tệ nhất của việc quy về mặc định chỉ là một nhãn
    cần sửa sau.
    """
    candidate = str(value or "").strip().lower()
    return candidate if candidate in DEPOSIT_PAYMENT_METHODS else default
```

- [ ] **Step 4: Chạy test để xác nhận xanh**

Run: `venv/bin/python -m pytest tests/test_deposit_payment_method.py -v`
Expected: PASS (3 test)

- [ ] **Step 5: Commit**

```bash
git add services/payment_service.py tests/test_deposit_payment_method.py
git commit -m "feat: add payment method normalizer for deposits

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 2: Ba nơi ghi cọc nhận phương thức từ payload

**Files:**
- Modify: `controllers/timeline_controller.py` (đọc payload ~dòng 517; ghi cọc ~dòng 588; nộp thêm cọc ~dòng 1267)
- Modify: `controllers/booking_controller.py` (đọc payload ~dòng 825; ghi cọc ~dòng 897)
- Test: `tests/test_deposit_payment_method.py`

**Interfaces:**
- Consumes: `payment_service.normalize_payment_method` (Task 1)
- Produces: ba endpoint nhận thêm trường payload `deposit_payment_method` (tuỳ chọn, mặc định `cash`)

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_deposit_payment_method.py`:

```python
def test_new_booking_records_the_selected_deposit_method(client, seed_hotels, login_as):
    hotel, _, admin, _, br, _ = seed_hotels
    room_number = br.room.room_number
    br.status = "cancelled"          # giải phóng phòng seed để tạo booking mới
    db.session.commit()
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/create",
        json={
            "room_number": room_number,
            "status": "booked",
            "rental_type": "daily",
            "customer_name": "Khach Chuyen Khoan",
            "customer_phone": "0900777001",
            "check_in": "2026-10-01T14:00",
            "check_out": "2026-10-02T12:00",
            # Cọc phải đúng 50% hoặc 100% tiền phòng dự kiến, nếu không request
            # bị chặn TRƯỚC khi tới bước ghi sổ. Phòng seed 500.000/đêm x 1 đêm.
            "deposit": 500000,
            "deposit_payment_method": "banking",
            "source": "walk_in",
        },
    )

    assert response.get_json()["success"] is True, response.get_json()
    deposit = Payment.query.filter_by(payment_type="deposit").one()
    assert deposit.payment_method == "banking"


def test_group_booking_records_the_selected_deposit_method(client, seed_hotels, login_as):
    hotel, _, admin, _, br, _ = seed_hotels
    room_id = br.room_id
    br.status = "cancelled"
    db.session.commit()
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/bookings/api/bookings/group_create",
        json={
            "customer": {"phone": "0900777002", "name": "Doan Chuyen Khoan"},
            "room_ids": [room_id],
            "check_in": "2026-10-05",
            "check_out": "2026-10-06",
            "deposit": 500000,
            "deposit_payment_method": "credit_card",
        },
    )

    assert response.get_json()["success"] is True, response.get_json()
    deposit = Payment.query.filter_by(payment_type="deposit").one()
    assert deposit.payment_method == "credit_card"


def test_topping_up_a_deposit_records_the_selected_method(client, seed_hotels, login_as):
    hotel, _, admin, _, br, _ = seed_hotels
    br.room_deposit_amount = 0
    db.session.commit()
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json={
            "booking_id": br.booking_id,
            "booking_room_id": br.id,
            "room_id": br.room_id,
            "status": br.status,
            "check_in": "2026-10-01T14:00",
            "check_out": "2026-10-02T12:00",
            "deposit": 200000,
            "deposit_payment_method": "banking",
        },
    )

    assert response.get_json()["success"] is True, response.get_json()
    deposit = Payment.query.filter_by(payment_type="deposit").one()
    assert deposit.payment_method == "banking"


def test_deposit_defaults_to_cash_when_the_client_sends_nothing(client, seed_hotels, login_as):
    """Client cũ chưa biết trường mới vẫn phải chạy đúng như trước."""
    hotel, _, admin, _, br, _ = seed_hotels
    br.room_deposit_amount = 0
    db.session.commit()
    login_as(client, admin)

    client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json={
            "booking_id": br.booking_id,
            "booking_room_id": br.id,
            "room_id": br.room_id,
            "status": br.status,
            "check_in": "2026-10-01T14:00",
            "check_out": "2026-10-02T12:00",
            "deposit": 150000,
        },
    )

    assert Payment.query.filter_by(payment_type="deposit").one().payment_method == "cash"
```

> **Nếu request bị chặn vì tỉ lệ cọc:** hai luồng tạo booking bắt cọc đúng 50%
> hoặc 100% tiền phòng dự kiến, **trước** khi tới bước ghi sổ. Con số 500.000
> ở trên suy ra từ phòng seed (`price_per_night=500000`, một đêm). Nếu máy chủ
> trả về lỗi tỉ lệ, đọc số tiền dự kiến trong `msg` rồi chỉnh lại con số
> `deposit` cho khớp — **đừng** nới lỏng assert về `payment_method`, vì đó mới
> là thứ test này canh.

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_deposit_payment_method.py -v`
Expected: FAIL — ba test đầu báo `assert 'cash' == 'banking'` (hoặc `'credit_card'`). Đây chính là lỗi cần vá.

- [ ] **Step 3: Sửa luồng tạo booking trong `controllers/timeline_controller.py`**

Ngay dưới dòng đọc tiền cọc (khoảng dòng 517):

```python
        deposit_amount = float(data.get('deposit') or 0)
        deposit_method = payment_service.normalize_payment_method(
            data.get('deposit_payment_method')
        )
```

Rồi ở lời gọi `record_deposit` (khoảng dòng 588), thay `payment_method='cash'`:

```python
                payment_method=deposit_method,
```

- [ ] **Step 4: Sửa luồng nộp thêm cọc trong cùng file**

Trong `update_booking`, nhánh `if room_deposit > old_deposit:` (khoảng dòng 1267):

```python
                payment_method=payment_service.normalize_payment_method(
                    data.get('deposit_payment_method')
                ),
```

- [ ] **Step 5: Sửa luồng đặt đoàn trong `controllers/booking_controller.py`**

Ngay dưới dòng đọc tổng cọc (khoảng dòng 825):

```python
        total_deposit = float(data.get('deposit', 0))
        deposit_method = payment_service.normalize_payment_method(
            data.get('deposit_payment_method')
        )
```

Rồi ở lời gọi `record_deposit` (khoảng dòng 897), thay `payment_method='cash'`:

```python
                payment_method=deposit_method,
```

- [ ] **Step 6: Chạy test để xác nhận xanh**

Run: `venv/bin/python -m pytest tests/test_deposit_payment_method.py -v && venv/bin/python -m pytest -m "not mysql" -q`
Expected: PASS toàn bộ

- [ ] **Step 7: Commit**

```bash
git add controllers/timeline_controller.py controllers/booking_controller.py tests/test_deposit_payment_method.py
git commit -m "fix: record the real payment method for deposits instead of hardcoding cash

All three deposit paths (single booking, group booking, top-up) labelled every
deposit as cash, so a bank transfer left the cash drawer short at end of shift.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 3: Nút chọn phương thức trong ba modal

**Files:**
- Modify: `static/js/main.js`
- Modify: `templates/rooms/_booking_modal.html`, `templates/rooms/_group_booking_modal.html`, `templates/rooms/timeline.html`
- Modify: `static/js/timeline_manager.js`, `static/js/room.js`, `static/js/group_booking.js`
- Test: `tests/test_deposit_payment_method.py`

**Interfaces:**
- Consumes: endpoint nhận `deposit_payment_method` (Task 2)
- Produces: hàm toàn cục `setDepositPaymentMethod(method, button, inputId)`; ba input ẩn `bk-deposit-method`, `group-deposit-method`, `edit-deposit-method`

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_deposit_payment_method.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_all_three_deposit_modals_offer_the_payment_method_choice():
    cases = (
        ("templates/rooms/_booking_modal.html", "bk-deposit-method"),
        ("templates/rooms/_group_booking_modal.html", "group-deposit-method"),
        ("templates/rooms/timeline.html", "edit-deposit-method"),
    )
    for rel, input_id in cases:
        source = _source(rel)
        assert f'id="{input_id}"' in source, f"{rel} thiếu input ẩn {input_id}"
        for method in ("cash", "banking", "credit_card"):
            assert f'data-method="{method}"' in source, f"{rel} thiếu nút {method}"
        assert "setDepositPaymentMethod" in source, f"{rel} chưa nối hàm chọn"


def test_shared_deposit_method_helper_lives_in_main_js():
    assert "function setDepositPaymentMethod(" in _source("static/js/main.js")


def test_every_booking_path_sends_the_deposit_method():
    """Có HAI hàm submitFullBooking — Timeline và Sơ đồ phòng. Sửa sót một cái
    thì luồng kia vẫn âm thầm ghi tiền mặt."""
    for rel in (
        "static/js/timeline_manager.js",
        "static/js/room.js",
        "static/js/group_booking.js",
    ):
        assert "deposit_payment_method" in _source(rel), f"{rel} chưa gửi phương thức"
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_deposit_payment_method.py -k modal -v`
Expected: FAIL — chưa template nào có input ẩn.

- [ ] **Step 3: Thêm hàm dùng chung vào `static/js/main.js`**

Đặt ngay sau `escapeHtml`:

```javascript
/**
 * Chọn phương thức nhận cọc trong các modal đặt phòng.
 * Giá trị lưu vào input ẩn để payload đọc được; nút được tô đậm để lễ tân thấy
 * mình đang chọn gì.
 */
function setDepositPaymentMethod(method, button, inputId) {
    const input = document.getElementById(inputId);
    if (input) input.value = method;
    const group = button?.closest('[role="group"]');
    if (group) {
        group.querySelectorAll('.pos-method-btn').forEach(b => {
            b.classList.toggle('active', b === button);
        });
    }
}
```

> Ghi chú: `static/js/checkout.js` có `setCheckoutPaymentMethod` gần giống. Gộp hai hàm nằm **ngoài phạm vi** đợt này để không đụng vào luồng thanh toán vừa ổn định — ghi nhận là nợ nhỏ.

- [ ] **Step 4: Thêm nhóm nút vào `templates/rooms/_booking_modal.html`**

Ngay sau khối `<div id="quick-deposit-buttons" ...>...</div>` (kết thúc khoảng dòng 89):

```html
                                    <div class="d-flex gap-2 mt-2" role="group" aria-label="Phương thức nhận cọc">
                                        <button type="button" class="pos-method-btn active" data-method="cash" onclick="setDepositPaymentMethod('cash', this, 'bk-deposit-method')">Tiền mặt</button>
                                        <button type="button" class="pos-method-btn" data-method="banking" onclick="setDepositPaymentMethod('banking', this, 'bk-deposit-method')">Chuyển khoản</button>
                                        <button type="button" class="pos-method-btn" data-method="credit_card" onclick="setDepositPaymentMethod('credit_card', this, 'bk-deposit-method')">Thẻ</button>
                                    </div>
                                    <input type="hidden" id="bk-deposit-method" value="cash">
```

- [ ] **Step 5: Thêm nhóm nút vào `templates/rooms/_group_booking_modal.html`**

Ngay sau `<small ... id="group-deposit-hint"></small>` (khoảng dòng 83):

```html
                            <div class="d-flex gap-2 mt-2" role="group" aria-label="Phương thức nhận cọc đoàn">
                                <button type="button" class="pos-method-btn active" data-method="cash" onclick="setDepositPaymentMethod('cash', this, 'group-deposit-method')">Tiền mặt</button>
                                <button type="button" class="pos-method-btn" data-method="banking" onclick="setDepositPaymentMethod('banking', this, 'group-deposit-method')">Chuyển khoản</button>
                                <button type="button" class="pos-method-btn" data-method="credit_card" onclick="setDepositPaymentMethod('credit_card', this, 'group-deposit-method')">Thẻ</button>
                            </div>
                            <input type="hidden" id="group-deposit-method" value="cash">
```

- [ ] **Step 6: Thêm nhóm nút vào `templates/rooms/timeline.html`**

Trong `editBookingModal`, ngay sau `<small class="text-muted d-block mt-1">Khoản cọc được trừ trực tiếp khi thanh toán.</small>` (khoảng dòng 146), **trước** khối `deposit-adjust-block`:

```html
                        <div class="d-flex gap-2 mt-2" role="group" aria-label="Phương thức nhận thêm cọc">
                            <button type="button" class="pos-method-btn active" data-method="cash" onclick="setDepositPaymentMethod('cash', this, 'edit-deposit-method')">Tiền mặt</button>
                            <button type="button" class="pos-method-btn" data-method="banking" onclick="setDepositPaymentMethod('banking', this, 'edit-deposit-method')">Chuyển khoản</button>
                            <button type="button" class="pos-method-btn" data-method="credit_card" onclick="setDepositPaymentMethod('credit_card', this, 'edit-deposit-method')">Thẻ</button>
                        </div>
                        <input type="hidden" id="edit-deposit-method" value="cash">
```

- [ ] **Step 7: Gửi trường mới trong ba payload JS**

`static/js/timeline_manager.js`, trong `submitFullBooking`, thêm vào object `data` (cạnh dòng `deposit:`):

```javascript
        deposit_payment_method: document.getElementById('bk-deposit-method')?.value || 'cash',
```

`static/js/timeline_manager.js`, trong `saveBookingChanges`, thêm vào object `data` (cạnh dòng `deposit:`):

```javascript
            deposit_payment_method: document.getElementById('edit-deposit-method')?.value || 'cash',
```

`static/js/room.js`, trong `submitFullBooking` (bản của trang Sơ đồ phòng), thêm vào payload cạnh trường `deposit`:

```javascript
        deposit_payment_method: document.getElementById('bk-deposit-method')?.value || 'cash',
```

`static/js/group_booking.js`, trong `submitGroupBooking`, thêm vào payload cạnh trường `deposit`:

```javascript
        deposit_payment_method: document.getElementById('group-deposit-method')?.value || 'cash',
```

- [ ] **Step 8: Kiểm cú pháp JS và chạy test**

Run:
```bash
node --check static/js/main.js && node --check static/js/timeline_manager.js && \
node --check static/js/room.js && node --check static/js/group_booking.js && \
venv/bin/python -m pytest tests/test_deposit_payment_method.py tests/test_accessibility_markup.py tests/test_workflow_modal_markup.py -q
```
Expected: JS OK, test PASS

- [ ] **Step 9: Commit**

```bash
git add static/js/ templates/rooms/ tests/test_deposit_payment_method.py
git commit -m "feat: let reception pick how a deposit was paid

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 4: Cổng khai mục đích khi giảm cọc (máy chủ)

**Files:**
- Modify: `controllers/timeline_controller.py` (nhánh `elif room_deposit < old_deposit:`, khoảng dòng 1276-1300)
- Test: `tests/test_deposit_adjustment.py`

**Interfaces:**
- Produces: `/api/bookings/update` nhận thêm `deposit_change_type` (`correction` | `returned_to_guest`), bắt buộc khi giảm cọc; mã lỗi `deposit_change_type_required` và `use_refund_flow`

- [ ] **Step 1a: Cập nhật ba test giảm cọc đã có**

> **Việc này bắt buộc.** `tests/test_deposit_adjustment.py` đã có ba test giảm
> cọc **không** gửi `deposit_change_type`. Cổng mới sẽ chặn chúng, nên chúng
> phải được cập nhật cùng lúc — đây là thay đổi hợp đồng có chủ đích, không
> phải test hỏng.

Mở rộng helper `_update_payload` sẵn có (**không** viết helper thứ hai):

```python
def _update_payload(br, deposit, reason=None, change_type=None):
    payload = {
        "booking_id": br.booking_id,
        "booking_room_id": br.id,
        "room_id": br.room_id,
        "status": br.status,
        "check_in": "2026-08-19T14:00",
        "check_out": "2026-08-20T12:00",
        "deposit": deposit,
    }
    if reason is not None:
        payload["deposit_reason"] = reason
    if change_type is not None:
        payload["deposit_change_type"] = change_type
    return payload
```

Rồi thêm `change_type="correction"` vào đúng ba lời gọi sau, giữ nguyên phần
assert của chúng:

| Test | Lời gọi cũ | Lời gọi mới |
| --- | --- | --- |
| `test_lowering_a_deposit_without_a_reason_is_rejected` | `_update_payload(br, 500000)` | `_update_payload(br, 500000, change_type="correction")` |
| `test_lowering_a_deposit_with_a_reason_leaves_a_trace` | `_update_payload(br, 500000, reason="gõ nhầm số 0")` | `_update_payload(br, 500000, reason="gõ nhầm số 0", change_type="correction")` |
| `test_lowering_a_deposit_to_zero_still_keeps_the_original_mark` | `_update_payload(br, 0, reason="Gõ nhầm số 0 khi nhận cọc")` | `_update_payload(br, 0, reason="Gõ nhầm số 0 khi nhận cọc", change_type="correction")` |

Test đầu vẫn phải trả `deposit_reason_required` — nó chứng minh cổng mục đích
chạy **trước** nhưng không nuốt mất việc kiểm tra lý do.

`test_raising_a_deposit_needs_no_reason` giữ nguyên: tăng cọc không đi qua cổng.

- [ ] **Step 1b: Viết test mới cho cổng mục đích**

Thêm vào cuối `tests/test_deposit_adjustment.py`:

```python
def test_lowering_a_deposit_without_stating_the_intent_is_rejected(
    client, seed_hotels, login_as
):
    """Có lý do bằng chữ vẫn chưa đủ: phải nói rõ tiền có rời két hay không."""
    hotel, _, admin, _, br, _ = seed_hotels
    br.room_deposit_amount = 5000000
    br.room_deposit_original = 5000000
    db.session.commit()
    login_as(client, admin)
    payments_before = Payment.query.count()

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json=_update_payload(br, 500000, reason="gõ nhầm số 0"),
    )

    body = response.get_json()
    assert body["success"] is False
    assert body["error_code"] == "deposit_change_type_required"
    db.session.refresh(br)
    assert float(br.room_deposit_amount) == 5000000.0     # không đổi gì
    assert Payment.query.count() == payments_before


def test_money_returned_to_the_guest_is_pushed_to_the_refund_flow(
    client, seed_hotels, login_as
):
    """Điều chỉnh cọc không có trần cứng và không hiện trên hóa đơn khách, nên
    nó không được dùng làm đường cho tiền rời két."""
    hotel, _, admin, _, br, _ = seed_hotels
    br.room_deposit_amount = 5000000
    br.room_deposit_original = 5000000
    db.session.commit()
    login_as(client, admin)
    payments_before = Payment.query.count()

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json=_update_payload(
            br, 0, reason="khách hủy, đã đưa lại tiền", change_type="returned_to_guest"
        ),
    )

    body = response.get_json()
    assert body["success"] is False
    assert body["error_code"] == "use_refund_flow"
    assert "Hoàn tiền" in body["msg"]
    db.session.refresh(br)
    assert float(br.room_deposit_amount) == 5000000.0
    assert Payment.query.count() == payments_before


def test_an_unknown_change_type_is_rejected_like_a_missing_one(
    client, seed_hotels, login_as
):
    hotel, _, admin, _, br, _ = seed_hotels
    br.room_deposit_amount = 5000000
    br.room_deposit_original = 5000000
    db.session.commit()
    login_as(client, admin)

    response = client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json=_update_payload(
            br, 500000, reason="gõ nhầm", change_type="something_else"
        ),
    )

    assert response.get_json()["error_code"] == "deposit_change_type_required"


def test_the_audit_trail_keeps_the_stated_intent(client, seed_hotels, login_as):
    """Đối soát về sau phải đọc được mục đích, không chỉ câu chữ tự do."""
    from models.audit_event import AuditEvent

    hotel, _, admin, _, br, _ = seed_hotels
    br.room_deposit_amount = 5000000
    br.room_deposit_original = 5000000
    db.session.commit()
    login_as(client, admin)

    client.post(
        f"/{hotel.slug}/timeline/api/bookings/update",
        json=_update_payload(
            br, 500000, reason="gõ nhầm số 0", change_type="correction"
        ),
    )

    event = AuditEvent.query.filter_by(action="deposit_adjustment").one()
    assert event.after_data["change_type"] == "correction"
    assert event.after_data["reason"] == "gõ nhầm số 0"
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_deposit_adjustment.py -v`
Expected: FAIL ở bốn test mới — hiện việc giảm cọc chỉ cần lý do, nên
`..._without_stating_the_intent...` và `..._returned_to_guest...` trả
`success: True` thay vì bị chặn, `..._unknown_change_type...` cũng cho qua, và
`..._audit_trail_keeps_the_stated_intent` báo `KeyError: 'change_type'`.
Ba test đã sửa ở Step 1a phải **xanh ngay** (trường thừa bị bỏ qua) — nếu chúng
đỏ thì payload đã sai, sửa trước khi đi tiếp.

- [ ] **Step 3: Thêm cổng vào `controllers/timeline_controller.py`**

Trong nhánh `elif room_deposit < old_deposit:`, chèn **trước** phần kiểm tra lý do hiện có:

```python
            elif room_deposit < old_deposit:
                # Giảm cọc nghĩa là tiền CÓ THỂ đã rời két. Bắt khai rõ mục đích:
                # đính chính số ghi sai thì ghi bút toán đối ứng; đã trả tiền cho
                # khách thì phải đi qua luồng Hoàn tiền — nơi có trần cứng và
                # hiện dòng hoàn trên hóa đơn của khách.
                change_type = (data.get('deposit_change_type') or '').strip().lower()
                if change_type == 'returned_to_guest':
                    return jsonify({
                        'success': False,
                        'error_code': 'use_refund_flow',
                        'msg': (
                            'Tiền đã đưa lại cho khách phải ghi qua chức năng Hoàn tiền '
                            'ở màn Hóa đơn cũ, để có trần kiểm soát và hiện trên hóa đơn '
                            'của khách.'
                        ),
                    }), 400
                if change_type != 'correction':
                    return jsonify({
                        'success': False,
                        'error_code': 'deposit_change_type_required',
                        'msg': (
                            'Cho biết vì sao giảm cọc: sửa số nhập sai, hay đã trả tiền '
                            'lại cho khách.'
                        ),
                    }), 400

                deposit_reason = (data.get('deposit_reason') or '').strip()
```

(phần còn lại của nhánh giữ nguyên)

- [ ] **Step 4: Ghi mục đích vào nhật ký**

Trong cùng nhánh, bổ sung `after_data` của `audit_service.record_event`:

```python
                    after_data={
                        'room_deposit_amount': room_deposit,
                        'reason': deposit_reason,
                        'change_type': change_type,
                    },
```

- [ ] **Step 5: Chạy test để xác nhận xanh**

Run: `venv/bin/python -m pytest tests/test_deposit_adjustment.py -v && venv/bin/python -m pytest -m "not mysql" -q`
Expected: PASS toàn bộ

- [ ] **Step 6: Commit**

```bash
git add controllers/timeline_controller.py tests/test_deposit_adjustment.py
git commit -m "feat: require an explicit intent when a deposit is lowered

deposit_adjustment has no cap and never shows on the guest bill, so it must not
double as a way to hand cash back. Money returned to a guest is now pushed to
the refund flow instead.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 5: Hai lựa chọn mục đích trên giao diện

**Files:**
- Modify: `templates/rooms/timeline.html` (khối `deposit-adjust-block` ~dòng 147-152; nút Lưu ~dòng 203)
- Modify: `static/js/timeline_manager.js` (`toggleDepositReason`, `saveBookingChanges`)
- Modify: `tests/test_accessibility_markup.py` (danh sách id cứng ~dòng 362)
- Test: `tests/test_deposit_adjustment.py`

**Interfaces:**
- Consumes: hợp đồng máy chủ `deposit_change_type` (Task 4)
- Produces: radio `deposit-change-correction` / `deposit-change-returned`; nút Lưu có `id="btn-save-booking"`; hàm `applyDepositChangeTypeState()`

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_deposit_adjustment.py`:

```python
def test_edit_modal_offers_the_two_intents_with_linked_labels():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "templates/rooms/timeline.html"
    ).read_text(encoding="utf-8")

    for control_id in ("deposit-change-correction", "deposit-change-returned"):
        assert f'id="{control_id}"' in source
        assert f'for="{control_id}"' in source          # nhãn phải liên kết
    assert 'value="correction"' in source
    assert 'value="returned_to_guest"' in source
    assert 'id="btn-save-booking"' in source            # JS cần khoá được nút này


def test_edit_modal_js_blocks_before_the_request_is_sent():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "static/js/timeline_manager.js"
    ).read_text(encoding="utf-8")

    assert "function applyDepositChangeTypeState" in source
    assert "deposit_change_type" in source
```

Và thêm hai id vào danh sách cứng trong `tests/test_accessibility_markup.py` (khoảng dòng 362, ngay sau `"deposit-adjust-reason",`):

```python
        "deposit-change-correction",
        "deposit-change-returned",
```

- [ ] **Step 2: Chạy test để chắc chắn nó đỏ**

Run: `venv/bin/python -m pytest tests/test_deposit_adjustment.py tests/test_accessibility_markup.py -v`
Expected: FAIL — chưa có radio nào trong template.

- [ ] **Step 3: Thay khối `deposit-adjust-block` trong `templates/rooms/timeline.html`**

```html
                        <div id="deposit-adjust-block" class="mt-2" style="display: none;">
                            <fieldset class="mb-2">
                                <legend class="pos-label" style="float: none;">Vì sao giảm cọc? <span class="text-danger" aria-hidden="true">*</span></legend>
                                <div class="form-check">
                                    <input class="form-check-input" type="radio" name="deposit-change-type"
                                           id="deposit-change-correction" value="correction"
                                           onchange="applyDepositChangeTypeState()">
                                    <label class="form-check-label" for="deposit-change-correction">
                                        Sửa số nhập sai
                                        <small class="text-muted d-block">Tiền không rời khỏi két</small>
                                    </label>
                                </div>
                                <div class="form-check">
                                    <input class="form-check-input" type="radio" name="deposit-change-type"
                                           id="deposit-change-returned" value="returned_to_guest"
                                           onchange="applyDepositChangeTypeState()">
                                    <label class="form-check-label" for="deposit-change-returned">
                                        Đã trả tiền lại cho khách
                                        <small class="text-muted d-block">Phải ghi qua chức năng Hoàn tiền</small>
                                    </label>
                                </div>
                            </fieldset>
                            <div id="deposit-returned-warning" class="alert alert-warning py-2 px-2 small d-none" role="alert">
                                Tiền đã đưa lại cho khách phải ghi qua chức năng <strong>Hoàn tiền</strong> ở màn
                                <strong>Hóa đơn cũ</strong> — ở đó có trần kiểm soát và khoản hoàn sẽ hiện trên hóa đơn của khách.
                            </div>
                            <label class="pos-label" for="deposit-adjust-reason">Lý do giảm cọc <span class="text-danger" aria-hidden="true">*</span></label>
                            <input type="text" class="form-control form-control-sm" id="deposit-adjust-reason" autocomplete="off" placeholder="Ví dụ: gõ nhầm số 0">
                            <small class="text-muted d-block mt-1">Sổ quỹ sẽ ghi một dòng điều chỉnh kèm lý do này.</small>
                        </div>
```

- [ ] **Step 4: Đặt id cho nút Lưu trong cùng file**

Tìm nút Lưu ở chân `editBookingModal` và thêm `id`:

```html
                <button type="button" id="btn-save-booking" class="btn btn-primary px-3 fw-bold" onclick="saveBookingChanges()">
                    <i class="fas fa-save me-1" aria-hidden="true"></i> Lưu lại
                </button>
```

- [ ] **Step 5: Cập nhật `toggleDepositReason` và thêm `applyDepositChangeTypeState` trong `static/js/timeline_manager.js`**

```javascript
// Ô lý do chỉ hiện khi số cọc bị GIẢM so với lúc mở modal.
function toggleDepositReason() {
    const block = document.getElementById('deposit-adjust-block');
    if (!block) return;
    const current = Number(document.getElementById('edit-deposit')?.value || 0);
    const original = Number(document.getElementById('edit-deposit-original')?.value || 0);
    const lowering = current < original;
    block.style.display = lowering ? 'block' : 'none';
    if (!lowering) {
        // Thôi giảm cọc thì xoá lựa chọn cũ, tránh gửi nhầm ở lần lưu sau.
        document.querySelectorAll('input[name="deposit-change-type"]').forEach(radio => {
            radio.checked = false;
        });
    }
    applyDepositChangeTypeState();
}

// Chọn "đã trả tiền lại cho khách" thì khoá nút Lưu ngay tại chỗ — để lễ tân
// biết mình đi nhầm đường trước khi bấm, chứ không phải sau khi nhận lỗi 400.
function applyDepositChangeTypeState() {
    const picked = document.querySelector('input[name="deposit-change-type"]:checked')?.value || '';
    const warning = document.getElementById('deposit-returned-warning');
    const saveButton = document.getElementById('btn-save-booking');
    if (warning) warning.classList.toggle('d-none', picked !== 'returned_to_guest');
    if (saveButton) saveButton.disabled = (picked === 'returned_to_guest');
}
```

- [ ] **Step 6: Chặn sớm trong `saveBookingChanges` của cùng file**

Thay khối kiểm tra lý do hiện có bằng:

```javascript
        const depositNow = Number(document.getElementById('edit-deposit').value || 0);
        const depositWas = Number(document.getElementById('edit-deposit-original')?.value || 0);
        const depositReason = document.getElementById('deposit-adjust-reason')?.value.trim() || '';
        let depositChangeType = '';
        if (depositNow < depositWas) {
            depositChangeType = document.querySelector('input[name="deposit-change-type"]:checked')?.value || '';
            if (!depositChangeType) {
                alert('Cho biết vì sao giảm cọc: sửa số nhập sai, hay đã trả tiền lại cho khách.');
                document.getElementById('deposit-change-correction')?.focus();
                return;
            }
            if (depositChangeType === 'returned_to_guest') {
                alert('Tiền đã đưa lại cho khách phải ghi qua chức năng Hoàn tiền ở màn Hóa đơn cũ.');
                return;
            }
            if (!depositReason) {
                alert('Giảm tiền cọc phải có lý do để đối soát.');
                document.getElementById('deposit-adjust-reason')?.focus();
                return;
            }
        }
```

Và thêm vào object `data` gửi lên (cạnh `deposit_reason`):

```javascript
            deposit_change_type: depositChangeType,
```

- [ ] **Step 7: Chứng minh test khả năng tiếp cận thật sự canh được**

Danh sách id trong test này là **cứng**, không quét tự động — nên phải chứng minh
nó thật sự canh được hai radio mới, chứ không phải xanh vì chưa biết tới chúng.

Sửa **bằng tay** trong `templates/rooms/timeline.html`: xoá đúng đoạn
`for="deposit-change-correction"` khỏi thẻ `<label>` (giữ nguyên mọi thứ khác), rồi chạy:

Run: `venv/bin/python -m pytest tests/test_accessibility_markup.py -q`
Expected: FAIL — báo thiếu label liên kết cho `deposit-change-correction`

Gõ lại `for="deposit-change-correction"` vào chỗ cũ rồi chạy lại:

Run: `venv/bin/python -m pytest tests/test_accessibility_markup.py -q`
Expected: PASS

> **Không dùng `git checkout` để khôi phục ở bước này** — các thay đổi ở Step 3-4
> chưa được commit, `git checkout` sẽ xoá sạch chúng. Sửa và hoàn nguyên bằng tay.

- [ ] **Step 8: Kiểm cú pháp và chạy toàn bộ**

Run:
```bash
node --check static/js/timeline_manager.js && \
venv/bin/python -m pytest -m "not mysql" -q && \
TZ=UTC venv/bin/python -m pytest -m "not mysql" -q
```
Expected: cả hai lần cùng số test, cùng xanh

- [ ] **Step 9: Commit**

```bash
git add templates/rooms/timeline.html static/js/timeline_manager.js tests/
git commit -m "feat: make reception state why a deposit is being lowered

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Nghiệm thu

- [ ] **Bước 1: Suite ở cả hai múi giờ**

```bash
venv/bin/python -m pytest -m "not mysql" -q
TZ=UTC venv/bin/python -m pytest -m "not mysql" -q
TZ=Asia/Ho_Chi_Minh venv/bin/python -m pytest -m "not mysql" -q
```
Expected: ba lần xanh với **cùng số test**

- [ ] **Bước 2: Bộ MySQL ở cả hai múi giờ**

```bash
set -a; source .env; set +a
TEST_MYSQL_DATABASE_URL="mysql+pymysql://root:${MYSQL_ROOT_PASSWORD}@127.0.0.1:3306/hotel_test" venv/bin/python -m pytest -m mysql -q
TZ=UTC TEST_MYSQL_DATABASE_URL="mysql+pymysql://root:${MYSQL_ROOT_PASSWORD}@127.0.0.1:3306/hotel_test" venv/bin/python -m pytest -m mysql -q
```
Expected: xanh cả hai (nếp này ra đời vì đợt trước CI đỏ do chỉ chạy ở múi VN)

- [ ] **Bước 3: Dựng lại stack + bộ trình duyệt**

```bash
docker compose build web && docker compose up -d web && sleep 6
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/healthz
set -a; source .env; set +a
BROWSER_BASE_URL=http://127.0.0.1:8000 BROWSER_ADMIN_PASSWORD="$ADMIN_PASSWORD" \
  venv/bin/python -m pytest tests/browser -q
```
Expected: `200` và bộ trình duyệt xanh

- [ ] **Bước 4: Kiểm chứng tay trong container**

1. Đặt một phòng, chọn cọc **Chuyển khoản** → mở **Sổ Quỹ**, dòng cọc phải mang nhãn chuyển khoản, không phải tiền mặt.
2. Mở modal sửa booking, giảm cọc, chọn **"Đã trả tiền lại cho khách"** → nút Lưu bị khoá kèm câu chỉ đường sang màn Hóa đơn cũ.
3. Gọi thẳng API bỏ qua giao diện:
```bash
curl -s -X POST http://127.0.0.1:8000/central/timeline/api/bookings/update \
  -H 'Content-Type: application/json' \
  -d '{"booking_room_id":1,"room_id":1,"deposit":0,"deposit_change_type":"returned_to_guest"}'
```
Expected: `400` với `error_code: use_refund_flow`, và dữ liệu **không đổi**.

- [ ] **Bước 5: Đẩy và theo dõi CI**

```bash
git push origin dev
gh run list --branch dev --limit 1
```
Expected: cả 3 job xanh. Sau đó đóng dấu "ĐÃ TRIỂN KHAI" vào đầu spec và commit.
