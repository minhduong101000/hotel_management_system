# Spec: Sửa lỗi múi giờ, XSS hóa đơn in, dấu vết cọc và thống nhất chống trùng phòng

> **ĐÃ TRIỂN KHAI 20-08-2026** — 32 commit, 15 task, mỗi task qua review riêng + 1 review
> toàn nhánh. Nghiệm thu: 495 unit (xanh ở cả 3 múi giờ) + 12 mysql (xanh cả VN lẫn UTC)
> + 5 browser; CI xanh cả 3 job; kiểm chứng tay trong container UTC lúc 01:09 giờ VN.
> Ghi chú: review toàn nhánh tìm thêm 1 lỗi Critical (modal ghi ngược giờ UTC vào cột giờ
> nghiệp vụ, thu oan 500.000đ) mà 15 lần review từng-task đều không thấy — đã vá.

**Nguồn:** audit đối kháng 17-08-2026 (6 lát cắt song song + phản biện). Mọi
phát hiện dưới đây đã được kiểm chứng bằng code đọc trực tiếp; riêng giả định
"container chạy UTC" đã xác minh **trên container đang chạy**:

```
$ docker compose exec web python -c "print(datetime.now())"
2026-08-17T13:56:28      # trong khi đồng hồ VN là 20:56 — lệch đúng 7 tiếng
$ docker compose exec web sh -c 'echo TZ=${TZ:-<unset>}'
TZ=<unset>               # không có /etc/timezone => UTC
```

**Phạm vi:** 4 cụm — (1) hợp đồng thời gian, (2) XSS hóa đơn in, (3) dấu vết
tiền cọc, (4) thống nhất chống trùng phòng. Cụm 4 được chủ khách sạn duyệt gộp
vào đợt này vì cùng vùng code với cụm 1.

---

## 1. Nguyên nhân gốc: một chữ `datetime.now()`, hai ý nghĩa khác nhau

Hợp đồng thời gian (spec 14-08) chia mốc thời gian làm hai loại:

| Loại | Ví dụ cột | Hệ quy chiếu |
| --- | --- | --- |
| Giờ **dự kiến** do người dùng nhập | `check_in_expected`, `check_out_expected` | giờ nghiệp vụ VN, naive |
| Timestamp **hệ thống** ghi | `created_at`, `*_actual`, `cancelled_at`, `completed_at` | UTC, naive |

`datetime.now()` trả về giờ **đồng hồ máy** — nghĩa là nó **không đúng cho cả
hai loại**: trong Docker (UTC) nó tình cờ đúng loại 2 và sai loại 1; trên máy
dev (giờ VN) thì ngược lại. Đây là gốc của 1 lỗi P1, 3 lỗi P2 và góp phần vào
lỗi P1 thứ hai.

**Cạm bẫy phải tránh:** đặt `TZ=Asia/Ho_Chi_Minh` cho container **không phải là
lời giải**. Nó chữa được loại 1 nhưng làm hỏng loại 2 — mọi `created_at` sẽ ghi
giờ VN vào cột quy ước UTC, khiến phiếu thu sau 17:00 rơi sang ngày nghiệp vụ
hôm sau trong báo cáo két, và tạo ra bảng ledger trộn hai gốc thời gian không
sửa hồi tố được. Lời giải là **gọi đúng hàm cho đúng ý nghĩa**.

### 1.1 Hai helper mới trong `services/time_service.py`

```python
def business_now_naive() -> datetime:
    """'Bây giờ' theo giờ nghiệp vụ, dạng naive.
    DÙNG KHI: so sánh với các cột *_expected (vốn là giờ VN naive).
    """
    return business_now().replace(tzinfo=None)


def to_business_naive(utc_dt) -> datetime | None:
    """Đổi một mốc UTC (naive/aware) sang giờ nghiệp vụ dạng naive.
    DÙNG KHI: cần đặt timestamp hệ thống cạnh giờ dự kiến để so/tính.
    """
```

### 1.2 Luật phân loại — mỗi `datetime.now()` thuộc đúng một nhóm

