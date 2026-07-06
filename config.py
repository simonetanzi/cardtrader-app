import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-before-hosting")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'app.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CARDTRADER_API_TOKEN = os.environ.get("CARDTRADER_API_TOKEN", "").strip()
    CARDTRADER_BASE_URL = os.environ.get(
        "CARDTRADER_BASE_URL",
        "https://api.cardtrader.com/api/v2",
    ).rstrip("/")
    BLUEPRINTS_DB_PATH = Path(
        os.environ.get("BLUEPRINTS_DB_PATH", BASE_DIR / "data" / "blueprints_db.json.gz")
    )
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
