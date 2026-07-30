# Spec: Củng cố tính toàn vẹn nghiệp vụ, bảo mật và production

**Ngày:** 30-07-2026

**Trạng thái:** Chờ review

**Phạm vi:** Bảo mật web, cấu hình runtime, migration/schema đa tenant, báo cáo tài chính, checkout lẻ/đoàn, tính giá và tiền cọc, trạng thái booking, dời/hủy lịch, dịch vụ, tồn kho theo lô, accessibility và hiệu năng dashboard.

**Mức ưu tiên:** P0 cho Stored XSS, tính đúng tiền và cô lập tenant; P1 cho CSRF, migration/schema production, cấu hình fail-closed, giá, kho và phân quyền; P2 cho accessibility và hiệu năng truy vấn.

## 1. Quan hệ với các spec hiện có

Spec này kế thừa các quyết định còn phù hợp từ:

- `2026-07-26-business-operations-hardening-design.md`
- `2026-07-27-booking-reschedule-price-lock-design.md`
- `2026-07-29-inventory-batch-expiry-adjustment-design.md`

Các yêu cầu trong tài liệu này được ưu tiên khi có khác biệt ở các nội dung:

- Tenant scope của báo cáo tài chính.
- Idempotency và điều kiện trạng thái của checkout đoàn.
- Nguồn dữ liệu duy nhất cho báo giá, tiền cọc và quyết toán.
- Cách tính các đêm phát sinh khi khách ở quá ngày.
- Phân quyền dời lịch và hành vi kéo-thả Timeline.
- Tính bất biến của hóa đơn/dịch vụ sau checkout.
- Đồng bộ số lượng tổng với lô kho và hoàn đúng lô.
- Output encoding, CSRF và cấu hình production.
- Alembic, schema đa tenant và test trên database production.
- Accessibility của form/modal/action và query budget của dashboard phòng.

Spec không thay đổi quyết định hiện có rằng Staff được checkout thông thường, phòng đã check-in không được cancel trực tiếp, và dời lịch booking chưa check-in là thao tác của Admin.

## 2. Bối cảnh

Review trực tiếp code và các ca tái hiện độc lập cho thấy các nhóm lỗi sau:

| Nhóm | Hiện trạng | Tác động |
|---|---|---|
| Báo cáo | Một số tổng hợp không lọc `hotel_id`, vẫn tính Expense đã void | Lộ/sai số liệu giữa khách sạn, sai lợi nhuận |
| Checkout lẻ | Tin `amount` từ client; số tiền 0 vẫn checkout | Hoàn tất phòng khi chưa thu tiền, sai `payment_status` |
| Checkout đoàn | Nhận cả phòng `booked`; retry có thể ghi tổng booking về 0 | Checkout phòng chưa ở, mất tổng hóa đơn, ghi tiền lặp |
| Giá và cọc | API báo giá, validation cọc và engine quyết toán dùng công thức khác nhau | UI gợi ý sai, cọc sai tỷ lệ, khó đối soát |
| Ở quá ngày | Snapshot cũ không được mở rộng theo số đêm thực tế | Thiếu doanh thu đêm phát sinh |
| Kho | Vật tư mới từ chi phí được cộng số lượng hai lần | Tồn tổng khác tồn theo lô |
| Dịch vụ | Có thể sửa dòng dịch vụ sau checkout; thay danh sách làm mất liên kết lô | Hóa đơn đã chốt bị đổi, sai FEFO và lịch sử kho |
| Phân quyền | Staff gọi được API dời lịch; kéo Timeline có thể sửa giờ thực tế | Vượt quyền và thay đổi giá trị hóa đơn |
| Trạng thái | Booking cha, BookingRoom, Room và Payment có thể lệch nhau | Báo cáo/filter/luồng thao tác nhận sai trạng thái |
| Stored XSS | Dữ liệu khách hàng được ghép vào `innerHTML` và inline event handler | Payload lưu trong DB chạy trong phiên Staff/Admin |
| CSRF | Mutation form/API không yêu cầu CSRF token | Website khác có thể kích hoạt thao tác bằng phiên đăng nhập |
| Alembic | Có hai head độc lập `a6b0c4d8e1f3` và `c8d2e3f4a5b6` | Không thể chạy upgrade production theo quy trình chuẩn |
| Schema tenant | `rooms.room_number` unique toàn hệ thống trong migration nhưng model không có constraint | Database migration và `db.create_all()` cho hành vi khác nhau |
| Runtime production | Có secret/DB credential/mật khẩu seed mặc định và `debug=True` | Triển khai nhầm cấu hình yếu, tạo tài khoản dự đoán được |
| Accessibility | Label/input, modal close và icon-only action thiếu liên kết/tên truy cập | Người dùng keyboard/screen reader không thao tác tin cậy |
| Dashboard | Giá và room count phát sinh query theo từng phòng | Thời gian đáp ứng tăng tuyến tính theo số phòng |
| Test environment | Test chính dùng SQLite `create_all()`, bỏ qua Alembic/MySQL | Test xanh nhưng không phát hiện constraint, migration và row lock production |

### 2.1. Traceability của nhóm phát hiện kỹ thuật

| Phát hiện | Code/môi trường đã kiểm tra | Phần remediation |
|---|---|---|
| Stored XSS khách hàng | `controllers/customer_controller.py`, `static/js/customer.js` | 6.5, 17.1, 20.1 |
| Hai Alembic head | `migrations/versions/a6b0c4d8e1f3_add_booking_reschedules.py`, `migrations/versions/c8d2e3f4a5b6_add_expense_voiding.py` | 18.1, 20.2 |
| Unique số phòng sai tenant | `migrations/versions/569522b7e4f1_init.py`, `migrations/versions/a3471c834318_add_multi_tenant_support.py`, `models/room.py` | 18.2, 20.2 |
| Thiếu CSRF | `static/js/customer.js`, các form/mutation controller và `requirements.txt` | 17.2, 20.1 |
| Production không fail-closed | `config.py`, entrypoint trực tiếp trong `app.py` | 17.3, 20.2 |
| Accessibility | `templates/auth/login.html`, `templates/rooms/_booking_modal.html`, action trong `static/js/customer.js` | 15.5, 20.3 |
| N+1 dashboard | `services/pricing_service.py`, `controllers/room_controller.py` | 19, 20.3 |
| Test lệch production | `tests/conftest.py` dùng SQLite `create_all()` | 18.4, 20.2 |

