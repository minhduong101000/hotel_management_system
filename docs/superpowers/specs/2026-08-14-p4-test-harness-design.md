# Spec P4 — Bộ khung test

**Trạng thái:** ⬜ Chưa làm · **Ước tính:** 2 ngày · **Phụ thuộc:** P3

## Mục tiêu

Dựng pytest harness và phủ test cho hai vùng đắt nhất: engine tính giá (chỗ sai là mất tiền) và luồng đặt–ở–trả (chỗ sai là mất dữ liệu). Đây là lưới an toàn để P5 dám sửa nghiệp vụ.

## Việc cần làm

### 1. Harness

- `tests/conftest.py`: fixture `app` (TestConfig, SQLite in-memory), `client` (đã đăng nhập), `db_session` (transaction rollback sau mỗi test).
- `requirements-dev.txt`: pytest + pytest-cov.
- Riêng test cần constraint MySQL thật (unique, `FOR UPDATE`) đánh dấu `@pytest.mark.mysql`, chạy với container `db` của compose — số lượng ít, chủ yếu cho P5.

### 2. `tests/test_pricing.py` — engine giá (SDD mục 6)

Các ca bắt buộc, mỗi ca một test đặt tên rõ:

- Thuê giờ: trong block đầu / đúng ranh giới block / lố ≤ 10 phút (ân hạn, không tính thêm) / lố > 10 phút (làm tròn lên).
- Trần giá: tiền giờ vượt giá đêm → tự chuyển tính ngày, breakdown có dòng giải thích.
- Thuê ngày: 1 đêm, N đêm, `nights < 1` ép về 1.
- Phụ thu sớm/muộn đủ 4 bậc: ≤1h (0%), 1–4h (30%), 4–6h (50%), >6h (100%) — test đúng tại biên 1h/4h/6h.
- PriceRule: rule đúng khoảng ngày thắng giá niêm yết; rule `days_of_week="5,6"` chỉ áp T7/CN; hai rule chồng nhau chọn `priority` cao hơn; **rule không có ngày (NULL) phải áp quanh năm** — ca này hiện tại FAIL (bug so sánh NULL, SDD 6.1): viết test trước, đánh dấu `xfail` có ghi chú, P5 sửa cho pass.
- Rule chỉ ghi đè giá ngày, giá giờ giữ nguyên niêm yết.

### 3. `tests/test_booking_flow.py` — luồng nghiệp vụ

- Đặt phòng lẻ → check-in → gọi 2 dịch vụ → preview (tiền phòng + dịch vụ − cọc) → checkout.
- Check-in bị chặn khi phòng `dirty`.
- Sau checkout: phòng về `available` + `dirty`.
- Các bước hiện đang hỏng (ghi Payment, cập nhật `payment_status`…) viết test theo **hành vi đúng trong SDD** và đánh dấu `xfail` — P5 gỡ dấu dần, tiến độ P5 đo bằng số `xfail` còn lại.

## Tiêu chí nghiệm thu

- [ ] `pytest` chạy xanh toàn bộ (trừ các ca `xfail` có chủ đích, mỗi ca có reason trỏ về SDD).
- [ ] Coverage `app/services/pricing.py` ≥ 90%.
- [ ] Chạy được cả ngoài Docker (SQLite) lẫn trong Docker (profile mysql).

## Ngoài phạm vi

- Không sửa code nghiệp vụ để test pass — hành vi sai ghi nhận bằng `xfail`, sửa ở P5.
- CI chạy tự động → Backlog.
