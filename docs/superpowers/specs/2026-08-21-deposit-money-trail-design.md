# Spec: Đường đi của tiền cọc — ghi đúng phương thức và buộc khai rõ mục đích khi giảm

> **ĐÃ TRIỂN KHAI 21-08-2026** — nhánh `dev`, 15 commit từ `1d58f5f` tới `79741c9`.
> Plan: `docs/superpowers/plans/2026-08-21-deposit-money-trail.md`.
> Nghiệm thu: 520 test xanh ở cả ba múi giờ (local / UTC / Asia/Ho_Chi_Minh) với
> cùng số lượng; 12 test MySQL xanh ở hai múi giờ; 5 test trình duyệt xanh; hai
> đường bị từ chối đã kiểm tay trên container thật (gọi thẳng API, bỏ qua giao
> diện) và xác nhận không đổi một dòng dữ liệu nào.
>
> **Một sai lệch so với spec đã được sửa trong đợt review cuối:** plan ban đầu bỏ
> sót yêu cầu §5.1 (Sổ Quỹ mang nhãn phương thức). Đã bổ sung ở `d0fa041`.
>
> **Đã đóng — không phải việc cần làm.** Review tổng nêu lo ngại rằng
> `billing_controller.py:45` lọc hóa đơn cũ theo `checked_out`/`cancelled` nên đơn
> đang ở không hiện trong màn Hoàn tiền, và coi đó là "bịt lối trung thực". Chủ
> khách sạn bác bỏ tiền đề: **không có nghiệp vụ hoàn cọc khi khách còn đang ở**.
> Khách đi sớm thì trả phòng sớm, cọc trừ vào hóa đơn lúc đó. Ba lối ra tiền có
> thật đều đã có đường đi — hủy trước khi đến → Hoàn tiền; đã trả phòng → Hoàn
> tiền; đang ở → trừ vào hóa đơn khi trả phòng. Câu chữ hiện tại đã nói đúng cả
> ba, không cần sửa gì thêm.

**Nguồn:** rà soát nghiệp vụ 21-08-2026, sau đợt sửa hợp đồng thời gian / XSS / dấu vết cọc.
**Chủ khách sạn đã chốt:** với việc giảm cọc, đi theo hướng **bắt chọn mục đích** — chọn
"đã trả tiền lại cho khách" thì hệ thống chặn và chỉ sang luồng Hoàn tiền.

Hai vấn đề dưới đây gộp một đợt vì cùng một vùng nghiệp vụ (dòng tiền cọc) và
cộng hưởng với nhau thành lỗi lệch két.

---

## 1. Vấn đề

### 1.1 Nhận cọc luôn ghi là tiền mặt

Ba nơi ghi nhận cọc đều cứng hoá `payment_method='cash'`:

| Vị trí | Luồng |
| --- | --- |
| `controllers/timeline_controller.py:590` | Tạo booking từ Timeline / Sơ đồ phòng |
| `controllers/timeline_controller.py:1270` | Nộp thêm cọc qua modal sửa booking |
| `controllers/booking_controller.py:897` | Đặt phòng theo đoàn |

Giao diện cũng không có chỗ chọn: `templates/rooms/_booking_modal.html` và
`_group_booking_modal.html` chỉ có ô nhập số tiền.

**Đang xảy ra thật.** Truy vấn dữ liệu sản phẩm:

```
payment_method  payment_type      COUNT(*)
cash            deposit           49
cash            refund             2
cash            refund_reversal    1
```

Toàn bộ 49 khoản cọc đã nhận đều mang nhãn tiền mặt, bất kể khách trả bằng gì.
Khách chuyển khoản thì cuối ca đếm két sẽ thiếu đúng khoản đó.

Trớ trêu là màn **thanh toán** đã có nút chọn Tiền mặt / Chuyển khoản / Thẻ từ
đợt 15-08, còn màn **nhận cọc** thì chưa — hai đầu của cùng một dòng tiền đang
bất nhất.

### 1.2 Bút toán điều chỉnh cọc gánh hai nghiệp vụ trái ngược

`deposit_adjustment` (thêm ở đợt 19-08) được thiết kế cho việc **đính chính số
ghi sai**. Nhưng không có gì ngăn dùng nó cho việc **trả tiền mặt lại cho khách**
— hai sự kiện kinh tế khác hẳn nhau.

