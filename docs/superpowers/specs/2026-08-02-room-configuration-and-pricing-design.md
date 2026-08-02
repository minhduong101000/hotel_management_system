# Spec: Cấu hình phòng và giá

**Ngày:** 02-08-2026

**Trạng thái:** Đã chốt nghiệp vụ, chờ lập kế hoạch TDD để triển khai

**Phạm vi:** Ứng dụng web theo từng khách sạn (tenant), dành cho Staff, Hotel admin và Master admin khi đang ở đúng ngữ cảnh khách sạn

## 1. Bối cảnh và hiện trạng

Trong lịch sử dự án từng có trang `/settings` với mục “Quản lý loại phòng & Giá”, nhưng trang này chỉ là placeholder dùng liên kết `href="#"`. Controller và template tương ứng đã bị xoá ở commit `30477a8`.

Hệ thống hiện có:

- `Room` chứa số phòng, loại phòng, giá qua đêm mặc định, giá block đầu, số giờ block đầu, giá giờ tiếp theo, trạng thái vận hành và trạng thái vệ sinh.
- `PriceRule` chứa luật giá đặc biệt theo loại phòng, thời gian, ngày trong tuần và mức ưu tiên.
- Trang `templates/admin/price_manager.html` cho phép cập nhật giá mặc định của phòng và quản lý luật giá đặc biệt.
- `services/pricing_service.py` dùng giá mặc định từ `Room`, sau đó chỉ ghi đè giá qua đêm khi tìm được `PriceRule` phù hợp.
- Chưa có màn hình hoặc API nghiệp vụ để tạo phòng mới, sửa thông tin cơ bản của phòng hay chủ động bật/tắt bảo trì.
- Quyền hiện tại và test hiện tại vẫn cho Staff truy cập trang/API quản lý giá; spec này không được âm thầm thu hồi quyền đó.

## 2. Mục tiêu

- Khôi phục khu vực cấu hình phòng thành chức năng thật, không khôi phục placeholder cũ.
- Cho phép tạo và chỉnh sửa phòng trong đúng tenant.
- Đặt giá mặc định cạnh thông tin phòng để người dùng hiểu đây là cấu hình nền của từng phòng.
- Giữ luật giá đặc biệt thành một nhóm nghiệp vụ riêng, chỉ ghi đè giá qua đêm.
- Gộp cấu hình phòng và giá vào một mục điều hướng nhưng tách thành hai tab/trang có URL riêng.
- Giữ nguyên khả năng tính giá, snapshot giá booking, tenant isolation, CSRF và audit trail hiện có.
- Đảm bảo màn hình dễ quét, dùng được bằng bàn phím, không tràn ngang toàn trang và phù hợp thiết kế Hotel POS Pro hiện tại.

## 3. Ngoài phạm vi

- Không tạo bảng hoặc model danh mục `RoomType` riêng trong đợt này; `Room.room_type` tiếp tục là chuỗi và giao diện gợi ý từ các loại phòng đang có trong tenant.
- Không hỗ trợ xoá cứng phòng vì phòng có thể đã được tham chiếu bởi lịch sử booking, dịch vụ và báo cáo.
- Không hỗ trợ nhập phòng hàng loạt, sơ đồ tầng, tiện nghi, sức chứa, hình ảnh hoặc mô tả phòng.
- Không xây dựng lịch bảo trì theo khoảng ngày/giờ; trạng thái bảo trì hiện tại là trạng thái vô thời hạn cho đến khi được tắt thủ công.
- Không tự động dời, huỷ hoặc sửa booking khi bật bảo trì.
- Không bổ sung cơ chế chặn cứng mới đối với booking đã tồn tại trên phòng vừa chuyển sang bảo trì; lễ tân chịu trách nhiệm kiểm tra và xử lý thủ công theo quyết định nghiệp vụ đã chốt.
- Không cho luật giá đặc biệt ghi đè giá block đầu, số giờ block hoặc giá giờ tiếp theo.
- Không thay đổi cách tính checkout, phụ thu, cọc, snapshot hoặc hoá đơn của booking đã tạo.
- Không thay Bootstrap, Jinja, Font Awesome hoặc kiến trúc Flask hiện tại.