## 3. Mục tiêu

1. Mọi số tiền hiển thị, xác nhận, ghi Payment và báo cáo đều được tính từ dữ liệu server trong đúng tenant.
2. Một thao tác checkout/hủy chỉ có thể tạo đúng một kết quả tài chính.
3. Không checkout phòng chưa check-in và không hoàn tất booking còn công nợ trong phạm vi chức năng hiện tại.
4. Báo giá, tỷ lệ cọc, snapshot và checkout dùng cùng một pricing service.
5. Tồn tổng, tồn theo lô, phân bổ dịch vụ và movement luôn đối soát được.
6. Mọi mutation trạng thái đi qua một state transition service có validation và audit.
7. UI giúp người vận hành nhận biết số cần thu/hoàn, trạng thái xử lý và cách phục hồi khi có xung đột.
8. Dữ liệu lưu từ người dùng luôn được render như text; mọi mutation cùng-origin được bảo vệ CSRF.
9. Production từ chối khởi động nếu thiếu secret/database config hoặc còn credential mặc định.
10. Alembic chỉ có một head và schema migration khớp constraint trong model.
11. Luồng chính dùng được bằng keyboard/screen reader và dashboard có số query không tăng theo số phòng.

## 4. Ngoài phạm vi

- Quản lý công nợ doanh nghiệp, trả chậm hoặc ghi nợ sau checkout.
- Tích hợp cổng thanh toán, hóa đơn điện tử hoặc phần mềm kế toán.
- Tự động thay đổi chính sách hoàn cọc theo thời gian.
- Đổi phòng cho khách đang check-in; luồng này cần một spec riêng về chuyển dịch vụ, cọc và lịch sử phòng.
- Tự động sửa số liệu tài chính lịch sử mà không có báo cáo đối soát và phê duyệt.
- Thiết kế lại toàn bộ giao diện hoặc thay framework frontend.
- Triển khai SSO, WAF hoặc hệ thống quản lý secret bên thứ ba.
- Tối ưu toàn bộ endpoint ngoài dashboard phòng và các truy vấn trực tiếp liên quan phát hiện N+1.

## 5. Quyết định nghiệp vụ đề xuất

Các quyết định dưới đây giúp spec khép kín và là mặc định đề xuất để review:

1. **Checkout thông thường phải tất toán đủ.** Nếu cần hỗ trợ công nợ, phải làm luồng riêng; không dùng `amount=0` để ngầm ghi nợ.
2. **Số tiền xác nhận checkout do server quyết định.** Client chỉ gửi lựa chọn VAT, phương thức thanh toán và reference của preview.
3. **Cọc dư được hoàn bằng Payment loại `refund`.** Không ghi số âm dưới loại `room_payment`.
4. **Phòng phải ở trạng thái `checked_in` mới được checkout.** Booking đoàn còn phòng `booked` phải bị chặn và trả danh sách phòng chưa nhận.
5. **Đêm ở quá phát sinh dùng đơn giá snapshot của đêm cuối gần nhất.** Mỗi đêm phát sinh tạo dòng breakdown nguồn `overstay_extension`; không dùng rule hiện hành để tránh giá thay đổi sau khi đặt.
6. **Booking hoàn tất khi mọi phòng là trạng thái kết thúc và có ít nhất một phòng `checked_out`.** Booking chỉ là `cancelled` khi tất cả phòng đều `cancelled`.
7. **Dịch vụ của phòng đã checkout là bất biến.** Sai sót sau checkout phải xử lý bằng chứng từ điều chỉnh riêng trong tương lai, không sửa trực tiếp dòng cũ.
8. **Expense đã void không tham gia P&L hoặc sổ quỹ.** Lô kho liên quan vẫn giữ nguyên theo quyết định đã chốt; điều chỉnh kho là chứng từ riêng.

## 6. Invariant toàn hệ thống

### 6.1. Tenant

- Mọi truy vấn model có `hotel_id` phải có điều kiện `hotel_id == g.hotel_id`, kể cả aggregate, subquery, join, biểu đồ và top-N.
- Không dựa vào việc ID là duy nhất toàn database để coi truy vấn đã tenant-safe.
- Mọi service tài chính/kho nhận `hotel_id` tường minh hoặc lấy từ entity đã được tenant-scope; không nhận ID trần rồi dùng `Model.query`.
- API ngoài tenant trả `404`, không trả tổng hợp có lẫn dữ liệu tenant khác.

### 6.2. Tiền

- Dùng `Decimal` hoặc số tiền nguyên theo một quy ước duy nhất từ pricing đến Payment; không dùng `float` cho quyết định cuối cùng.
- Với một booking:

```text
gross_amount = tổng final_amount của toàn bộ BookingRoom
net_paid = tổng Payment.amount, bao gồm refund âm
balance_due = gross_amount - net_paid
```

- `payment_status` được suy ra bằng một helper duy nhất:
  - `unpaid`: chưa có thực thu và còn phải thu.
  - `partial`: đã có thực thu nhưng còn số dư phải thu.
  - `paid`: `balance_due == 0`.
  - `refunded`: booking bị hủy/điều chỉnh và toàn bộ số cần hoàn đã hoàn.
- Không gán `paid` chỉ vì endpoint checkout đã chạy.
- `Booking.total_amount` luôn bằng tổng `BookingRoom.final_amount` sau mọi mutation finalize; không chỉ bằng các phòng vừa xử lý.

### 6.3. Trạng thái

Các trạng thái BookingRoom hợp lệ:

```text
booked -> checked_in -> checked_out
booked -> cancelled
```

Không cho:

```text
booked -> checked_out
checked_in -> cancelled
checked_out/cancelled -> trạng thái active
```

Trạng thái Booking cha được tính lại sau mỗi mutation phòng:

| Trạng thái các phòng | Booking cha |
|---|---|
| Có ít nhất một `checked_in` | `checked_in` |
| Không có `checked_in`, còn `booked` | `confirmed` |
| Tất cả `cancelled` | `cancelled` |
| Tất cả kết thúc và có ít nhất một `checked_out` | `completed` |

Room vật lý:

- `occupied` chỉ khi có đúng một BookingRoom `checked_in`.
- `available` sau checkout/cancel nếu không có BookingRoom `checked_in` khác.
- `maintenance` không được check-in, dời lịch tới hoặc đổi phòng tới.
- `dirty` không được check-in cho đến khi hoàn tất dọn phòng.

### 6.4. Transaction và idempotency

