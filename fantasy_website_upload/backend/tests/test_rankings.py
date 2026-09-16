from app.models.schemas import Player, Team, WeeklyPlayer, WeeklyTeam
from app.services.rankings import (
    calculate_health_scores,
    calculate_power_rankings,
    projected_points_lost_for_team,
    weighted_recent_average,
)


def team(roster_id: int, wins: int, losses: int, points_for: float) -> Team:
    return Team(
        roster_id=roster_id,
        owner_id=f"u{roster_id}",
        owner_name=f"Owner {roster_id}",
        team_name=f"Team {roster_id}",
        wins=wins,
        losses=losses,
        points_for=points_for,
        points_against=100,
    )


def wp(
    player_id: str,
    slot: str,
    position: str,
    projection: float | None,
    *,
    injury_status: str | None = None,
    is_starter: bool = True,
) -> WeeklyPlayer:
    return WeeklyPlayer(
        player=Player(
            player_id=player_id,
            full_name=player_id,
            position=position,
            nfl_team="AAA",
            injury_status=injury_status,
            image_url=f"/{player_id}.jpg",
        ),
        player_id=player_id,
        roster_slot=slot,
        projected_points=projection,
        actual_points=0,
        is_starter=is_starter,
    )


def weekly_team(starters: list[WeeklyPlayer], bench: list[WeeklyPlayer]) -> WeeklyTeam:
    return WeeklyTeam(
        team=team(1, 1, 0, 100),
        week=2,
        matchup_id=1,
        projected_points=100,
        actual_points=0,
        starters=starters,
        bench=bench,
    )


def test_recent_form_weights_latest_week_most_and_redistributes():
    assert weighted_recent_average([100, 110, 130]) == 118
    assert weighted_recent_average([100, 120]) == 112.5
    assert weighted_recent_average([100]) == 100


def test_health_single_out_starter_uses_legal_replacement():
    lost, notes = projected_points_lost_for_team(
        weekly_team(
            [wp("Starter", "RB", "RB", 19.4, injury_status="Out")],
            [wp("Bench", "BN", "RB", 10.1, is_starter=False)],
        )
    )
    assert lost == 9.3
    assert "Starter" in notes[0]


def test_health_no_legal_replacement_charges_full_baseline():
    lost, _ = projected_points_lost_for_team(
        weekly_team(
            [wp("Starter", "QB", "QB", 18.0, injury_status="Out")],
            [wp("Bench", "BN", "RB", 10.0, is_starter=False)],
        )
    )
    assert lost == 18.0


def test_health_uses_previous_projection_when_current_projection_is_zeroed():
    lost, notes = projected_points_lost_for_team(
        weekly_team(
            [wp("Starter", "RB", "RB", 0.0, injury_status="IR")],
            [wp("Bench", "BN", "RB", 8.0, is_starter=False)],
        ),
        recent_projections_by_player={"Starter": [14.0, 16.0]},
    )
    assert lost == 8.0
    assert "previous_projection" in notes[0]


def test_health_uses_recent_actuals_when_projection_baseline_is_missing():
    lost, notes = projected_points_lost_for_team(
        weekly_team(
            [wp("Starter", "RB", "RB", None, injury_status="Out")],
            [wp("Bench", "BN", "RB", 6.0, is_starter=False)],
        ),
        recent_actuals_by_player={"Starter": [12.0, 18.0]},
    )
    assert lost == 6.75
    assert "recent_actual_average_85pct" in notes[0]


def test_health_stronger_replacement_never_creates_negative_loss():
    lost, _ = projected_points_lost_for_team(
        weekly_team(
            [wp("Starter", "WR", "WR", 8.0, injury_status="Out")],
            [wp("Bench", "BN", "WR", 12.0, is_starter=False)],
        )
    )
    assert lost == 0.0


def test_health_multiple_injuries_do_not_reuse_same_bench_player():
    lost, notes = projected_points_lost_for_team(
        weekly_team(
            [
                wp("StarterA", "WR", "WR", 18.0, injury_status="Out"),
                wp("StarterB", "WR", "WR", 16.0, injury_status="Out"),
            ],
            [
                wp("BenchA", "BN", "WR", 11.0, is_starter=False),
                wp("BenchB", "BN", "WR", 7.0, is_starter=False),
            ],
        )
    )
    assert lost == 16.0
    assert "BenchA" in " ".join(notes)
    assert "BenchB" in " ".join(notes)


def test_health_flex_replacement_and_status_weights():
    questionable, _ = projected_points_lost_for_team(
        weekly_team(
            [wp("Flex", "FLEX", "RB", 20.0, injury_status="Questionable")],
            [wp("BenchWR", "BN", "WR", 12.0, is_starter=False)],
        )
    )
    doubtful, _ = projected_points_lost_for_team(
        weekly_team(
            [wp("Flex", "FLEX", "RB", 20.0, injury_status="Doubtful")],
            [wp("BenchWR", "BN", "WR", 12.0, is_starter=False)],
        )
    )
    ir, _ = projected_points_lost_for_team(
        weekly_team(
            [wp("Flex", "FLEX", "RB", 20.0, injury_status="IR")],
            [wp("BenchWR", "BN", "WR", 12.0, is_starter=False)],
        )
    )
    assert questionable == 2.0
    assert doubtful == 6.0
    assert ir == 8.0


def test_missing_baseline_and_empty_slot_do_not_fabricate_loss():
    empty = WeeklyPlayer(player=None, roster_slot="RB", is_starter=True, is_empty=True)
    lost, notes = projected_points_lost_for_team(
        weekly_team(
            [wp("Starter", "RB", "RB", None, injury_status="Out"), empty],
            [wp("Bench", "BN", "RB", 10.0, is_starter=False)],
        )
    )
    assert lost == 0.0
    assert "no defensible baseline" in notes[0]


def test_health_normalization_rewards_low_points_lost():
    scores = calculate_health_scores({1: 0.0, 2: 10.0, 3: 25.0})
    assert scores[1] == 100.0
    assert scores[3] == 0.0
    assert calculate_health_scores({1: 0.0, 2: 0.0}) == {1: 100.0, 2: 100.0}


def test_power_ranking_formula_order_and_rank_change():
    teams = {
        1: team(1, 2, 1, 360),
        2: team(2, 3, 0, 330),
        3: team(3, 1, 2, 300),
    }
    weekly_scores = {
        1: [110, 120, 130],
        2: [100, 115, 115],
        3: [90, 105, 105],
    }
    rankings = calculate_power_rankings(
        teams,
        weekly_scores,
        week=3,
        current_projections={1: 140, 2: 125, 3: 110},
        points_lost={1: 0, 2: 8, 3: 14},
        previous_ranks={1: 2, 2: 1, 3: 3},
    )
    assert rankings[0].roster_id == 1
    assert rankings[0].rank_change == 1
    assert rankings[-1].roster_id == 3
    assert rankings[0].component_points["season_scoring"] <= 40
    assert rankings[0].component_points["projected_strength"] <= 25
    assert 0 <= rankings[0].score <= 100
