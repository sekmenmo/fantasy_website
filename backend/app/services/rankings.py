from __future__ import annotations

from statistics import pstdev

from app.config import AVAILABILITY_STATUS_WEIGHTS, POWER_RANKING_WEIGHTS
from app.models.schemas import PowerRanking, Team, WeeklyPlayer, WeeklyTeam

FLEX_POSITIONS = {"RB", "WR", "TE"}
HEALTHY_STATUSES = {None, "", "ACTIVE", "HEALTHY"}


def minmax(values: dict[int, float]) -> dict[int, float]:
    if not values:
        return {}
    low = min(values.values())
    high = max(values.values())
    if high == low:
        return {key: 100.0 for key in values}
    return {key: round((value - low) / (high - low) * 100, 2) for key, value in values.items()}


def inverse_minmax(values: dict[int, float]) -> dict[int, float]:
    normalized = minmax(values)
    return {key: round(100.0 - value, 2) for key, value in normalized.items()}


def weighted_recent_average(scores: list[float]) -> float:
    recent = scores[-3:]
    if not recent:
        return 0.0
    base_weights = [0.2, 0.3, 0.5][-len(recent):]
    total_weight = sum(base_weights)
    return round(sum(score * weight for score, weight in zip(recent, base_weights, strict=True)) / total_weight, 2)


def consistency_score(scores: list[float]) -> float:
    if not scores:
        return 0.0
    average = sum(scores) / len(scores)
    if average <= 0:
        return 0.0
    deviation = pstdev(scores) if len(scores) > 1 else 0.0
    coefficient = deviation / average
    return average / (1 + coefficient)


def availability_weight(player: WeeklyPlayer) -> float:
    if player.is_empty or player.player is None:
        return 0.0
    status = player.player.injury_status or player.player.status
    normalized = str(status or "").upper()
    return AVAILABILITY_STATUS_WEIGHTS.get(normalized, 0.0)


def player_position(player: WeeklyPlayer) -> str | None:
    if player.player is None:
        return None
    return player.player.position


def is_legal_replacement(slot: str, player: WeeklyPlayer) -> bool:
    position = player_position(player)
    if position is None or player.is_empty:
        return False
    if slot == "FLEX":
        return position in FLEX_POSITIONS
    return position == slot


def healthy_baseline(
    player: WeeklyPlayer,
    recent_actuals: list[float] | None = None,
    recent_projections: list[float] | None = None,
) -> tuple[float | None, str | None]:
    if player.projected_points is not None and player.projected_points > 0:
        return player.projected_points, "current_projection"
    if recent_projections:
        previous_projection = next((value for value in reversed(recent_projections) if value > 0), None)
        if previous_projection is not None:
            return previous_projection, "previous_projection"
    if recent_actuals:
        average = sum(recent_actuals) / len(recent_actuals)
        if average > 0:
            return round(average * 0.85, 2), "recent_actual_average_85pct"
    return None, None


def projected_points_lost_for_team(
    weekly_team: WeeklyTeam,
    recent_actuals_by_player: dict[str, list[float]] | None = None,
    recent_projections_by_player: dict[str, list[float]] | None = None,
) -> tuple[float, list[str]]:
    recent_actuals_by_player = recent_actuals_by_player or {}
    recent_projections_by_player = recent_projections_by_player or {}
    injured: list[tuple[WeeklyPlayer, float, float, str]] = []
    notes: list[str] = []
    for starter in weekly_team.starters:
        weight = availability_weight(starter)
        if weight <= 0 or starter.is_empty:
            continue
        recent_actuals = recent_actuals_by_player.get(starter.player_id or "", [])
        recent_projections = recent_projections_by_player.get(starter.player_id or "", [])
        baseline, source = healthy_baseline(starter, recent_actuals, recent_projections)
        if baseline is None:
            notes.append(f"{starter.player.full_name if starter.player else starter.roster_slot}: no defensible baseline")
            continue
        injured.append((starter, baseline, weight, source or "unknown"))

    if not injured:
        return 0.0, notes

    replacement_pool = [
        player for player in weekly_team.bench
        if not player.is_empty and player.projected_points is not None
    ]
    best_loss: float | None = None
    best_notes: list[str] = []

    def search(
        index: int,
        used_ids: set[str],
        assignments: list[WeeklyPlayer | None],
    ) -> None:
        nonlocal best_loss, best_notes
        if index == len(injured):
            evaluate(assignments)
            return
        starter = injured[index][0]
        search(index + 1, used_ids, assignments + [None])
        for replacement in replacement_pool:
            if replacement.player_id in used_ids:
                continue
            if not is_legal_replacement(starter.roster_slot, replacement):
                continue
            next_used = set(used_ids)
            next_used.add(replacement.player_id or "")
            search(index + 1, next_used, assignments + [replacement])

    def evaluate(option: list[WeeklyPlayer | None]) -> None:
        nonlocal best_loss, best_notes
        loss = 0.0
        option_notes: list[str] = []
        for index, (starter, baseline, weight, source) in enumerate(injured):
            replacement = option[index]
            replacement_projection = 0.0
            replacement_name = "no legal replacement"
            if replacement is not None:
                replacement_projection = replacement.projected_points or 0.0
                replacement_name = replacement.player.full_name if replacement.player else "replacement"
            raw_loss = max(0.0, baseline - replacement_projection)
            loss += raw_loss * weight
            starter_name = starter.player.full_name if starter.player else starter.roster_slot
            option_notes.append(
                f"{starter_name}: baseline {baseline:.1f} ({source}), "
                f"replacement {replacement_name} {replacement_projection:.1f}, weight {weight:.2f}"
            )
        if best_loss is None or loss < best_loss:
            best_loss = loss
            best_notes = option_notes

    # Brute force is tiny for this league: at most 10 starters and 5 bench players.
    search(0, set(), [])

    return round(best_loss or 0.0, 2), notes + best_notes


