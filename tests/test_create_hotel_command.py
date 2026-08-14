from extensions import db
from models import Hotel, User


def _invoke(app, *args):
    return app.test_cli_runner().invoke(args=["create-hotel", *args])


def test_create_hotel_creates_hotel_and_first_admin(app):
    with app.app_context():
        result = _invoke(
            app,
            "--name", "Khách sạn Bờ Hồ",
            "--slug", "bo-ho",
            "--address", "1 Hồ Gươm, Hà Nội",
            "--admin-username", "boho_admin",
            "--admin-password", "mat-khau-du-dai-12",
        )
        assert result.exit_code == 0, result.output

        hotel = Hotel.query.filter_by(slug="bo-ho").one()
        assert hotel.name == "Khách sạn Bờ Hồ"
        assert hotel.is_active is True

        admin = User.query.filter_by(username="boho_admin").one()
        assert admin.role == "admin"
        assert admin.hotel_id == hotel.id
        assert admin.is_super_admin in (False, None)
        assert admin.check_password("mat-khau-du-dai-12")


def test_create_hotel_without_admin_creates_no_user(app):
    with app.app_context():
        result = _invoke(app, "--name", "Solo Hotel", "--slug", "solo")
        assert result.exit_code == 0, result.output
        assert Hotel.query.filter_by(slug="solo").count() == 1
        assert User.query.count() == 0


def test_create_hotel_rejects_duplicate_slug(app, seed_hotels):
    with app.app_context():
        before = Hotel.query.count()
        result = _invoke(app, "--name", "Trùng Slug", "--slug", "central")
        assert result.exit_code != 0
        assert "central" in result.output
        assert Hotel.query.count() == before


def test_create_hotel_normalizes_and_validates_slug(app):
    with app.app_context():
        # Chữ hoa được chuẩn hóa về thường
        ok = _invoke(app, "--name", "Hoa Hotel", "--slug", "Hoa-Binh")
        assert ok.exit_code == 0, ok.output
        assert Hotel.query.filter_by(slug="hoa-binh").count() == 1

        # Slug có ký tự ngoài [a-z0-9-] bị từ chối (slug nằm trong URL)
        bad = _invoke(app, "--name", "Xấu", "--slug", "trung tâm!")
        assert bad.exit_code != 0
        assert Hotel.query.count() == 1


def test_create_hotel_requires_admin_username_and_password_together(app):
    with app.app_context():
        only_user = _invoke(
            app, "--name", "A", "--slug", "a1", "--admin-username", "adm"
        )
        assert only_user.exit_code != 0
        assert "đi cùng nhau" in only_user.output
        assert Hotel.query.count() == 0

        only_pass = _invoke(
            app, "--name", "A", "--slug", "a1", "--admin-password", "mat-khau-du-dai-12"
        )
        assert only_pass.exit_code != 0
        assert "đi cùng nhau" in only_pass.output
        assert Hotel.query.count() == 0


def test_create_hotel_rejects_short_admin_password(app):
    with app.app_context():
        result = _invoke(
            app,
            "--name", "A", "--slug", "a1",
            "--admin-username", "adm",
            "--admin-password", "ngan",
        )
        assert result.exit_code != 0
        assert "ít nhất 12 ký tự" in result.output
        assert Hotel.query.count() == 0
        assert User.query.count() == 0


def test_create_hotel_rejects_taken_admin_username(app, seed_hotels):
    with app.app_context():
        result = _invoke(
            app,
            "--name", "B", "--slug", "b1",
            "--admin-username", "admin_a",  # đã thuộc khách sạn central
            "--admin-password", "mat-khau-du-dai-12",
        )
        assert result.exit_code != 0
        assert "đã được sử dụng" in result.output
        # Không được ghi nửa vời: hotel cũng không được tạo
        assert Hotel.query.filter_by(slug="b1").count() == 0
