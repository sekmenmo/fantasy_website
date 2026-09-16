from app.services.week_state import (
    WeekState,
    classify_week,
    completed_ranking_weeks,
    latest_completed_week,
)


def test_classifies_complete_week_from_last_scored_and_scoring():
    state = classify_week(
        1,
        current_week=2,
        last_scored_week=1,
        matchups=[{"points": 112.4}, {"points": 98.1}],
    )
    assert state == WeekState.COMPLETE


def test_classifies_current_scoring_week_as_in_progress_until_scored():
    state = classify_week(
        2,
        current_week=2,
        last_scored_week=1,
        matchups=[{"points": 12.5}, {"points": 0}],
    )
    assert state == WeekState.IN_PROGRESS


def test_classifies_unscored_future_week_as_upcoming():
    state = classify_week(
        3,
        current_week=2,
        last_scored_week=1,
        matchups=[{"points": 0}, {"points": 0}],
    )
    assert state == WeekState.UPCOMING


def test_completed_ranking_weeks_stop_at_last_completed_scoring_week():
    assert latest_completed_week(current_week=2, last_scored_week=1) == 1
    assert completed_ranking_weeks(current_week=2, last_scored_week=1) == [1]
    assert completed_ranking_weeks(current_week=4, last_scored_week=3) == [1, 2, 3]


def test_no_completed_ranking_weeks_before_first_score():
    assert latest_completed_week(current_week=1, last_scored_week=0) == 0
    assert completed_ranking_weeks(current_week=1, last_scored_week=0) == []