## 4. Thuật ngữ và quy tắc giá

### 4.1 Giá mặc định của phòng

Mỗi `Room` có một bộ giá mặc định riêng:

- `price_per_night`: giá qua đêm mặc định.
- `price_initial_block`: giá block đầu.
- `initial_hours`: số giờ của block đầu.
- `price_next_hour`: giá cho mỗi giờ tiếp theo.

Bộ giá này được dùng khi không có luật giá đặc biệt phù hợp. Giá theo giờ luôn lấy từ bộ giá mặc định này.

### 4.2 Giá đặc biệt

Một `PriceRule` được xét theo:

- Đúng khách sạn.
- Đúng loại phòng.
- Đang active.
- Ngày áp dụng nằm trong khoảng bắt đầu/kết thúc nếu các mốc này được cấu hình.
- Ngày trong tuần phù hợp nếu luật giới hạn ngày trong tuần.
- Mức ưu tiên theo logic hiện có của `pricing_service`.

Khi có luật phù hợp:

- Chỉ `price_per_night` hiệu lực được thay bằng `PriceRule.price_daily`.
- `price_initial_block`, `initial_hours` và `price_next_hour` vẫn lấy từ `Room`.
- Booking mới chốt snapshot theo giá hiệu lực tại thời điểm tạo.
- Booking đã có snapshot không bị đổi giá khi cấu hình phòng hoặc luật giá được sửa sau đó.

Khi không có luật phù hợp, toàn bộ giá hiệu lực lấy từ cấu hình mặc định của phòng.

## 5. Kiến trúc thông tin và điều hướng

Sidebar chỉ có một mục **“Cấu hình phòng & giá”** trong nhóm “Dịch vụ & Kho”. Mục này thay cho liên kết “Quản lý Giá phòng” hiện tại.

Khu vực này gồm hai tab dạng liên kết thật, không dùng tab chỉ đổi DOM trên cùng một URL:

1. **Phòng & giá mặc định** — route mới dự kiến `/<hotel_slug>/rooms/settings`.
2. **Giá đặc biệt** — tiếp tục dùng endpoint và route hiện tại `/<hotel_slug>/prices/admin/price-manager` để giữ tương thích bookmark, test và liên kết cũ.

Yêu cầu điều hướng:

- Tab hiện tại có active state rõ ràng và `aria-current="page"`.
- Refresh và nút Back của trình duyệt giữ đúng tab.
- Cả hai endpoint làm sidebar “Cấu hình phòng & giá” ở trạng thái active.
- Người dùng mở URL cũ của trang giá vẫn tới đúng tab “Giá đặc biệt”, không bị 404.
- Không thêm một mục sidebar thứ hai chỉ dành riêng cho luật giá.

## 6. Màn hình “Phòng & giá mặc định”

### 6.1 Page header

- Tiêu đề: **Cấu hình phòng**.
- Mô tả: “Quản lý thông tin phòng, trạng thái bảo trì và giá mặc định”.
- Hành động phụ: **Làm mới**.
- Hành động chính: **Thêm phòng**, chỉ hiển thị khi người dùng có quyền quản lý cấu trúc phòng.

Mỗi màn hình chỉ có một primary action nổi bật. Nút “Làm mới” dùng kiểu outline.

### 6.2 Bộ lọc

- Tìm theo số phòng hoặc loại phòng.
- Lọc theo loại phòng.
- Lọc theo trạng thái: tất cả, sẵn sàng, đang có khách, bảo trì.
- Kết quả và tổng số phòng được cập nhật rõ ràng.
- Bộ lọc phải có label hoặc accessible name; không dùng placeholder làm label duy nhất.

### 6.3 Bảng phòng

Các cột bắt buộc:

| Cột | Nội dung |
|---|---|
| Phòng | Số phòng và loại phòng |
| Trạng thái | Sẵn sàng, đang có khách hoặc bảo trì; không chỉ dùng màu để truyền đạt |
| Giá qua đêm | Giá mặc định của phòng |
| Block đầu | Giá và số giờ block đầu |
| Giờ tiếp theo | Giá mỗi giờ tiếp theo |
| Thao tác | Sửa thông tin/cấu hình theo quyền |

