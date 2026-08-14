import os

from dotenv import load_dotenv

# Nạp .env cho MỌI cách chạy (python app.py, script trần) — trước đây chỉ
# Flask CLI tự nạp, khiến app rơi nhầm về SQLite khi thiếu biến môi trường.
load_dotenv()



DEVELOPMENT_SECRET = "development-only-secret-do-not-use-in-production"
DEVELOPMENT_DATABASE_URL = "sqlite:///hotel_management_development.db"
KNOWN_INSECURE_SECRETS = {
    DEVELOPMENT_SECRET,
    "luxury-secret-key-change-in-production",
}
KNOWN_INSECURE_DATABASE_FRAGMENTS = {
    "root:123456@",
}


class BaseConfig:
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    HOTEL_NAME = os.environ.get("HOTEL_NAME", "HOTEL POS PRO")
    HOTEL_BRANCH = os.environ.get("HOTEL_BRANCH", "Chi nhanh trung tam")
    HOTEL_ADDRESS = os.environ.get("HOTEL_ADDRESS", "123 Duong ABC, Ha Noi")
    HOTEL_PHONE = os.environ.get("HOTEL_PHONE", "0987 654 321")
    HOTEL_EMAIL = os.environ.get("HOTEL_EMAIL", "contact@hotelpos.vn")
    HOTEL_LOGO_URL = os.environ.get("HOTEL_LOGO_URL", "/static/img/hotel-logo.png")

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "xxx@gmail.com")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "xxx@gmail.com")


class DevelopmentConfig(BaseConfig):
    APP_ENV = "development"
    DEBUG = True
    TESTING = False
    SECRET_KEY = os.environ.get("SECRET_KEY", DEVELOPMENT_SECRET)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", DEVELOPMENT_DATABASE_URL
    )
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


class TestingConfig(BaseConfig):
    APP_ENV = "testing"
    DEBUG = False
    TESTING = True
    SECRET_KEY = None
    SQLALCHEMY_DATABASE_URI = None
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


class ProductionConfig(BaseConfig):
    APP_ENV = "production"
    DEBUG = False
    TESTING = False
    SECRET_KEY = None
    SQLALCHEMY_DATABASE_URI = None
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "Lax"


CONFIG_BY_ENVIRONMENT = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}

# Backward-compatible import for code that still expects Config.
Config = DevelopmentConfig


def resolve_environment(environment=None, test_config=None):
    if environment:
        selected = environment
    elif test_config and test_config.get("TESTING"):
        selected = "testing"
    else:
        selected = os.environ.get("APP_ENV", "development")

    selected = selected.strip().lower()
    if selected not in CONFIG_BY_ENVIRONMENT:
        raise RuntimeError(
            f"APP_ENV không hợp lệ: {selected!r}. "
            "Chỉ hỗ trợ development, testing hoặc production."
        )
    return selected


def apply_runtime_config(app, environment=None, test_config=None):
    selected = resolve_environment(environment, test_config)
    app.config.from_object(CONFIG_BY_ENVIRONMENT[selected])

    if test_config:
        app.config.update(test_config)

    if selected == "production":
        app.config.update(
            SECRET_KEY=os.environ.get("SECRET_KEY"),
            SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL"),
            DEBUG=False,
            TESTING=False,
        )
        validate_production_config(app.config)

    app.config["APP_ENV"] = selected
    return selected


def validate_production_config(config):
    secret_key = config.get("SECRET_KEY")
    if not secret_key:
        raise RuntimeError("Production yêu cầu biến môi trường SECRET_KEY.")
    if len(secret_key) < 32 or secret_key in KNOWN_INSECURE_SECRETS:
        raise RuntimeError(
            "SECRET_KEY production phải dài ít nhất 32 ký tự "
            "và không được dùng giá trị mẫu."
        )

    database_url = config.get("SQLALCHEMY_DATABASE_URI")
    if not database_url:
        raise RuntimeError("Production yêu cầu biến môi trường DATABASE_URL.")
    if any(
        fragment.lower() in database_url.lower()
        for fragment in KNOWN_INSECURE_DATABASE_FRAGMENTS
    ):
        raise RuntimeError(
            "DATABASE_URL production chứa credential mặc định không an toàn."
        )

    if config.get("DEBUG") or config.get("TESTING"):
        raise RuntimeError("Production không được bật DEBUG hoặc TESTING.")
