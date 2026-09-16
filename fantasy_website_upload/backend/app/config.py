from __future__ import annotations

import os

from pydantic import BaseModel


DEFAULT_LEAGUE_ID = "1393359396699930624"
DEFAULT_SLEEPER_API_BASE_URL = "https://api.sleeper.app/v1"
DEFAULT_SLEEPER_PROJECTIONS_BASE_URL = "https://api.sleeper.com"
DEFAULT_DATABASE_URL = "sqlite:///./fantasy.db"

PLAYER_CACHE_TTL_SECONDS = 24 * 60 * 60
SHORT_CACHE_TTL_SECONDS = 5 * 60

POWER_RANKING_WEIGHTS = {
    "season_scoring": 0.40,
    "projected_strength": 0.25,
    "recent_form": 0.20,
    "record": 0.10,
    "health": 0.05,
}

AVAILABILITY_STATUS_WEIGHTS = {
    "IR": 1.00,
    "OUT": 1.00,
    "DOUBTFUL": 0.75,
    "QUESTIONABLE": 0.25,
}


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


class Settings(BaseModel):
    app_env: str = os.getenv("APP_ENV", "development")
    app_name: str = os.getenv("APP_NAME", "Fantasy Broadcast Dashboard")
    debug: bool = env_bool("DEBUG", False)
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = env_int("PORT", 8000)
    league_id: str = os.getenv("LEAGUE_ID", DEFAULT_LEAGUE_ID)
    sleeper_api_base_url: str = os.getenv("SLEEPER_API_BASE_URL", DEFAULT_SLEEPER_API_BASE_URL)
    sleeper_projections_base_url: str = os.getenv(
        "SLEEPER_PROJECTIONS_BASE_URL",
        DEFAULT_SLEEPER_PROJECTIONS_BASE_URL,
    )
    database_url: str = normalize_database_url(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
    player_cache_ttl_seconds: int = env_int("SLEEPER_PLAYER_CACHE_TTL", PLAYER_CACHE_TTL_SECONDS)
    short_cache_ttl_seconds: int = env_int("SLEEPER_CACHE_TTL", SHORT_CACHE_TTL_SECONDS)

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @property
    def should_open_browser(self) -> bool:
        return not self.is_production and env_bool("OPEN_BROWSER", True)


settings = Settings()
