import runpy
from pathlib import Path

import pytest


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.py"


def load_config(monkeypatch, environment, secret_key=None):
    monkeypatch.setenv("FLASK_ENV", environment)

    if secret_key is None:
        monkeypatch.delenv("SECRET_KEY", raising=False)
    else:
        monkeypatch.setenv("SECRET_KEY", secret_key)

    return runpy.run_path(str(CONFIG_PATH))["Config"]


def test_development_uses_fallback_secret_key(monkeypatch):
    config = load_config(monkeypatch, "development")

    assert config.SECRET_KEY == "dev-secret-key"


def test_production_rejects_missing_secret_key(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        runpy.run_path(str(CONFIG_PATH))


def test_production_accepts_environment_secret_key(monkeypatch):
    secret = "test-production-secret-key"
    config = load_config(monkeypatch, "production", secret)

    assert config.SECRET_KEY == secret


def test_development_cookie_security_settings(monkeypatch):
    config = load_config(monkeypatch, "development")

    assert config.SESSION_COOKIE_HTTPONLY is True
    assert config.SESSION_COOKIE_SAMESITE == "Lax"
    assert config.SESSION_COOKIE_SECURE is False
    assert config.REMEMBER_COOKIE_HTTPONLY is True
    assert config.REMEMBER_COOKIE_SAMESITE == "Lax"
    assert config.REMEMBER_COOKIE_SECURE is False


def test_production_cookie_security_settings(monkeypatch):
    config = load_config(
        monkeypatch,
        "production",
        "test-production-secret-key",
    )

    assert config.SESSION_COOKIE_HTTPONLY is True
    assert config.SESSION_COOKIE_SAMESITE == "Lax"
    assert config.SESSION_COOKIE_SECURE is True
    assert config.REMEMBER_COOKIE_HTTPONLY is True
    assert config.REMEMBER_COOKIE_SAMESITE == "Lax"
    assert config.REMEMBER_COOKIE_SECURE is True


def test_development_csrf_security_settings(monkeypatch):
    config = load_config(monkeypatch, "development")

    assert config.WTF_CSRF_ENABLED is True
    assert config.WTF_CSRF_TIME_LIMIT == 3600
    assert config.WTF_CSRF_SSL_STRICT is False


def test_production_csrf_security_settings(monkeypatch):
    config = load_config(
        monkeypatch,
        "production",
        "test-production-secret-key",
    )

    assert config.WTF_CSRF_ENABLED is True
    assert config.WTF_CSRF_TIME_LIMIT == 3600
    assert config.WTF_CSRF_SSL_STRICT is True