Quy tắc hiển thị:

- Tiền dùng định dạng VND thống nhất và canh phải.
- Trạng thái dùng badge có label chữ và icon phù hợp.
- Không nhồi toàn bộ form vào từng hàng.
- Bảng nằm trong wrapper cuộn ngang riêng trên màn hình nhỏ; body trang không được tràn ngang.
- Có loading state, empty state, error state và retry action.
- Empty state dành cho Hotel admin/Master có nút **Thêm phòng**; Staff không có quyền tạo phòng chỉ thấy hướng dẫn liên hệ quản lý.

### 6.4 Modal thêm/sửa phòng

Trường dữ liệu:

| Trường | Bắt buộc | Quy tắc |
|---|---:|---|
| Số phòng | Có | Trim khoảng trắng, tối đa 10 ký tự, duy nhất trong cùng khách sạn |
| Loại phòng | Có | Trim khoảng trắng, tối đa 20 ký tự; gợi ý từ các loại phòng hiện có nhưng vẫn cho nhập giá trị hợp lệ mới |
| Giá qua đêm mặc định | Có | Số tiền lớn hơn 0 |
| Giá block đầu | Có | Số tiền lớn hơn 0 |
| Số giờ block đầu | Có | Số nguyên lớn hơn hoặc bằng 1 |
| Giá mỗi giờ tiếp theo | Có | Số tiền lớn hơn 0 |
| Bảo trì | Có | Toggle rõ nhãn; mặc định tắt khi tạo phòng |

Quy tắc modal:

- “Thêm phòng” và “Sửa phòng” dùng cùng cấu trúc form nhưng tiêu đề/nút submit phản ánh đúng hành động.
- Mọi label liên kết với input bằng `for`/`id`.
- Nút đóng có accessible name.
- Focus đi vào trường đầu tiên khi mở; đóng modal trả focus về nút đã mở modal.
- Enter không được gửi form khi dữ liệu tiền còn đang ở trạng thái không hợp lệ.
- Khi đang lưu, khoá submit và hiển thị trạng thái xử lý để tránh gửi trùng.
- Lỗi theo trường hiển thị ngay cạnh trường; lỗi tổng quát có vùng `role="alert"`.
- Sau khi lưu thành công, đóng modal, thông báo thành công và cập nhật đúng hàng mà không cần tải lại toàn trang.

### 6.5 Trạng thái bảo trì

- Bật bảo trì chỉ thay đổi trạng thái cấu hình của phòng; không tự động huỷ, dời hoặc chỉnh sửa booking.
- Nếu phòng đang có khách hoặc còn booking tương lai, giao diện hiển thị cảnh báo rõ: “Phòng còn booking/khách đang ở. Hệ thống không tự xử lý các booking này.”
- Cảnh báo không phải hard block; người có quyền vẫn có thể xác nhận bật bảo trì.
- Tắt bảo trì phải đồng bộ lại trạng thái vật lý: nếu còn lượt `checked_in` thì hiển thị `occupied`, nếu không thì `available`; `clean_status` được giữ nguyên.
- Mọi lần bật/tắt bảo trì phải ghi audit event với trạng thái trước và sau.
- Quyết định không bổ sung hard guard mới không được làm mất các chặn bảo trì đang có trong tìm phòng, tạo booking, đặt đoàn hoặc dời lịch.

## 7. Màn hình “Giá đặc biệt”

Màn hình này kế thừa chức năng hiện tại của `price_manager.html`, nhưng chỉ tập trung vào luật giá đặc biệt.

### 7.1 Nội dung

- Danh sách luật giá đặc biệt.
- Tạo, sửa và xoá luật theo quyền hiện có.
- Các trường: tên luật, loại phòng, mức ưu tiên, ngày bắt đầu, ngày kết thúc, các ngày trong tuần và giá qua đêm đặc biệt.
- Không hiển thị trường giá block đầu hoặc giá giờ tiếp theo trong modal luật giá.
- Mỗi luật thể hiện rõ loại phòng, thời gian áp dụng, mức ưu tiên và giá qua đêm.