| Nhóm | Ý nghĩa | Thay bằng |
| --- | --- | --- |
| **A** | So sánh với `*_expected` | `time_service.business_now_naive()` |
| **B** | Ghi vào cột timestamp hệ thống | `time_service.utc_now_naive()` |
| **C** | Sinh nhãn/mã/đếm theo **ngày nghiệp vụ** | `time_service.business_today()` |

### 1.3 Nhóm A — các phép so với giờ dự kiến (nguồn của P1 + P2)

| Vị trí | Việc | Hậu quả hiện tại |
| --- | --- | --- |
| `booking_controller.py:157` | guard "check-in sớm tối đa 3h" | **P1** — khách đến đúng 14:00 bị chặn, chỉ vào được sau 18:00 |
| `timeline_controller.py:516` | guard "vào ở ngay" | **P1** — walk-in luôn bị từ chối |
| `timeline_controller.py:68` | clamp overstay trong `_has_room_time_conflict` | P2 — chống trùng phòng chết 7 tiếng |
| `timeline_controller.py:132` | clamp overstay trong `_has_active_booking_conflict` | P2 — như trên |
| `timeline_controller.py:208` | cờ "Quá giờ" + clamp `end` của bar | P2 — badge trễ 7h; bar khách overstay kết thúc sai |
| `room_controller.py:283` | mốc so `check_in_expected` (dòng 332, 347) | P2 — nhãn "chờ/sắp đến" sai |
| `room_controller.py:399` | `is_overdue` trên sơ đồ phòng | P2 — cờ quá giờ trễ 7h |

**Chi tiết quan trọng tại `booking_controller.py:157`:** biến `now` ở đây đang
được dùng cho **cả hai** mục đích — vừa so với `check_in_expected` (dòng 158,
nhóm A) vừa ghi vào `check_in_actual` qua `checked_in_at=now` (dòng 164, nhóm
B). Phải **tách thành hai biến**, không được đổi chung một chỗ:

```python
now_business = time_service.business_now_naive()   # để so với *_expected
now_utc = time_service.utc_now_naive()             # để ghi *_actual

if booking_room.check_in_expected and booking_room.check_in_expected - now_business > timedelta(hours=3):
    return ...
booking_state_service.check_in_room(booking_room, checked_in_at=now_utc)
```

### 1.4 Nhóm B — timestamp hệ thống

| Vị trí | Cột được ghi |
| --- | --- |
| `booking_controller.py:365, 530, 1200, 1376` | `checkout_at` → `check_out_actual` |
| `booking_controller.py:869, 884` | `Booking.created_at`, `Payment.created_at` |
| `booking_controller.py:971` | `changed_at` |
| `timeline_controller.py:594, 606, 1163, 1288` | `created_at` của Booking/Payment |
| `timeline_controller.py:649, 654, 1115, 1366` | `checked_in_at`, `changed_at`, `cancelled_at`, `check_in_actual` |
| `expense_controller.py:289` | `voided_at` |
| `business_operation_service.py:49` | `completed_at` |
| `refund_service.py:85` | `effective_at` |

Với 4 lời gọi `payment_service.record_*(created_at=datetime.now())`
(`timeline_controller.py:606, 1163, 1288`; `booking_controller.py:884`) thì
cách sửa đúng là **xóa hẳn tham số** — `payment_service._now()` đã có mặc định
`utc_now_naive()` chuẩn (payment_service.py:20-24). Với `Booking.created_at`
thì phải **thay** bằng `utc_now_naive()` chứ không xóa, vì default của model là
`db.func.now()` (giờ session MySQL).

### 1.5 Nhóm C — ngày nghiệp vụ

| Vị trí | Việc | Hậu quả |
| --- | --- | --- |
| `timeline_controller.py:119` | mã booking `BK-yymmdd` | 0–7h sáng in ngày hôm trước |
| `booking_controller.py:863` | tiền tố mã đoàn `GRP` | như trên |
| `master_controller.py:45` | đếm `today_bookings` | dashboard lệch báo cáo |
| `pricing_service.py:120, 138` | mặc định `check_date` khi dò `PriceRule` | 0–7h sáng áp giá **ngày hôm trước** (rule lễ/Tết, cuối tuần) |

### 1.6 Ranh giới định giá — lỗi P1 thu oan tiền khách

