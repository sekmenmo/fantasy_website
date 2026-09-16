from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.config import settings
from app.services.cache import JsonCache


def projection_stat_key(scoring_settings: dict[str, Any]) -> str:
    receptions = float(scoring_settings.get("rec", 0) or 0)
    if receptions >= 1:
        return "pts_ppr"
    if receptions == 0.5:
        return "pts_half_ppr"
    return "pts_std"


class ProjectionProvider(ABC):
    @abstractmethod
    async def get_week_projections(
        self,
        season: int,
        week: int,
        player_ids: list[str],
        *,
        force_refresh: bool = False,
    ) -> dict[str, float | None]:
        raise NotImplementedError


class NullProjectionProvider(ProjectionProvider):
    async def get_week_projections(
        self,
        season: int,
        week: int,
        player_ids: list[str],
        *,
        force_refresh: bool = False,
    ) -> dict[str, float | None]:
        return {player_id: None for player_id in player_ids}


class SleeperProjectionProvider(ProjectionProvider):
    def __init__(
        self,
        cache: JsonCache,
        *,
        base_url: str = settings.sleeper_projections_base_url,
        stat_key: str = "pts_ppr",
    ) -> None:
        self.cache = cache
        self.base_url = base_url.rstrip("/")
        self.stat_key = stat_key

    async def get_week_projections(
        self,
        season: int,
        week: int,
        player_ids: list[str],
        *,
        force_refresh: bool = False,
    ) -> dict[str, float | None]:
        wanted = {player_id for player_id in player_ids if player_id and player_id != "0"}
        projections = {player_id: None for player_id in player_ids}
        if not wanted:
            return projections

        records = await self._get_week_records(season, week, force_refresh=force_refresh)

        for record in records:
            player_id = str(record.get("player_id", ""))
            if player_id not in wanted:
                continue
            stats = record.get("stats") or {}
            value = stats.get(self.stat_key)
            projections[player_id] = float(value) if value is not None else None
        return projections

    async def get_week_projection_records(
        self,
        season: int,
        week: int,
        *,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        return await self._get_week_records(season, week, force_refresh=force_refresh)

    async def _get_week_records(self, season: int, week: int, *, force_refresh: bool) -> list[dict[str, Any]]:
        cache_key = f"projections:nfl:{season}:{week}:{self.stat_key}"
        if not force_refresh:
            records = self.cache.get(cache_key)
            if records is not None:
                return records
        try:
            records = await self._fetch_week(season, week)
        except Exception:
            stale = self.cache.get_stale(cache_key)
            if stale is not None:
                return stale
            raise
        try:
            self.cache.set(cache_key, records, ttl_seconds=settings.short_cache_ttl_seconds)
        except Exception:
            pass
        return records

    async def _fetch_week(self, season: int, week: int) -> list[dict[str, Any]]:
        url = f"{self.base_url}/projections/nfl/{season}/{week}"
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(
                url,
                params={"season_type": "regular", "order_by": self.stat_key},
            )
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, list) else []