Đối chiếu cách hệ thống đối xử với hai loại bút toán:

| | `refund` (Hoàn tiền) | `deposit_adjustment` (Điều chỉnh cọc) |
| --- | --- | --- |
| Trần cứng | **Có** — `refundable_cap`, vượt thì ném `RefundCapExceeded` | **Không** (chỉ chặn số dương) |
| Hiện trên hóa đơn khách | **Có** — `_effective_refunds_data` lọc `payment_type == 'refund'` | **Không** |
| Vào ô "Tổng hoàn cọc" của sổ quỹ | **Có** | **Không** — nó làm giảm "đã thu" |
| Bắt buộc lý do | **Có** | Có (từ đợt 19-08) |

Nói gọn: **điều chỉnh cọc là con đường để tiền rời khỏi két mà sổ không ghi nhận
là tiền ra.**

### 1.3 Hai lỗi cộng hưởng thành lệch két thật

Riêng lẻ thì mỗi lỗi chỉ sai nhãn. Ghép lại thì số dư sai:

> Khách **chuyển khoản** 5.000.000 tiền cọc → hệ thống ghi là **tiền mặt** (1.1).
> Khách hủy, lễ tân **rút két đưa lại 5.000.000 tiền mặt**, ghi bằng điều chỉnh cọc (1.2).
> Sổ quỹ báo: đã thu **0**, đã hoàn **0**.
> Két thật: **thiếu 5.000.000** — tiền vào tài khoản ngân hàng, tiền mặt đã chi ra.

Không có dòng nào trong sổ giải thích được khoản thiếu đó.

---

## 2. Phần 1 — Phương thức thanh toán cho tiền cọc

### 2.1 Bộ giá trị

Dùng **đúng ba giá trị mà màn thanh toán đang dùng**: `cash`, `banking`,
`credit_card`. Nhãn hiển thị: "Tiền mặt", "Chuyển khoản", "Thẻ".

**Quyết định có chủ đích — không thêm `qr_code`:** enum cũ trong migration
`a3471c834318` từng có giá trị này, nhưng quét QR ngân hàng về bản chất là một
lệnh chuyển khoản và sẽ về cùng tài khoản với "Chuyển khoản". Thêm một giá trị
thứ tư sẽ tách đôi cùng một dòng tiền trong báo cáo mà không mang lại thông tin
mới cho việc đối soát. Nếu sau này cần tách, cột là `String(50)` (không phải
ENUM) nên thêm giá trị **không cần đổi cấu trúc bảng**.

### 2.2 Máy chủ

Ba nơi ở mục 1.1 nhận `payment_method` từ payload thay vì cứng hoá. Thêm một
helper dùng chung để chuẩn hoá và chặn giá trị lạ:

```python
# services/payment_service.py
DEPOSIT_PAYMENT_METHODS = ("cash", "banking", "credit_card")


def normalize_payment_method(value, *, default="cash"):
    """Chuẩn hoá phương thức thanh toán do client gửi lên.

    Giá trị lạ bị quy về mặc định thay vì ném lỗi: đây là nhãn kế toán, không
    phải điều kiện an toàn — chặn cứng sẽ làm hỏng thao tác của lễ tân vì một
    lỗi gõ, trong khi hậu quả tệ nhất của việc quy về mặc định chỉ là một nhãn
    cần sửa sau.
    """
    candidate = str(value or "").strip().lower()
    return candidate if candidate in DEPOSIT_PAYMENT_METHODS else default
```

### 2.3 Giao diện

- `templates/rooms/_booking_modal.html`: dưới ô "Tiền cọc (VNĐ)", thêm nhóm nút
  chọn phương thức, dùng lại lớp `pos-method-btn` đã có sẵn từ modal thanh toán
  (để hai màn trông giống nhau). Mặc định **Tiền mặt**.
- `templates/rooms/_group_booking_modal.html`: tương tự, dưới ô "Tiền cọc tổng".
- `templates/rooms/timeline.html` (`editBookingModal`): tương tự, dưới ô
  "Tiền đặt cọc (VNĐ)" — chỉ áp dụng khi **nộp thêm** cọc.