- Checkout lẻ, checkout đoàn, cancel/refund, nhập kho và sửa dịch vụ + tồn phải chạy trong một transaction.
- Tạo `BusinessOperation` trước mutation tiền, với operation key có namespace entity:

```text
checkout:booking_room:{booking_room_id}
checkout_group:booking:{booking_id}
cancel:booking_room:{booking_room_id}
cancel:booking:{booking_id}
```

- Không dùng chung `cancel:{id}` cho hai loại entity.
- Lock Booking/BookingRoom/Room theo thứ tự ID ổn định trước khi kiểm tra trạng thái và tính tiền.
- Retry operation đã `completed` trả `409` cùng `operation_key` và snapshot kết quả; không ghi Payment, audit hoặc tổng tiền lần nữa.
- Operation đang `processing` trả `409` với thông báo thao tác đang được xử lý.

### 6.5. Dữ liệu không tin cậy và request mutation

- Mọi dữ liệu từ request, database, email import hoặc QR đều được coi là không tin cậy khi render.
- Dữ liệu text phải đi qua cơ chế output encoding theo context; validation độ dài/định dạng không thay thế output encoding.
- Không ghép dữ liệu không tin cậy vào `innerHTML`, HTML attribute, inline JavaScript hoặc inline event handler.
- Mọi request `POST`, `PUT`, `PATCH`, `DELETE` dùng session cookie phải có CSRF token hợp lệ.
- `GET` và `HEAD` không được làm thay đổi dữ liệu.
- CSRF không được coi là biện pháp chống XSS; hai lớp bảo vệ phải được triển khai và test độc lập.

## 7. Thiết kế dữ liệu

### 7.1. Liên kết Payment với operation

Bổ sung vào `payments`:

| Trường | Ý nghĩa |
|---|---|
| `business_operation_id` | Operation sinh Payment |
| `component_key` | Thành phần duy nhất trong operation, ví dụ `room`, `service`, `tax:room:12`, `refund` |

Ràng buộc duy nhất:

```text
(hotel_id, business_operation_id, component_key)
```

Ràng buộc cho phép một operation tạo nhiều Payment cấu phần nhưng không tạo trùng cùng cấu phần khi retry.

### 7.2. Snapshot kết quả operation

Bổ sung `result_snapshot` JSON nullable cho `business_operations`, tối thiểu gồm:

- `booking_id`, `booking_room_ids`
- `gross_amount`
- `deposit_applied`
- `tax_amount`
- `amount_collected`
- `amount_refunded`
- `balance_due`
- trạng thái booking/phòng sau xử lý

Snapshot chỉ phục vụ idempotency/audit; nguồn sự thật kế toán vẫn là BookingRoom và Payment.

### 7.3. Dữ liệu dịch vụ và lô

- Không xóa cứng `BookingService` đã có allocation hoặc movement.
- Khi số lượng giảm về 0, giữ dòng với `quantity=0`; UI ẩn khỏi hóa đơn hoạt động nhưng lịch sử vẫn truy vết được.
- Foreign key từ allocation/movement đến BookingService dùng `RESTRICT`, không cascade xóa lịch sử.
- Mọi lượng hoàn kho phải tham chiếu allocation gốc và batch cụ thể.

## 8. Pricing service thống nhất

### 8.1. Một nguồn tính giá

Tạo một service trả `PriceQuote` dùng chung cho:

- API tính giá nhanh.
- Validation tỷ lệ cọc.
- Tạo snapshot booking lẻ/đoàn.
- Preview checkout.
- Checkout lẻ/đoàn.
- So sánh giá khi dời lịch.

`PriceQuote` tối thiểu:

```text
rental_type
check_in
check_out
line_items[]
room_amount
deposit_options: [50%, 100%]
pricing_version
quote_hash
```

Mỗi line thuê ngày có `business_date`, `amount`, `source`, `rule_name`. Thuê giờ có block đầu, giờ tiếp theo, giá trần qua đêm và số giờ tính tiền.

### 8.2. Tiền cọc

- 50%/100% được tính từ `PriceQuote.room_amount`, không tính lại bằng helper khác.
- Booking đoàn cộng tổng snapshot thật của từng phòng rồi mới tính lựa chọn cọc.
- Phân bổ cọc theo tổng snapshot của từng BookingRoom, không theo `price_per_night` cơ bản.
- Tổng phân bổ phải bằng đúng cọc booking sau làm tròn; chênh lệch làm tròn dồn vào phòng cuối theo thứ tự ổn định.

### 8.3. Ở quá ngày

Đối với thuê ngày:

1. Giữ nguyên toàn bộ line snapshot đã chốt cho khoảng đặt ban đầu.
2. Nếu ngày checkout thực tế tạo thêm đêm billable, thêm line cho từng đêm phát sinh.
3. Đơn giá line phát sinh bằng giá snapshot của đêm cuối gần nhất.
4. Line có `source=overstay_extension` và lưu ngày nghiệp vụ thực tế.
5. Sau khi cộng đêm phát sinh mới tính phụ thu checkout muộn trong ngày cuối, tránh vừa tính thêm đêm vừa phạt trùng cùng khoảng thời gian.

Ví dụ:

```text
Đặt: 01/08 14:00 -> 02/08 12:00, snapshot 500.000đ
Thực tế: checkout 03/08 12:00

Đêm 01/08: 500.000đ (snapshot)
Đêm 02/08: 500.000đ (overstay_extension)
Tổng tiền phòng: 1.000.000đ
```

### 8.4. Quote chống stale

- Preview trả `quote_hash` cùng thời điểm tính.
- Confirm checkout gửi lại `quote_hash`.
- Server luôn tính lại trong transaction. Nếu breakdown/số tiền thay đổi, trả `409 code=quote_changed` kèm quote mới; không mutation.
- Client không gửi `amount` như nguồn quyết định. Nếu vẫn nhận trường cũ trong giai đoạn tương thích, server bỏ qua giá trị đó.

## 9. Checkout lẻ

### 9.1. Điều kiện

- BookingRoom thuộc tenant hiện tại.
- Trạng thái đúng `checked_in`.
- Room không có BookingRoom `checked_in` khác.
- Có ít nhất một preview hợp lệ hoặc server tạo preview mới trong transaction.

### 9.2. Trình tự

