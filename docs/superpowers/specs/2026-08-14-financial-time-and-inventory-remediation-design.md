# Spec: Hoàn tiền nhập trực tiếp có kiểm soát, thời gian báo cáo và kiểm thử kho

**Ngày:** 14-08-2026
**Trạng thái:** ĐÃ TRIỂN KHAI 14-08-2026 (7 commit, 1208cc2..6d3bf31) — thiết kế hoàn tiền đổi từ "luồng phê duyệt bất khả kháng" (bản nháp sáng 14-08) sang "nhập trực tiếp có lưới an toàn" theo quyết định của chủ dự án. Phần thời gian báo cáo và kho giữ nguyên bản nháp.
**Phạm vi:** Hoàn tiền khi hủy/trả phòng sớm, sửa sai bút toán, hóa đơn khách vs sổ nội bộ, báo cáo doanh thu theo múi giờ, kiểm thử phân bổ kho theo lô.
**Không bao gồm:** Công nợ khách hàng, tích hợp cổng thanh toán, ngưỡng phê duyệt theo hạn mức (có thể thêm sau nếu vận hành cần), đính kèm tệp chứng cứ, thay đổi chính sách giá phòng.

## 1. Bối cảnh

Rà soát 14-08 phát hiện:

| Vấn đề | Hiện trạng | Hướng xử lý |
|---|---|---|
| Checkout đoàn tự tạo `Payment` refund khi `balance < 0` | `group_checkout_service.settle_group_checkout()` tự hoàn không ai quyết định | Bỏ auto-refund. Hoàn tiền luôn là hành động chủ động của người dùng qua form hoàn tiền (mục 3–4). |
| API hủy nhận `refund_percent` từ client không kiểm soát | Client gửi gì server ghi nấy, không trần, không lý do, không cơ sở tính | Giữ tinh thần "người nhập %", nhưng thêm cơ sở tính, trần cứng server-side, lý do bắt buộc và bút toán đảo (mục 3–4). |
| Báo cáo lọc `completed_bookings` theo `Booking.updated_at`, trộn UTC của DB với giờ ứng dụng | Sai số quanh biên ngày (sau 00:00 giờ VN booking có thể rơi về ngày trước) | Thêm `completed_at` + time service UTC/Bangkok (mục 7). |
| Test FEFO dùng hạn dùng hardcode đã qua | Đã sửa tạm 14-08 bằng ngày tương đối (commit `f919eaf`) | Hoàn thiện bằng clock inject được + regression bổ sung (mục 8). |

## 2. Mục tiêu

- Hoàn tiền do **con người nhập trực tiếp** (lễ tân hoặc admin — hai vai ngang quyền trong nghiệp vụ này), có cơ sở tính rõ ràng, không bao giờ vượt tiền đã thu.
- Nhập sai sửa được bằng **bút toán đảo**, không sửa/xóa lịch sử; sổ nội bộ giữ đủ mọi dòng, **hóa đơn khách chỉ hiển thị trạng thái ròng sạch sẽ**.
- Checkout/hủy thường không bao giờ tự sinh refund.
- Chuẩn hóa quy ước thời gian UTC + múi giờ nghiệp vụ (Asia/Bangkok) cho báo cáo tài chính.
- Kiểm thử FEFO xác định theo thời gian, bảo toàn invariant phân bổ/hoàn kho.

## 3. Chính sách hoàn tiền (biên bản đã chốt với chủ dự án, 14-08-2026)

1. **Ai nhập:** Lễ tân hoặc Admin, ngang quyền — cả nhập hoàn lẫn tạo bút toán đảo sửa sai. Chưa áp ngưỡng hạn mức (bổ sung sau nếu cần).
2. **Nhập gì:** phần trăm `%` kèm **cơ sở tính**, hoặc nhập thẳng số tiền:
   - Cơ sở A — **phần chưa sử dụng**: giá trị các đêm chưa ở (từ thời điểm rời đi, theo giá snapshot của booking) — khách chịu tiền đêm đã ở và dịch vụ đã gọi.
   - Cơ sở B — **toàn bộ hóa đơn**: tổng giá trị đơn — dùng cho thỏa thuận thiện chí.
