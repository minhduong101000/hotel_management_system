# Spec: Làm mới thị giác giao diện Hotel POS Pro

**Ngày:** 02-08-2026

**Trạng thái:** Đã chốt yêu cầu thiết kế, chờ lập kế hoạch TDD để triển khai

**Phạm vi:** Giao diện web nội bộ cho Hotel admin và Staff; giữ tính nhất quán với Master Console

## 1. Quan hệ với tài liệu hiện có

Spec này mở rộng các tài liệu:

- `docs/superpowers/specs/2026-07-26-web-ui-ux-redesign-design.md`.
- `docs/superpowers/specs/2026-07-30-modal-workflow-design.md`.
- `design-system/hotel-pos-pro/MASTER.md`.

Khi có khác biệt, spec này được ưu tiên cho **màu sắc, typography, button, spacing, trạng thái dữ liệu và mức độ polish thị giác**. Các quyết định đã chốt về nghiệp vụ, cấu trúc modal, booking, checkout, phân quyền và tenant scope vẫn giữ nguyên.

## 2. Căn cứ đánh giá

Spec được xây dựng từ:

- Kiểm tra trực tiếp code trong `templates/`, `static/css/style.css` và các file JavaScript liên quan.
- Kiểm tra bằng `bb-browser` ở viewport desktop 1920 × 945 cho đăng nhập, sơ đồ phòng, Timeline, khách hàng, kho, modal nhập vật tư, doanh thu, chi phí, sổ quỹ, hóa đơn và nhân sự.
- Định hướng `ui-ux-pro-max`: dashboard vận hành mật độ cao, tương phản WCAG AA, touch target tối thiểu 44 px, khoảng cách giữa vùng bấm tối thiểu 8 px và motion nhẹ 150–300 ms.

Các vấn đề chính của baseline:

- Button giữa các trang có kích thước, màu và khoảng cách chưa đồng nhất.
- Màu xanh cũ tại trang đăng nhập không cùng nhận diện teal/navy của ứng dụng.
- Một số màn hình rỗng chỉ hiển thị một dòng chữ trong vùng trắng lớn.
- Báo cáo vẫn dựng biểu đồ và trục số khi không có dữ liệu.
- Nhiều template còn dùng màu Bootstrap, inline style và màu header modal riêng.
- Một số icon-only button và nút đóng modal chưa có accessible name; một số label chưa liên kết với input.

## 3. Mục tiêu

- Làm giao diện tươi sáng, rõ ràng và hiện đại hơn nhưng vẫn phù hợp công cụ vận hành khách sạn.
- Chuẩn hóa button, spacing, card, toolbar, filter, form, modal và trạng thái dữ liệu.
- Làm nổi bật hành động chính mà không biến toàn bộ màn hình thành nhiều CTA cạnh tranh.
- Tăng tốc độ quét thông tin ở sơ đồ phòng, Timeline, bảng nghiệp vụ và báo cáo.
- Đảm bảo keyboard, screen reader, contrast và touch target ở mức WCAG AA phù hợp.
- Không làm thay đổi nghiệp vụ, API, dữ liệu, quyền truy cập hoặc framework Bootstrap/Font Awesome hiện tại.

## 4. Ngoài phạm vi

- Không bổ sung dark mode trong đợt này.
- Không thay Bootstrap, Font Awesome, Flask/Jinja hoặc kiến trúc JavaScript hiện tại.
- Không thêm nghiệp vụ, endpoint hoặc trường database chỉ để trang trí giao diện.
- Không thiết kế app mobile riêng; màn hình 375 px chỉ cần không vỡ layout và không tràn ngang.
- Không thay đổi quy tắc booking, check-in/check-out, tính tiền, kho, chi phí, báo cáo hoặc phân quyền.
- Không thêm animation trang trí phức tạp, parallax hoặc thư viện motion mới.

## 5. Định hướng thiết kế

Tên định hướng: **Hospitality Operations — Bright & Calm**.

- Phong cách: data-dense dashboard, sáng, sạch và dễ quét.
- Variance: 4/10 — cân bằng, hiện đại, không phá cách quá mức.
- Motion: 3/10 — chỉ dùng micro-interaction có ý nghĩa.
- Density: 8/10 — giữ mật độ cần thiết cho lễ tân và vận hành.
- Navy dùng cho nhận diện và điều hướng; teal dùng cho CTA chính; blue dùng cho thông tin/điều hướng theo thời gian; màu semantic chỉ dùng đúng nghiệp vụ.
- Cảm giác tươi sáng đến từ nền sáng, surface tint, border rõ và shadow nhẹ; không làm nhạt CTA đến mức giảm tương phản.
- Mỗi màn hình hoặc mỗi vùng thao tác chỉ có một primary action.