1. Lock Booking, BookingRoom và Room.
2. Tạo/kiểm tra `BusinessOperation`.
3. Tính lại quote, dịch vụ, VAT, tổng hóa đơn, Payment đã có và số dư.
4. Nếu quote thay đổi so với client, trả `409`, rollback.
5. Nếu `balance_due > 0`, tạo Payment đúng số tiền cần thu theo phương thức người dùng chọn.
6. Nếu `balance_due < 0`, chỉ tiếp tục qua nhánh hoàn tiền có lý do và capability phù hợp; tạo Payment `refund`.
7. Ghi `BookingRoom.final_amount`, `checked_out`, `check_out_actual`.
8. Tính lại `Booking.total_amount`, `payment_status`, trạng thái Booking cha và Room.
9. Hoàn tất operation, lưu snapshot kết quả và audit trong cùng transaction.

### 9.3. Không hỗ trợ

- Không cho nhập số thực thu thấp hơn số phải thu rồi vẫn checkout.
- Không ghi Payment số âm loại `room_payment`.
- Không tự chuyển BookingRoom `booked` thành `checked_in` trong preview/checkout. Dữ liệu lệch trạng thái phải có công cụ reconciliation riêng.

## 10. Checkout đoàn

### 10.1. Điều kiện

- Có ít nhất một BookingRoom `checked_in`.
- Không còn BookingRoom `booked`. Nếu còn, trả `409 code=rooms_not_checked_in` và danh sách số phòng.
- Không xử lý lại BookingRoom đã `checked_out` hoặc `cancelled`.
- Có operation key `checkout_group:booking:{booking_id}`.

### 10.2. Trình tự

1. Lock Booking và toàn bộ BookingRoom theo ID tăng dần.
2. Kiểm tra operation và state trước khi tính tiền.
3. Tính quote cho từng phòng `checked_in`; dịch vụ chỉ lấy đúng room_id.
4. Tính VAT, áp cọc còn lại và số dư phải thu/hoàn.
5. Ghi `final_amount` cho từng phòng vừa checkout.
6. Tạo Payment với component key ổn định.
7. Tính lại `Booking.total_amount` từ **toàn bộ** BookingRoom, gồm phòng đã checkout/hủy trước đó.
8. Tính lại trạng thái và `payment_status`; lưu result snapshot.

Nếu không có phòng `checked_in`, endpoint trả `409`, không được ghi `total_amount=0`, không đổi trạng thái và không tạo audit thành công.

## 11. Hủy booking/phòng

- Operation key phân biệt Booking và BookingRoom.
- Chỉ hủy BookingRoom `booked`.
- Refund tính từ cọc đã phân bổ theo snapshot thật của phòng.
- Sau hủy, tính lại `prepaid_amount`, `total_amount`, `payment_status` và trạng thái Booking cha bằng helper chung.
- Booking có phòng đã checkout và các phòng còn lại cancelled phải là `completed`, không giữ `confirmed/checked_in`.
- Retry cùng entity trả `409` reference cũ; hủy booking ID trùng BookingRoom ID khác không được va operation key.

## 12. Dời lịch và Timeline

### 12.1. Quyền

- Chỉ Hotel Admin hoặc Master Admin trong tenant context có capability `booking.reschedule`.
- Cả API availability và confirm đều kiểm tra capability ở backend.
- Staff gọi trực tiếp nhận JSON `403`, không mutation và không audit thành công.

### 12.2. Hợp nhất đường mutation

- `update_timeline` không được thay phòng/lịch của BookingRoom `booked` trực tiếp.
- Kéo-thả hoặc resize booking `booked` chỉ mở modal Dời lịch; confirm gọi service reschedule duy nhất.
- Không cho sửa `check_in_actual` của phòng đang ở qua Timeline.
- Đổi phòng cho khách đang check-in bị chặn cho đến khi có spec riêng.
- Reschedule service luôn kiểm tra trạng thái `booked`, phòng bảo trì, overlap, lý do, price mode và tenant.

## 13. Dịch vụ và tồn kho

### 13.1. Khóa theo trạng thái

- Thêm/gọi/sửa/giảm dịch vụ chỉ hợp lệ khi BookingRoom tương ứng là `checked_in`.
- API bắt buộc nhận `booking_room_id`; không suy luận chỉ từ `booking_id + service_id` khi booking có nhiều phòng.
- Phòng `checked_out/cancelled` trả `409 service_bill_finalized`.

### 13.2. Cập nhật theo delta

- Không bulk delete toàn bộ BookingService.
- Cập nhật dòng hiện hữu theo `booking_room_id/room_id + service_id`.
- Dòng mới: validate toàn bộ tồn trước, tạo BookingService, flush, rồi trừ kho và lưu allocation.
- Tăng quantity: phân bổ thêm theo FEFO.
- Giảm quantity: hoàn theo thứ tự ngược allocation gốc vào đúng batch.
- Quantity về 0: giữ BookingService và lịch sử, hoàn hết allocation còn lại.
- Mỗi lượng trừ/hoàn đều có InventoryMovement; không có nhánh tăng batch/item mà thiếu movement.

### 13.3. Invariant kho

Sau mỗi transaction:

```text
InventoryItem.quantity
= tổng InventoryBatch.quantity_available của vật tư
```

Tổng trên vẫn bao gồm hàng quá hạn chưa được hủy vật lý, đúng với spec kho hiện hành. Tồn **dùng được** cho gọi dịch vụ chỉ gồm batch active và chưa hết hạn.

Khi tạo vật tư mới từ chi phí:

1. Khởi tạo `InventoryItem.quantity = 0`.
2. Tạo đúng một receipt batch.
3. `create_receipt_batch()` là nơi duy nhất tăng tồn tổng và tạo movement.

## 14. Báo cáo và sổ quỹ

### 14.1. Nguồn dữ liệu

| Chỉ số | Nguồn và thời gian |
|---|---|
| Doanh thu hóa đơn | Tổng `BookingRoom.final_amount` đã finalize trong tenant, theo `check_out_actual`/thời điểm hủy |
| Thực thu/hoàn | `Payment.amount` trong tenant, theo `Payment.created_at` |
| Chi phí P&L | Expense trong tenant, `is_voided=False`, theo `expense_date` |
| Sổ quỹ | Payment và Expense hợp lệ trong tenant, theo thời điểm ghi nhận tiền |
| Lợi nhuận | Doanh thu hóa đơn trừ Expense hợp lệ cùng kỳ |

