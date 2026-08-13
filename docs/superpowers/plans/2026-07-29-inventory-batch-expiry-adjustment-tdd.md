# Kế hoạch TDD: Kho theo lô, hạn dùng và điều chỉnh tồn

**Spec nguồn:** `docs/superpowers/specs/2026-07-29-inventory-batch-expiry-adjustment-design.md`  
**Trạng thái:** Chờ review, chưa triển khai  
**Nguyên tắc thực hiện:** Mỗi hạng mục bên dưới phải đi theo thứ tự test đỏ → triển khai tối thiểu → refactor → test xanh → kiểm tra phù hợp → commit tiếng Anh riêng. Không chuyển sang hạng mục kế tiếp khi hạng mục hiện tại chưa hoàn tất.

## Hiện trạng kỹ thuật đã kiểm tra

- `InventoryItem` chỉ lưu số lượng tổng trong `quantity`; chưa có lô hàng, hạn dùng hoặc ledger biến động.
- `expense_controller.add_expense` cộng thẳng `InventoryItem.quantity` khi chọn đồng bộ kho; nguồn chi phí chỉ được gắn gián tiếp qua `[KHO:<mã>]` trong mô tả.
- `warehouse_controller` cho tạo/sửa/nhập thêm/xóa vật tư bằng cách sửa trực tiếp `quantity`.
- `inventory_service` kiểm tra, trừ và hoàn theo `InventoryItem`, chưa thể biết lô nào đã được dùng.
- `BookingService` chưa có liên kết đến lô kho, nên không thể hoàn đúng lô sau khi giảm món.

## Quy ước dữ liệu áp dụng cho toàn kế hoạch

- `InventoryBatch`: lô hàng; số lượng còn lại là nguồn chi tiết của tồn kho.
- `InventoryMovement`: chứng từ biến động bất biến, loại `receipt`, `consumption`, `disposal`, `adjustment_in`, `adjustment_out`.
- `BookingServiceBatchAllocation`: số lượng một dòng dịch vụ đã lấy từ từng lô.
- Tồn tổng `InventoryItem.quantity` được giữ để tương thích code cũ, nhưng mọi thay đổi số lượng mới phải thông qua service quản lý lô/ledger.
- FEFO: xuất lô có hạn gần nhất trước; lô không hạn chỉ dùng sau các lô còn hạn.
- Lô hết hạn không tự bị giảm tồn; chỉ bị loại khỏi hàng khả dụng cho gọi món và chờ phiếu hủy/điều chỉnh.

## Hạng mục 1 — Nền dữ liệu lô hàng và ledger

**Mục tiêu:** Có schema và service nền tảng an toàn, chưa thay đổi giao diện vận hành.

### Test đỏ trước

Tạo `tests/test_inventory_batches.py` với các ca:

1. Tạo lô thuộc vật tư của khách sạn A làm tăng `quantity_available`, `InventoryItem.quantity` và sinh đúng một movement `receipt`.
2. Không thể tạo lô cho vật tư của khách sạn khác.
3. Lô theo dõi hạn dùng phải có `expires_at` sau `received_at`; lô không theo dõi hạn dùng được phép để trống.
4. Backfill vật tư có tồn cũ thành một lô `Tồn đầu` không hạn dùng, không làm đổi tổng tồn.
5. Hủy/điều chỉnh không được làm số lượng lô hoặc tồn tổng âm.

Chạy: `pytest tests/test_inventory_batches.py -q` và xác nhận đỏ vì model/service chưa tồn tại.

### Triển khai tối thiểu

1. Thêm model, relationship và migration cho ba bảng nêu trên.
2. Viết `services/inventory_batch_service.py` với các hàm tạo lô, tính tồn khả dụng, tạo movement và đồng bộ số tổng.
3. Viết migration backfill “Tồn đầu” cho các `InventoryItem.quantity > 0` hiện có, không gán hạn dùng giả.
4. Tạo migration có rollback phù hợp; kiểm tra unique theo tenant cho mã lô.

### Kiểm tra và commit

- Chạy test hạng mục, `pytest tests/test_order_submission.py -q` và toàn bộ test suite.
- Commit riêng: `feat: add inventory batch tracking`.

## Hạng mục 2 — Nhập kho theo lô từ Kho và Chi phí

**Mục tiêu:** Mọi đường tăng tồn mới đều sinh lô và ledger.

### Test đỏ trước

Mở rộng `tests/test_inventory_batches.py` và thêm `tests/test_expense_inventory_batches.py`:

