from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from typing import Any, Awaitable, Callable

from app.config import settings
from app.database.models import PowerRankingSnapshot
from app.database.session import engine
from app.models.schemas import MatchupBoard, PowerRanking, StandingRow
from app.services.cache import JsonCache
from app.services.images import PlayerImageProvider
from app.services.normalization import build_matchup_board, normalize_teams, standings
from app.services.player_metadata import PlayerMetadataService
from app.services.projections import SleeperProjectionProvider, projection_stat_key
from app.services.rankings import calculate_power_rankings, projected_points_lost_for_team
from app.services.sleeper import SleeperClient
from app.services.week_state import completed_ranking_weeks, has_scoring
from sqlmodel import Session, select


@dataclass
class BoardResult:
    board: MatchupBoard
    warning: str | None = None
    last_updated: str | None = None
    refreshed: bool = False


@dataclass
class PowerRankingResult:
    rows: list[PowerRanking]
    selected_week: int
    available_weeks: list[int]


class DashboardDataService:
    def __init__(self, client: SleeperClient | None = None, cache: JsonCache | None = None) -> None:
        self.client = client or SleeperClient()
        self.cache = cache or JsonCache()

    async def matchup_board(self, week: int | None = None, *, force_refresh: bool = False) -> BoardResult:
        warning_parts: list[str] = []
        fresh_keys: set[str] = set()
        nfl_state = await self._cached(
            "sleeper:nfl_state",
            self.client.get_nfl_state,
            ttl_seconds=settings.short_cache_ttl_seconds,
            force_refresh=force_refresh,
            warnings=warning_parts,
            fresh_keys=fresh_keys,
        )
        selected_week = week or int(nfl_state.get("week") or nfl_state.get("leg") or 1)
        league = await self._cached(
            "sleeper:league",
            lambda: self.client.get_league(settings.league_id),
            ttl_seconds=settings.short_cache_ttl_seconds,
            force_refresh=force_refresh,
            warnings=warning_parts,
            fresh_keys=fresh_keys,
        )
        users = await self._cached(
            "sleeper:users",
            lambda: self.client.get_users(settings.league_id),
            ttl_seconds=settings.short_cache_ttl_seconds,
            force_refresh=force_refresh,
            warnings=warning_parts,
            fresh_keys=fresh_keys,
        )
        rosters = await self._cached(
            "sleeper:rosters",
            lambda: self.client.get_rosters(settings.league_id),
            ttl_seconds=settings.short_cache_ttl_seconds,
            force_refresh=force_refresh,
            warnings=warning_parts,
            fresh_keys=fresh_keys,
        )
        matchup_cache_key = f"sleeper:matchups:{selected_week}"
        matchups = await self._cached(
            matchup_cache_key,
            lambda: self.client.get_matchups(settings.league_id, selected_week),
            ttl_seconds=settings.short_cache_ttl_seconds,
            force_refresh=force_refresh,
            warnings=warning_parts,
            fresh_keys=fresh_keys,
        )

        player_service = PlayerMetadataService(self.client, self.cache)
        try:
            all_players = await player_service.get_all_players()
        except Exception:
            all_players = self.cache.get_stale(PlayerMetadataService.cache_key) or {}
            if all_players:
                warning_parts.append("Showing cached player metadata.")
            else:
                raise

        player_ids = sorted(
            {
                str(player_id)
                for matchup in matchups
                for player_id in (matchup.get("players") or []) + (matchup.get("starters") or [])
                if player_id and str(player_id) != "0"
            }
        )
        players = {player_id: all_players[player_id] for player_id in player_ids if player_id in all_players}

        stat_key = projection_stat_key(league.get("scoring_settings") or {})
        projection_provider = SleeperProjectionProvider(self.cache, stat_key=stat_key)
        try:
            projections = await projection_provider.get_week_projections(
                int(league["season"]),
                selected_week,
                player_ids,
                force_refresh=force_refresh,
            )
            projection_records = await projection_provider.get_week_projection_records(
                int(league["season"]),
                selected_week,
                force_refresh=force_refresh,
            )
        except Exception:
            projections = {player_id: None for player_id in player_ids}
            projection_records = []
            warning_parts.append("Projections are temporarily unavailable. Scores were refreshed where possible.")

        opponents = {str(record.get("player_id")): record.get("opponent") for record in projection_records}
        board = build_matchup_board(
            league,
            users,
            rosters,
            matchups,
            nfl_state,
            players,
            projections,
            opponents,
            selected_week,
            PlayerImageProvider(),
        )
        return BoardResult(
            board=board,
            warning=" ".join(dict.fromkeys(warning_parts)) or None,
            last_updated=self._latest_update(selected_week),
            refreshed=force_refresh and matchup_cache_key in fresh_keys,
        )

    async def standings(self) -> list[StandingRow]:
        league = await self._cached(
            "sleeper:league",
            lambda: self.client.get_league(settings.league_id),
            ttl_seconds=settings.short_cache_ttl_seconds,
            force_refresh=False,
            warnings=[],
        )
        users = await self._cached(
            "sleeper:users",
            lambda: self.client.get_users(settings.league_id),
            ttl_seconds=settings.short_cache_ttl_seconds,
            force_refresh=False,
            warnings=[],
        )
        rosters = await self._cached(
            "sleeper:rosters",
            lambda: self.client.get_rosters(settings.league_id),
            ttl_seconds=settings.short_cache_ttl_seconds,
            force_refresh=False,
            warnings=[],
        )
        teams = normalize_teams(users, rosters)
        completed_weeks = int((league.get("settings") or {}).get("last_scored_leg") or 0)
        return standings(teams, completed_weeks)

    async def power_rankings(self, week: int | None = None) -> list[PowerRanking]:
        return (await self.power_ranking_context(week)).rows

    async def power_ranking_context(self, week: int | None = None) -> PowerRankingResult:
        selected_week, available_weeks = await self._resolve_power_ranking_week(week)
        if not available_weeks:
            return PowerRankingResult(rows=[], selected_week=selected_week, available_weeks=[])

        board_result = await self.matchup_board(selected_week)
        board = board_result.board
        teams = {
            team.team.roster_id: team.team
            for matchup in board.matchups
            for team in [matchup.team_a, matchup.team_b]
        }
        completed_scores = await self._weekly_scores(int(board.league.season), board.week)
        current_projections = {
            team.team.roster_id: team.projected_points
            for matchup in board.matchups
            for team in [matchup.team_a, matchup.team_b]
        }
        points_lost: dict[int, float] = {}
        health_notes: dict[int, list[str]] = {}
        stat_key = projection_stat_key(board.league.scoring_settings)
        projection_provider = SleeperProjectionProvider(self.cache, stat_key=stat_key)
        player_ids = sorted(
            {
                player.player_id
                for matchup in board.matchups
                for weekly_team in [matchup.team_a, matchup.team_b]
                for player in weekly_team.starters + weekly_team.bench
                if player.player_id
            }
        )
        fallback_projections, fallback_actuals = await self._recent_player_baselines(
            int(board.league.season),
            board.week,
            player_ids,
            projection_provider,
        )
        for matchup in board.matchups:
            for weekly_team in [matchup.team_a, matchup.team_b]:
                lost, notes = projected_points_lost_for_team(
                    weekly_team,
                    fallback_actuals,
                    fallback_projections,
                )
                points_lost[weekly_team.team.roster_id] = lost
                health_notes[weekly_team.team.roster_id] = notes

        previous_ranks = self._previous_ranks(board.league.season, board.week)
        rankings = calculate_power_rankings(
            teams,
            completed_scores,
            board.week,
            current_projections=current_projections,
            points_lost=points_lost,
            health_notes=health_notes,
            previous_ranks=previous_ranks,
        )
        self._persist_ranking_snapshot(board.league.season, board.week, rankings)
        return PowerRankingResult(rows=rankings, selected_week=board.week, available_weeks=available_weeks)

    async def _recent_player_baselines(
        self,
        season: int,
        week: int,
        player_ids: list[str],
        projection_provider: SleeperProjectionProvider,
    ) -> tuple[dict[str, list[float]], dict[str, list[float]]]:
        if week <= 1 or not player_ids:
            return {}, {}

        start_week = max(1, week - 3)
        recent_projections: dict[str, list[float]] = {player_id: [] for player_id in player_ids}
        recent_actuals: dict[str, list[float]] = {player_id: [] for player_id in player_ids}

        for scored_week in range(start_week, week):
            projections = await projection_provider.get_week_projections(season, scored_week, player_ids)
            for player_id, value in projections.items():
                if value is not None and value > 0:
                    recent_projections.setdefault(player_id, []).append(float(value))

            rows = await self._cached(
                f"sleeper:matchups:{scored_week}",
                lambda scored_week=scored_week: self.client.get_matchups(settings.league_id, scored_week),
                ttl_seconds=settings.short_cache_ttl_seconds,
                force_refresh=False,
                warnings=[],
            )
            for row in rows:
                players_points = row.get("players_points") or {}
                for player_id in player_ids:
                    value = players_points.get(player_id)
                    if value is not None and float(value) > 0:
                        recent_actuals.setdefault(player_id, []).append(float(value))

        return (
            {player_id: values for player_id, values in recent_projections.items() if values},
            {player_id: values for player_id, values in recent_actuals.items() if values},
        )

    async def power_ranking_weeks(self) -> list[int]:
        _, available_weeks = await self._resolve_power_ranking_week(None)
        return available_weeks

    async def _resolve_power_ranking_week(self, week: int | None) -> tuple[int, list[int]]:
        nfl_state = await self._cached(
            "sleeper:nfl_state",
            self.client.get_nfl_state,
            ttl_seconds=settings.short_cache_ttl_seconds,
            force_refresh=False,
            warnings=[],
        )
        league = await self._cached(
            "sleeper:league",
            lambda: self.client.get_league(settings.league_id),
            ttl_seconds=settings.short_cache_ttl_seconds,
            force_refresh=False,
            warnings=[],
        )
        current_week = int(nfl_state.get("week") or nfl_state.get("leg") or 1)
        last_scored_week = int((league.get("settings") or {}).get("last_scored_leg") or 0)
        candidate_weeks = completed_ranking_weeks(current_week, last_scored_week)
        available_weeks: list[int] = []
        for candidate_week in candidate_weeks:
            matchups = await self._cached(
                f"sleeper:matchups:{candidate_week}",
                lambda candidate_week=candidate_week: self.client.get_matchups(settings.league_id, candidate_week),
                ttl_seconds=settings.short_cache_ttl_seconds,
                force_refresh=False,
                warnings=[],
            )
            if has_scoring(matchups):
                available_weeks.append(candidate_week)
        if not available_weeks:
            return max(1, min(18, week or current_week)), []
        if week in available_weeks:
            return int(week), available_weeks
        return available_weeks[-1], available_weeks

    async def _weekly_scores(self, season: int, week: int) -> dict[int, list[float]]:
        league = await self._cached(
            "sleeper:league",
            lambda: self.client.get_league(settings.league_id),
            ttl_seconds=settings.short_cache_ttl_seconds,
            force_refresh=False,
            warnings=[],
        )
        last_scored = int((league.get("settings") or {}).get("last_scored_leg") or 0)
        max_week = min(week, last_scored)
        scores: dict[int, list[float]] = {}
        for scored_week in range(1, max_week + 1):
            rows = await self._cached(
                f"sleeper:matchups:{scored_week}",
                lambda scored_week=scored_week: self.client.get_matchups(settings.league_id, scored_week),
                ttl_seconds=settings.short_cache_ttl_seconds,
                force_refresh=False,
                warnings=[],
            )
            for row in rows:
                scores.setdefault(int(row["roster_id"]), []).append(float(row.get("points") or 0))
        return scores

    def _previous_ranks(self, season: str, week: int) -> dict[int, int]:
        with Session(engine) as session:
            rows = session.exec(
                select(PowerRankingSnapshot).where(
                    PowerRankingSnapshot.season == season,
                    PowerRankingSnapshot.week == week - 1,
                )
            ).all()
            return {row.roster_id: row.rank for row in rows}

    def _persist_ranking_snapshot(self, season: str, week: int, rankings: list[PowerRanking]) -> None:
        with Session(engine) as session:
            existing = session.exec(
                select(PowerRankingSnapshot).where(
                    PowerRankingSnapshot.season == season,
                    PowerRankingSnapshot.week == week,
                )
            ).first()
            if existing is not None:
                return
            now = datetime.now(UTC)
            for ranking in rankings:
                session.add(
                    PowerRankingSnapshot(
                        season=season,
                        week=week,
                        roster_id=ranking.roster_id,
                        rank=ranking.rank,
                        power_score=ranking.score,
                        season_scoring_score=ranking.components.get("season_scoring", 0.0),
                        projected_strength_score=ranking.components.get("projected_strength", 0.0),
                        recent_form_score=ranking.components.get("recent_form", 0.0),
                        record_score=ranking.components.get("record", 0.0),
                        health_score=ranking.components.get("health", 0.0),
                        projected_points_lost=ranking.projected_points_lost,
                        created_at=now,
                    )
                )
            session.commit()

    async def _cached(
        self,
        key: str,
        fetcher: Callable[[], Awaitable[Any]],
        *,
        ttl_seconds: int,
        force_refresh: bool,
        warnings: list[str],
        fresh_keys: set[str] | None = None,
    ) -> Any:
        if not force_refresh:
            cached = self.cache.get(key)
            if cached is not None:
                return cached
        try:
            payload = await fetcher()
        except Exception:
            stale = self.cache.get_stale(key)
            if stale is not None:
                if force_refresh:
                    warnings.append("Unable to refresh Sleeper right now. Showing existing data.")
                else:
                    warnings.append("Showing cached Sleeper data.")
                return stale
            raise
        if fresh_keys is not None:
            fresh_keys.add(key)
        try:
            self.cache.set(key, payload, ttl_seconds=ttl_seconds)
        except Exception:
            warnings.append("Fresh data loaded, but the local cache could not be updated.")
        return payload

    def _latest_update(self, week: int) -> str | None:
        keys = [
            "sleeper:league",
            "sleeper:users",
            "sleeper:rosters",
            "sleeper:nfl_state",
            f"sleeper:matchups:{week}",
        ]
        dates = [self.cache.updated_at(key) for key in keys]
        dates = [date for date in dates if date is not None]
        if not dates:
            return None
        return max(dates).strftime("%Y-%m-%d %H:%M")
