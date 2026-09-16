import importlib

from fastapi.testclient import TestClient

from app.config import Settings, normalize_database_url
from app.main import app


def test_normalize_postgres_database_url():
    assert normalize_database_url("postgres://user:pass@host/db").startswith("postgresql+psycopg://")
    assert normalize_database_url("postgresql://user:pass@host/db").startswith("postgresql+psycopg://")
    assert normalize_database_url("sqlite:///./fantasy.db") == "sqlite:///./fantasy.db"


def test_settings_read_environment_overrides(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@host/db")
    monkeypatch.setenv("PORT", "9000")
    import app.config as config

    reloaded = importlib.reload(config)
    assert reloaded.settings.app_env == "production"
    assert reloaded.settings.port == 9000
    assert reloaded.settings.database_url.startswith("postgresql+psycopg://")
    monkeypatch.delenv("APP_ENV")
    monkeypatch.delenv("DATABASE_URL")
    monkeypatch.delenv("PORT")
    importlib.reload(config)


def test_production_browser_auto_open_disabled():
    settings = Settings(app_env="production")
    assert settings.should_open_browser is False


def test_local_sqlite_default():
    settings = Settings()
    assert settings.database_url.startswith("sqlite")


def test_root_health_route():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
