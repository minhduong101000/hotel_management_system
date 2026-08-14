import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


class BaseConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevConfig(BaseConfig):
    DEBUG = True


class TestConfig(BaseConfig):
    TESTING = True
    SECRET_KEY = 'test-secret-key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


class ProdConfig(BaseConfig):
    DEBUG = False


_config_map = {
    'development': DevConfig,
    'testing': TestConfig,
    'production': ProdConfig,
}


def get_config(name=None):
    name = name or os.environ.get('FLASK_CONFIG', 'development')
    if name == 'production':
        missing = [k for k in ('SECRET_KEY', 'DATABASE_URL') if not os.environ.get(k)]
        if missing:
            raise RuntimeError(f'Thiếu biến môi trường bắt buộc cho production: {missing}')
    return _config_map[name]
