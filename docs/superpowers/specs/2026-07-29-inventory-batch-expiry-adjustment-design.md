                                                                                                                                                                                                                                                    # Spec: Quản lý kho theo lô, hạn dùng và điều chỉnh tồn

**Trạng thái:** ĐÃ TRIỂN KHAI (cập nhật trạng thái 15-08-2026 — tính năng đã vận hành, xem business-operations-guide.md)
**Phạm vi:** Chi phí đồng bộ kho, kho hàng, dịch vụ/minibar và lịch sử biến động kho.  
**Không bao gồm:** Xuất báo cáo, sao lưu/khôi phục, chính sách hoàn cọc tự động.

## 1. Bối cảnh và vấn đề hiện tại

Hiện tại mỗi vật tư chỉ có một số lượng tổng trong `inventory_items.quantity`. Khi tạo chi phí và chọn đồng bộ kho, hệ thống tăng số lượng của vật tư tương ứng; liên kết với khoản chi chỉ được lưu gián tiếp trong mô tả bằng mã `[KHO:<mã>]`.

Hệ thống chưa lưu từng lần nhập, hạn dùng, số lượng còn lại của lần nhập, hoặc lịch sử tăng/giảm tồn riêng. Khi xóa chi phí, chỉ bản ghi chi phí bị xóa; tồn kho và dịch vụ đã đồng bộ không bị đảo lại. Vì vậy hệ thống không thể biết chính xác hàng nào sắp hết hạn, hàng nào đã quá hạn, hay có thể giảm tồn an toàn khi một khoản chi bị xử lý lại.

## 2. Mục tiêu

- Theo dõi hàng có hạn dùng theo **từng lô nhập**.
- Cảnh báo hàng sắp hết hạn và hàng đã quá hạn, nhưng không tự động làm giảm tồn kho.
- Cho phép nhân viên tạo phiếu hủy hàng quá hạn/hư hỏng để giảm đúng số lượng thực tế.
- Không cho sử dụng để gọi món các hàng thuộc lô đã hết hạn.
- Ghi lại đầy đủ mọi biến động tồn: nhập, khách dùng, hủy hàng và điều chỉnh.
- Giữ dữ liệu tách biệt tuyệt đối theo `hotel_id`.
- Không làm mất lịch sử đối soát khi một khoản chi đã được ghi nhận.

## 3. Quy tắc nghiệp vụ

### 3.1. Vật tư và lô hàng

- Một vật tư có thể có nhiều lô hàng.
- Mỗi lô thuộc đúng một khách sạn và một vật tư.
- Lô có các thông tin: mã lô nội bộ, ngày nhập, số lượng nhập, số lượng còn lại, đơn giá nhập, hạn dùng (nếu có), khoản chi nguồn (nếu có) và trạng thái.
- Vật tư không có hạn dùng, ví dụ khăn hoặc đồ dùng lâu bền, được phép tạo lô không có hạn dùng.
- Vật tư có hạn dùng phải nhập hạn dùng khi nhập kho. Hạn dùng phải sau ngày nhập.
- `inventory_items.quantity` tiếp tục là số tổng để giữ tương thích với chức năng hiện có, nhưng phải được cập nhật từ các biến động/lô hợp lệ, không còn là nguồn lịch sử duy nhất.

### 3.2. Nhập kho từ chi phí

- Khi tạo chi phí và chọn “đồng bộ vào kho”, hệ thống tạo một **lô nhập** thay vì chỉ cộng số trực tiếp vào vật tư.
- Nếu đồng bộ dịch vụ, vật tư vẫn liên kết với dịch vụ như hiện tại; việc đó không tạo thêm lô thứ hai.
- Người dùng chọn “Có theo dõi hạn dùng” cho lần nhập. Khi bật, hạn dùng là bắt buộc; khi tắt, không hiển thị trường hạn dùng.
- Hệ thống tạo một biến động kho loại `Nhập kho`, có liên kết tới khoản chi và lô vừa tạo.

### 3.3. Dùng dịch vụ/minibar

- Khi gọi món hoặc cập nhật số lượng dịch vụ, hệ thống chỉ được phân bổ từ các lô còn hàng và chưa hết hạn.
- Thứ tự xuất kho là **FEFO**: lô có hạn dùng gần nhất được dùng trước; lô không có hạn dùng dùng sau các lô có hạn dùng hợp lệ.
- Một lần gọi món có thể lấy hàng từ nhiều lô; hệ thống phải lưu chi tiết phân bổ để khi giảm/hủy món có thể trả lại đúng các lô đã dùng.
- Nếu tổng hàng còn sử dụng được không đủ, giữ nguyên hành vi từ chối thao tác; không được trừ một phần rồi báo lỗi.
- Lô đã hết hạn không được chọn để phân bổ cho dịch vụ, kể cả khi `inventory_items.quantity` tổng vẫn còn dương.

