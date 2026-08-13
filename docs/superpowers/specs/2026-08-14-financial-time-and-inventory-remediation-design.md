# Spec: Chỉnh sửa hoàn tiền bất khả kháng, thời gian báo cáo và kiểm thử kho

**Ngày:** 14-08-2026  
**Trạng thái:** Chờ review nghiệp vụ  
**Phạm vi:** Hủy/trả phòng, hoàn tiền, báo cáo doanh thu và kiểm thử phân bổ kho theo lô.  
**Không bao gồm:** Hoàn tiền tự động khi checkout thông thường, công nợ khách hàng, tích hợp cổng thanh toán, đính kèm tệp chứng cứ, hoặc thay đổi chính sách giá phòng.

## 1. Bối cảnh và kết quả rà soát

Lần chạy regression hiện tại có **3 test đỏ**. Chúng cần được xử lý theo ba nhóm khác nhau, không gộp thành một lỗi “hoàn cọc dư”.

| Nhóm | Bằng chứng hiện tại | Kết luận cần xử lý |
|---|---|---|
| Hoàn tiền lúc checkout đoàn | `group_checkout_service.settle_group_checkout()` tự tạo `Payment` loại `refund` khi `quote.balance < 0`; test `test_group_checkout_excess_deposit_creates_one_refund` đang yêu cầu đúng hành vi này | Lệch với nghiệp vụ đã chốt: checkout bình thường không được tự hoàn cọc. Cần thay thế bằng luồng bất khả kháng có kiểm soát. |
| Hủy phòng | API `POST /timeline/api/bookings/cancel` chỉ cần đăng nhập, nhận trực tiếp `is_force_majeure` và `refund_percent` từ client; đồng thời từ chối phòng `checked_in` | Cờ bất khả kháng và tỷ lệ hoàn không thể do client quyết định. Chưa có luồng cho khách đã ở một phần kỳ lưu trú rồi buộc phải rời đi. |
| Báo cáo doanh thu | Báo cáo dùng `datetime.now()` theo giờ ứng dụng để tạo kỳ, nhưng `Booking.updated_at` có default `db.func.now()`; SQLite trả UTC. `completed_bookings` lọc theo `updated_at` | Sau 00:00 giờ Bangkok, một booking hoàn tất trong ngày có thể rơi vào ngày UTC trước và bị đếm là 0. `updated_at` cũng không phải mốc nghiệp vụ để đếm booking hoàn tất. |
| FEFO kho | Test dùng lô hết hạn `2026-08-01`; ngày chạy là 14-08-2026. `batches_for_consumption()` đúng quy tắc bỏ lô đã hết hạn nên lấy lô hết hạn 01-09 | Đây là test không ổn định theo lịch, không phải bằng chứng thuật toán FEFO sai. Cần kiểm thử với thời điểm nghiệp vụ được kiểm soát. |

Các quy tắc dưới đây thay thế kỳ vọng hoàn tiền tự động trong test checkout đoàn và chuẩn hóa các điểm còn mơ hồ.

## 2. Mục tiêu

- Chỉ hoàn tiền khi một vụ việc **bất khả kháng** được phê duyệt; hỗ trợ cả trước check-in và sau khi khách đã ở một phần kỳ lưu trú.
- Không cho client tự quyết định loại bất khả kháng, phần trăm hoàn, số tiền hoàn hoặc giá trị hóa đơn.
- Đảm bảo số tiền hoàn không vượt quá khoản khách đã thanh toán và không hoàn tiền cho đêm/dịch vụ đã dùng.
- Bảo toàn transaction, idempotency, tenant isolation và audit trail của dòng tiền.
- Định nghĩa một quy ước thời gian UTC + múi giờ nghiệp vụ Bangkok cho báo cáo tài chính.
- Làm test FEFO xác định theo thời gian và vẫn bảo vệ các invariant phân bổ/hoàn kho.

## 3. Thuật ngữ và phạm vi bất khả kháng

### 3.1. Điều kiện nghiệp vụ

