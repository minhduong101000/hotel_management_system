from pathlib import Path

import pytest

from app import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = PROJECT_ROOT / "app.py"


def clear_production_environment(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    # .env dev co the dat false (Safari/LAN); hop dong mac dinh van phai True
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)


def test_production_requires_secret_key(monkeypatch):
    clear_production_environment(monkeypatch)
    monkeypatch.setenv(
        "DATABASE_URL",
        "mysql+pymysql://hotel_app:secure-password@db/hotel",
    )

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(environment="production")


def test_production_requires_database_url(monkeypatch):
    clear_production_environment(monkeypatch)
    monkeypatch.setenv("SECRET_KEY", "a-production-secret-with-at-least-32-characters")

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_app(environment="production")


@pytest.mark.parametrize(
    ("secret_key", "database_url", "expected_error"),
    [
        (
            "luxury-secret-key-change-in-production",
            "mysql+pymysql://hotel_app:secure-password@db/hotel",
            "SECRET_KEY",
        ),
        (
            "too-short",
            "mysql+pymysql://hotel_app:secure-password@db/hotel",
            "SECRET_KEY",
        ),
        (
            "a-production-secret-with-at-least-32-characters",
            "mysql+pymysql://root:123456@localhost/Hotel_Management_System",
            "DATABASE_URL",
        ),
    ],
)
def test_production_rejects_known_insecure_defaults(
    monkeypatch, secret_key, database_url, expected_error
):
    clear_production_environment(monkeypatch)
    monkeypatch.setenv("SECRET_KEY", secret_key)
    monkeypatch.setenv("DATABASE_URL", database_url)

    with pytest.raises(RuntimeError, match=expected_error):
        create_app(environment="production")


def test_production_forces_safe_runtime_flags_and_headers(monkeypatch):
    clear_production_environment(monkeypatch)
    monkeypatch.setenv("SECRET_KEY", "a-production-secret-with-at-least-32-characters")
    monkeypatch.setenv(
        "DATABASE_URL",
        "mysql+pymysql://hotel_app:secure-password@db/hotel",
    )
    monkeypatch.setenv("FLASK_DEBUG", "1")

    app = create_app(environment="production")
    response = app.test_client().get("/not-found")

    assert app.config["DEBUG"] is False
    assert app.config["TESTING"] is False
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "same-origin"
    # 15-08: bo CSP report-only (khong report-to = vo dung + spam console
    # Safari); chong clickjacking bang X-Frame-Options cho den khi co CSP that.
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "Content-Security-Policy-Report-Only" not in response.headers


def test_direct_startup_has_no_schema_backfill_or_default_accounts():
    source = APP_SOURCE.read_text(encoding="utf-8")

    assert "db.create_all()" not in source
    assert "ensure_schema_updates" not in source
    assert "backfill_room_deposits" not in source
    assert "admin123" not in source
    assert "staff123" not in source
    assert "app.run(debug=True)" not in source