## 6. Design token bắt buộc

### 6.1 Màu sắc

| Token | Giá trị | Mục đích |
|---|---:|---|
| `--color-brand-navy` | `#18212F` | Sidebar, thương hiệu, heading đậm |
| `--color-action` | `#0F766E` | Primary button và CTA chính |
| `--color-action-hover` | `#115E59` | Hover/pressed của CTA chính |
| `--color-info` | `#2563EB` | Điều hướng thời gian, thông tin, liên kết |
| `--color-success` | `#15803D` | Hoàn tất, sẵn sàng, thu tiền thành công |
| `--color-warning` | `#D97706` | Cảnh báo cần chú ý |
| `--color-warning-surface` | `#FFFBEB` | Nền cảnh báo; chữ dùng màu tối |
| `--color-danger` | `#DC2626` | Xóa, hủy, lỗi và hành động phá hủy |
| `--color-background` | `#F8FAFC` | Nền ứng dụng |
| `--color-surface` | `#FFFFFF` | Card, bảng, modal |
| `--color-surface-teal` | `#F0FDFA` | KPI/empty-state teal nhạt |
| `--color-surface-blue` | `#EFF6FF` | KPI/thông tin blue nhạt |
| `--color-border` | `#E2E8F0` | Viền và phân tách |
| `--color-text` | `#0F172A` | Chữ chính |
| `--color-muted-text` | `#64748B` | Chữ phụ |
| `--color-focus-ring` | `rgba(37, 99, 235, 0.32)` | Focus keyboard |

Quy tắc:

- Chữ thường phải đạt tương phản tối thiểu 4.5:1.
- Warning button dùng nền amber với chữ tối, không dùng chữ trắng nếu không đạt contrast.
- Không dùng màu làm tín hiệu duy nhất; trạng thái luôn có label và khi phù hợp có thêm icon.
- Không thêm raw hex mới trong từng template nếu đã có token tương ứng.
- Biểu đồ có thể dùng bảng màu riêng nhưng phải được khai báo tập trung và có legend/label.

### 6.2 Typography

- Font chính: `Be Vietnam Pro`.
- Fallback: `Noto Sans`, sau đó `sans-serif`.
- Không chuyển sang Lora/Raleway hoặc font mono cho heading vì không phù hợp mật độ và khả năng đọc tiếng Việt của ứng dụng vận hành hiện tại.

| Vai trò | Kích thước desktop | Weight | Line-height |
|---|---:|---:|---:|
| Page title | 18–20 px | 700 | 1.3 |
| Section title | 16 px | 650–700 | 1.4 |
| Body | 14 px | 400 | 1.5 |
| Label/button | 13–14 px | 600 | 1.3 |
| Caption/helper | 12 px | 400–500 | 1.45 |
| KPI value | 24–28 px | 700 | 1.2 |

- Body và input tăng tối thiểu lên 16 px tại viewport nhỏ để tránh zoom tự động.
- Giá tiền, số lượng, timer và KPI dùng `font-variant-numeric: tabular-nums`.
- Không viết hoa toàn bộ button; chỉ dùng uppercase cho menu header hoặc label ngắn.

### 6.3 Spacing

| Token | Giá trị | Cách dùng |
|---|---:|---|
| `--space-1` | `4px` | Khoảng cách rất nhỏ |
| `--space-2` | `8px` | Icon–text, button group |
| `--space-3` | `12px` | Thành phần trong toolbar |
| `--space-4` | `16px` | Field, card compact |
| `--space-5` | `24px` | Section và page padding desktop |
| `--space-6` | `32px` | Phân tách nhóm nội dung lớn |

Quy tắc:

- Page padding: 24 px ở desktop, 16 px ở tablet và 12 px ở màn hình nhỏ.
- Khoảng cách giữa các section: 24 px; giữa các card cùng nhóm: 16 px.
- Button group có `gap: 8px`; toolbar nhiều nhóm có `gap: 12px` và ngắt nhóm bằng whitespace hoặc divider.
- Form field có khoảng cách dọc 16 px; label cách input 6 px; helper/error cách input 6 px.
- Table cell mặc định 12 px dọc và 14 px ngang.
- Không thêm margin/padding tùy ý ngoài thang token nếu không có lý do được ghi chú.

### 6.4 Radius, shadow và motion