def calculate_health_scores(points_lost: dict[int, float]) -> dict[int, float]:
    if not points_lost:
        return {}
    capped = {roster_id: min(value, 25.0) for roster_id, value in points_lost.items()}
    if len(set(capped.values())) == 1:
        return {roster_id: 100.0 for roster_id in capped}
    return inverse_minmax(capped)


def calculate_power_rankings(
    teams: dict[int, Team],
    weekly_scores: dict[int, list[float]],
    week: int,
    *,
    current_projections: dict[int, float | None] | None = None,
    points_lost: dict[int, float] | None = None,
    health_notes: dict[int, list[str]] | None = None,
    previous_ranks: dict[int, int] | None = None,
) -> list[PowerRanking]:
    previous_ranks = previous_ranks or {}
    current_projections = current_projections or {}
    points_lost = points_lost or {}
    health_notes = health_notes or {}

    ppg = {
        roster_id: round(sum(scores) / len(scores), 2)
        for roster_id, scores in weekly_scores.items()
        if scores
    }
    recent = {roster_id: weighted_recent_average(scores) for roster_id, scores in weekly_scores.items()}
    record = {
        roster_id: (team.wins + 0.5 * team.ties) / (team.wins + team.losses + team.ties)
        if team.wins + team.losses + team.ties
        else 0.0
        for roster_id, team in teams.items()
    }
    projection_values = {
        roster_id: value
        for roster_id, value in current_projections.items()
        if value is not None
    }

    normalized = {
        "season_scoring": minmax(ppg),
        "projected_strength": minmax(projection_values),
        "recent_form": minmax(recent),
        "record": minmax(record),
        "health": calculate_health_scores(points_lost),
    }

    rankings: list[PowerRanking] = []
    for roster_id, team in teams.items():
        components = {
            "season_scoring": normalized["season_scoring"].get(roster_id, 0.0),
            "projected_strength": normalized["projected_strength"].get(roster_id, 0.0),
            "recent_form": normalized["recent_form"].get(roster_id, 0.0),
            "record": normalized["record"].get(roster_id, 0.0),
            "health": normalized["health"].get(roster_id, 100.0 if not points_lost else 0.0),
        }
        component_points = {
            key: round(components[key] * POWER_RANKING_WEIGHTS[key], 2)
            for key in POWER_RANKING_WEIGHTS
        }
        score = sum(component_points.values())
        rankings.append(
            PowerRanking(
                week=week,
                roster_id=roster_id,
                rank=0,
                score=round(score, 2),
                previous_rank=previous_ranks.get(roster_id),
                components=components,
                component_points=component_points,
                ppg=ppg.get(roster_id, 0.0),
                current_projection=current_projections.get(roster_id),
                recent_form=recent.get(roster_id, 0.0),
                projected_points_lost=points_lost.get(roster_id, 0.0),
                baseline_notes=health_notes.get(roster_id, []),
                team=team,
            )
        )

    rankings.sort(key=lambda ranking: (-ranking.score, -(ranking.team.points_for if ranking.team else 0), ranking.roster_id))
    for index, ranking in enumerate(rankings, start=1):
        ranking.rank = index
        if ranking.previous_rank is not None:
            ranking.rank_change = ranking.previous_rank - index
    return rankings