### 7.2 Di chuyển chức năng hiện tại

- Bảng “Giá cơ bản” hiện nằm trong `price_manager.html` được chuyển sang tab “Phòng & giá mặc định”.
- Không duy trì hai nơi cùng sửa giá mặc định.
- API cập nhật giá mặc định hiện có có thể được tái sử dụng hoặc gom vào API cấu hình phòng, nhưng chỉ được có một nguồn ghi nghiệp vụ và một bộ validation.
- API luật giá hiện tại được giữ đường dẫn hoặc có redirect/alias tương thích nếu refactor.
- JavaScript không được gửi/hiển thị `price_initial` hoặc `price_next` cho `PriceRule`, vì model và nghiệp vụ chỉ hỗ trợ giá qua đêm đặc biệt.

## 8. Phân quyền

Spec giữ quyền giá đang được code và test hiện tại cho phép, đồng thời tách quyền cấu trúc phòng:

| Hành vi | Staff | Hotel admin | Master admin trong tenant context |
|---|---:|---:|---:|
| Xem danh sách phòng và giá mặc định | Có | Có | Có |
| Xem tab giá đặc biệt | Có | Có | Có |
| Cập nhật giá mặc định | Có, giữ hành vi hiện tại | Có | Có |
| Tạo/sửa/xoá luật giá đặc biệt | Có, giữ hành vi hiện tại | Có | Có |
| Tạo phòng | Không | Có | Có |
| Đổi số phòng hoặc loại phòng | Không | Có | Có |
| Bật/tắt bảo trì | Không | Có | Có |
| Xoá cứng phòng | Không hỗ trợ | Không hỗ trợ | Không hỗ trợ |

Yêu cầu kỹ thuật:

- UI ẩn hoặc vô hiệu hoá đúng hành động không có quyền để hỗ trợ trải nghiệm.
- Backend mới là lớp quyết định quyền; gọi API trực tiếp khi thiếu quyền phải trả JSON `403`, không redirect HTML.
- Master admin chỉ được thao tác khi đã ở đúng tenant URL/ngữ cảnh khách sạn.
- Không nhận `hotel_id` từ payload để quyết định tenant.

## 9. API và hợp đồng dữ liệu dự kiến

Tên endpoint có thể điều chỉnh trong implementation plan, nhưng trách nhiệm phải giữ như sau.

### 9.1 Đọc cấu hình phòng

`GET /<hotel_slug>/rooms/api/settings`

Response thành công:

```json
{
  "rooms": [
    {
      "id": 1,
      "room_number": "101",
      "room_type": "Standard",
      "price_per_night": 500000,
      "price_initial_block": 300000,
      "initial_hours": 2,
      "price_next_hour": 50000,
      "status": "available",
      "clean_status": "cleaned",
      "active_booking_count": 0
    }
  ],
  "room_types": ["Standard"]
}
```

`active_booking_count` chỉ phục vụ cảnh báo vận hành; không được dùng làm hard block trong phạm vi đã chốt.

### 9.2 Tạo phòng

`POST /<hotel_slug>/rooms/api/settings`

- Chỉ Hotel admin hoặc Master admin trong tenant context.
- Server gán `hotel_id` từ `g.hotel_id`.
- Thành công trả `201` cùng room vừa tạo.
- Trùng số phòng trong cùng tenant trả `409` với `error_code="room_number_conflict"`.
- Validation trả `400` với lỗi theo trường.
- Ghi audit action `create_room`.

### 9.3 Cập nhật phòng

`PUT /<hotel_slug>/rooms/api/settings/<int:room_id>`

- Thay đổi thông tin phòng, giá mặc định và cờ bảo trì theo quyền tương ứng.
- Lookup bắt buộc tenant-scoped; ID hotel khác trả `404`.
- Trùng số phòng trả `409`.
- Ghi audit snapshot trước/sau; action có thể là `update_room` và `set_room_maintenance`/`clear_room_maintenance` khi trạng thái bảo trì thay đổi.