- Button/input: radius 10 px.
- Card/filter/table container: radius 12 px.
- Modal: radius 14–16 px.
- Shadow card: `0 2px 10px rgba(15, 23, 42, 0.06)`.
- Shadow button hover: `0 6px 14px rgba(15, 118, 110, 0.18)` cho primary action.
- Shadow modal: `0 24px 56px rgba(24, 33, 47, 0.26)`.
- Transition chuẩn: 180 ms; khoảng cho phép 150–250 ms.
- Hover button được nâng tối đa 1 px; active trở về vị trí gốc.
- Motion chỉ dùng `transform` và `opacity`; phải tắt hoặc giảm khi `prefers-reduced-motion: reduce`.

## 7. Hệ thống button

### 7.1 Kích thước

| Biến thể | Chiều cao | Padding ngang | Trường hợp dùng |
|---|---:|---:|---|
| `btn-sm` | 36 px desktop; 44 px dưới 992 px | 12 px | Filter phụ, thao tác bảng có text |
| `btn-md` | 44 px | 16 px | Mặc định |
| `btn-lg` | 48 px | 20 px | Login, CTA quan trọng |
| Icon-only | 44 × 44 px | 0 | Sửa, xóa, làm mới, đóng modal |

- Icon 16–18 px; khoảng cách icon–text 8 px.
- Hai vùng bấm liền nhau cách tối thiểu 8 px.
- Không dùng icon-only khi text ngắn giúp người dùng hiểu nhanh hơn.

### 7.2 Biến thể

- `Primary`: teal solid, chữ trắng; dùng cho hành động chính như Lưu, Thêm, Xác nhận.
- `Secondary`: nền trắng, viền slate, chữ slate; dùng cho Hủy, Quay lại, Xóa lọc.
- `Info`: blue solid hoặc blue outline; dùng cho điều hướng thời gian, Xem chi tiết, Làm mới khi cần nhấn mạnh.
- `Success`: xanh lá; chỉ dùng khi hành động mang nghĩa hoàn tất nghiệp vụ như Nhận phòng hoặc Thanh toán.
- `Warning`: amber với chữ tối; dùng khi cần xác nhận chú ý nhưng chưa phá hủy.
- `Danger`: đỏ; chỉ dùng cho Xóa, Hủy booking, Hủy hàng, Void chi phí và hành động không dễ hoàn tác.
- `Ghost`: nền trong suốt, chữ slate/blue; dùng cho hành động cấp ba và toolbar phụ.

### 7.3 Trạng thái

- `hover`: đổi màu có kiểm soát, tăng shadow và nâng tối đa 1 px.
- `active`: trở về vị trí gốc, shadow giảm.
- `focus-visible`: outline 3 px, offset 2 px.
- `disabled`: opacity 0.45–0.5, `cursor: not-allowed`, không nhận click.
- `loading`: giữ nguyên chiều rộng, vô hiệu hóa click, hiển thị spinner và `aria-busy="true"`.
- `success/error`: phản hồi bằng toast hoặc status region; không đổi nhãn button vĩnh viễn nếu làm người dùng mất ngữ cảnh.

### 7.4 Quy tắc bố trí

- Một màn hình có tối đa một primary CTA trong page header.
- Footer modal: secondary action bên trái primary action; danger action tách khỏi nhóm thường bằng khoảng cách hoặc vị trí riêng.
- Toolbar ưu tiên thứ tự: điều hướng/filter → action phụ → action chính.
- Table row không hiển thị quá hai button trực tiếp; phần còn lại đưa vào action menu nếu nghiệp vụ cho phép.
- Không dùng màu success hoặc danger chỉ để “làm đẹp”.

## 8. Component và trạng thái dùng chung

### 8.1 Page shell

Mọi trang chuẩn có thứ tự:

1. `PageHeader`: icon, H1, mô tả ngắn và tối đa hai action cấp trang.
2. `FilterBar` hoặc toolbar nếu trang có tìm kiếm/lọc.
3. KPI/status summary nếu có giá trị vận hành.
4. Nội dung chính: room grid, timeline, table, chart hoặc form.
5. `DataState`: loading, empty hoặc error nằm trong chính vùng nội dung.

### 8.2 Empty state

Empty state gồm:

- Icon có tính mô tả, không dùng emoji.
- Tiêu đề ngắn, ví dụ `Kho chưa có vật tư`.
- Một câu giải thích hoặc hướng dẫn tiếp theo.
- Tối đa một CTA phù hợp với quyền và nghiệp vụ hiện có.

Không để một dòng chữ nghiêng đơn độc giữa vùng trắng lớn. Empty state của chart phải thay thế toàn bộ canvas/trục khi không có dữ liệu.

### 8.3 Loading và error