3. **Ba lưới an toàn khi nhập:**
   - Form luôn hiển thị: *Đã thu · Giá trị phần chưa dùng · Tối đa còn hoàn được*.
   - Hộp xác nhận quy đổi ra tiền thật ("Hoàn 350.000đ (70% của 500.000đ)…") + **lý do bắt buộc**.
   - **Server chặn cứng:** `tiền hoàn ≤ tổng đã thu của booking − tổng đã hoàn trước đó` (tính cả các dòng đảo). UI cảnh báo là phụ; API tự vệ độc lập.
4. **Sửa sai — bút toán đảo:** không sửa/xóa dòng `Payment` nào. Dòng đảo (+) nối với dòng bị đảo qua khóa tham chiếu, kèm lý do; sau đó nhập dòng hoàn đúng. Ai cũng thấy trong sổ nội bộ và audit.
5. **Hai góc nhìn dữ liệu tiền:**
   - **Sổ nội bộ (sổ quỹ, audit, đối soát):** hiển thị đầy đủ mọi dòng kể cả cặp sai/đảo.
   - **Hóa đơn khách (billing in ra):** lọc bỏ các cặp hoàn/đảo đã triệt tiêu nhau, chỉ hiển thị các dòng còn hiệu lực — khách thấy một dòng hoàn đúng, không thấy vết sửa.
6. **Checkout không auto-refund:** khi cọc còn dư sau checkout, hệ thống hiển thị phần dư kèm lối tắt mở form hoàn tiền; việc hoàn là thao tác chủ động, có lưới an toàn như trên. Hủy thường mặc định hoàn 0đ; muốn hoàn thì nhập.

## 4. Thiết kế luồng hoàn tiền

### 4.1. Điểm vào

- Từ chi tiết booking / màn checkout / màn hủy: nút **"Hoàn tiền"** mở form (chỉ khả dụng khi booking có tiền đã thu chưa hoàn hết).
- Hủy phòng: form hủy bỏ trường `refund_percent`/`is_force_majeure` cũ; sau khi hủy, nếu có tiền đã thu, UI gợi ý mở form hoàn tiền.
- Checkout (lẻ/đoàn) có `balance < 0`: hoàn tất checkout bình thường, hiển thị "Còn X đ chưa hoàn cho khách" + nút mở form hoàn tiền. Không tự tạo Payment refund.

### 4.2. Form hoàn tiền

| Trường | Quy tắc |
|---|---|
| Cơ sở tính | Radio: "Phần chưa sử dụng" (mặc định, kèm số tiền máy tính) / "Toàn bộ hóa đơn" |
| % hoặc số tiền | Nhập một trong hai; bên còn lại tự quy đổi hiển thị |
| Thời điểm rời đi | Chỉ hiện khi phòng đang `checked_in` (trả sớm); mặc định = hiện tại; dùng để tính "phần chưa sử dụng" |
| Phương thức hoàn | `cash`, `banking`, `credit_card`, `qr_code`, `other` — bắt buộc |
| Lý do | Bắt buộc, tối thiểu có nội dung; lưu vào Payment.note ngắn gọn + audit đầy đủ |

Server tính lại mọi con số lúc submit (client chỉ gửi cơ sở, %, phương thức, lý do, thời điểm); từ chối khi vượt trần, booking đổi trạng thái, hoặc trùng operation (idempotency theo `BusinessOperation` hiện có). Không partial mutation.

### 4.3. Dữ liệu

- `Payment` thêm: `payment_type` giá trị mới `refund` (âm) và `refund_reversal` (dương), cột `reverses_payment_id` (FK nullable tự trỏ `payments.id`, duy nhất — một dòng chỉ bị đảo một lần).
- Snapshot tính toán (cơ sở, %, giá trị cơ sở, người nhập) lưu trong payload `AuditEvent` + `BusinessOperation`; không tạo bảng mới.
- Không migration dữ liệu cũ; các Payment refund lịch sử giữ nguyên.

### 4.4. Bút toán đảo

- Chỉ áp dụng cho dòng `refund` chưa bị đảo; tạo dòng `refund_reversal` cùng số tiền dương, `reverses_payment_id` trỏ dòng sai, lý do bắt buộc.
- Sổ quỹ tính cả hai dòng (tổng ròng đúng két). Billing khách lọc bỏ cặp `refund` + `refund_reversal` đã khớp.
- Audit event riêng: `create_refund`, `reverse_refund`.