Nếu implementation tách API cập nhật giá để giữ quyền Staff, API cập nhật giá hiện tại phải dùng cùng validation tiền, tenant scope và audit; Staff không được lợi dụng payload giá để đổi số phòng, loại phòng hoặc trạng thái.

### 9.4 API luật giá

Giữ tương thích với:

- `GET /<hotel_slug>/prices/api/prices/all-data` hoặc endpoint đọc luật tương đương có alias.
- `POST /<hotel_slug>/prices/api/prices/save-rule`.
- `DELETE /<hotel_slug>/prices/api/prices/delete-rule/<id>`.

Nếu response đọc giá được tách, tab “Giá đặc biệt” chỉ cần nhận `rules` và danh sách loại phòng; giá mặc định được đọc từ API cấu hình phòng.

## 10. Validation, transaction và tenant isolation

- Mọi query `Room` và `PriceRule` phải scope theo `g.hotel_id` qua helper tenant hiện có.
- Tạo/cập nhật phòng gán `hotel_id` tường minh trên server.
- Không tin `room_id`, `hotel_id`, `status` hoặc giá từ client nếu chưa validate.
- Unique `(hotel_id, room_number)` ở database là lớp bảo vệ cuối; controller phải bắt lỗi cạnh tranh và trả `409` thân thiện.
- Không commit một phần khi audit hoặc mutation lỗi.
- Giá tiền được parse theo một quy ước nhất quán, không chấp nhận `NaN`, số âm, chuỗi rỗng hoặc giá trị vô hạn.
- `initial_hours` phải là số nguyên hợp lệ.
- Chỉ chấp nhận trạng thái cấu hình `available` hoặc `maintenance`; `occupied` là trạng thái phát sinh từ nghiệp vụ check-in, không phải lựa chọn tuỳ ý trong form.
- CSRF áp dụng cho mọi mutation thông qua cơ chế toàn cục hiện có.

## 11. Audit trail

Tối thiểu ghi các action:

- `create_room`.
- `update_room`.
- `update_base_price` — tiếp tục giữ tương thích log hiện có.
- `set_room_maintenance`.
- `clear_room_maintenance`.
- `create_price_rule`.
- `update_price_rule`.
- `delete_price_rule`.

Snapshot không chứa dữ liệu không liên quan. Đối với phòng, snapshot gồm số phòng, loại phòng, bộ giá mặc định và trạng thái trước/sau.

## 12. Accessibility, responsive và thiết kế trực quan

Spec tuân theo `docs/superpowers/specs/2026-08-02-ui-visual-refresh-design.md` và định hướng UI-UX-PROMAX:

- Một primary action trên mỗi màn hình.
- Touch target tối thiểu 44 × 44 px và khoảng cách giữa các vùng bấm tối thiểu 8 px.
- Contrast chữ thường tối thiểu 4.5:1.
- Focus ring luôn nhìn thấy; thứ tự Tab khớp thứ tự hiển thị.
- Tab là liên kết có tên rõ, hỗ trợ keyboard và deep link.
- Icon chỉ hỗ trợ nhận biết, không thay thế accessible label.
- Input mobile dùng font tối thiểu 16 px để tránh trình duyệt tự zoom.
- Modal không vượt viewport; nội dung dài có vùng cuộn bên trong hợp lý.
- Các viewport bắt buộc kiểm tra: 375, 768, 1024, 1440 và desktop 1920 px phù hợp.
- Không dùng hover gây dịch layout; transition có ý nghĩa trong khoảng 150–300 ms và tôn trọng `prefers-reduced-motion`.

## 13. Trạng thái giao diện và phản hồi

- Loading: skeleton hoặc data state đang tải có `role="status"`.
- Empty: giải thích chưa có phòng và đưa đúng CTA theo quyền.
- Error: thông báo nguyên nhân có thể hành động và nút thử lại.
- Saving: khoá đúng nút submit, không khoá toàn bộ trang không cần thiết.
- Success: thông báo ngắn, cập nhật dữ liệu tại chỗ.
- Conflict: giữ dữ liệu form, focus lỗi số phòng và giải thích số phòng đã tồn tại.
- Maintenance warning: dùng warning surface và nội dung chữ; không chỉ dùng màu amber.

