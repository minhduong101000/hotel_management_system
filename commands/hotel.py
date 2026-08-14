import re

import click

from extensions import db
from models import Hotel, User


SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MIN_ADMIN_PASSWORD_LENGTH = 12


def register_hotel_commands(app):
    @app.cli.command("create-hotel")
    @click.option("--name", required=True, help="Tên hiển thị của khách sạn.")
    @click.option("--slug", required=True, help="Định danh trong URL, ví dụ: bo-ho.")
    @click.option("--address", default=None)
    @click.option("--phone", default=None)
    @click.option("--email", default=None)
    @click.option("--admin-username", default=None, help="Tạo kèm tài khoản admin đầu tiên.")
    @click.option("--admin-password", default=None, hide_input=True)
    def create_hotel(name, slug, address, phone, email, admin_username, admin_password):
        """Tạo khách sạn mới (kèm tài khoản admin đầu tiên nếu truyền --admin-*).

        Chạy được ở mọi môi trường — đây là lệnh bootstrap production,
        khác với seed-development (chỉ dành cho development).
        """
        slug = (slug or "").strip().lower()
        if not SLUG_PATTERN.match(slug):
            raise click.ClickException(
                f"Slug {slug!r} không hợp lệ: chỉ dùng chữ thường a-z, số và dấu gạch "
                "ngang (slug xuất hiện trong URL, ví dụ /bo-ho/login)."
            )

        if bool(admin_username) != bool(admin_password):
            raise click.ClickException(
                "--admin-username và --admin-password phải đi cùng nhau."
            )
        if admin_password and len(admin_password) < MIN_ADMIN_PASSWORD_LENGTH:
            raise click.ClickException(
                f"Mật khẩu admin phải có ít nhất {MIN_ADMIN_PASSWORD_LENGTH} ký tự."
            )

        if Hotel.query.filter_by(slug=slug).first():
            raise click.ClickException(f"Đã tồn tại khách sạn với slug {slug!r}.")
        if admin_username and User.query.filter_by(username=admin_username).first():
            raise click.ClickException(
                f"Tên đăng nhập {admin_username!r} đã được sử dụng."
            )

        hotel = Hotel(
            name=name.strip(),
            slug=slug,
            address=address,
            phone=phone,
            email=email,
            is_active=True,
        )
        db.session.add(hotel)
        db.session.flush()

        if admin_username:
            admin = User(username=admin_username, role="admin", hotel_id=hotel.id)
            admin.set_password(admin_password)
            db.session.add(admin)

        db.session.commit()

        click.echo(f"Đã tạo khách sạn {hotel.name!r} (slug: {hotel.slug}).")
        if admin_username:
            click.echo(f"Đã tạo tài khoản admin {admin_username!r} cho khách sạn này.")
        click.echo(f"Đăng nhập tại: /{hotel.slug}/login")