`calculate_complex_hotel_bill` so `check_in` (từ `check_in_actual`, UTC) với
`expected_check_in` (VN) tại `pricing_service.py:350-353` → ra chênh 7 giờ →
`get_surcharge_ratio(7h)` = **100% giá một đêm** cộng vào hóa đơn với nhãn
"Phụ thu phát sinh · Sớm 7.0h". Ngoài ra `pricing_service.py:272` lấy
`check_in.date()`: khách check-in 00:00–06:59 VN có ngày UTC là **hôm trước** →
tính thừa hẳn một đêm. Chiều ngược lại, trả muộn tới 7 giờ **không** bị phụ thu.

**Cách sửa — quy đổi tại biên, không sửa trong lòng `pricing_service`:**

`calculate_complex_hotel_bill` được tuyên bố là hàm **thuần giờ nghiệp vụ VN**
(ghi vào docstring). `build_checkout_quote` (booking_quote_service.py:138-157)
chịu trách nhiệm quy đổi trước khi gọi:

```python
check_in_business = (
    time_service.to_business_naive(booking_room.check_in_actual)
    if booking_room.check_in_actual
    else (booking_room.check_in_expected or time_service.to_business_naive(checkout_at))
)
checkout_business = time_service.to_business_naive(checkout_at)
```

Ràng buộc: giá trị `checkout_at` **trả ra trong quote** (dùng cho
`quote_fingerprint` / `quote_checkout_at` và ghi `check_out_actual`) phải **giữ
nguyên UTC** — chỉ bản quy đổi được truyền vào hàm tính giá. Thuê theo giờ chỉ
dùng độ dài khoảng nên bất biến khi cả hai đầu cùng dịch.

---

## 2. Cụm 2 — XSS lưu trữ qua nút "In hóa đơn"

`bdPrintInvoice` (timeline_manager.js:1113-1181) đọc tên khách bằng
`textContent` rồi **nội suy thô vào HTML** (`${customer}` dòng 1152,
`${bookingCode}` dòng 1134, `${room}` dòng 1153) và ghi bằng
`printWin.document.write(html)` (dòng 1179). Popup mở qua `window.open('', '_blank')`
là **same-origin** với app; chính template đã chèn `<script>window.print()</script>`
nên script trong popup chắc chắn thực thi. App **không có CSP** (bỏ có chủ ý,
test_production_config.py:89-92) nên không có lớp giảm nhẹ.

Kịch bản: lễ tân nhập tên khách `<img src=x onerror="fetch('/central/api/...')">`
→ admin bấm "In hóa đơn" → mã chạy với phiên admin → gọi được API chỉ-admin
(giá, dịch vụ, nhân sự) → **staff leo thang thành admin**.

**Cách sửa:**

1. Thêm `escapeHtml(value)` dùng chung vào `static/js/main.js` (nạp ở mọi trang):

```javascript
function escapeHtml(value) {
    const el = document.createElement('div');
    el.textContent = value == null ? '' : String(value);
    return el.innerHTML;
}
```

2. `bdPrintInvoice`: escape mọi trường nội suy; **dựng lại các dòng hóa đơn từ
   dữ liệu** (`bookingDetailServicesLines` + dòng tiền phòng) thay vì sao chép
   `bd-invoice-table-body.innerHTML` (dòng 1121) — bản sao đó kế thừa luôn mọi
   chỗ chưa escape của renderer.
3. Escape các sink còn lại đang cấp dữ liệu cho bảng đó và cho POS:
   `timeline_manager.js:993` (catalog dịch vụ), `:1057` (dòng hóa đơn),
   `:565, :1432, :1438` (option số phòng); `checkout.js:213`;
   `service.js:103, :168`.
4. Gộp `checkoutEscapeHtml` (checkout.js:387) về helper chung để chỉ còn một
   đường escape trong toàn app.

---

## 3. Cụm 3 — dấu vết tiền cọc

### 3.1 Giảm cọc hiện không để lại dấu vết

`update_booking` (timeline_controller.py:1278-1294): **tăng** cọc thì ghi
`record_deposit` cho phần chênh; **giảm** cọc thì không ghi gì, gán thẳng
`br.room_deposit_amount` và **ghi đè cả `br.room_deposit_original`** — xóa mất
bản ghi duy nhất về số tiền ban đầu đã thu, trên một hệ sổ vốn append-only.