- Không dùng raw `db.session.query(Model)` cho aggregate nếu thiếu filter tenant tường minh.
- Top phòng join `BookingRoom.room_id == Room.id` và lọc cả BookingRoom/Room theo tenant.
- Booking active không tính vào doanh thu finalize.
- Expense void vẫn xem được trong lịch sử/audit nhưng không vào tổng, chart hoặc sổ quỹ.

### 14.2. Tỷ lệ lấp đầy

- Khoảng báo cáo dùng `[start_date 00:00, end_date + 1 ngày 00:00)`.
- Số ngày mẫu số là số ngày lịch thực tế trong khoảng, bao gồm cả ngày bắt đầu và kết thúc mà người dùng chọn.
- Mỗi phòng chỉ đóng góp tối đa một room-night cho một ngày.
- Booking phải overlap ngày đó mới được tính; không dựa riêng vào trạng thái hiện tại.
- Không chia theo `(end - start).days` trong khi vòng lặp lại bao gồm cả hai đầu.

## 15. UI/UX vận hành

Thiết kế giữ Bootstrap/JavaScript hiện tại và design system của dự án. Không thêm framework mới.

### 15.1. Checkout

- Số tiền cần thu là trường chỉ đọc, lấy từ server; không dùng input ẩn có thể bị sửa làm nguồn quyết định.
- Hiển thị rõ: tiền phòng, dịch vụ, VAT, cọc/Payment đã thu, còn phải thu hoặc cần hoàn.
- Người dùng chỉ chọn phương thức thanh toán và VAT.
- Nếu cần hoàn, form hiện trường lý do bắt buộc và nhãn `Số tiền cần hoàn`; không hiển thị như số phải thu âm.
- Nút xác nhận bị khóa khi request đang chạy, có spinner và text `Đang xử lý`; double-click không gửi thêm request.
- Lỗi `quote_changed` hiển thị breakdown mới và CTA `Xem lại số tiền`, không âm thầm tiếp tục.
- Lỗi đặt ngay dưới phần liên quan và có `role="alert"` hoặc `aria-live`.
- Thành công hiển thị operation reference để đối soát.

### 15.2. Checkout đoàn

- Modal phân nhóm `Đang ở`, `Chưa nhận`, `Đã trả`, `Đã hủy`.
- Khi còn phòng `Chưa nhận`, nút checkout đoàn bị khóa và nêu rõ các phòng cần check-in/hủy trước.
- Tổng tiền của phòng đã finalize vẫn hiển thị trong tổng booking nhưng không bị tính/thu lại.
- Retry/xung đột hiển thị trạng thái giao dịch trước và CTA tải lại; không chỉ báo lỗi chung.

### 15.3. Dời lịch

- Nút/menu Dời lịch chỉ hiển thị khi user có capability và booking `booked`.
- Kéo-thả không tự lưu; modal luôn yêu cầu kiểm tra phòng trống, price mode và lý do.
- Không hiển thị thao tác sửa giờ thực tế cho Staff.

### 15.4. Báo cáo

- Mỗi KPI luôn có số dạng text; biểu đồ không là nguồn duy nhất.
- Màu doanh thu/chi phí/refund có nhãn hoặc legend, không chỉ phân biệt bằng màu.
- Có trạng thái loading, empty và lỗi; lỗi nêu cách thử lại.
- Bộ lọc hiển thị rõ khoảng ngày đang áp dụng và timezone khách sạn.
- Bảng chi tiết hoặc dữ liệu số phải truy cập được bằng bàn phím; tooltip không chứa thông tin duy nhất chỉ xuất hiện khi hover.

### 15.5. Accessibility nền tảng

Áp dụng tối thiểu cho trang đăng nhập, danh sách/form khách hàng, modal đặt phòng, checkout và dời lịch:

- Mỗi input có label nhìn thấy được và liên kết bằng `for`/`id`; placeholder không phải label duy nhất.
- Nút chỉ có icon phải có accessible name cụ thể, ví dụ `Sửa khách Nguyễn Văn A`, `Xóa khách Nguyễn Văn A`, `Đóng modal đặt phòng`.
- Nút đóng modal có `aria-label`; tiêu đề modal được nối bằng `aria-labelledby`.
- Thứ tự Tab theo thứ tự thị giác; mọi action dùng được bằng keyboard và có focus indicator nhìn thấy rõ.
- Khi mở modal, focus vào tiêu đề hoặc trường đầu tiên hợp lệ; khi đóng, focus trở về control đã mở modal.
- Không có keyboard trap ngoài cơ chế giữ focus hợp lệ của modal; phím Escape đóng được modal khi thao tác không bắt buộc phải hoàn tất.
- Lỗi form hiển thị cạnh trường, dùng `aria-describedby` và vùng `role="alert"`/`aria-live`; sau submit lỗi, focus chuyển tới trường lỗi đầu tiên.
- Trạng thái không chỉ truyền đạt bằng màu; luôn có text/icon bổ sung.
- Vùng bấm của action chính và icon button đạt tối thiểu 44×44 px khi hiển thị ở viewport cảm ứng.
- Button async bị disable trong khi xử lý và có text trạng thái, không chỉ spinner.

### 15.6. Kiểm tra UI bắt buộc

Sau implementation, dùng `bb-browser` ở desktop phù hợp để kiểm tra:

- Checkout lẻ đủ tiền, cọc dư cần hoàn và quote thay đổi.
- Checkout đoàn còn phòng booked, checkout thành công và retry.
- Staff/Admin nhìn thấy đúng action dời lịch.
- Báo cáo tenant A không hiển thị dữ liệu tenant B, Expense void không vào tổng.
- Payload XSS lưu trong name/phone/email/address hiển thị như text và không thực thi.
- Trang đăng nhập, modal đặt phòng và action khách hàng có accessible name, focus order và keyboard operation đúng.
- Không có lỗi console trong các luồng trên.

## 16. API contract dự kiến

### 16.1. Preview checkout

`POST /<hotel_slug>/bookings/api/rooms/preview_checkout`

Input:

```json
{
  "booking_room_id": 12,
  "include_tax": true
}
```

Output chính:

```json
{
  "success": true,
  "quote_hash": "...",
  "gross_amount": 1080000,
  "net_paid": 500000,
  "balance_due": 580000,
  "amount_to_refund": 0,
  "line_items": []
}
```

### 16.2. Confirm checkout

`POST /<hotel_slug>/bookings/api/rooms/checkout`

Input:

```json
{
  "booking_room_id": 12,
  "include_tax": true,
  "payment_method": "cash",
  "quote_hash": "..."
}
```

