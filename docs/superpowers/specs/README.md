# Sổ tổng Refactor HotelPOS

File điều phối toàn bộ đợt refactor. **Mọi việc cần làm đều phải có mặt ở đây** — hoặc trong bảng spec, hoặc trong mục Backlog. Làm xong spec nào thì cập nhật trạng thái spec đó.

## Nguyên tắc xuyên suốt

> **Mỗi giai đoạn phải tạo ra lưới an toàn cho giai đoạn kế tiếp.**
> Không dời thư mục khi chưa boot ổn định. Không viết test khi chưa có factory. Không sửa nghiệp vụ khi chưa có test.

- Làm **tuần tự từng spec**, không nhảy cóc — thứ tự là ràng buộc kỹ thuật, không phải gợi ý.
- Chi tiết thiết kế (ERD, API, engine giá, máy trạng thái) nằm trong [`docs/SDD.md`](../../SDD.md) — spec chỉ tham chiếu, không chép lại.

## Chu trình mỗi spec: SDD → TDD → Thực thi → Nghiệm thu

1. **SDD** — đọc spec + phần SDD liên quan; nếu thực tế lệch thiết kế thì sửa SDD *trước*, không code lệch tài liệu. Viết implementation plan bằng `/superpowers:writing-plans`.
2. **TDD** — viết test trước theo hành vi đúng trong SDD (`/superpowers:test-driven-development`), chạy đỏ.
3. **Thực thi** — code cho test xanh, đúng phạm vi spec, không phình.
4. **Nghiệm thu** — chạy toàn bộ tiêu chí trong mục "Tiêu chí nghiệm thu" của spec (`/superpowers:verification-before-completion`), có bằng chứng (output lệnh) rồi mới tick ✅ ở bảng dưới.

## Bảng spec

| # | Spec | Phạm vi | Ước tính | Phụ thuộc | Trạng thái |
|---|------|---------|----------|-----------|------------|
| P0 | [Đóng băng hiện trạng](2026-08-14-p0-freeze-baseline-design.md) | Pin deps, tag git, checklist smoke thủ công · [plan](../plans/2026-08-14-p0-freeze-baseline.md) | 0,5 ngày | — | 📝 Plan xong, chờ thực thi |
| P1 | [Config + Docker + Vá bảo mật](2026-08-14-p1-config-docker-security-design.md) | Config class, `.env`, compose, migration đầu (đổi tên bảng), 4 vá bảo mật | 2 ngày | P0 | ⬜ Chưa làm |
| P2 | [Application Factory + Smoke test](2026-08-14-p2-app-factory-design.md) | `create_app()`, export đủ model, smoke test url_map | 1 ngày + 2h | P1 | ⬜ Chưa làm |
| P3 | [Tổ chức lại thư mục](2026-08-14-p3-folder-restructure-design.md) | Package `app/`, tách api/views/services, handler 401, errors tập trung | 2 ngày | P2 | ⬜ Chưa làm |
| P4 | [Bộ khung test](2026-08-14-p4-test-harness-design.md) | pytest, fixture, test pricing + luồng booking | 2 ngày | P3 | ⬜ Chưa làm |
| P5 | [Sửa nghiệp vụ tiền & booking](2026-08-14-p5-business-fixes-design.md) | 9 lỗi: sổ Payment, Decimal, chống double-booking, phân quyền… | kéo dài | P4 | ⬜ Chưa làm |

Trạng thái: ⬜ Chưa làm · 📝 Đang viết plan · 🔨 Đang làm · ✅ Xong (đã verify)

## Backlog — ghi nhớ nhưng chưa thuộc spec nào

Những việc đã xác định nhưng **cố tình để sau P5**, tránh phình phạm vi:

- [ ] Màn hình **thu ngân** — bỏ dữ liệu cứng, đọc từ bảng `payments` (làm được ngay sau P5 vì P5 mới bắt đầu ghi sổ)
- [ ] Màn hình **báo cáo doanh thu** — đọc từ `payments`, thay số hardcode
- [ ] Màn hình **kho hàng**, **giao ca**, **cấu hình** — hiện là khung tĩnh, cần thiết kế nghiệp vụ riêng trước khi code
- [ ] CI (GitHub Actions chạy pytest) — cân nhắc sau khi P4 có bộ test ổn định
- [ ] Backup MySQL tự động (`mysqldump` theo lịch) — sau khi P1 chạy Docker ổn định
- [ ] Đổi mật khẩu MySQL đã lộ trong lịch sử git **trên mọi máy đang dùng chung DB** (việc vận hành, ngoài code — nhắc để không quên)

## Tài liệu liên quan

- [`docs/SDD.md`](../../SDD.md) — Software Design Document (kiến trúc, ERD, API, engine giá)
- Lộ trình gốc (artifact): https://claude.ai/code/artifact/d5b0acb7-b4d0-4bad-a2ae-2ad1a2543637
