from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.services.dashboard import BoardResult, DashboardDataService

router = APIRouter()
APP_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


def fmt_points(value: float | None) -> str:
    if value is None:
        return "--"
    return f"{value:.1f}"


def initials(value: str | None) -> str:
    if not value:
        return "FB"
    parts = [part for part in value.replace("&", " ").split() if part]
    if not parts:
        return "FB"
    return "".join(part[0] for part in parts[:2]).upper()


def record(team) -> str:
    return f"{team.wins}-{team.losses}-{team.ties}"


templates.env.globals["fmt_points"] = fmt_points
templates.env.globals["initials"] = initials
templates.env.globals["record"] = record

data_service_factory: Callable[[], DashboardDataService] = DashboardDataService


def resolve_matchup_index(matchup: int | None, total: int) -> int:
    if total <= 0:
        return 1
    if matchup is None:
        return 1
    return ((matchup - 1) % total) + 1


def wrapped_neighbor(index: int, total: int, direction: int) -> int:
    if total <= 0:
        return 1
    return ((index - 1 + direction) % total) + 1


def resolve_week(week: int | None) -> int | None:
    if week is None:
        return None
    return min(18, max(1, week))


def board_context(request: Request, result: BoardResult, matchup: int | None = None) -> dict:
    board = result.board
    current_week = board.week
    matchup_count = len(board.matchups)
    selected_matchup_index = resolve_matchup_index(matchup, matchup_count)
    selected_matchup = board.matchups[selected_matchup_index - 1] if board.matchups else None
    return {
        "request": request,
        "board": board,
        "selected_matchup": selected_matchup,
        "selected_matchup_index": selected_matchup_index,
        "matchup_count": matchup_count,
        "previous_matchup": wrapped_neighbor(selected_matchup_index, matchup_count, -1),
        "next_matchup": wrapped_neighbor(selected_matchup_index, matchup_count, 1),
        "warning": result.warning,
        "last_updated": result.last_updated,
        "selected_week": current_week,
        "weeks": range(1, 19),
        "previous_week": max(1, current_week - 1),
        "next_week": min(18, current_week + 1),
        "active_page": "matchups",
    }


@router.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/matchups", status_code=303)


@router.get("/matchups", response_class=HTMLResponse)
async def matchups(
    request: Request,
    week: int | None = Query(default=None),
    matchup: int | None = Query(default=1),
) -> HTMLResponse:
    try:
        result = await data_service_factory().matchup_board(resolve_week(week))
        return templates.TemplateResponse(request, "matchups.html", board_context(request, result, matchup))
    except Exception:
        return templates.TemplateResponse(
            request,
            "matchups.html",
            {
                "request": request,
                "board": None,
                "error": "No usable Sleeper data is available yet.",
                "selected_week": resolve_week(week) or 1,
                "weeks": range(1, 19),
                "active_page": "matchups",
            },
        )


@router.get("/matchups/content", response_class=HTMLResponse)
async def matchup_content_partial(
    request: Request,
    week: int | None = Query(default=None),
    matchup: int | None = Query(default=1),
) -> HTMLResponse:
    try:
        result = await data_service_factory().matchup_board(resolve_week(week))
        return templates.TemplateResponse(request, "partials/matchups_content.html", board_context(request, result, matchup))
    except Exception:
        return templates.TemplateResponse(
            request,
            "partials/error_banner.html",
            {
                "request": request,
                "message": "Could not load that week. Try Refresh.",
                "week": resolve_week(week) or 1,
            },
        )


@router.get("/matchups/board", response_class=HTMLResponse)
async def matchup_board_partial(
    request: Request,
    week: int = Query(default=1),
    matchup: int = Query(default=1),
) -> HTMLResponse:
    return await matchup_panel_partial(request, week, matchup)


@router.get("/matchups/panel", response_class=HTMLResponse)
async def matchup_panel_partial(
    request: Request,
    week: int = Query(default=1),
    matchup: int = Query(default=1),
) -> HTMLResponse:
    try:
        result = await data_service_factory().matchup_board(resolve_week(week))
        return templates.TemplateResponse(request, "partials/matchup_panel.html", board_context(request, result, matchup))
    except Exception:
        return templates.TemplateResponse(
            request,
            "partials/error_banner.html",
            {
                "request": request,
                "message": "Could not load that week. Try Refresh.",
                "week": resolve_week(week) or 1,
            },
        )


@router.post("/matchups/refresh", response_class=HTMLResponse)
async def refresh_matchups(
    request: Request,
    week: int = Query(default=1),
    matchup: int = Query(default=1),
) -> HTMLResponse:
    try:
        result = await data_service_factory().matchup_board(resolve_week(week), force_refresh=True)
        return templates.TemplateResponse(request, "partials/matchup_panel.html", board_context(request, result, matchup))
    except Exception:
        return templates.TemplateResponse(
            request,
            "partials/error_banner.html",
            {
                "request": request,
                "message": "Refresh failed and no cached board could be rendered.",
                "week": resolve_week(week) or 1,
            },
        )


@router.get("/standings", response_class=HTMLResponse)
async def standings_page(request: Request) -> HTMLResponse:
    rows = await data_service_factory().standings()
    return templates.TemplateResponse(
        request,
        "standings.html",
        {"request": request, "rows": rows, "active_page": "standings"},
    )


@router.get("/rankings", response_class=HTMLResponse)
async def rankings_alias() -> RedirectResponse:
    return RedirectResponse(url="/power-rankings", status_code=303)


@router.get("/power-rankings", response_class=HTMLResponse)
async def rankings_page(
    request: Request,
    week: int | None = Query(default=None),
) -> HTMLResponse:
    resolved_week = resolve_week(week)
    result = await data_service_factory().power_ranking_context(resolved_week)
    return templates.TemplateResponse(
        request,
        "rankings.html",
        {
            "request": request,
            "rows": result.rows,
            "active_page": "rankings",
            "selected_week": result.selected_week,
            "available_weeks": result.available_weeks,
        },
    )
