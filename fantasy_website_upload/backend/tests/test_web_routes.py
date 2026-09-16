from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import PowerRanking, Team
from app.services.dashboard import BoardResult, PowerRankingResult
from app.services.normalization import build_matchup_board
from app.web import routes as web_routes


def fake_board(week=2):
    league = {
        "league_id": "league-1",
        "name": "Football Sunday",
        "season": "2026",
        "status": "in_season",
        "total_rosters": 2,
        "roster_positions": ["QB", "RB", "BN"],
        "scoring_settings": {"rec": 1.0},
    }
    users = [
        {"user_id": "u1", "display_name": "Owner A", "avatar": None, "metadata": {"team_name": "Alpha"}},
        {"user_id": "u2", "display_name": "Owner B", "avatar": None, "metadata": {"team_name": "Beta"}},
    ]
    rosters = [
        {"roster_id": 1, "owner_id": "u1", "settings": {"wins": 1, "losses": 0, "ties": 0}},
        {"roster_id": 2, "owner_id": "u2", "settings": {"wins": 0, "losses": 1, "ties": 0}},
    ]
    matchups = [
        {
            "roster_id": 1,
            "matchup_id": 1,
            "points": 10,
            "players": ["p1", "p2"],
            "starters": ["p1", "p2"],
            "players_points": {"p1": 6, "p2": 4},
        },
        {
            "roster_id": 1,
            "matchup_id": 2,
            "points": 11,
            "players": ["p1", "p2"],
            "starters": ["p1", "p2"],
            "players_points": {"p1": 7, "p2": 4},
        },
        {
            "roster_id": 2,
            "matchup_id": 2,
            "points": 12,
            "players": ["p3"],
            "starters": ["p3", "0"],
            "players_points": {"p3": 12},
        },
        {
            "roster_id": 2,
            "matchup_id": 1,
            "points": 9,
            "players": ["p3"],
            "starters": ["p3", "0"],
            "players_points": {"p3": 9},
        },
    ]
    players = {
        "p1": {"full_name": "Pass Thrower", "position": "QB", "team": "AAA"},
        "p2": {"full_name": "Run Runner", "position": "RB", "team": "BBB"},
        "p3": {"full_name": "Other QB", "position": "QB", "team": "CCC"},
    }
    return build_matchup_board(
        league,
        users,
        rosters,
        matchups,
        {"week": 2},
        players,
        {"p1": 11.0, "p2": 8.0, "p3": 10.0},
        {"p1": "ZZZ", "p2": "YYY", "p3": "XXX"},
        week,
    )


class FakeService:
    async def matchup_board(self, week=None, force_refresh=False):
        return BoardResult(board=fake_board(week or 2), warning=None, last_updated="2026-09-16 12:00")

    async def standings(self):
        return []

    async def power_rankings(self, week=None):
        return (await self.power_ranking_context(week)).rows

    async def power_ranking_context(self, week=None):
        selected_week = 1 if week not in (None, 1) else (week or 1)
        return [
            PowerRankingResult(
                rows=[
                    PowerRanking(
                        week=selected_week,
                        roster_id=1,
                        rank=1,
                        score=91.4,
                        previous_rank=3,
                        rank_change=2,
                        components={
                            "season_scoring": 100,
                            "projected_strength": 90,
                            "recent_form": 85,
                            "record": 80,
                            "health": 100,
                        },
                        component_points={
                            "season_scoring": 40,
                            "projected_strength": 22.5,
                            "recent_form": 17,
                            "record": 8,
                            "health": 5,
                        },
                        ppg=130,
                        current_projection=122,
                        recent_form=128,
                        projected_points_lost=0,
                        team=Team(
                            roster_id=1,
                            owner_id="u1",
                            owner_name="Owner A",
                            team_name="Alpha",
                            wins=1,
                            losses=0,
                        ),
                    )
                ],
                selected_week=selected_week,
                available_weeks=[1],
            )
        ][0]