### 3.2 Chính sách đã chốt (chủ khách sạn duyệt 19-08)

Cho phép giảm, nhưng **phải để lại bút toán và lý do** — cùng tinh thần bút
toán đảo đã chốt cho hoàn tiền:

- Thêm loại thanh toán `deposit_adjustment` (số tiền **âm**).
- `payment_service.record_deposit_adjustment(booking_id, amount, reason, ...)`,
  chặn cứng nếu `amount >= 0`.
- `update_booking` khi phát hiện `new_deposit < old_deposit`:
  - **bắt buộc** có lý do (`deposit_reason`), thiếu thì trả lỗi, không ghi gì;
  - ghi một dòng `deposit_adjustment` âm, ghi chú `"Điều chỉnh cọc: {lý do}"`;
  - **giữ nguyên** `room_deposit_original`;
  - ghi `audit_service.record_event` như các thao tác tiền khác.
- UI: modal sửa booking hiện ô lý do khi số cọc bị giảm (theo đúng khuôn
  `refund-section` sẵn có), id `deposit-adjust-reason`, có `<label for=...>`.

### 3.3 Hiển thị: nội bộ đủ, hóa đơn khách gọn

- **Sổ quỹ / nhật ký nội bộ:** hiện đủ hai dòng (`+5.000.000` nhận cọc,
  `−4.500.000` điều chỉnh cọc kèm lý do và người thực hiện). Báo cáo két đặt
  nhãn "Điều chỉnh cọc" cho loại mới.
- **Hóa đơn khách in ra:** hiển thị **tổng cọc ròng** (500.000), không liệt kê
  cặp cộng-trừ — đúng nguyên tắc đã chốt cho hoàn tiền.
- **Trần hoàn tiền:** `refundable_cap` = tổng mọi `Payment.amount` nên tự động
  giảm theo dòng âm. Không cần sửa `refund_service`, nhưng **phải có test khóa**
  hành vi này (giảm cọc xong thì không hoàn quá phần còn lại).

---

## 4. Cụm 4 — thống nhất chống trùng phòng

Hiện có **ba** cách kiểm tra trùng phòng khác nhau, mạnh yếu không đều:

| Đường | Cách kiểm tra | Vấn đề |
| --- | --- | --- |
| Đặt lẻ | `_has_room_time_conflict` (timeline_controller.py:68) | có xét giờ thực tế + overstay (mạnh nhất) |
| Đặt đoàn | SQL thô (booking_controller.py:903-908) | chỉ so `*_expected`, bỏ qua giờ thực tế và khách overstay |
| Tìm phòng trống | SQL thô (room_controller.py:530-536) | như trên — **mời** phòng đang có khách |

**Cách sửa:** rút thành `services/room_availability_service.py`, lấy ngữ nghĩa
của bản mạnh nhất:

```python
def has_room_conflict(*, room_id, start, end, exclude_booking_room_id=None, now=None) -> bool
def find_available_room_ids(*, start, end, now=None) -> set[int]
```

Ngữ nghĩa chuẩn (áp cho cả ba đường):
- Xét `BookingRoom.status in ('booked', 'checked_in')`;
- `row_start = check_in_actual or check_in_expected`;
  `row_end = check_out_actual or check_out_expected`;
- nếu `status == 'checked_in'` và `row_end < now` → `row_end = now`
  (**khách overstay vẫn chiếm phòng**), với `now = business_now_naive()`;
- `checked_in` mà không có mốc kết thúc → coi là đang bận;
- trùng khi `row_start < end and row_end > start`.

### 4.1 Lỗ hổng đi kèm ở `update_booking`

Kiểm tra trùng lịch (timeline_controller.py:1311) chỉ chạy khi
`new_status in ['booked', 'checked_in']`, trong khi dòng 1332 gán thẳng
`br.status = new_status`. Một request `/api/bookings/update` **không kèm
`status`** sẽ: bỏ qua kiểm tra trùng, vẫn đổi giờ/phòng, và **ghi `status =
None`**. Giao diện hiện luôn gửi `status` nên chưa lộ, nhưng API gọi trực tiếp
thì thủng.