## 5. Phân quyền

| Hành động | Staff | Admin | Master Admin trong tenant |
|---|---:|---:|---:|
| Nhập hoàn tiền (mọi cơ sở tính) | Có | Có | Có |
| Bút toán đảo sửa sai | Có | Có | Có |
| Xem sổ nội bộ đầy đủ (cả cặp sai/đảo) | Theo quyền sổ quỹ hiện hữu | Có | Theo policy sổ quỹ |

Endpoint hoàn tiền/đảo trả JSON `403` (không redirect) khi thiếu quyền; giữ tenant isolation như mọi API khác.

## 6. Giao diện

- Form theo pattern dashboard nội bộ: label liên kết, lỗi cạnh trường bằng `role="alert"`, primary action duy nhất, nút tối thiểu 44px, không cuộn ngang.
- Hộp xác nhận hiển thị số tiền + phương thức + khách; hành động tài chính tách biệt nút hủy bỏ, không phân biệt chỉ bằng màu.
- Billing in: mục "Hoàn tiền" chỉ các dòng còn hiệu lực; sổ quỹ nội bộ đánh dấu rõ cặp sai/đảo (badge chữ, không chỉ màu).
- Toast kết quả `aria-live="polite"`; đóng modal trả focus về trigger.

## 7. Quy ước thời gian cho tài chính và báo cáo

*(Giữ nguyên bản nháp 14-08 của phần này.)*

- Timestamp lưu UTC; cột `DateTime` legacy chưa timezone-aware lưu UTC-naive, helper gắn UTC khi đọc.
- Time service duy nhất: `utc_now()`, `business_now()`, `business_period_to_utc()`. `BUSINESS_TIMEZONE` mặc định `Asia/Bangkok`; chưa hỗ trợ timezone riêng từng hotel.
- Write path tài chính/trạng thái (Payment, BusinessOperation, Booking state transition, refund) dùng helper UTC, không gọi `datetime.now()` trực tiếp hoặc dựa clock của database.
- `Booking.updated_at` chỉ là mốc kỹ thuật, không dùng làm ngày hoàn tất/doanh thu.
- Thêm `Booking.completed_at` nullable; `booking_state_service` set khi chuyển `completed`. Migration backfill từ `MAX(booking_rooms.check_out_actual)`; thiếu mốc thì để `NULL` và báo qua reconciliation.
- `completed_bookings` lọc theo `completed_at` trong khoảng UTC của kỳ; kỳ `today/week/month/custom` chọn theo ngày Bangkok rồi đổi `[start_utc, end_utc)`.
- Nhãn ngày/chart chuyển UTC → ngày Bangkok trước khi gom nhóm; không dùng `func.date()` theo timezone của dialect.
- Giữ filter `hotel_id`, Expense void và quy tắc cash-in/cash-out hiện có. Báo cáo dòng tiền: cặp `refund`/`refund_reversal` tính đủ hai chiều để khớp két.

## 8. FEFO kho và kiểm thử xác định thời gian

*(Giữ nguyên bản nháp 14-08; ghi nhận fix tạm commit `f919eaf` ngày 14-08 đã đổi test sang ngày tương đối.)*

- Không đổi quy tắc FEFO của `batches_for_consumption()`.
- Thêm tham số `as_of_date`/clock inject được cho validate tồn, trừ tồn, chọn lô; production mặc định ngày nghiệp vụ hiện tại (qua time service mục 7).
- Sửa test FEFO cố định ngày tham chiếu qua clock inject thay vì phụ thuộc ngày chạy.
- Test bổ sung: lô quá hạn không bao giờ có consumption/allocation; lô không hạn đứng sau lô còn hạn; thiếu tồn không ghi partial movement/allocation.
- Giữ quy tắc hoàn kho theo `BookingServiceBatchAllocation` và invariant `InventoryItem.quantity` = tổng `quantity_available` các lô.

## 9. TDD và tiêu chí nghiệm thu

Mỗi hạng mục: test đỏ → triển khai tối thiểu → refactor → chạy test hạng mục → commit riêng (message tiếng Anh).