1. API nhập thêm kho tạo lô, receipt movement và tăng tổng tồn đúng một lần.
2. API tạo vật tư với số lượng ban đầu tạo lô `Tồn đầu/nhập mới` có nguồn rõ ràng.
3. API tạo chi phí đồng bộ kho tạo lô liên kết `expense_id`, lưu đơn giá, hạn dùng và quantity ban đầu/chưa dùng.
4. Chi phí đồng bộ vật tư có hạn dùng nhưng thiếu hạn dùng trả lỗi 400 với thông báo trường cần sửa.
5. Nhập kho của hotel A không thể tạo hoặc đọc lô thuộc hotel B.
6. Liên kết dịch vụ sai nhóm vẫn bị chặn như hiện có.

### Triển khai tối thiểu

1. Thay việc cộng thẳng `InventoryItem.quantity` trong `expense_controller.py` và `warehouse_controller.py` bằng service lô hàng.
2. Mở rộng payload nhập kho: ngày nhập, checkbox theo dõi hạn dùng, hạn dùng, đơn giá; validate phía server là nguồn xác thực cuối cùng.
3. Bổ sung API trả về thông tin tổng: tồn dùng được, tồn quá hạn, lô sắp hết hạn.
4. Không sửa trực tiếp `quantity` qua API cập nhật vật tư; endpoint cập nhật chỉ sửa metadata. Thay đổi số lượng phải đi qua nhập kho hoặc điều chỉnh ở hạng mục 4.

### Kiểm tra và commit

- Test mới, `tests/test_audit_log.py`, `tests/test_tenant_isolation.py`, toàn suite.
- Commit riêng: `feat: record inventory receipts by batch`.

## Hạng mục 3 — Xuất kho FEFO cho dịch vụ/minibar

**Mục tiêu:** Gọi món chỉ dùng tồn còn hạn và có thể hoàn đúng lô.

### Test đỏ trước

Tạo `tests/test_inventory_batch_consumption.py`:

1. Hai lô cùng một vật tư: gọi món ưu tiên lô hết hạn sớm hơn nhưng vẫn còn hạn.
2. Lô quá hạn không được tính vào tồn khả dụng; gọi món bị từ chối nếu chỉ còn lô quá hạn.
3. Một lần gọi món lớn hơn một lô được phân bổ sang nhiều lô, tạo đúng movement và allocation cho từng lô.
4. Cập nhật giảm số lượng món hoàn lại đúng các lô đã bị trừ, theo allocation, không hoàn vào lô tùy ý.
5. Cập nhật tăng số lượng món tiếp tục FEFO và không có mutation một phần khi không đủ tồn.
6. Dịch vụ không quản lý kho vẫn gọi món bình thường.
7. Tenant A không thể tiêu dùng hoặc hoàn hàng trong lô tenant B.

Chạy test đỏ trước khi thay `services/inventory_service.py`.

### Triển khai tối thiểu

1. Chuyển `validate_inventory`, `deduct_inventory`, `restore_inventory` sang gọi `inventory_batch_service`.
2. Lưu allocation theo `BookingService`; xử lý cả luồng tạo order và cập nhật dịch vụ đoàn đã có trong `booking_controller.py`.
3. Bảo đảm transaction rollback đầy đủ nếu một line không đủ tồn còn hạn.
4. Ghi audit phù hợp nhưng không tăng trùng log cho từng lô khi một thao tác người dùng chỉ có một ý nghĩa nghiệp vụ.

### Kiểm tra và commit

- Test mới, `tests/test_order_submission.py`, `tests/test_checkout_idempotency.py`, toàn suite.
- Commit riêng: `feat: allocate service inventory by expiry batch`.

## Hạng mục 4 — Hủy hàng, điều chỉnh tồn và bảo vệ lịch sử chi phí

**Mục tiêu:** Xử lý hàng quá hạn/hư hỏng thực tế mà không làm mất dấu vết kế toán hoặc kho.

### Test đỏ trước

Tạo `tests/test_inventory_disposal.py` và mở rộng test chi phí:

1. Hủy 30 đơn vị từ lô quá hạn giảm đúng lô, tồn tổng và tạo movement `disposal` có lý do/người thực hiện.
2. Không thể hủy số lượng lớn hơn số còn lại, số âm/0, lô đã hết, hoặc lô khác tenant.
3. Điều chỉnh tăng/giảm cần lý do; không thể làm tồn âm.
4. Hủy ghi nhận chi phí đồng bộ kho không thay đổi tồn/lô và tạo audit.
5. Chi phí đã đồng bộ kho bị chặn xóa trực tiếp; chi phí không đồng bộ giữ hành vi xóa hiện có hoặc chuyển sang hủy ghi nhận theo quyết định trong spec.
6. Admin có quyền; Staff bị chặn ở API, không chỉ bị ẩn nút.