Không nhận `amount` như dữ liệu quyết định.

### 16.3. Mã lỗi nghiệp vụ

| HTTP | `code` | Trường hợp |
|---:|---|---|
| 400 | `invalid_request` | Dữ liệu đầu vào sai |
| 403 | `forbidden_capability` | Thiếu quyền |
| 404 | `entity_not_found` | Không tồn tại/ngoài tenant |
| 409 | `invalid_state_transition` | Sai trạng thái |
| 409 | `quote_changed` | Số tiền thay đổi sau preview |
| 409 | `operation_in_progress` | Request cạnh tranh đang xử lý |
| 409 | `operation_completed` | Retry operation đã xong |
| 409 | `rooms_not_checked_in` | Checkout đoàn còn phòng booked |
| 409 | `service_bill_finalized` | Sửa dịch vụ sau finalize |

## 17. Bảo mật web và cấu hình production

### 17.1. Loại bỏ Stored XSS

Phạm vi đầu tiên là dữ liệu khách hàng `name`, `phone`, `cccd`, `email`, `address`; quy tắc tương tự áp dụng cho mọi dữ liệu người dùng khác khi render.

Backend:

- Chuẩn hóa kiểu, trim và giới hạn độ dài theo model/API contract; lưu giá trị như plain text.
- Không “lọc chuỗi nguy hiểm” bằng blacklist tag/event; blacklist không phải biện pháp chống XSS.
- JSON trả dữ liệu text bình thường. Output encoding phải diễn ra tại đúng render context.
- Template Jinja giữ autoescape; không dùng `|safe` cho dữ liệu người dùng nếu chưa có allowlist sanitizer được duyệt.

Frontend:

- Tạo row/cell/button bằng DOM API; gán dữ liệu bằng `textContent`, `.value`, `.title` hoặc property an toàn.
- Không đưa dữ liệu khách hàng vào `innerHTML`, template HTML string, inline `onclick`, `javascript:` URL hoặc chuỗi code.
- ID được parse thành số và gắn qua `dataset`; action dùng `addEventListener`.
- Static HTML cố định như empty state được phép dùng template, nhưng không được trộn dữ liệu không tin cậy.
- Không dùng client-side sanitizer như lớp bảo vệ duy nhất. Nếu tương lai có rich text hợp lệ, phải dùng allowlist sanitizer đã được duyệt và có test riêng.

Defense in depth:

- Loại bỏ inline script/event handler ở các luồng thay đổi trước khi bật CSP chặt.
- Triển khai `Content-Security-Policy-Report-Only` để thu thập vi phạm; chỉ chuyển sang enforce sau khi inventory inline script/style đã được xử lý.
- Mục tiêu CSP script cuối cùng không cần `'unsafe-inline'`.

### 17.2. CSRF protection

- Thêm giải pháp CSRF toàn cục cho Flask, ưu tiên `Flask-WTF/CSRFProtect` để dùng chung cho form và JSON API.
- Base template phát token cho JavaScript qua meta tag hoặc bootstrap data không chứa secret khác.
- Fetch wrapper dùng chung tự thêm header `X-CSRFToken` cho `POST`, `PUT`, `PATCH`, `DELETE`.
- Form HTML gửi hidden CSRF field; login và các form trước đăng nhập cũng được bảo vệ.
- API CSRF failure trả JSON `400 code=csrf_failed`; request HTML render trang lỗi phù hợp.
- Không exemption endpoint mutation nội bộ. Exemption tương lai chỉ dành cho webhook có cơ chế xác thực chữ ký riêng và phải được document.
- Token thiếu, sai, hết hạn hoặc thuộc session khác đều không được mutation.
- Cấu hình cookie production: `HttpOnly`, `Secure`, `SameSite=Lax` hoặc chặt hơn nếu luồng đăng nhập cho phép.

### 17.3. Cấu hình fail-closed và startup

Tách cấu hình rõ ràng:

- `DevelopmentConfig`: được dùng default local không nhạy cảm nhưng phải hiển thị rõ là development.
- `TestingConfig`: database/test secret truyền tường minh từ fixture.
- `ProductionConfig`: bắt buộc `SECRET_KEY`, `DATABASE_URL` và mọi credential thực sự cần cho tính năng bật.

Production phải từ chối khởi động nếu:

- Thiếu biến bắt buộc.
- `SECRET_KEY` trùng giá trị mẫu/độ dài không đạt quy ước.
- Database URL chứa credential mặc định đã biết như `root:123456`.
- `DEBUG` hoặc testing mode đang bật.

Startup production:

- Không gọi `db.create_all()`, `ensure_schema_updates()` hoặc backfill ad-hoc.
- Không tự tạo `admin/admin123`, `staff1/staff123` hoặc tài khoản mặc định khác.
- Không tự chạy migration khi web worker khởi động.
- Seed development chuyển thành CLI command tường minh; password phải truyền qua option/env hoặc được sinh ngẫu nhiên, không có giá trị mặc định đã biết.
- Backfill/reconciliation là CLI command riêng có dry-run.
- `app.run(debug=True)` chỉ tồn tại trong entrypoint development và không là đường chạy production.
- Log không in secret, password, database credential hoặc CSRF token.

Security headers production tối thiểu:

- `Content-Security-Policy` theo rollout nêu trên.
- `X-Content-Type-Options: nosniff`.
- `Referrer-Policy` phù hợp dữ liệu nội bộ.
- `frame-ancestors 'self'` hoặc `'none'` trong CSP nếu không có yêu cầu embed.

## 18. Schema, Alembic và kiểm thử production

### 18.1. Hợp nhất Alembic head

Hiện có hai head:

```text
a6b0c4d8e1f3
c8d2e3f4a5b6
```

Tạo một merge revision:

- `down_revision = ('a6b0c4d8e1f3', 'c8d2e3f4a5b6')`.
- Merge revision chỉ hợp nhất graph, không tự ý thay schema.
- Mọi migration remediation tiếp theo phải `down_revision` từ merge revision này.
- `flask db heads` sau thay đổi trả đúng một head.
- Kiểm thử upgrade từ database trống, database ở từng head cũ và database production snapshot đã ẩn dữ liệu nhạy cảm.

### 18.2. Constraint phòng theo tenant

Quy tắc:

```text
UNIQUE (hotel_id, room_number)
```

Model và migration phải cùng khai báo một tên constraint ổn định, ví dụ `_hotel_room_number_uc`.

Migration remediation:

