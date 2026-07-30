from app import create_app
from extensions import db
from models import Hotel, User


def make_development_app():
    return create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SECRET_KEY": "development-command-test",
        },
        environment="development",
    )


def test_development_seed_requires_explicit_passwords():
    app = make_development_app()

    result = app.test_cli_runner().invoke(
        args=["seed-development", "--hotel-slug", "central"]
    )

    assert result.exit_code == 2
    assert "Missing option '--admin-password'" in result.output


def test_development_seed_creates_tenant_users_without_printing_passwords():
    app = make_development_app()
    admin_password = "safe-admin-password"
    staff_password = "safe-staff-password"
    with app.app_context():
        db.create_all()
        db.session.add(Hotel(name="Central Hotel", slug="central"))
        db.session.commit()

    result = app.test_cli_runner().invoke(
        args=[
            "seed-development",
            "--hotel-slug",
            "central",
            "--admin-password",
            admin_password,
            "--staff-password",
            staff_password,
        ]
    )

    assert result.exit_code == 0, result.output
    assert admin_password not in result.output
    assert staff_password not in result.output
    with app.app_context():
        admin = User.query.filter_by(username="admin", role="admin").one()
        staff = User.query.filter_by(username="staff1", role="staff").one()
        assert admin.hotel.slug == "central"
        assert staff.hotel.slug == "central"
        assert admin.check_password(admin_password)
        assert staff.check_password(staff_password)
