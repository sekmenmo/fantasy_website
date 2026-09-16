from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.models.schemas import (
    LeagueInfo,
    LeagueSummary,
    Matchup,
    MatchupBoard,
    Player,
    StandingRow,
    Team,
    WeeklyPlayer,
    WeeklyTeam,
)
from app.services.images import PlayerImageProvider, avatar_url

NON_STARTER_SLOTS = {"BN", "BE", "IR", "TAXI"}


def decimal_score(settings: dict[str, Any], whole_key: str, decimal_key: str) -> float:
    whole = float(settings.get(whole_key, 0) or 0)
    decimal = float(settings.get(decimal_key, 0) or 0)
    return round(whole + decimal / 100, 2)


def active_roster_positions(roster_positions: list[str]) -> list[str]:
    return [slot for slot in roster_positions if slot not in NON_STARTER_SLOTS]


def build_user_map(users: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(user["user_id"]): user for user in users if user.get("user_id") is not None}


def build_roster_map(rosters: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(roster["roster_id"]): roster for roster in rosters if roster.get("roster_id") is not None}


def team_name_for_roster(roster: dict[str, Any], user: dict[str, Any] | None) -> str:
    metadata = user.get("metadata") if user else None
    if isinstance(metadata, dict) and metadata.get("team_name"):
        return str(metadata["team_name"])
    if user and user.get("display_name"):
        return str(user["display_name"])
    return f"Roster {roster.get('roster_id', 'Unknown')}"


def owner_name_for_user(user: dict[str, Any] | None) -> str:
    if user and user.get("display_name"):
        return str(user["display_name"])
    return "Unknown Owner"


def normalize_teams(users: list[dict[str, Any]], rosters: list[dict[str, Any]]) -> dict[int, Team]:
    users_by_id = build_user_map(users)
    teams: dict[int, Team] = {}
    for roster in rosters:
        roster_id = int(roster["roster_id"])
        owner_id = roster.get("owner_id")
        user = users_by_id.get(str(owner_id)) if owner_id else None
        roster_settings = roster.get("settings") or {}
        avatar_id = user.get("avatar") if user else None
        teams[roster_id] = Team(
            roster_id=roster_id,
            owner_id=str(owner_id) if owner_id else None,
            owner_name=owner_name_for_user(user),
            team_name=team_name_for_roster(roster, user),
            avatar_id=avatar_id,
            avatar_url=avatar_url(avatar_id),
            avatar_thumb_url=avatar_url(avatar_id, thumbnail=True),
            wins=int(roster_settings.get("wins", 0) or 0),
            losses=int(roster_settings.get("losses", 0) or 0),
            ties=int(roster_settings.get("ties", 0) or 0),
            points_for=decimal_score(roster_settings, "fpts", "fpts_decimal"),
            points_against=decimal_score(roster_settings, "fpts_against", "fpts_against_decimal"),
        )
    return teams


def normalize_league(league: dict[str, Any]) -> LeagueInfo:
    avatar_id = league.get("avatar")
    scoring = league.get("scoring_settings") or {}
    return LeagueInfo(
        league_id=str(league["league_id"]),
        name=str(league.get("name") or "Sleeper League"),
        season=str(league.get("season") or ""),
        status=str(league.get("status") or "unknown"),
        total_rosters=int(league.get("total_rosters") or league.get("settings", {}).get("num_teams") or 0),
        roster_positions=list(league.get("roster_positions") or []),
        scoring_settings={key: float(value) for key, value in scoring.items() if isinstance(value, int | float)},
        avatar_id=avatar_id,
        avatar_url=avatar_url(avatar_id),
    )


def make_player(
    player_id: str,
    metadata: dict[str, Any] | None,
    image_provider: PlayerImageProvider,
) -> Player | None:
    if not player_id or player_id == "0":
        return None
    if metadata is None:
        return Player(
            player_id=player_id,
            full_name=f"Unknown Player {player_id}",
            image_url=image_provider.get_image_url(player_id),
        )
    first_name = metadata.get("first_name")
    last_name = metadata.get("last_name")
    full_name = metadata.get("full_name") or " ".join(part for part in [first_name, last_name] if part) or player_id
    nfl_team = metadata.get("team") or metadata.get("team_abbr")
    return Player(
        player_id=player_id,
        full_name=str(full_name),
        first_name=str(first_name) if first_name else None,
        last_name=str(last_name) if last_name else None,
        position=metadata.get("position"),
        nfl_team=nfl_team,
        injury_status=metadata.get("injury_status"),
        status=metadata.get("status"),
        image_url=image_provider.get_image_url(player_id, nfl_team),
    )