1. Preflight tìm duplicate `(hotel_id, room_number)` và dừng với báo cáo rõ nếu có; không tự đổi số phòng.
2. Xác định đúng tên global unique/index hiện có bằng schema inspector theo dialect.
3. Drop unique toàn hệ thống trên `room_number`.
4. Tạo unique `(hotel_id, room_number)`.
5. Downgrade chỉ thực hiện nếu dữ liệu hiện tại vẫn thỏa unique toàn hệ thống; nếu không, dừng an toàn và yêu cầu xử lý dữ liệu.

Tiêu chí:

- Hai khách sạn được phép cùng có phòng `101`.
- Một khách sạn không tạo được hai phòng `101`.
- Hành vi giống nhau giữa schema tạo bằng Alembic và metadata model.

### 18.3. Migration nghiệp vụ của spec

Sau merge/schema tenant mới triển khai:

- Liên kết Payment–BusinessOperation và component key.
- `result_snapshot` cho BusinessOperation.
- Index/ràng buộc unique cần thiết.
- Foreign key lịch sử kho dùng `RESTRICT`.
- Không tạo thêm branch migration; CI từ chối khi có nhiều hơn một head.

### 18.4. Ma trận test database

Giữ SQLite `create_all()` cho unit test nhanh, nhưng không dùng nó làm bằng chứng production.

CI có ba tầng:

1. **Unit/functional nhanh:** SQLite in-memory, test service/controller không phụ thuộc dialect.
2. **Migration/schema:** tạo database trống bằng Alembic, upgrade tới head, kiểm tra constraint/index/column bằng inspector và smoke downgrade/upgrade.
3. **MySQL integration:** chạy trên cùng major version production để kiểm tra foreign key, Decimal, unique tenant, transaction, `with_for_update()` và request cạnh tranh.

Các test migration tối thiểu:

- `flask db heads` có một head.
- Upgrade từ base đến head thành công.
- Upgrade từ từng head cũ qua merge thành công.
- Schema sau upgrade khớp các constraint quan trọng trong model.
- App chạy CRUD/checkout smoke trên database đã migrate, không gọi `db.create_all()`.
- Hai transaction cạnh tranh booking/checkout chỉ có một kết quả hợp lệ.

### 18.5. Công cụ reconciliation

Tạo command read-only/dry-run để báo cáo:

- Booking `total_amount` khác tổng BookingRoom.
- Booking `payment_status` khác trạng thái suy ra từ Payment.
- Booking cha lệch trạng thái các phòng.
- Phòng `occupied` không có đúng một BookingRoom checked-in.
- InventoryItem.quantity khác tổng batch.
- Payment/Expense/BookingRoom thiếu hoặc sai tenant liên kết.
- Room duplicate trong cùng tenant hoặc constraint thực tế không đúng.

Không tự sửa dữ liệu tài chính. Chế độ apply phải là command riêng, xuất log trước/sau và chỉ chạy sau khi Admin phê duyệt báo cáo dry-run.

## 19. Hiệu năng dashboard phòng

### 19.1. Query bulk

- Không gọi `get_effective_room_prices()` theo cách phát sinh một query PriceRule cho mỗi Room.
- Tạo helper bulk lấy candidate PriceRule một lần theo `hotel_id`, tập `room_type` và ngày hiệu lực; chọn priority trong memory bằng cùng rule engine.
- Kết quả bulk phải giống helper đơn cho mọi loại phòng/rule và không cache chéo tenant.
- Room count theo booking được lấy bằng một aggregate query `GROUP BY booking_id` cho toàn bộ booking active, không `.count()` trong vòng lặp phòng.

### 19.2. Query budget

Mục tiêu endpoint sơ đồ phòng:

```text
1 query Rooms
1 query active BookingRoom + joined Booking/Customer
1 query upcoming BookingRoom + joined Booking/Customer
1 query candidate PriceRule
1 query BookingRoom count theo booking
```

Tổng mục tiêu tối đa 5 SQL statements cho dữ liệu hiện tại, không tăng khi số phòng tăng từ 4 lên 40. Nếu implementation cần thêm một query cố định có lý do, query budget mới phải được ghi trong test và review trước.

- Dùng SQLAlchemy event trong test để đếm statement.
- So sánh payload và giá trước/sau tối ưu để tránh đổi nghiệp vụ.
- Chỉ thêm index sau khi có query plan/đo đạc chứng minh; không thêm index phỏng đoán.

## 20. TDD và tiêu chí nghiệm thu

Mỗi hạng mục triển khai theo test đỏ → code tối thiểu → refactor → test xanh → commit riêng.

### 20.1. XSS và CSRF

- Lưu payload trong từng trường customer, tải danh sách và xác nhận payload hiển thị như text.
- Browser test dùng cờ sentinel xác nhận `onerror`, `<script>`, quote breakout và inline handler không thực thi.
- Customer row không chứa inline event handler sinh từ dữ liệu.
- Request mutation thiếu/sai CSRF token bị từ chối và database không đổi.
- Request có token hợp lệ tiếp tục hoạt động cho form HTML và JSON fetch.
- Có test xác nhận CSRF token của session A không dùng được cho session B.
- CSP report-only không có vi phạm từ các luồng đã chuyển khỏi inline handler trước khi bật enforce.

### 20.2. Production config, migration và schema

- Production thiếu `SECRET_KEY` hoặc `DATABASE_URL` phải fail startup với thông báo không lộ secret.
- Production từ chối secret/DB credential mặc định và debug mode.
- Startup không tạo bảng, user hoặc chạy backfill.
- CLI seed development yêu cầu password an toàn hoặc sinh password ngẫu nhiên.
- Alembic chỉ có một head và upgrade các điểm xuất phát đã nêu đều thành công.
- Database migrate cho phép A/101 và B/101 nhưng từ chối hai A/101.
- Constraint được inspector thấy giống tên/cột đã khai báo trong model.

### 20.3. Accessibility và hiệu năng

- Login label liên kết đúng input.
- Modal đặt phòng có accessible name, close button có tên và focus trở về trigger.
- Nút sửa/xóa khách hàng có accessible name chứa hành động và đối tượng.
- Toàn bộ action liên quan dùng được bằng keyboard, có focus indicator và error announcement.
- `bb-browser` kiểm tra accessibility tree, Tab order, Escape và console.
- Endpoint phòng dùng tối đa query budget với 4 và 40 phòng; payload giá/trạng thái giữ nguyên.