- Tác vụ trên 300 ms có spinner hoặc skeleton phù hợp.
- Table/chart dùng skeleton giữ kích thước để tránh layout shift.
- Lỗi tải dữ liệu có nguyên nhân dễ hiểu và CTA `Thử lại`.
- Không dùng `alert()` làm phản hồi chính.
- Vùng status dùng `role="status"`, `role="alert"` hoặc `aria-live` đúng mức độ.

### 8.4 Card, KPI và status badge

- Card mặc định nền trắng; surface tint chỉ dùng để phân nhóm hoặc tạo điểm nhấn nhẹ.
- KPI cùng chiều cao, cùng vị trí label/value/icon và có kỳ dữ liệu rõ ràng.
- KPI tài chính ưu tiên giá trị và biến động so với kỳ trước nếu API hiện có đã cung cấp dữ liệu; không mở rộng API chỉ cho đợt visual refresh.
- Status badge luôn có text; các trạng thái quan trọng có icon hoặc ký hiệu bổ sung.

## 9. Yêu cầu theo màn hình

### 9.1 Đăng nhập

- Đồng bộ navy/teal với ứng dụng; bỏ màu xanh legacy riêng.
- Desktop rộng dùng card 420–460 px hoặc bố cục hai vùng cân đối; không để card nhỏ lọt thỏm trong khoảng trắng lớn.
- Button đăng nhập dùng `btn-lg`, full width, có loading và disabled state.
- Bổ sung nút hiện/ẩn mật khẩu; label và autocomplete giữ đúng semantics.
- Thông báo đăng xuất/lỗi không làm thay đổi kích thước card đột ngột.

### 9.2 Sidebar và topbar

- Giữ sidebar navy; active item sáng và rõ nhưng không dùng glow mạnh.
- Nhóm menu theo Lễ tân, Dịch vụ & Kho, Quản trị; cho phép thu gọn nhóm khi cần ở đợt triển khai tương ứng.
- Tên khách sạn bị cắt phải có tooltip hoặc cách xem đầy đủ.
- Topbar không lặp thông tin không cần thiết; khu vực user có menu cho tài khoản và đăng xuất.
- Icon và text menu có cùng baseline, khoảng cách 10–12 px.

### 9.3 Sơ đồ phòng

- Toolbar dùng button 44 px, gap 8–12 px; filter, refresh và KPI trạng thái chia nhóm rõ.
- Room card giữ khả năng nhận biết trạng thái nhanh nhưng giảm cảm giác “nhiều mảng màu”: ưu tiên nền/tint ổn định, status rail/badge và label rõ.
- Danger red dành cho quá giờ/lỗi; không dùng đỏ cho trạng thái bình thường.
- Empty state có hướng dẫn và CTA hiện có phù hợp; không chỉ hiển thị `Không tìm thấy phòng nào`.
- Không thay đổi action hoặc dữ liệu booking đã chốt trong spec cũ.

### 9.4 Timeline

- Giữ timeline là vùng trọng tâm.
- Tách ba nhóm toolbar: điều hướng ngày, chế độ xem, filter/action.
- Button điều hướng và chế độ xem có chiều cao đồng nhất; active state không phụ thuộc màu duy nhất.
- Legend dùng badge nhẹ hơn, có icon/text và không cạnh tranh với toolbar.
- Empty state phân biệt rõ: chưa có phòng, không có booking theo bộ lọc, lỗi tải dữ liệu.

### 9.5 Khách hàng, hóa đơn và các bảng CRUD

- Dùng cùng `PageHeader`, `FilterBar`, button tạo mới và table shell.
- Search input và button không dính sát; button tìm kiếm không chiếm ưu tiên hơn button tạo mới.
- Action row có tooltip/accessible name; icon-only button 44 × 44 px.
- Cột tiền/số lượng canh phải và dùng tabular numbers.
- Empty, loading và error nằm trong table container, không làm biến mất header trang.

### 9.6 Kho, dịch vụ và giá phòng

- KPI hạn dùng/tồn kho dùng surface tint và border semantic thay vì card viền màu ngẫu nhiên.
- `Thêm vật tư`, `Thêm dịch vụ`, `Thêm rule` là primary CTA tương ứng.
- Modal tạo/sửa dùng teal header trung tính; red chỉ cho modal hủy/xóa, amber cho cảnh báo.
- Tất cả nút đóng modal có accessible name; tất cả label dùng `for` trỏ đúng input.
- Helper text và field group có khoảng cách thống nhất theo section 6.3.

### 9.7 Doanh thu, sổ quỹ và chi phí