## 14. Tiêu chí nghiệm thu

### 14.1 Phòng và giá mặc định

- Hotel admin tạo được phòng với đầy đủ bộ giá mặc định.
- Hai khách sạn có thể dùng cùng số phòng; cùng khách sạn không thể trùng số phòng.
- Staff không thể tạo phòng, đổi số/loại phòng hoặc bật/tắt bảo trì bằng UI lẫn gọi API trực tiếp.
- Staff vẫn cập nhật được giá mặc định và luật giá như hành vi hiện tại.
- Sửa giá mặc định chỉ ảnh hưởng báo giá/booking mới; snapshot booking cũ không đổi.
- Không có luật giá phù hợp thì giá hiệu lực bằng giá mặc định của phòng.
- Có luật phù hợp thì chỉ giá qua đêm bị ghi đè; giá theo giờ vẫn giữ mặc định.
- Không có chức năng xoá cứng phòng.

### 14.2 Bảo trì

- Bật/tắt bảo trì ghi audit đúng tenant và snapshot trước/sau.
- Khi còn booking hoặc khách đang ở, UI cảnh báo nhưng vẫn cho người có quyền xác nhận.
- Bật bảo trì không tự sửa, dời hoặc huỷ booking hiện có.
- Các chặn bảo trì đã tồn tại trong luồng tìm/tạo/dời booking không bị gỡ bỏ.
- Tắt bảo trì đồng bộ trạng thái vật lý mà không làm mất `clean_status`.

### 14.3 Điều hướng và UI

- Sidebar chỉ có một mục “Cấu hình phòng & giá”.
- Hai tab có URL và active state riêng; Back/refresh hoạt động đúng.
- URL trang giá cũ vẫn dùng được.
- Bảng và modal không làm body tràn ngang ở các viewport bắt buộc.
- Form dùng được bằng bàn phím, label liên kết đúng và focus được khôi phục sau khi đóng modal.
- Không có lỗi JavaScript/console ở luồng tải danh sách, thêm, sửa, lỗi validation và chuyển tab.

## 15. Chiến lược kiểm thử TDD dự kiến

Implementation plan phải chia thành các lát dọc độc lập, mỗi lát có test đỏ trước:

1. Contract đọc cấu hình phòng và tenant isolation.
2. Tạo phòng: quyền, validation, unique theo tenant, audit và transaction.
3. Sửa phòng/giá mặc định: field-level permission, snapshot và không ảnh hưởng booking cũ.
4. Bật/tắt bảo trì: cảnh báo không hard block, audit và đồng bộ trạng thái.
5. Giá đặc biệt chỉ ghi đè giá qua đêm; giá giờ luôn lấy mặc định.
6. Điều hướng một mục/hai tab và tương thích URL cũ.
7. Accessibility/responsive markup và regression các trang giá hiện có.

Các nhóm test dự kiến:

- Unit/service test cho precedence giá.
- Controller test cho HTTP status, validation, role và tenant.
- Audit test cho create/update/maintenance.
- Markup/UI regression test cho sidebar, tab, form, label và state.
- Integration test MySQL cho unique `(hotel_id, room_number)` nếu môi trường khả dụng.
- `bb-browser` desktop bắt buộc cho toàn bộ luồng UI thay đổi trước khi báo hoàn tất triển khai.

## 16. Tương thích và triển khai

- Không cần migration mới nếu kiểm tra schema thực tế xác nhận các cột và unique constraint của `Room` đã khớp model.
- Không thay đổi dữ liệu phòng hiện có.
- Giữ endpoint/URL giá cũ hoặc cung cấp alias/redirect tương thích.
- Tách JavaScript theo trách nhiệm: cấu hình phòng không phụ thuộc DOM nội bộ của màn luật giá.
- Không xoá test quyền Staff truy cập giá; mở rộng test để bảo vệ field-level permission mới.
- Tài liệu implementation plan tiếp theo phải viết bằng tiếng Việt và nêu rõ từng bước test đỏ, triển khai tối thiểu, refactor, kiểm tra `bb-browser` và commit độc lập.