### 20.4. Báo cáo

- Tenant A chỉ nhận room revenue, Payment, Expense, top room và chart của A.
- Expense void không vào tổng chi phí, lợi nhuận, chart hoặc sổ quỹ.
- Kỳ custom hai ngày có đúng hai ngày ở mẫu số occupancy.
- Test dùng ít nhất hai hotel và các ID không trùng theo quan hệ giả định đơn giản.

### 20.5. Checkout lẻ

- Checkout `booked` bị từ chối.
- Checkout với client gửi `amount=0`, âm hoặc số tùy ý không ảnh hưởng số server quyết định.
- Checkout đủ tiền tạo đúng Payment, final amount và trạng thái.
- Cọc dư tạo refund đúng loại; không tạo room_payment âm.
- Retry không tạo Payment/audit trùng.
- Quote thay đổi trả 409 và không mutation.
- Booking nhiều phòng chỉ hoàn tất khi tất cả phòng kết thúc.

### 20.6. Checkout đoàn

- Còn một phòng booked thì toàn operation bị từ chối.
- Không có phòng checked-in thì không đổi tổng/status.
- Retry sau thành công giữ nguyên tổng, Payment và audit.
- Booking đã checkout một phần vẫn có `total_amount` bằng tổng toàn bộ phòng.
- Hai request cạnh tranh chỉ một request được hoàn tất.

### 20.7. Giá và cọc

- Thuê giờ API quote bằng đúng engine block giờ.
- Booking nhiều đêm/rule có tiền cọc 50%/100% từ tổng snapshot thật.
- Phân bổ cọc đoàn theo tổng snapshot từng phòng.
- Khách ở thêm một/hai đêm được cộng đúng line `overstay_extension`.
- Phụ thu checkout muộn không tính trùng với đêm phát sinh.

### 20.8. Kho và dịch vụ

- Tạo vật tư mới số lượng 4 tạo item total 4, batch 4 và một movement +4.
- Tăng dịch vụ trừ đúng batch FEFO.
- Giảm dịch vụ hoàn đúng batch gốc và tạo movement cho toàn bộ lượng hoàn.
- Sửa danh sách không xóa BookingService có lịch sử.
- Sửa dịch vụ sau checkout trả 409 và không đổi tồn.
- Invariant tổng item/batch đúng sau mọi success và rollback.
- Có test tích hợp database production cho foreign key và transaction, không chỉ SQLite `create_all`.

### 20.9. Phân quyền và trạng thái

- Staff không gọi được availability/confirm reschedule.
- Admin dời booking booked thành công; checked-in bị chặn.
- Tạo booking `checked_in` làm Booking cha `checked_in`.
- Một phòng checked_out và các phòng còn lại cancelled làm Booking `completed`.
- Operation key cancel Booking không va BookingRoom cùng ID.

## 21. Thứ tự triển khai

1. **P0.0 – Stored XSS:** test payload, render bằng DOM API, bỏ inline handler ở customer và kiểm tra browser.
2. **P1.0 – Alembic merge:** hợp nhất hai head và dựng test migration trước mọi schema change mới.
3. **P1.1 – Room tenant constraint:** đồng bộ model/migration, preflight và test MySQL.
4. **P1.2 – Production fail-closed:** config classes, bỏ startup seed/schema/debug.
5. **P1.3 – CSRF foundation:** bảo vệ form/API, fetch wrapper và cập nhật test.
6. **P0.1 – Tenant và báo cáo:** test tenant/void, sửa query, occupancy và sổ quỹ.
7. **P0.2 – Nền tảng operation/payment:** migration, component key, helper tiền và state transition.
8. **P0.3 – Checkout lẻ:** server-authoritative quote, tất toán, refund và idempotency.
9. **P0.4 – Checkout đoàn:** state guard, lock, idempotency và tổng booking.
10. **P1.4 – Pricing/cọc/overstay:** hợp nhất PriceQuote và snapshot phát sinh.
11. **P1.5 – Kho/dịch vụ:** sửa receipt vật tư mới, delta allocation và khóa hóa đơn.
12. **P1.6 – Dời lịch/trạng thái:** capability, vô hiệu mutation Timeline trực tiếp và helper aggregate state.
13. **P1.7 – Reconciliation:** command dry-run, báo cáo dữ liệu lịch sử và quy trình apply có phê duyệt.
14. **P2.1 – Accessibility:** label, modal, icon action, keyboard/focus và kiểm tra `bb-browser`.
15. **P2.2 – Dashboard query budget:** bulk PriceRule, aggregate room count và performance test.

UI/UX của từng hạng mục chỉ thực hiện sau backend/test tương ứng. Mỗi bước là một hạng mục độc lập, phải có test xanh và commit riêng; không trộn thay đổi dở dang hoặc file không liên quan.

## 22. Điều kiện hoàn tất

Hạng mục chỉ được coi là hoàn tất khi:

- Test mới của hạng mục và full regression đều xanh.
- Stored XSS payload không thực thi trong `bb-browser`; CSRF chặn request không token.
- Production config fail-closed và startup không tạo schema/tài khoản mặc định.
- `flask db heads` trả một head; upgrade/downgrade được kiểm tra trên database phù hợp.
- Constraint Room tenant giống nhau giữa model, Alembic và MySQL thực tế.
- Không còn query aggregate tài chính thiếu tenant scope.
- Các invariant tiền, trạng thái và kho được test trực tiếp.
- Query dashboard đạt budget cố định và payload không đổi.
- UI liên quan đã kiểm tra desktop bằng `bb-browser`, gồm accessibility tree, keyboard, console và luồng lỗi.
- Có ghi rõ phần production/concurrency nào chưa thể kiểm chứng.
- Commit chỉ chứa hạng mục đã hoàn tất và dùng commit message tiếng Anh.

## 23. Điểm cần phê duyệt khi review spec

1. Chấp thuận mặc định **không hỗ trợ công nợ**: checkout chỉ thành công khi balance về 0.
2. Chấp thuận đêm ở quá dùng **đơn giá snapshot đêm cuối**, không dùng rule hiện hành.
3. Chấp thuận giữ BookingService quantity 0 để bảo toàn lịch sử thay vì xóa cứng.
4. Chấp thuận Expense void không vào sổ quỹ/P&L nhưng không tự đảo tồn kho.
5. Chấp thuận tách công cụ reconciliation thành dry-run và apply có phê duyệt, không tự sửa tài chính trong migration.