- Mỗi nhóm có `<input type="hidden">` giữ giá trị, id lần lượt:
  `bk-deposit-method`, `group-deposit-method`, `edit-deposit-method`.
- JS gửi kèm trường `deposit_payment_method` trong payload của ba luồng tương ứng.

---

## 3. Phần 2 — Buộc khai rõ mục đích khi giảm cọc

### 3.1 Hợp đồng máy chủ

`/api/bookings/update` khi phát hiện `new_deposit < old_deposit` yêu cầu thêm
trường `deposit_change_type`, nhận đúng hai giá trị:

| Giá trị | Nghĩa | Hành vi |
| --- | --- | --- |
| `correction` | Sửa số nhập sai, tiền **không** rời két | Ghi `deposit_adjustment` như hiện tại |
| `returned_to_guest` | Đã đưa tiền lại cho khách | **Từ chối**, chỉ sang luồng Hoàn tiền |

Mã lỗi trả về:

- Thiếu trường → `400`, `error_code: 'deposit_change_type_required'`
- `returned_to_guest` → `400`, `error_code: 'use_refund_flow'`, thông báo:
  *"Tiền đã đưa lại cho khách phải ghi qua chức năng Hoàn tiền ở màn Hóa đơn cũ,
  để có trần kiểm soát và hiện trên hóa đơn của khách."*
- Giá trị lạ → `400`, `error_code: 'deposit_change_type_required'`

**Không được đổi bất kỳ dữ liệu nào trước khi trả lỗi** — giữ đúng nguyên tắc đã
thiết lập ở đợt 19-08: từ chối thì không ghi gì cả.

Lý do vẫn bắt buộc như hiện tại, và `deposit_change_type` được ghi vào
`audit_service.record_event` cùng lý do.

### 3.2 Giao diện

Khối `deposit-adjust-block` trong `editBookingModal` (hiện chỉ có ô lý do tự do)
được bổ sung **hai lựa chọn bắt buộc** đặt **phía trên** ô lý do:

```html
<fieldset class="mt-2">
  <legend class="pos-label">Vì sao giảm cọc? <span class="text-danger" aria-hidden="true">*</span></legend>
  <div class="form-check">
    <input class="form-check-input" type="radio" name="deposit-change-type"
           id="deposit-change-correction" value="correction">
    <label class="form-check-label" for="deposit-change-correction">
      Sửa số nhập sai <small class="text-muted d-block">Tiền không rời khỏi két</small>
    </label>
  </div>
  <div class="form-check">
    <input class="form-check-input" type="radio" name="deposit-change-type"
           id="deposit-change-returned" value="returned_to_guest">
    <label class="form-check-label" for="deposit-change-returned">
      Đã trả tiền lại cho khách <small class="text-muted d-block">Phải ghi qua Hoàn tiền</small>
    </label>
  </div>
</fieldset>
```

Hành vi phía trình duyệt:

- Chọn **"Sửa số nhập sai"** → ô lý do bật, nút Lưu hoạt động bình thường.
- Chọn **"Đã trả tiền lại cho khách"** → hiện cảnh báo ngay trong modal, **vô
  hiệu hoá nút Lưu**, kèm câu chỉ đường tới màn Hóa đơn cũ. Không để lễ tân bấm
  Lưu rồi mới nhận lỗi từ máy chủ.
- Chưa chọn gì mà bấm Lưu → chặn tại chỗ, đưa con trỏ về nhóm lựa chọn.

Cả hai `<input>` đều phải có `<label for=...>` liên kết — dự án có test bắt buộc
điều này, và test đó dùng **danh sách id cứng** nên phải thêm
`deposit-change-correction` và `deposit-change-returned` vào
`tests/test_accessibility_markup.py`, nếu không markup đúng mà test không canh
được (đúng lỗi đã gặp ở đợt trước).

### 3.3 Giới hạn thành thật của cách làm này

Hệ thống **không thể biết** lễ tân có thật sự đưa tiền cho khách hay không. Ai
cố tình chọn "Sửa số nhập sai" cho một khoản đã trả ra thì vẫn lọt.

Cách làm này không nhằm chống gian lận có chủ đích. Nó nhằm hai việc:

