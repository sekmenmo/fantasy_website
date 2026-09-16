from __future__ import annotations

from enum import StrEnum
from typing import Any


class WeekState(StrEnum):
    UPCOMING = "upcoming"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


def has_scoring(matchups: list[dict[str, Any]]) -> bool:
    return any(float(row.get("points") or 0) > 0 for row in matchups)


def classify_week(
    week: int,
    *,
    current_week: int,
    last_scored_week: int,
    matchups: list[dict[str, Any]],
) -> WeekState:
    if week <= last_scored_week and has_scoring(matchups):
        return WeekState.COMPLETE
    if week == current_week and has_scoring(matchups):
        return WeekState.IN_PROGRESS
    return WeekState.UPCOMING


def latest_completed_week(current_week: int, last_scored_week: int) -> int:
    if last_scored_week > 0:
        return min(last_scored_week, current_week)
    return 0


def completed_ranking_weeks(current_week: int, last_scored_week: int) -> list[int]:
    latest = latest_completed_week(current_week, last_scored_week)
    return list(range(1, latest + 1))