Vụ việc chỉ được xử lý theo luồng này khi sự kiện khách quan, không thể dự đoán hợp lý và không thể khắc phục bằng biện pháp phù hợp khiến khách hoặc khách sạn không thể tiếp tục thực hiện một phần/toàn bộ lưu trú. Ví dụ: bão, lũ, hỏa hoạn, lệnh sơ tán của cơ quan có thẩm quyền, dịch bệnh hoặc sự cố an toàn diện rộng.

Lý do khách đổi kế hoạch, đến trễ, muốn về sớm, hoặc nhập sai booking **không** là bất khả kháng.

### 3.2. Hai trường hợp được hỗ trợ

1. **Hủy trước check-in:** phòng còn trạng thái `booked`. Nếu được phê duyệt, hủy các phòng đã chọn và hoàn tối đa phần tiền khách đã trả, theo phân bổ cọc thực tế của các phòng đó.
2. **Trả phòng sớm sau check-in:** phòng đang `checked_in`, ví dụ khách đã ở một đêm rồi phải rời đi vì bão. Nếu được phê duyệt, hệ thống checkout tại `effective_at`, thu phần phòng/dịch vụ/thuế đã phát sinh đến mốc đó và hoàn phần tiền đã trả nhưng chưa được dùng.

Phòng đã `checked_out` hoặc `cancelled` không thể đưa vào yêu cầu mới.

### 3.3. Ngoài luồng bất khả kháng

- Hủy thông thường luôn có tiền hoàn bằng `0`; không còn trường `refund_percent` cho người dùng nhập.
- Checkout thường không được tạo `Payment.refund` chỉ vì `balance` âm.
- Nếu dữ liệu lịch sử hoặc thay đổi bất thường làm cọc còn lại lớn hơn hóa đơn checkout thường, API trả `409` với mã `excess_deposit_requires_exception`, không đổi trạng thái, tiền hay audit. Admin phải xử lý theo yêu cầu bất khả kháng đã được phê duyệt hoặc theo quy trình điều chỉnh tài chính ngoài phạm vi này.
- Không tự động hoàn tiền khi khách tự trả phòng sớm. Chính sách giá/điều khoản đặt phòng quyết định phần phí phải thu; phạm vi này không tạo cơ chế công nợ hoặc giảm giá mới.

## 4. Quy trình xử lý bất khả kháng

### 4.1. Tạo và phê duyệt

1. Staff tạo **yêu cầu** trong đúng tenant, chọn một hoặc nhiều phòng đang còn hiệu lực, loại tình huống, thời điểm có hiệu lực, lý do và mô tả chứng cứ.
2. Hệ thống chỉ lưu yêu cầu ở trạng thái `submitted`; chưa đổi trạng thái phòng và chưa ghi `Payment`.
3. Admin hoặc Master Admin trong ngữ cảnh tenant xem báo giá server-side và phê duyệt hoặc từ chối. Người phê duyệt phải ghi ghi chú khi từ chối; ghi chú phê duyệt là tùy chọn nhưng được khuyến nghị.
4. Khi phê duyệt, server khóa Booking và các BookingRoom mục tiêu, tính lại báo giá tại thời điểm phê duyệt, thực thi một transaction duy nhất, tạo operation/audit rồi đổi yêu cầu thành `processed`.
5. Người gửi xem được kết quả, số tiền, thời điểm, người phê duyệt và lý do. Yêu cầu bị từ chối hoặc đã xử lý là bất biến; muốn điều chỉnh phải tạo nghiệp vụ điều chỉnh mới, không sửa/xóa lịch sử.

Staff không thể phê duyệt yêu cầu của mình hoặc gọi endpoint thực thi tài chính. Admin không được phê duyệt yêu cầu thuộc tenant khác.

### 4.2. Tính tiền tại thời điểm phê duyệt

Mọi con số đến từ server; client chỉ gửi định danh phòng, thời điểm, loại sự kiện, lý do/chứng cứ và phương thức hoàn tiền.

Với từng phòng được duyệt:

```text
chi_phi_da_dung = tiền phòng từ check_in_actual đến effective_at
                + dịch vụ đã gọi
                + thuế theo lựa chọn/booking hiện hành

tien_da_phan_bo = phần tiền khách đã trả còn được phân bổ cho phòng
tien_hoan = max(0, tien_da_phan_bo - chi_phi_da_dung)
```

- Tiền phòng được tính bằng engine báo giá và snapshot giá đang dùng cho checkout; không dùng giá cấu hình hiện tại để viết lại lịch sử.
- Đêm đã ở, dịch vụ đã dùng và thuế liên quan không được hoàn.
- Tổng hoàn của case không vượt tổng tiền đã thu và tiền cọc còn lại của Booking. Không được tạo số tiền hoàn âm hoặc một dòng thanh toán âm khác loại `refund`.
- Khi một case có nhiều phòng, hệ thống tạo **một** `Payment` âm cho toàn case, với `component_key = force_majeure_refund`; bảng chi tiết/snapshot lưu số tiền theo từng phòng.
- Phương thức hoàn (`cash`, `banking`, `credit_card`, `qr_code`, `other`) là bắt buộc và chỉ được lưu sau khi Admin phê duyệt.
- Nếu báo giá thay đổi, phòng không còn đúng trạng thái, số tiền không còn khả dụng, hoặc đã có case đang xử lý cho cùng phòng thì từ chối, không partial mutation và yêu cầu tải lại.

### 4.3. Chuyển trạng thái

- Case trước check-in dùng transition hủy hiện có: phòng thành `cancelled`, `final_amount` theo kết quả case và `check_out_actual = effective_at` để giữ mốc kết thúc rõ ràng.
- Case sau check-in dùng checkout: phòng thành `checked_out`, `check_out_actual = effective_at`, `final_amount` là chi phí thực tế đã dùng.
- Trạng thái Booking cha tiếp tục được suy ra từ toàn bộ phòng qua `booking_state_service`; case không được tự ép Booking thành `completed` khi còn phòng khác `booked`/`checked_in`.
- Chỉ operation được tạo khi phê duyệt mới mang dòng tiền. Retry cùng request/operation trả lại kết quả cũ, không tạo `Payment`, audit hoặc hoàn tiền thứ hai.

## 5. Dữ liệu, phân quyền và audit

### 5.1. Dữ liệu đề xuất

Thêm `force_majeure_cases`:

| Trường | Ý nghĩa |
|---|---|
| `id`, `hotel_id`, `booking_id` | Định danh và tenant scope |
| `case_type` | `pre_checkin_cancellation` hoặc `early_departure` |
| `status` | `submitted`, `approved`, `rejected`, `processed`, `failed` |
| `effective_at` | Thời điểm khách không thể tiếp tục lưu trú |
| `event_type`, `reason`, `evidence_note` | Căn cứ xử lý; không có trường tỷ lệ/số tiền do client nhập |
| `requested_by`, `requested_at` | Người tạo và thời điểm tạo |
| `reviewed_by`, `reviewed_at`, `review_note` | Thông tin phê duyệt/từ chối |
| `business_operation_id` | Operation đã thực thi, duy nhất khi `processed` |
| `quote_snapshot`, `settlement_snapshot` | Số liệu server tính lúc phê duyệt/kết quả để đối soát |

Thêm `force_majeure_case_rooms` để liên kết case với từng `BookingRoom` và lưu snapshot tiền cọc phân bổ, tiền phòng/dịch vụ/thuế, final amount và refund amount theo phòng. Mọi bản ghi phải thuộc cùng `hotel_id` với case, booking và room; service layer kiểm tra điều này trước khi ghi.

Không backfill case từ lịch sử hủy cũ. Migration chỉ thêm bảng/index/foreign key và giữ nguyên lịch sử `Payment`, `BookingRoom` hiện hữu.

### 5.2. Quyền hạn

