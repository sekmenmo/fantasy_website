from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


class SleeperClient:
    def __init__(self, base_url: str = settings.sleeper_api_base_url) -> None:
        self.base_url = base_url.rstrip("/")

    async def _get(self, path: str) -> Any:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def get_league(self, league_id: str) -> dict[str, Any]:
        return await self._get(f"/league/{league_id}")

    async def get_users(self, league_id: str) -> list[dict[str, Any]]:
        return await self._get(f"/league/{league_id}/users")

    async def get_rosters(self, league_id: str) -> list[dict[str, Any]]:
        return await self._get(f"/league/{league_id}/rosters")

    async def get_matchups(self, league_id: str, week: int) -> list[dict[str, Any]]:
        return await self._get(f"/league/{league_id}/matchups/{week}")

    async def get_players(self) -> dict[str, dict[str, Any]]:
        return await self._get("/players/nfl")

    async def get_nfl_state(self) -> dict[str, Any]:
        return await self._get("/state/nfl")
