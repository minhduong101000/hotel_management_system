import logging
import os

from app import create_app
from extensions import db
from services import notification_service


def test_healthz_ok(app, client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_healthz_reports_db_failure(app, client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(db.session, "execute", boom)
    response = client.get("/healthz")
    assert response.status_code == 503
    assert response.json == {"status": "degraded"}


def test_notification_logs_instead_of_print(app, seed_hotels, caplog):
    hotel, _, _, _, booking_room, _ = seed_hotels
    with app.app_context():
        hotel.email = None
        with caplog.at_level(logging.INFO):
            notification_service.send_booking_notification(
                booking_room.booking, hotel
            )
    assert any("no email configured" in r.message for r in caplog.records)


def test_session_cookie_secure_env_override(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "x" * 40)
    monkeypatch.setenv("DATABASE_URL", "sqlite://")

    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    app_http = create_app(environment="production")
    assert app_http.config["SESSION_COOKIE_SECURE"] is False

    monkeypatch.delenv("SESSION_COOKIE_SECURE")
    app_https = create_app(environment="production")
    assert app_https.config["SESSION_COOKIE_SECURE"] is True