- KPI cùng kích thước, màu sáng vừa phải và có label/kỳ dữ liệu rõ.
- Khi toàn bộ dữ liệu bằng rỗng, không dựng trục chart 0; thay bằng empty state.
- Chart có legend gần biểu đồ, tooltip giá trị chính xác và tóm tắt bằng text hoặc bảng dữ liệu tương ứng.
- Màu revenue/expense không chỉ phân biệt bằng xanh/đỏ; có label, kiểu nét hoặc marker khi cần.
- Filter ngày và button áp dụng/xóa lọc dùng cùng component giữa ba trang.

### 9.8 Nhân sự và Master Console

- Form tạo tài khoản và danh sách tài khoản dùng card, spacing và button system chung.
- Xóa user/hotel là danger action tách khỏi thao tác lưu/reset mật khẩu.
- Login Master và login hotel cùng typography, radius, input và feedback nhưng vẫn có nhãn ngữ cảnh khác nhau.

## 10. Accessibility và responsive

- Tương phản chữ thường tối thiểu 4.5:1; thành phần UI và text lớn tối thiểu 3:1.
- Mọi hành động dùng được bằng keyboard; thứ tự tab khớp thứ tự thị giác.
- Icon-only button có `aria-label`; tooltip không thay thế accessible name.
- Input có label liên kết bằng `for`/`id`; placeholder không phải label duy nhất.
- Touch target chính tối thiểu 44 × 44 px; khoảng cách vùng bấm tối thiểu 8 px.
- Focus ring không bị `overflow: hidden` cắt mất.
- Trạng thái không truyền đạt chỉ bằng màu.
- Hỗ trợ `prefers-reduced-motion`.
- Breakpoint cần kiểm tra: 375, 768, 1024, 1440 và 1920 px.
- Không có horizontal scroll toàn trang; table rộng được cuộn trong wrapper riêng.

## 11. Ưu tiên triển khai

### P0 — Nền thị giác dùng chung

- Token màu, spacing, typography, radius, shadow và motion.
- Button system đầy đủ trạng thái.
- PageHeader, FilterBar, DataState, KPI card và modal header/footer chung.

### P1 — Luồng có tần suất sử dụng cao

- Đăng nhập, sidebar/topbar.
- Sơ đồ phòng, Timeline.
- Khách hàng, hóa đơn.
- Kho và các modal kho.

### P2 — Báo cáo và quản trị

- Doanh thu, sổ quỹ, chi phí.
- Dịch vụ, giá phòng, nhân sự, audit và Master Console.
- Responsive/accessibility sweep cuối.

Mỗi hạng mục độc lập phải hoàn tất theo TDD và có commit riêng; không thực hiện một lần thay toàn bộ template.

## 12. Tiêu chí nghiệm thu

- Tất cả trang trong phạm vi dùng cùng token và button system; không còn button cùng vai trò nhưng khác màu/kích thước tùy trang.
- Primary button desktop cao 44 px, icon-only button 44 × 44 px; button group có gap tối thiểu 8 px.
- Giao diện sáng và tươi hơn nhưng chữ/button vẫn đạt WCAG AA.
- Login dùng palette chung và không còn card quá nhỏ trong viewport desktop lớn.
- Sơ đồ phòng, Timeline, Kho và Báo cáo có empty/loading/error state hoàn chỉnh.
- Dashboard doanh thu không hiển thị chart/trục giả khi không có dữ liệu.
- Nút đóng modal và icon-only action có accessible name; label form liên kết đúng input.
- Không thay đổi API contract, nghiệp vụ, quyền hoặc tenant scope.
- Không có JavaScript error mới và không có horizontal scroll toàn trang.
- Test markup/route/behavior liên quan xanh; full `pytest -q` xanh.
- `git diff --check` xanh.
- Mỗi màn hình thay đổi được kiểm tra bằng `bb-browser` ở desktop phù hợp; layout chung kiểm tra thêm 1024/768 px và kiểm tra chống vỡ ở 375 px.
- Kiểm tra cả trạng thái có dữ liệu và không có dữ liệu bằng fixture/seed local cô lập; không dùng dữ liệu production.

## 13. Điều kiện dừng và phê duyệt

- Spec này không tự động cho phép thay đổi nghiệp vụ hoặc API để tạo KPI/CTA mới.
- Nếu một CTA empty-state cần route hoặc quyền chưa tồn tại, phải dừng và xin xác nhận thay vì tự thêm chức năng.
- Nếu màu sáng đề xuất không đạt contrast trong kiểm tra thực tế, ưu tiên accessibility và dùng tone đậm hơn.
- Sau P0 cần duyệt trực quan button, spacing và palette trên Login, Sơ đồ phòng, Timeline và Kho trước khi áp dụng hàng loạt sang P1/P2.
