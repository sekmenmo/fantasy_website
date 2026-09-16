from __future__ import annotations

from typing import Any

from app.config import settings
from app.services.cache import JsonCache
from app.services.sleeper import SleeperClient


class PlayerMetadataService:
    cache_key = "players:nfl"

    def __init__(self, client: SleeperClient, cache: JsonCache) -> None:
        self.client = client
        self.cache = cache

    async def refresh(self) -> dict[str, dict[str, Any]]:
        players = await self.client.get_players()
        self.cache.set(self.cache_key, players, ttl_seconds=settings.player_cache_ttl_seconds)
        return players

    async def get_all_players(self) -> dict[str, dict[str, Any]]:
        cached = self.cache.get(self.cache_key)
        if cached is not None:
            return cached
        return await self.refresh()

    async def get_player(self, player_id: str) -> dict[str, Any] | None:
        players = await self.get_all_players()
        return players.get(player_id)

    async def get_players(self, player_ids: list[str]) -> dict[str, dict[str, Any]]:
        players = await self.get_all_players()
        return {player_id: players[player_id] for player_id in player_ids if player_id in players}