### 3.4. Hàng quá hạn, hỏng hoặc thất thoát

- Đến ngày quá hạn, lô chuyển sang trạng thái “Đã quá hạn” để cảnh báo; số lượng chưa bị tự trừ.
- Nhân viên tạo phiếu “Hủy hàng” khi đã loại hàng thực tế khỏi kho. Phiếu bắt buộc: lô, số lượng và lý do.
- Lý do mặc định gồm: `Quá hạn sử dụng`, `Hư hỏng`, `Thất thoát`, `Kiểm kê điều chỉnh`; có ô ghi chú bổ sung.
- Số lượng hủy không vượt quá số lượng còn lại của lô. Sau khi xác nhận, giảm số lượng lô, giảm tồn tổng, tạo biến động `Hủy hàng` và audit log.
- Nếu lô đã hết số lượng còn lại, trạng thái là `Đã hết`; nếu chưa hết nhưng đã quá hạn, vẫn hiển thị là `Đã quá hạn`.
- Không được xóa phiếu hủy. Nếu ghi nhầm, Admin tạo phiếu điều chỉnh tăng/giảm mới với lý do bắt buộc.

### 3.5. Sửa hoặc xóa chi phí đã đồng bộ kho

- Không tự động trừ lại kho khi xóa một khoản chi đã từng đồng bộ. Hàng của lần nhập đó có thể đã được dùng hoặc hủy.
- Chi phí đã đồng bộ kho không có nút xóa trực tiếp. Thay bằng thao tác `Hủy ghi nhận chi phí`, bắt buộc lý do và lưu audit.
- Hủy ghi nhận chi phí chỉ làm mất hiệu lực sổ chi phí; **không** tự thay đổi tồn kho. Nếu cần xử lý hàng thực tế, người dùng tạo phiếu điều chỉnh kho riêng.
- Chưa hỗ trợ sửa trực tiếp phiếu nhập đã phát sinh sử dụng. Admin dùng điều chỉnh kho và/hoặc hủy ghi nhận chi phí để đảm bảo có vết đối soát.

## 4. Mô hình dữ liệu đề xuất

### 4.1. `inventory_batches`

| Trường | Ý nghĩa |
|---|---|
| `id`, `hotel_id`, `inventory_item_id` | Định danh và tenant scope |
| `expense_id` (nullable) | Khoản chi sinh ra lô, nếu có |
| `batch_code` | Mã lô nội bộ, duy nhất trong một khách sạn |
| `received_at` | Ngày nhập thực tế |
| `expires_at` (nullable) | Hạn dùng |
| `quantity_received` | Số lượng nhập ban đầu |
| `quantity_available` | Số lượng còn lại trong lô |
| `unit_cost` | Giá nhập một đơn vị tại thời điểm nhập |
| `status` | `active`, `expired`, `depleted`, `voided` |
| `created_at`, `created_by` | Truy vết |

### 4.2. `inventory_movements`

| Trường | Ý nghĩa |
|---|---|
| `id`, `hotel_id`, `inventory_item_id`, `batch_id` | Phạm vi và lô bị tác động |
| `movement_type` | `receipt`, `consumption`, `disposal`, `adjustment_in`, `adjustment_out` |
| `quantity_delta` | Dương khi tăng, âm khi giảm |
| `reason`, `note` | Lý do/ngữ cảnh bắt buộc theo từng loại |
| `expense_id`, `booking_service_id` (nullable) | Nguồn nghiệp vụ nếu có |
| `created_by`, `created_at` | Truy vết |

### 4.3. Liên kết tiêu dùng dịch vụ

Thêm bảng chi tiết phân bổ giữa dòng dịch vụ booking và lô kho. Mỗi dòng lưu `booking_service_id`, `batch_id` và `quantity`. Bảng này bảo đảm giảm/hủy số lượng dịch vụ hoàn trả đúng lô ban đầu, thay vì tăng lại vào một lô bất kỳ.

## 5. Giao diện vận hành

Thiết kế bám dashboard nội bộ hiện có: thông tin dày vừa phải, màu trạng thái có nhãn chữ, biểu mẫu có label rõ ràng, không chỉ dựa vào màu.

### 5.1. Trang Kho hàng