### 9.1. Hoàn tiền

1. Checkout (lẻ/đoàn) có `balance < 0` hoàn tất bình thường, **không** tạo Payment refund; response chứa số dư chưa hoàn.
2. Hủy thường không nhận `refund_percent`/`is_force_majeure` từ client; hoàn mặc định 0.
3. Nhập hoàn cơ sở A (phần chưa dùng): đúng công thức đêm chưa ở theo giá snapshot; cơ sở B: đúng % tổng hóa đơn.
4. Trần cứng: mọi request vượt `đã thu − đã hoàn` trả 4xx, không mutation; kể cả gọi API trực tiếp bỏ qua UI.
5. Thiếu lý do / thiếu phương thức → từ chối.
6. Bút toán đảo: chỉ đảo được dòng `refund` chưa bị đảo, đúng một lần; sổ quỹ ròng đúng; billing khách không hiển thị cặp đã triệt tiêu; audit `create_refund`/`reverse_refund` đầy đủ người + số liệu.
7. Idempotency: retry cùng operation không tạo refund/đảo trùng. Tenant khác không thấy/không tác động được (`403`/`404` nhất quán).
8. Staff và Admin có quyền như nhau trên toàn bộ luồng này.

### 9.2. Báo cáo thời gian

1. 00:30 Bangkok với timestamp UTC ngày trước vẫn đếm doanh thu/Payment/completed booking vào "hôm nay".
2. 23:30 Bangkok không lẫn sang ngày sau; chart dùng ngày Bangkok.
3. Booking hoàn tất rồi sửa metadata ngày khác chỉ đếm theo `completed_at`.
4. Backfill đúng max checkout actual; bản ghi thiếu mốc không xuất hiện sai trong report.
5. Tenant isolation và Expense void hiện có tiếp tục xanh.

### 9.3. Kho

1. Test FEFO chạy ở bất kỳ ngày nào (clock inject) vẫn lấy lô còn hạn gần nhất trước.
2. Lô quá hạn không bao giờ được xuất; lô không hạn chỉ lấy sau lô còn hạn.
3. Hoàn một phần trả đúng lô đã phân bổ; invariant tồn/lô/movement giữ đúng.

### 9.4. UI

- Test API/DOM: 3 con số ngữ cảnh hiển thị, xác nhận quy đổi tiền thật, validation lý do/phương thức, billing khách sạch vs sổ nội bộ đầy đủ.
- Trước bàn giao UI, kiểm desktop bằng `bb-browser`: luồng nhập hoàn, nhập sai → đảo → nhập lại, in bill, Escape/focus, console sạch, không tràn ngang.

## 10. Thứ tự triển khai

1. Test đỏ chặn auto-refund checkout + gỡ `refund_percent` khỏi hủy thường; commit riêng.
2. Migration `Payment.reverses_payment_id` + payment_type mới; service hoàn tiền (cơ sở tính, trần cứng, idempotency, audit); commit riêng.
3. Bút toán đảo + hai góc nhìn (billing lọc cặp triệt tiêu, sổ quỹ đầy đủ); commit riêng.
4. UI form hoàn tiền + điểm vào checkout/hủy, kiểm `bb-browser`; commit riêng.
5. Time service, `completed_at` + backfill, truy vấn báo cáo theo kỳ UTC; commit riêng.
6. FEFO clock inject + regression kho; commit riêng.
7. Full regression (cả `-m mysql`); migration kiểm từ DB trống và DB có dữ liệu.

## 11. Điều kiện hoàn tất

- Không còn đường code nào tự tạo refund; mọi refund có người nhập, lý do, phương thức, audit.
- Không refund nào vượt tiền đã thu, kể cả qua API trực tiếp.
- Nhập sai sửa bằng bút toán đảo; billing khách không lộ vết sửa; sổ nội bộ và két luôn khớp.
- Báo cáo nhất quán qua biên ngày Bangkok/UTC, dùng `completed_at`.
- FEFO kiểm thử xác định thời gian, không dùng lô hết hạn.
- Test hạng mục + full regression (369 + 12 mysql + test mới) xanh; UI kiểm bằng `bb-browser`.
