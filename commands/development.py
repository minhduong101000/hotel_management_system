import click
from flask import current_app

from extensions import db
from models import Hotel, User


def register_development_commands(app):
    @app.cli.command("seed-development")
    @click.option("--hotel-slug", required=True)
    @click.option("--admin-password", required=True, hide_input=True)
    @click.option("--staff-password", required=True, hide_input=True)
    def seed_development(hotel_slug, admin_password, staff_password):
        """Tạo tài khoản mẫu một cách chủ động cho môi trường development."""
        if current_app.config["APP_ENV"] != "development":
            raise click.ClickException(
                "seed-development chỉ được phép chạy trong môi trường development."
            )
        if len(admin_password) < 12 or len(staff_password) < 12:
            raise click.ClickException("Mật khẩu development phải có ít nhất 12 ký tự.")

        hotel = Hotel.query.filter_by(slug=hotel_slug).first()
        if not hotel:
            raise click.ClickException(
                f"Không tìm thấy khách sạn có slug {hotel_slug!r}."
            )

        created = []
        for username, role, password in (
            ("admin", "admin", admin_password),
            ("staff1", "staff", staff_password),
        ):
            user = User.query.filter_by(username=username).first()
            if user:
                if user.hotel_id != hotel.id:
                    raise click.ClickException(
                        f"Tài khoản {username!r} đã thuộc khách sạn khác."
                    )
                continue

            user = User(username=username, role=role, hotel_id=hotel.id)
            user.set_password(password)
            db.session.add(user)
            created.append(username)

        db.session.commit()
        if created:
            click.echo(f"Đã tạo tài khoản development: {', '.join(created)}.")
        else:
            click.echo("Các tài khoản development đã tồn tại; không thay đổi dữ liệu.")