### Triển khai tối thiểu

1. API `POST /api/warehouse/batches/<id>/dispose` và API điều chỉnh tồn có validate reason, scope và transaction.
2. Thay xóa chi phí đã đồng bộ bằng trạng thái/phiếu hủy ghi nhận, thêm migration/model tối thiểu nếu cần trạng thái hiệu lực.
3. Chặn xóa vật tư khi còn lô hoặc movement lịch sử; chỉ cho archive/ẩn sau này nếu cần, không xóa dữ liệu có đối soát.
4. Thêm audit action tiếng Việt đã map tại trang nhật ký.

### Kiểm tra và commit

- Test mới, `tests/test_staff_permissions.py`, `tests/test_audit_log.py`, toàn suite.
- Commit riêng: `feat: add inventory disposal controls`.

## Hạng mục 5 — Giao diện kho và chi phí

**Mục tiêu:** Nhân viên thấy cảnh báo rõ, Admin thao tác hủy hàng/nhập lô an toàn trên desktop/tablet.

### Test đỏ trước

Tạo `tests/test_warehouse_batch_ui.py` kiểm tra server-rendered markup và quyền:

1. Trang kho có KPI “Sắp hết hạn”, “Đã quá hạn”, bộ lọc trạng thái và nút xem lô.
2. Modal nhập kho có label, checkbox theo dõi hạn dùng, input hạn dùng và vùng lỗi cạnh trường.
3. Modal hủy hàng có số lượng, lý do, xác nhận; Staff không có action này.
4. Trang chi phí hiển thị trạng thái đã đồng bộ kho và không đưa nút xóa trực tiếp cho chi phí đã đồng bộ.

### Triển khai tối thiểu

1. Cập nhật `templates/warehouse/index.html`, `templates/reports/expenses.html` và JS/CSS liên quan.
2. Theo design system hiện có: dashboard dày vừa phải, khoảng cách 8px, màu semantic kèm nhãn chữ, nút hủy tách biệt màu destructive, không dùng icon không có nhãn truy cập.
3. Trạng thái tải/lỗi/rỗng rõ ràng; disable nút submit khi đang gửi; focus vào trường lỗi đầu tiên.
4. Drawer/modal lô hiển thị lịch sử, hạn dùng, số còn lại, nguồn nhập. Giữ filter và vị trí trang khi đóng modal.

### Kiểm tra giao diện bắt buộc

Sau test backend/UI xanh, dùng `bb-browser` desktop để kiểm tra:

1. Nhập lô có hạn dùng, lỗi validation và feedback thành công.
2. Danh sách lô sắp hết hạn/quá hạn, bộ lọc và empty state.
3. Hủy hàng với xác nhận/lý do; tồn và lịch sử cập nhật.
4. Staff không thấy và không thực hiện được thao tác quản trị.
5. Console không có lỗi JavaScript, bố cục không tràn ở desktop/tablet.

### Commit

- Chạy toàn suite và `git diff --check`.
- Commit riêng: `feat: add inventory expiry operations UI`.

## Hạng mục 6 — Regression và bàn giao

1. Chạy migration trên database local có dữ liệu mẫu sau khi tạo bản backup thủ công của database.
2. Kiểm tra lại tenant isolation cho lô, movement, allocation và API hủy hàng.
3. Chạy `pytest -q`, kiểm tra bb-browser các luồng thay đổi, rà `git status` để không commit `TASKS.md`, `feature.md` hoặc các spec/plan chờ review.
4. Cập nhật `TASKS.md` từ `[ ]` sang `[x]` sau khi toàn bộ hạng mục hoàn tất; file theo dõi chỉ commit khi bạn yêu cầu.

## Những phần chủ động không làm trong đợt này

- Tự động hủy hàng chỉ vì đã qua hạn: không làm, vì cần xác nhận đã loại hàng thực tế.
- PDF/Excel, backup/restore, hoàn cọc tự động: giữ ngoài phạm vi.
- Quản lý nhà cung cấp, giá vốn bình quân, barcode/QR lô và kiểm kê bằng máy quét: để backlog sau khi luồng lô cơ bản ổn định.