def weekly_player(
    player_id: str,
    slot: str,
    actual_points: float | None,
    projected_points: float | None,
    players_by_id: dict[str, dict[str, Any]],
    projection_opponents: dict[str, str | None],
    image_provider: PlayerImageProvider,
    *,
    is_starter: bool,
) -> WeeklyPlayer:
    player = make_player(player_id, players_by_id.get(player_id), image_provider)
    is_empty = not player_id or player_id == "0"
    return WeeklyPlayer(
        player=player,
        player_id=player_id if not is_empty else None,
        roster_slot=slot,
        projected_points=projected_points,
        actual_points=actual_points,
        opponent=projection_opponents.get(player_id),
        is_starter=is_starter,
        is_empty=is_empty,
    )


def build_weekly_team(
    matchup_row: dict[str, Any],
    team: Team,
    week: int,
    roster_positions: list[str],
    players_by_id: dict[str, dict[str, Any]],
    projections: dict[str, float | None],
    projection_opponents: dict[str, str | None],
    image_provider: PlayerImageProvider,
) -> WeeklyTeam:
    starter_slots = active_roster_positions(roster_positions)
    starters = list(matchup_row.get("starters") or [])
    players = list(matchup_row.get("players") or [])
    players_points = matchup_row.get("players_points") or {}

    starter_rows: list[WeeklyPlayer] = []
    for index, slot in enumerate(starter_slots):
        player_id = str(starters[index]) if index < len(starters) else "0"
        actual = players_points.get(player_id)
        starter_rows.append(
            weekly_player(
                player_id,
                slot,
                float(actual) if actual is not None else None,
                projections.get(player_id),
                players_by_id,
                projection_opponents,
                image_provider,
                is_starter=True,
            )
        )

    starter_set = set(starters)
    bench_rows: list[WeeklyPlayer] = []
    for player_id in players:
        player_id = str(player_id)
        if player_id in starter_set:
            continue
        actual = players_points.get(player_id)
        bench_rows.append(
            weekly_player(
                player_id,
                "BN",
                float(actual) if actual is not None else None,
                projections.get(player_id),
                players_by_id,
                projection_opponents,
                image_provider,
                is_starter=False,
            )
        )

    projected_total = sum(row.projected_points for row in starter_rows if row.projected_points is not None)
    non_empty_starters = [row for row in starter_rows if not row.is_empty]
    has_projection = any(row.projected_points is not None for row in non_empty_starters)
    projection_complete = bool(non_empty_starters) and all(
        row.projected_points is not None for row in non_empty_starters
    )
    return WeeklyTeam(
        team=team,
        week=week,
        matchup_id=int(matchup_row["matchup_id"]),
        projected_points=round(projected_total, 2) if has_projection else None,
        projection_complete=projection_complete,
        actual_points=float(matchup_row.get("points") or 0),
        starters=starter_rows,
        bench=bench_rows,
    )


