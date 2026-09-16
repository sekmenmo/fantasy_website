from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.services.dashboard import DashboardDataService
from app.services.normalization import normalize_league
from app.services.sleeper import SleeperClient

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/league")
async def league() -> dict:
    client = SleeperClient()
    return normalize_league(await client.get_league(settings.league_id)).model_dump()


@router.get("/weeks/{week}/matchups")
async def week_matchups(week: int) -> dict:
    try:
        result = await DashboardDataService().matchup_board(week)
        return result.board.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/standings")
async def standings_endpoint() -> list[dict]:
    rows = await DashboardDataService().standings()
    return [row.model_dump() for row in rows]
