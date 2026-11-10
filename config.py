import os
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


class Config:
    ENVIRONMENT = os.environ.get("FLASK_ENV", "development").lower()

    SECRET_KEY = os.environ.get("SECRET_KEY")

    if not SECRET_KEY:
        if ENVIRONMENT == "production":
            raise RuntimeError(
                "SECRET_KEY environment variable is required in production."
            )
        SECRET_KEY = "dev-secret-key"

    SQLALCHEMY_DATABASE_URI = (
        "sqlite:///" + str(BASE_DIR / "instance" / "trustvault.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 30 * 1024 * 1024
    UPLOAD_FOLDER = str(BASE_DIR / "private_uploads")

    ONLYOFFICE_DOCUMENT_SERVER = os.environ.get("ONLYOFFICE_DOCUMENT_SERVER", "").rstrip("/")
    ONLYOFFICE_INTERNAL_BASE_URL = os.environ.get("ONLYOFFICE_INTERNAL_BASE_URL", "http://host.docker.internal:5000").rstrip("/")
    ONLYOFFICE_JWT_SECRET = os.environ.get("ONLYOFFICE_JWT_SECRET", "")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = ENVIRONMENT == "production"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = ENVIRONMENT == "production"

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    WTF_CSRF_SSL_STRICT = ENVIRONMENT == "production"
