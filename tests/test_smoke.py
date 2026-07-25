def test_factory_uses_test_database(app):
    assert app.config["TESTING"] is True
    assert app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite")

def test_health_request_does_not_require_mysql(client):
    response = client.get("/")
    assert response.status_code in {302, 404}