- Thêm ba chỉ số đầu trang: `Sắp hết hạn`, `Đã quá hạn`, `Chờ xử lý hủy`.
- Mỗi dòng vật tư hiển thị: tồn dùng được, tồn đã quá hạn, lô gần hết hạn và trạng thái cảnh báo bằng nhãn chữ.
- Nút “Xem lô” mở drawer/modal danh sách lô theo vật tư: mã lô, hạn dùng, còn lại, nguồn nhập và lịch sử biến động.
- Nút “Hủy hàng” chỉ xuất hiện cho Admin; form mặc định chọn lô, giới hạn số lượng theo tồn lô và yêu cầu lý do.
- Bộ lọc: tất cả, sắp hết hạn (7/30 ngày), quá hạn, hết hàng; bộ lọc không làm mất trạng thái tìm kiếm hiện tại.

### 5.2. Form thêm chi phí/nhập kho

- Khi chọn đồng bộ kho, hiển thị nhóm “Thông tin lô nhập”.
- Có checkbox `Theo dõi hạn dùng`; chỉ khi bật mới bắt buộc nhập hạn dùng.
- Hiển thị helper text: hạn dùng dùng để cảnh báo và ngăn xuất kho sau khi hết hạn.
- Lỗi hiển thị cạnh trường: thiếu hạn dùng, hạn dùng không hợp lệ, số lượng không hợp lệ hoặc mã vật tư trùng sai tenant.

### 5.3. Cảnh báo

- Cảnh báo hiển thị trong kho; không dùng modal chặn công việc khi chỉ là “sắp hết hạn”.
- Trạng thái quá hạn dùng màu cảnh báo/destructive kèm chữ “Đã quá hạn”; không chỉ dùng màu.
- Trong luồng gọi món, nếu không đủ hàng còn hạn: thông báo nêu rõ sản phẩm và số lượng khả dụng, không tiết lộ dữ liệu khách sạn khác.
- Tất cả nút icon có `aria-label`, trạng thái tải/lỗi có nội dung chữ, và thao tác hủy yêu cầu xác nhận rõ ràng.

## 6. Quyền hạn và audit

- Staff: xem tồn và cảnh báo theo quyền hiện hữu; không được hủy hàng, điều chỉnh kho hoặc hủy ghi nhận chi phí.
- Admin: nhập lô, hủy hàng, điều chỉnh kho và hủy ghi nhận chi phí trong khách sạn của mình.
- Master Admin: chỉ xem/truy cập khi vào ngữ cảnh khách sạn; không có kho tổng toàn hệ thống.
- Audit bắt buộc cho: tạo lô, tiêu dùng dịch vụ theo lô, hủy hàng, điều chỉnh tồn, hủy ghi nhận chi phí và thay đổi trạng thái lô.

## 7. Tiêu chí nghiệm thu

1. Nhập 200 chai nước có hạn dùng tạo đúng một lô và tăng tồn tổng 200.
2. Gọi món ưu tiên lô gần hết hạn nhưng chưa quá hạn; không sử dụng lô đã quá hạn.
3. Hủy 30 chai quá hạn giảm 30 ở đúng lô và tồn tổng, lưu lý do, người thực hiện và audit.
4. Không thể hủy quá số còn lại, hủy lô thuộc khách sạn khác, hoặc gọi món vượt tồn còn hạn.
5. Giảm/hủy số lượng món hoàn lại đúng lô đã bị trừ ban đầu.
6. Xóa/hủy ghi nhận chi phí không tự làm thay đổi tồn kho; mọi điều chỉnh tồn có chứng từ riêng.
7. Cảnh báo 7/30 ngày, quá hạn và danh sách lô hoạt động đúng trong phạm vi từng khách sạn.
8. Các giao diện mới kiểm tra được bằng test phù hợp và `bb-browser` ở desktop trước khi bàn giao.

## 8. Thứ tự triển khai đề xuất

1. Migration/model cho lô hàng, biến động kho và phân bổ dịch vụ theo lô.
2. TDD cho nhập lô, FEFO, chặn lô quá hạn, hủy hàng và tenant isolation.
3. Chuyển luồng nhập chi phí đồng bộ kho sang tạo lô/biến động.
4. Chuyển luồng gọi món và cập nhật món sang phân bổ/hoàn trả theo lô.
5. Thêm UI kho, cảnh báo, phiếu hủy và hủy ghi nhận chi phí; kiểm tra desktop bằng `bb-browser`.
6. Chạy regression toàn bộ và tạo commit riêng theo từng hạng mục hoàn chỉnh.
