import re

import pytest

from app import create_app
from extensions import db
from models import Hotel, User


CSRF_INPUT_PATTERN = re.compile(
    rb'name="csrf_token"[^>]*value="([^"]+)"|'
    rb'value="([^"]+)"[^>]*name="csrf_token"'
)
CSRF_META_PATTERN = re.compile(
    rb'<meta[^>]+name="csrf-token"[^>]+content="([^"]+)"'
)


@pytest.fixture()
def csrf_app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SECRET_KEY": "csrf-test-secret",
            "WTF_CSRF_ENABLED": True,
        }
    )
    with app.app_context():
        db.create_all()
        hotel = Hotel(name="Central Hotel", slug="central")
        db.session.add(hotel)
        db.session.flush()
        admin = User(username="csrf_admin", role="admin", hotel_id=hotel.id)
        admin.set_password("correct-password")
        db.session.add(admin)
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


def extract_form_csrf(response):
    match = CSRF_INPUT_PATTERN.search(response.data)
    assert match, response.data.decode("utf-8")
    return (match.group(1) or match.group(2)).decode("utf-8")


def extract_meta_csrf(response):
    match = CSRF_META_PATTERN.search(response.data)
    assert match, response.data.decode("utf-8")
    return match.group(1).decode("utf-8")


def login_with_csrf(client):
    login_page = client.get("/central/login")
    token = extract_form_csrf(login_page)
    response = client.post(
        "/central/login",
        data={
            "username": "csrf_admin",
            "password": "correct-password",
            "csrf_token": token,
        },
    )
    assert response.status_code == 302


def test_login_form_rejects_missing_token(csrf_app):
    client = csrf_app.test_client()
    client.get("/central/login")

    response = client.post(
        "/central/login",
        data={"username": "csrf_admin", "password": "correct-password"},
    )

    assert response.status_code == 400
    assert b"Phi\xc3\xaan thao t\xc3\xa1c kh\xc3\xb4ng h\xe1\xbb\xa3p l\xe1\xbb\x87" in response.data


def test_login_form_accepts_valid_token(csrf_app):
    client = csrf_app.test_client()

    login_with_csrf(client)


def test_json_mutation_rejects_missing_token_with_stable_error(csrf_app):
    client = csrf_app.test_client()
    login_with_csrf(client)

    response = client.post(
        "/central/customers/api/customers",
        json={"name": "CSRF Customer", "phone": "0900000001"},
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error_code": "csrf_failed",
        "msg": "Phiên thao tác không hợp lệ hoặc đã hết hạn.",
    }


def test_json_mutation_accepts_valid_header_token(csrf_app):
    client = csrf_app.test_client()
    login_with_csrf(client)
    page = client.get("/central/customers/customers")
    token = extract_meta_csrf(page)

    response = client.post(
        "/central/customers/api/customers",
        headers={"X-CSRFToken": token},
        json={"name": "CSRF Customer", "phone": "0900000002"},
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True


def test_json_mutation_rejects_token_from_another_session(csrf_app):
    first_client = csrf_app.test_client()
    second_client = csrf_app.test_client()
    login_with_csrf(first_client)
    login_with_csrf(second_client)
    foreign_token = extract_meta_csrf(
        first_client.get("/central/customers/customers")
    )

    response = second_client.delete(
        "/central/customers/api/customers/999",
        headers={"X-CSRFToken": foreign_token},
    )

    assert response.status_code == 400
    assert response.get_json()["error_code"] == "csrf_failed"


def test_safe_methods_do_not_require_csrf_token(csrf_app):
    client = csrf_app.test_client()
    login_with_csrf(client)

    response = client.get("/central/customers/api/customers")

    assert response.status_code == 200


def test_shared_fetch_wrapper_adds_csrf_header():
    source = (csrf_app_path() / "static" / "js" / "main.js").read_text(
        encoding="utf-8"
    )

    assert "function csrfFetch" in source
    assert "X-CSRFToken" in source
    assert "window.fetch = csrfFetch" in source


def csrf_app_path():
    from pathlib import Path

    return Path(__file__).resolve().parents[1]
