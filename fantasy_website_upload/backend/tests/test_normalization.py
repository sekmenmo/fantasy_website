from app.services.normalization import (
    active_roster_positions,
    build_matchup_board,
    build_roster_map,
    build_user_map,
    decimal_score,
    normalize_teams,
    pair_matchup_rows,
)


LEAGUE = {
    "league_id": "league-1",
    "name": "Test League",
    "season": "2026",
    "status": "in_season",
    "total_rosters": 2,
    "roster_positions": ["QB", "RB", "FLEX", "K", "DEF", "BN", "BN"],
    "scoring_settings": {"rec": 1.0},
}

USERS = [
    {
        "user_id": "u1",
        "display_name": "Owner One",
        "avatar": "avatar1",
        "metadata": {"team_name": "Alpha"},
    },
    {"user_id": "u2", "display_name": "Owner Two", "avatar": None, "metadata": {}},
]

ROSTERS = [
    {
        "roster_id": 1,
        "owner_id": "u1",
        "settings": {
            "wins": 1,
            "losses": 0,
            "ties": 0,
            "fpts": 123,
            "fpts_decimal": 45,
            "fpts_against": 100,
            "fpts_against_decimal": 10,
        },
    },
    {
        "roster_id": 2,
        "owner_id": "u2",
        "settings": {
            "wins": 0,
            "losses": 1,
            "ties": 0,
            "fpts": 100,
            "fpts_decimal": 10,
            "fpts_against": 123,
            "fpts_against_decimal": 45,
        },
    },
]

PLAYERS = {
    "p1": {"full_name": "Player One", "first_name": "Player", "last_name": "One", "position": "QB", "team": "AAA"},
    "p2": {"full_name": "Player Two", "first_name": "Player", "last_name": "Two", "position": "RB", "team": "BBB"},
    "p3": {"full_name": "Player Three", "first_name": "Player", "last_name": "Three", "position": "WR", "team": "CCC"},
    "p4": {"full_name": "Player Four", "first_name": "Player", "last_name": "Four", "position": "K", "team": "DDD"},
    "DST": {"first_name": "Test", "last_name": "Defense", "position": "DEF", "team": "DST"},
}

MATCHUPS = [
    {
        "roster_id": 1,
        "matchup_id": 8,
        "points": 80.5,
        "players": ["p1", "p2", "p3", "p4", "DST"],
        "starters": ["p1", "p2", "p3", "p4", "DST"],
        "players_points": {"p1": 20, "p2": 10, "p3": 30, "p4": 8, "DST": 12.5},
    },
    {
        "roster_id": 2,
        "matchup_id": 8,
        "points": 75.0,
        "players": ["p1", "p2", "p3", "p4", "DST"],
        "starters": ["p1", "0", "p3", "p4", "DST"],
        "players_points": {"p1": 18, "p3": 25, "p4": 12, "DST": 20},
    },
]


def test_user_and_roster_mappings_are_distinct():
    users = build_user_map(USERS)
    rosters = build_roster_map(ROSTERS)
    assert users["u1"]["display_name"] == "Owner One"
    assert rosters[1]["owner_id"] == "u1"
    assert "1" not in users


def test_decimal_score_and_team_name_preference():
    teams = normalize_teams(USERS, ROSTERS)
    assert decimal_score(ROSTERS[0]["settings"], "fpts", "fpts_decimal") == 123.45
    assert teams[1].team_name == "Alpha"
    assert teams[2].team_name == "Owner Two"
    assert teams[1].points_against == 100.1


def test_matchup_pairing_and_starter_ordering_with_empty_slot():
    assert pair_matchup_rows(MATCHUPS)[0][0] == 8
    assert active_roster_positions(LEAGUE["roster_positions"]) == ["QB", "RB", "FLEX", "K", "DEF"]
    board = build_matchup_board(
        LEAGUE,
        USERS,
        ROSTERS,
        MATCHUPS,
        {"week": 1},
        PLAYERS,
        {"p1": 21.0, "p2": 11.0, "p3": 12.0, "p4": 7.0, "DST": 6.0},
        {"p1": "ZZZ"},
        1,
    )
    matchup = board.matchups[0]
    assert matchup.team_a.starters[0].roster_slot == "QB"
    assert matchup.team_a.starters[0].player.full_name == "Player One"
    assert matchup.team_b.starters[1].roster_slot == "RB"
    assert matchup.team_b.starters[1].player is None
    assert matchup.team_b.starters[1].is_empty is True
    assert matchup.team_a.actual_points == 80.5
    assert matchup.team_a.projected_points == 57.0
    assert matchup.team_a.projection_complete is True
    assert matchup.team_b.projection_complete is True
    assert matchup.actual_margin == 5.5


def test_projection_total_marks_incomplete_when_starter_projection_missing():
    board = build_matchup_board(
        LEAGUE,
        USERS,
        ROSTERS,
        MATCHUPS,
        {"week": 2},
        PLAYERS,
        {"p1": 21.0, "p3": 12.0, "p4": 7.0, "DST": 6.0},
        {},
        2,
    )
    team = board.matchups[0].team_a
    assert team.projected_points == 46.0
    assert team.projection_complete is False
    assert board.league_summary.largest_projected_margin is not None


def test_missing_avatar_and_player_image_fallback_state():
    teams = normalize_teams(USERS, ROSTERS)
    assert teams[2].avatar_thumb_url is None
    board = build_matchup_board(
        LEAGUE,
        USERS,
        ROSTERS,
        MATCHUPS,
        {"week": 2},
        {},
        {},
        {},
        2,
    )
    unknown_player = board.matchups[0].team_a.starters[0].player
    assert unknown_player.full_name == "Unknown Player p1"
    assert unknown_player.image_url.endswith("/p1.jpg")
