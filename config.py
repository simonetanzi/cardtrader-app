import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def database_uri():
    uri = os.environ.get("DATABASE_URL")
    if not uri:
        return f"sqlite:///{BASE_DIR / 'app.db'}"

    if uri.startswith("postgresql://"):
        return uri.replace("postgresql://", "postgresql+psycopg://", 1)
    if uri.startswith("postgres://"):
        return uri.replace("postgres://", "postgresql+psycopg://", 1)
    return uri


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-before-hosting")
    SQLALCHEMY_DATABASE_URI = database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CARDTRADER_API_TOKEN = os.environ.get("CARDTRADER_API_TOKEN", "").strip()
    ENABLE_GUEST_ACCOUNT = os.environ.get("ENABLE_GUEST_ACCOUNT", "false").lower() == "true"
    GUEST_USERNAME = os.environ.get("GUEST_USERNAME", "guest").strip() or "guest"
    CARDTRADER_BASE_URL = os.environ.get(
        "CARDTRADER_BASE_URL",
        "https://api.cardtrader.com/api/v2",
    ).rstrip("/")
    CARDTRADER_MAX_RATE_LIMIT_RETRIES = int(
        os.environ.get("CARDTRADER_MAX_RATE_LIMIT_RETRIES", "2")
    )
    BLUEPRINTS_DB_PATH = Path(
        os.environ.get("BLUEPRINTS_DB_PATH", BASE_DIR / "data" / "blueprints.sqlite")
    )
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
