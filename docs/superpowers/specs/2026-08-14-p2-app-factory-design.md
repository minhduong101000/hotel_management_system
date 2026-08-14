# Spec P2 — Application Factory + Smoke test

**Trạng thái:** ⬜ Chưa làm · **Ước tính:** 1 ngày + 2 giờ · **Phụ thuộc:** P1

## Mục tiêu

Gỡ nút thắt kỹ thuật lớn nhất: `app.py` đang tạo `app` ở cấp module nên không thể có config test, không thể chạy 2 môi trường, không thể viết test. Kết thúc P2 phải mở được hai app instance với hai config khác nhau trong cùng một tiến trình Python, và có smoke test làm lưới an toàn cho P3.

## Việc cần làm

### 1. Vá export model (làm TRƯỚC khi động vào factory)

`models/__init__.py` đang export 6/9 model — thiếu `BookingRoom`, `BookingService`, `PriceRule`. Chúng hiện được đăng ký với SQLAlchemy nhờ may rủi theo thứ tự import của controller; đổi cách import là mapper vỡ. Export đủ 9 model.

### 2. Application factory

- `create_app(config_name: str) -> Flask`: nạp config, `init_app` cho extensions, đăng ký blueprint, đăng ký error handler — tất cả bên trong hàm.
- `extensions.py` giữ instance trần (`db`, `login_manager`, `migrate`); không import app.
- `wsgi.py`: entrypoint cho gunicorn (`app = create_app('production')`).
- `app.py` cũ giữ lại làm shim mỏng cho dev: chỉ còn `app = create_app('development')` + `if __name__ == '__main__': app.run(debug=True)`. Không xóa — giữ thói quen `python app.py` đang dùng, tránh đổi hai thứ một lúc.

### 3. Smoke test (P2.5)

- `tests/test_smoke.py` ~30 dòng: tạo app với `TestConfig`, duyệt `app.url_map`, gọi mọi route GET không tham số bằng test client (đăng nhập giả qua fixture), assert status < 500.
- Đây là lưới an toàn để dám `git mv` ở P3 — không cần đúng nghiệp vụ, chỉ cần "không sập".

## Tiêu chí nghiệm thu

- [ ] `create_app('development')` và `create_app('testing')` cùng chạy trong một tiến trình, config độc lập.
- [ ] `docker compose up` vẫn chạy như cuối P1 (gunicorn trỏ `wsgi:app`).
- [ ] 9/9 model import được từ `models` và mapper khởi tạo không phụ thuộc thứ tự import controller.
- [ ] `pytest tests/test_smoke.py` xanh; giả lập một route lỗi 500 thì smoke test đỏ (test có răng thật).

## Ngoài phạm vi

- Không dời file, không đổi tên thư mục (P3).
- Không viết test nghiệp vụ (P4).