def test_matchups_route_returns_html(monkeypatch):
    monkeypatch.setattr(web_routes, "data_service_factory", FakeService)
    client = TestClient(app)
    response = client.get("/matchups?week=2&matchup=1")
    assert response.status_code == 200
    assert "Football Sunday" in response.text
    assert "Matchup" in response.text
    assert "1 of 2" in response.text
    assert "Pass Thrower" in response.text
    assert "Empty Slot" in response.text
    assert "Collapse Bench" in response.text
    assert "2026 Season" not in response.text
    assert "Updated 2026-09-16" not in response.text


def test_matchup_partial_route_returns_board(monkeypatch):
    monkeypatch.setattr(web_routes, "data_service_factory", FakeService)
    client = TestClient(app)
    response = client.get("/matchups/panel?week=2&matchup=2")
    assert response.status_code == 200
    assert "matchup-card" in response.text
    assert "2 of 2" in response.text


def test_direct_url_selects_correct_week_dropdown(monkeypatch):
    monkeypatch.setattr(web_routes, "data_service_factory", FakeService)
    client = TestClient(app)
    response = client.get("/matchups?week=5&matchup=1")
    assert response.status_code == 200
    assert '<option value="5" selected>5</option>' in response.text
    assert 'hx-push-url="/matchups?week=6&matchup=1"' in response.text


def test_next_week_content_rerenders_selected_week(monkeypatch):
    monkeypatch.setattr(web_routes, "data_service_factory", FakeService)
    client = TestClient(app)
    response = client.get("/matchups/content?week=5&matchup=1")
    assert response.status_code == 200
    assert '<option value="5" selected>5</option>' in response.text
    assert 'hx-get="/matchups/content?week=4&matchup=1"' in response.text
    assert 'hx-get="/matchups/content?week=6&matchup=1"' in response.text


def test_previous_week_content_rerenders_selected_week(monkeypatch):
    monkeypatch.setattr(web_routes, "data_service_factory", FakeService)
    client = TestClient(app)
    response = client.get("/matchups/content?week=4&matchup=1")
    assert response.status_code == 200
    assert '<option value="4" selected>4</option>' in response.text
    assert 'hx-get="/matchups/content?week=3&matchup=1"' in response.text


def test_out_of_range_week_is_clamped_gracefully(monkeypatch):
    monkeypatch.setattr(web_routes, "data_service_factory", FakeService)
    client = TestClient(app)
    response = client.get("/matchups?week=99&matchup=1")
    assert response.status_code == 200
    assert '<option value="18" selected>18</option>' in response.text


def test_matchup_index_wrap_helpers():
    assert web_routes.resolve_matchup_index(8, 7) == 1
    assert web_routes.resolve_matchup_index(0, 7) == 7
    assert web_routes.wrapped_neighbor(1, 7, -1) == 7
    assert web_routes.wrapped_neighbor(7, 7, 1) == 1
    assert web_routes.resolve_week(99) == 18
    assert web_routes.resolve_week(-2) == 1


def test_power_rankings_route_renders_compact_table(monkeypatch):
    monkeypatch.setattr(web_routes, "data_service_factory", FakeService)
    client = TestClient(app)
    response = client.get("/power-rankings?week=1")
    assert response.status_code == 200
    assert "Power Rankings" in response.text
    assert "Alpha" in response.text
    assert "91.4" in response.text
    assert "Projected Points Lost" not in response.text
    assert "Season Scoring" not in response.text
    assert "▲ 2" in response.text
    assert "Moved up 2 positions" in response.text
    assert '<option value="1" selected>Week 1</option>' in response.text


def test_power_rankings_resolves_to_completed_week(monkeypatch):
    monkeypatch.setattr(web_routes, "data_service_factory", FakeService)
    client = TestClient(app)
    response = client.get("/power-rankings?week=2")
    assert response.status_code == 200
    assert '<option value="1" selected>Week 1</option>' in response.text
    assert '<option value="2"' not in response.text