| Hành động | Staff | Admin | Master Admin trong tenant |
|---|---:|---:|---:|
| Tạo/xem yêu cầu của tenant | Có | Có | Có |
| Xem báo giá case | Có, chỉ đọc | Có | Có |
| Phê duyệt/từ chối/thực thi | Không | Có | Có |
| Sửa số tiền/tỷ lệ từ client | Không | Không | Không |

Endpoint hủy thông thường giữ quyền hiện hữu nhưng bỏ chấp nhận `is_force_majeure` và `refund_percent`. Endpoint xử lý/approve case phải có decorator quyền riêng, trả JSON `403` thay vì redirect cho API.

### 5.3. Audit và đối soát

- Audit event riêng: `create_force_majeure_case`, `approve_force_majeure_case`, `reject_force_majeure_case`, `process_force_majeure_case`.
- Event/bản ghi operation chứa case ID, Booking/BookingRoom IDs, trạng thái trước/sau, snapshot báo giá, refund theo phòng, phương thức hoàn, người gửi và người duyệt.
- `Payment.note` mô tả case ID và lý do ngắn; không đặt toàn bộ chứng cứ nhạy cảm trong note hiển thị sổ quỹ.
- Báo cáo dòng tiền coi `Payment.amount < 0` là tiền ra, vì vậy hoàn tiền case tự đi vào `total_cash_out` và `total_net_payment` một lần.

## 6. Giao diện và khả năng truy cập

Giao diện dùng pattern dashboard nội bộ hiện có: thông tin dày vừa phải, bảng dễ quét và một primary action duy nhất cho từng màn hình. Theo UI-UX-PROMAX, biểu mẫu phải có label liên kết, báo lỗi gần trường bằng `role="alert"`/`aria-live`, phản hồi submit rõ ràng, màu không là tín hiệu duy nhất và thao tác nguy hiểm phải xác nhận.

### 6.1. Tạo yêu cầu

- Từ chi tiết Booking/timeline hiển thị nút **“Yêu cầu xử lý bất khả kháng”**, không đặt trong nút checkout thường.
- Modal/form gồm: phòng chịu ảnh hưởng (checkbox có số phòng/trạng thái), loại xử lý, thời điểm hiệu lực, loại sự kiện, lý do và mô tả chứng cứ.
- Không hiển thị input phần trăm hoàn hoặc số tiền hoàn. Hiển thị câu giải thích: “Số tiền do hệ thống tính và chỉ phát sinh sau khi Admin phê duyệt.”
- Nhóm chọn phòng và trường bắt buộc có label/legend; lỗi nêu nguyên nhân và cách sửa, focus tới trường lỗi đầu tiên. Nút xác nhận có trạng thái loading; thành công báo bằng toast `aria-live="polite"`.
- Đóng modal bằng Escape/nút đóng phải trả focus về trigger; đóng form có thay đổi chưa gửi phải xác nhận.

### 6.2. Duyệt và thực thi

- Admin có danh sách yêu cầu `submitted`, lọc theo ngày, loại, người tạo và trạng thái. Một dòng hiển thị rõ số booking, phòng, thời điểm, lý do và badge chữ cho trạng thái.
- Trang/detail duyệt hiển thị báo giá read-only theo từng phòng: đã dùng, cọc phân bổ, dự kiến hoàn, tổng hoàn. Đây là preview; server tính lại trước khi thực thi.
- Nút **“Phê duyệt & xử lý hoàn tiền”** là destructive/financial action, tách khỏi nút từ chối, yêu cầu hộp xác nhận chứa tổng tiền và phương thức hoàn. Không dùng màu đơn độc để phân biệt hai hành động.
- Từ chối yêu cầu cần ghi chú; không dùng modal lồng modal. Trên desktop và mobile không có cuộn ngang toàn trang, nút thao tác tối thiểu 44px.

### 6.3. Hủy/checkout hiện hữu

- Form hủy thường bỏ checkbox/cờ bất khả kháng và input tỷ lệ hoàn. Khi hủy thường, UI ghi rõ “Không phát sinh hoàn tiền tự động”.
- Khi checkout có cọc vượt hóa đơn, hiển thị lỗi nghiệp vụ có action dẫn đến case bất khả kháng (nếu người dùng có quyền tạo), không tạo toast “đã hoàn tiền”.