1. **Chặn nhầm lẫn** — người dùng ngay tình sẽ được chỉ sang đúng luồng.
2. **Biến một thao tác vô tình thành một lời khai có ghi nhật ký** — sau này đối
   soát, mỗi lần giảm cọc đều có một dòng ghi rõ người đó khai là gì.

Chống gian lận có chủ đích cần đối soát két theo ca, nằm ngoài phạm vi spec này.

---

## 4. Dữ liệu đã có

**Không sửa hồi tố.** 49 khoản cọc đang mang nhãn `cash` — hệ thống không có
thông tin nào để biết khoản nào thực sự là chuyển khoản, và đoán sẽ tệ hơn là
để nguyên. Từ khi triển khai trở đi, nhãn mới ghi đúng.

Nếu chủ khách sạn nhớ được khoản nào là chuyển khoản thì sửa tay bằng SQL, nhưng
spec này không tự động hoá việc đó.

**Không cần migration** — `payments.payment_method` là `String(50)`, các giá trị
mới đã nằm trong miền cho phép.

---

## 5. Kiểm chứng

### 5.1 Phần phương thức thanh toán

- Tạo booking lẻ với `deposit_payment_method='banking'` → `Payment` có
  `payment_method == 'banking'` (test này phải ĐỎ trước khi sửa).
- Đặt đoàn với `banking` → khoản cọc đoàn ghi đúng.
- Nộp thêm cọc qua modal sửa với `credit_card` → ghi đúng.
- Không gửi trường → mặc định `cash` (giữ tương thích với client cũ).
- Gửi giá trị lạ (`'bitcoin'`) → quy về `cash`, không ném lỗi.
- Sổ quỹ nhóm đúng theo phương thức: tạo hai khoản cọc khác phương thức, gọi
  `/{slug}/cashier/api/reports/cashier`, khẳng định mỗi dòng mang đúng nhãn.

### 5.2 Phần khai mục đích

- Giảm cọc **không** gửi `deposit_change_type` → `400`,
  `error_code == 'deposit_change_type_required'`, và **không** tạo `Payment` nào,
  **không** đổi `room_deposit_amount`.
- Giảm cọc với `returned_to_guest` → `400`, `error_code == 'use_refund_flow'`,
  không ghi gì.
- Giảm cọc với `correction` + lý do → tạo đúng một dòng `deposit_adjustment` âm,
  `room_deposit_original` **giữ nguyên**, audit event chứa `deposit_change_type`.
- **Tăng** cọc không cần `deposit_change_type` (không phải tiền ra).
- Markup: hai radio có `<label for>` liên kết; và test khả năng tiếp cận phải
  thật sự canh được — chứng minh bằng cách tạm xoá `for=` thì test ĐỎ.

---

## 6. Ngoài phạm vi

1. Phương thức thanh toán cho `record_cancellation_fee`
   (`timeline_controller.py:1144`) — bút toán này có **số tiền bằng 0**, chỉ để
   ghi vết, nên nhãn phương thức không ảnh hưởng đối soát.
2. Đối soát két theo ca (đếm tiền đầu/cuối ca so với sổ) — việc lớn riêng.
3. Sửa hồi tố 49 khoản cọc cũ.
4. Tách `qr_code` thành phương thức riêng.
5. Ba nhóm việc kỹ thuật còn treo: sao lưu & khôi phục, giám sát & vận hành,
   vendor thư viện.

---

## 7. Tiêu chí nghiệm thu

1. Toàn bộ suite xanh, **và xanh ở cả `TZ=UTC` lẫn `TZ=Asia/Ho_Chi_Minh`** với
   cùng số test (nếp đã thiết lập từ đợt 19-08).
2. Mỗi hành vi mới có ít nhất một test đã được chứng minh ĐỎ trước khi sửa.
3. CI xanh cả ba job.
4. Kiểm chứng tay trong container: nhận cọc bằng "Chuyển khoản" → mở Sổ Quỹ thấy
   đúng nhãn chuyển khoản, không phải tiền mặt.
5. Kiểm chứng tay: thử giảm cọc và chọn "Đã trả tiền lại cho khách" → nút Lưu bị
   khoá kèm câu chỉ đường; gọi thẳng API bỏ qua giao diện → trả `400` và dữ liệu
   không đổi.