Sửa: dùng `effective_status = new_status or br.status`, **luôn** chạy kiểm tra
trùng khi có đổi phòng/giờ, và không bao giờ ghi `None` vào `status`.

---

## 5. Chiến lược test — điểm mấu chốt của cả spec

Toàn bộ 434 test đang **xanh giả**: máy dev chạy giờ VN nên `datetime.now()`
tình cờ đúng, còn production chạy UTC thì sai. Nếu không đổi cách test, sửa
xong vẫn không có gì bảo vệ.

1. **Test chạy dưới TZ=UTC.** `tests/test_timezone_contract.py` với fixture đặt
   `os.environ['TZ'] = 'UTC'; time.tzset()` để **tái lập đúng môi trường
   production**, đóng băng `time_service.utc_now`, rồi khẳng định:
   - khách đến **đúng** giờ hẹn → check-in thành công (RED trước khi sửa);
   - walk-in "vào ở ngay" → thành công;
   - khách daily đến đúng giờ → **phụ thu = 0**;
   - khách check-in 01:00 VN → **không** tính thừa đêm;
   - khách quá hẹn 1 phút → `is_overstay = True` ngay, không đợi 7 tiếng.
2. **Grep-guard chống tái phát.** Test cấm `datetime.now()` mới trong
   `controllers/` và `services/` (whitelist `time_service.py`). Đây là thứ giữ
   cho lớp lỗi này không quay lại sau vài tháng.
3. **Test trùng phòng** cho cả ba đường: khách overstay thì `/api/rooms/search`
   không trả phòng đó, đặt đoàn bị từ chối, và `update_booking` không kèm
   `status` vẫn bị chặn khi đè lịch.
4. **Test dấu vết cọc:** giảm cọc thiếu lý do → bị từ chối; có lý do → sinh
   đúng một dòng âm, `room_deposit_original` không đổi, trần hoàn tiền giảm
   tương ứng.
5. **Test XSS trình duyệt (B5):** seed khách tên
   `<img src=x onerror="window.__xss=1">`, mở chi tiết booking, bấm In hóa đơn,
   bắt popup bằng `page.on("popup")` và khẳng định `window.__xss` là
   `undefined`. Kèm test chuỗi khẳng định đường in không còn nội suy thô.

---

## 6. Ngoài phạm vi (đã ghi nhận, làm đợt sau)

1. **Vendor thư viện CDN về máy** (Bootstrap/FA/fonts/html5-qrcode) để POS chạy
   được khi mất Internet — spec riêng, ưu tiên cao nhất trong số còn lại.
   Ngoại lệ: **pin `html5-qrcode@2.3.8`** làm luôn trong đợt này vì chỉ sửa 2
   dòng và đang là rủi ro trôi version y hệt vụ vis-timeline.
2. Backup: `backup.sh` nuốt lỗi (dump fail vẫn báo "done" rồi vẫn xóa bản cũ),
   backup nằm cùng máy với DB, chưa có diễn tập restore, chưa backup trước
   migrate.
3. Pin image Docker (`caddy:2`, `adminer` không tag, `mysql:8`); gunicorn đổi
   sang `gthread`; log bị mất khi recreate container; chưa có giám sát
   `/healthz`.
4. Test runtime cho JS (`booking_modal.js`, lưới timeline); browser smoke cho
   checkout lẻ/đoàn.
5. Hiển thị phòng bẩn (`clean_status`) trong kết quả tìm phòng đoàn.

---

## 7. Tiêu chí nghiệm thu

1. Toàn bộ suite (unit + mysql + browser) xanh, **và xanh cả khi chạy với
   `TZ=UTC`** — chứng minh kết quả không còn phụ thuộc giờ máy chạy test.
2. Mỗi lỗi P1 có ít nhất một test đã được chứng minh RED trước khi sửa.
3. Grep-guard `datetime.now()` hoạt động (thử thêm một dòng vi phạm thì test đỏ).
4. Kiểm chứng thủ công **trong container**: tạo booking hẹn giờ hiện tại →
   check-in được ngay; checkout → hóa đơn **không** có dòng "Phụ thu phát sinh"
   oan; giảm cọc → sổ quỹ hiện dòng điều chỉnh kèm lý do, hóa đơn khách chỉ
   hiện số ròng.
5. CI GitHub xanh cả 3 job.