## 7. Quy ước thời gian cho tài chính và báo cáo

### 7.1. Hợp đồng thời gian

- Timestamp lưu trong database theo UTC. Với các cột `DateTime` legacy chưa timezone-aware, adapter chỉ lưu UTC-naive và helper phải gắn UTC khi đọc để tránh trộn giờ local/UTC.
- Thêm một time service duy nhất: `utc_now()`, `business_now()` và `business_period_to_utc()`. `BUSINESS_TIMEZONE` mặc định là `Asia/Bangkok`; chưa bổ sung timezone riêng cho từng hotel trong đợt này.
- Các write path tài chính/trạng thái trong phạm vi này (Payment, BusinessOperation, Booking state transition, force majeure case) dùng helper UTC, không gọi trực tiếp `datetime.now()` hoặc dựa vào clock của database.
- `Booking.updated_at` chỉ là mốc kỹ thuật “lần sửa gần nhất”, không được dùng làm ngày hoàn tất hoặc doanh thu.

### 7.2. Mốc hoàn tất và truy vấn báo cáo

- Thêm `Booking.completed_at` nullable. `booking_state_service` chỉ set nó khi Booking chuyển sang `completed`; không đổi khi sau đó chỉnh note/dữ liệu không làm thay đổi completion. Nếu booking rời `completed` hợp lệ trong tương lai, quy tắc phải được review riêng.
- Migration backfill `completed_at` cho booking `completed` từ `MAX(booking_rooms.check_out_actual)`. Bản ghi không suy ra được mốc bị giữ `NULL` và báo qua reconciliation, không bịa thời gian từ `updated_at`.
- `completed_bookings` lọc `Booking.status = completed` và `Booking.completed_at` nằm trong khoảng UTC của kỳ báo cáo, không lọc `updated_at`.
- Kỳ `today`, `week`, `month`, `custom` được chọn theo ngày Bangkok, sau đó đổi thành `[start_utc, end_utc)` trước khi truy vấn.
- Nhãn ngày/chart doanh thu chuyển timestamp UTC về ngày Bangkok trước khi gom nhóm. Không dùng `func.date()` theo timezone của SQLite/MySQL vì hai dialect có thể cho ngày khác nhau.
- Báo cáo giữ toàn bộ filter `hotel_id`, loại Expense void và quy tắc cash-in/cash-out hiện có.

## 8. FEFO kho và kiểm thử xác định thời gian

`inventory_batch_service.batches_for_consumption()` hiện đã sắp lô theo hạn dùng tăng dần, ưu tiên lô có hạn dùng trước lô không có hạn và loại lô đã quá hạn. Không thay đổi quy tắc đó.

Các thay đổi cần làm:

- Cung cấp tham số nội bộ `as_of_date`/clock có thể inject cho validate tồn, trừ tồn và chọn lô; production mặc định dùng ngày nghiệp vụ hiện tại.
- Sửa test FEFO để cố định ngày tham chiếu (ví dụ 01-07-2026), với lô hết hạn 01-08 và 01-09; không dùng ngày cố định đã qua mà không kiểm soát clock.
- Thêm test riêng xác nhận lô đã quá hạn bị bỏ qua, lô không hạn dùng đứng sau lô còn hạn, và lỗi thiếu tồn không ghi partial movement/allocation.
- Giữ quy tắc hoàn kho theo `BookingServiceBatchAllocation`: hoàn từ allocation ghi sau trước, giảm đúng allocation và luôn khôi phục `InventoryItem.quantity` khớp tổng `quantity_available` của các lô.

## 9. TDD và tiêu chí nghiệm thu

Mỗi hạng mục bắt đầu bằng test đỏ, triển khai tối thiểu, refactor, chạy test hạng mục và commit riêng bằng tiếng Anh.

### 9.1. Hoàn tiền bất khả kháng