def pair_matchup_rows(matchups: list[dict[str, Any]]) -> list[tuple[int, list[dict[str, Any]]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in matchups:
        grouped[int(row["matchup_id"])].append(row)
    return sorted(grouped.items(), key=lambda item: item[0])


def matchup_status(week: int, nfl_state: dict[str, Any], matchup_rows: list[dict[str, Any]]) -> str:
    current_week = int(nfl_state.get("week") or nfl_state.get("leg") or 0)
    if week < current_week:
        return "completed"
    if week > current_week:
        return "upcoming"
    if any(float(row.get("points") or 0) > 0 for row in matchup_rows):
        return "live"
    return "upcoming"


def build_matchup_board(
    league: dict[str, Any],
    users: list[dict[str, Any]],
    rosters: list[dict[str, Any]],
    raw_matchups: list[dict[str, Any]],
    nfl_state: dict[str, Any],
    players_by_id: dict[str, dict[str, Any]],
    projections: dict[str, float | None],
    projection_opponents: dict[str, str | None],
    week: int,
    image_provider: PlayerImageProvider | None = None,
) -> MatchupBoard:
    image_provider = image_provider or PlayerImageProvider()
    league_info = normalize_league(league)
    teams = normalize_teams(users, rosters)
    status = matchup_status(week, nfl_state, raw_matchups)
    matchup_models: list[Matchup] = []

    for matchup_id, rows in pair_matchup_rows(raw_matchups):
        if len(rows) != 2:
            continue
        team_a = build_weekly_team(
            rows[0],
            teams[int(rows[0]["roster_id"])],
            week,
            league_info.roster_positions,
            players_by_id,
            projections,
            projection_opponents,
            image_provider,
        )
        team_b = build_weekly_team(
            rows[1],
            teams[int(rows[1]["roster_id"])],
            week,
            league_info.roster_positions,
            players_by_id,
            projections,
            projection_opponents,
            image_provider,
        )
        projected_margin = None
        if team_a.projected_points is not None and team_b.projected_points is not None:
            projected_margin = round(team_a.projected_points - team_b.projected_points, 2)
        matchup_models.append(
            Matchup(
                matchup_id=matchup_id,
                week=week,
                team_a=team_a,
                team_b=team_b,
                projected_margin=projected_margin,
                actual_margin=round(team_a.actual_points - team_b.actual_points, 2),
                status=status,
            )
        )

    summary = build_league_summary(week, status, matchup_models)
    return MatchupBoard(
        league=league_info,
        week=week,
        status=status,
        league_summary=summary,
        matchups=matchup_models,
    )


def build_league_summary(week: int, status: str, matchups: list[Matchup]) -> LeagueSummary:
    teams = [team for matchup in matchups for team in [matchup.team_a, matchup.team_b]]
    projected = [team for team in teams if team.projected_points is not None]
    summary = LeagueSummary(week=week, status=status, matchup_count=len(matchups))
    if projected:
        summary.league_avg_projection = round(
            sum(team.projected_points or 0 for team in projected) / len(projected), 2
        )
        high = max(projected, key=lambda team: team.projected_points or 0)
        low = min(projected, key=lambda team: team.projected_points or 0)
        summary.highest_projection_team = high.team.team_name
        summary.highest_projection = high.projected_points
        summary.lowest_projection_team = low.team.team_name
        summary.lowest_projection = low.projected_points
        projected_matchups = [m for m in matchups if m.projected_margin is not None]
        if projected_matchups:
            closest = min(projected_matchups, key=lambda matchup: abs(matchup.projected_margin or 0))
            largest = max(projected_matchups, key=lambda matchup: abs(matchup.projected_margin or 0))
            summary.closest_projected_matchup = (
                f"{closest.team_a.team.team_name} vs {closest.team_b.team.team_name}"
            )
            summary.closest_projected_margin = abs(closest.projected_margin or 0)
            summary.largest_projected_matchup = f"{largest.team_a.team.team_name} vs {largest.team_b.team.team_name}"
            summary.largest_projected_margin = abs(largest.projected_margin or 0)

    if teams and status in {"completed", "live"}:
        summary.league_avg_score = round(sum(team.actual_points for team in teams) / len(teams), 2)
        high_score = max(teams, key=lambda team: team.actual_points)
        low_score = min(teams, key=lambda team: team.actual_points)
        summary.highest_score_team = high_score.team.team_name
        summary.highest_score = high_score.actual_points
        summary.lowest_score_team = low_score.team.team_name
        summary.lowest_score = low_score.actual_points
        closest_actual = min(matchups, key=lambda matchup: abs(matchup.actual_margin))
        largest = max(matchups, key=lambda matchup: abs(matchup.actual_margin))
        summary.closest_actual_matchup = (
            f"{closest_actual.team_a.team.team_name} vs {closest_actual.team_b.team.team_name}"
        )
        summary.closest_actual_margin = abs(closest_actual.actual_margin)
        summary.largest_blowout_matchup = f"{largest.team_a.team.team_name} vs {largest.team_b.team.team_name}"
        summary.largest_blowout_margin = abs(largest.actual_margin)
    return summary


def standings(teams: dict[int, Team], completed_weeks: int) -> list[StandingRow]:
    rows: list[StandingRow] = []
    sorted_teams = sorted(
        teams.values(),
        key=lambda team: (team.wins, team.points_for, -team.losses),
        reverse=True,
    )
    for index, team in enumerate(sorted_teams, start=1):
        games = team.wins + team.losses + team.ties
        win_pct = (team.wins + 0.5 * team.ties) / games if games else 0.0
        rows.append(
            StandingRow(
                rank=index,
                team=team,
                record=f"{team.wins}-{team.losses}-{team.ties}",
                win_pct=round(win_pct, 3),
                points_for=team.points_for,
                points_against=team.points_against,
                point_differential=round(team.points_for - team.points_against, 2),
                avg_points_per_week=round(team.points_for / completed_weeks, 2) if completed_weeks else 0.0,
            )
        )
    return rows
