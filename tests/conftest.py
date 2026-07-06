import pytest

from app import create_app
from config import Config


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    CARDTRADER_API_TOKEN = "test-token"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def app_context():
    app = create_app(TestConfig)
    with app.app_context():
        yield app