1. Checkout đoàn thường có `balance < 0` trả `409`, không tạo Payment, BusinessOperation, audit hay đổi trạng thái.
2. Hủy thường bỏ qua/từ chối `refund_percent` và `is_force_majeure` từ client; tiền hoàn luôn bằng 0.
3. Staff tạo case thành công nhưng gọi approve/process nhận `403`; tenant khác nhận `404` hoặc `403` theo policy nhất quán và không lộ dữ liệu.
4. Admin duyệt case trước check-in tạo đúng một Payment refund âm, tối đa bằng cọc phân bổ, room thành `cancelled`, có operation và audit.
5. Case bão sau một đêm checkout ở `effective_at`, chỉ tính đêm/dịch vụ đã dùng và hoàn đúng phần đêm chưa dùng. Không hoàn quá tiền đã thu.
6. Case nhiều phòng phân bổ/tổng hợp đúng; phòng không được chọn không đổi trạng thái/cọc.
7. Retry/concurrent approve không tạo refund hoặc audit trùng; quote stale/state thay đổi rollback hoàn toàn.

### 9.2. Báo cáo thời gian

1. Test ở 00:30 Bangkok với timestamp UTC ngày trước vẫn đếm room revenue, Payment và completed booking vào “hôm nay”.
2. Test ở 23:30 Bangkok không lẫn sang ngày sau; chart dùng ngày Bangkok.
3. Booking hoàn tất, sau đó sửa note/metadata ở ngày khác, chỉ được đếm theo `completed_at`.
4. Migration backfill đúng max checkout actual; dữ liệu thiếu mốc được nhận diện và không xuất hiện sai trong report.
5. Tenant isolation và Expense void của test báo cáo hiện có tiếp tục xanh.

### 9.3. Kho

1. Test FEFO chạy lặp ở bất kỳ ngày nào vẫn lấy lô còn hạn gần nhất trước.
2. Lô đã hết hạn không bao giờ có consumption/allocation; lô không hạn chỉ được lấy sau các lô còn hạn.
3. Hoàn một phần trả đúng lô đã phân bổ và invariant tổng tồn/lô/movement giữ đúng.

### 9.4. UI

- Test API/DOM cho phân quyền, không có input số tiền/tỷ lệ hoàn do client kiểm soát, validation và lỗi submit.
- Trước bàn giao UI, kiểm tra desktop bằng `bb-browser`: luồng Staff tạo yêu cầu, Admin duyệt/từ chối, Escape/focus return, Tab order, console, trạng thái lỗi và không tràn ngang.

## 10. Thứ tự triển khai

1. Viết test đỏ cho chặn auto-refund checkout và khóa tham số hoàn tiền trong hủy thường; commit riêng.
2. Migration/model/service cho force majeure case, phân quyền, transaction/idempotency/audit; commit riêng.
3. UI tạo yêu cầu và duyệt case, sau khi backend xanh; kiểm tra `bb-browser`; commit riêng.
4. Time service, migration `completed_at`, backfill và truy vấn báo cáo theo kỳ UTC; commit riêng.
5. Sửa test/clock FEFO, bổ sung regression hết hạn/không hạn/hoàn kho; commit riêng.
6. Chạy full regression trên database test phù hợp. Migration phải được kiểm tra từ database trống và database có dữ liệu mẫu trước khi coi phần dữ liệu hoàn tất.

## 11. Điều kiện hoàn tất

- Không còn test nào yêu cầu hoặc cho phép hoàn tiền tự động chỉ vì cọc lớn hơn hóa đơn checkout.
- Mọi Payment refund có case bất khả kháng đã duyệt, operation idempotent và audit đầy đủ.
- Staff không thể thực thi dòng tiền; Admin chỉ tác động tenant của mình.
- Báo cáo tài chính nhất quán qua biên ngày Bangkok/UTC và không dùng `updated_at` làm mốc hoàn tất.
- FEFO được kiểm thử xác định thời gian, không làm dùng lô hết hạn và giữ invariant tồn kho.
- Test hạng mục và full regression xanh; UI liên quan được kiểm tra desktop bằng `bb-browser`.
