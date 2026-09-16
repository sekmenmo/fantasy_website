import pytest

from app.services import dashboard as dashboard_module
from app.services.dashboard import BoardResult, DashboardDataService

from test_web_routes import fake_board


class PowerRankingContextService(DashboardDataService):
    def __init__(self):
        super().__init__()
        self.baseline_player_ids: list[str] = []

    async def _resolve_power_ranking_week(self, week):
        return 2, [1, 2]

    async def matchup_board(self, week=None, *, force_refresh=False):
        return BoardResult(board=fake_board(week or 2))

    async def _weekly_scores(self, season, week):
        return {1: [100.0, 110.0], 2: [90.0, 95.0]}

    async def _recent_player_baselines(self, season, week, player_ids, projection_provider):
        self.baseline_player_ids = player_ids
        return {}, {}

    def _previous_ranks(self, season, week):
        return {}

    def _persist_ranking_snapshot(self, season, week, rankings):
        return None


@pytest.mark.asyncio
async def test_power_ranking_context_derives_player_ids_for_health_baselines():
    service = PowerRankingContextService()
    result = await service.power_ranking_context(2)

    assert result.selected_week == 2
    assert result.rows
    assert service.baseline_player_ids == ["p1", "p2", "p3"]


def league_payload():
    return {
        "league_id": "league-1",
        "name": "Football Sunday",
        "season": "2026",
        "status": "in_season",
        "total_rosters": 2,
        "roster_positions": ["QB", "RB", "BN"],
        "scoring_settings": {"rec": 1.0},
    }


def users_payload():
    return [
        {"user_id": "u1", "display_name": "Owner A", "avatar": None, "metadata": {"team_name": "Alpha"}},
        {"user_id": "u2", "display_name": "Owner B", "avatar": None, "metadata": {"team_name": "Beta"}},
    ]


def rosters_payload():
    return [
        {"roster_id": 1, "owner_id": "u1", "settings": {"wins": 1, "losses": 0, "ties": 0}},
        {"roster_id": 2, "owner_id": "u2", "settings": {"wins": 0, "losses": 1, "ties": 0}},
    ]


def matchups_payload(alpha_points=10, beta_points=9):
    return [
        {
            "roster_id": 1,
            "matchup_id": 1,
            "points": alpha_points,
            "players": ["p1", "p2"],
            "starters": ["p1", "p2"],
            "players_points": {"p1": alpha_points - 4, "p2": 4},
        },
        {
            "roster_id": 2,
            "matchup_id": 1,
            "points": beta_points,
            "players": ["p3"],
            "starters": ["p3", "0"],
            "players_points": {"p3": beta_points},
        },
    ]


def players_payload():
    return {
        "p1": {"full_name": "Pass Thrower", "position": "QB", "team": "AAA"},
        "p2": {"full_name": "Run Runner", "position": "RB", "team": "BBB"},
        "p3": {"full_name": "Other QB", "position": "QB", "team": "CCC"},
    }


class MemoryCache:
    def __init__(self):
        self.store = {
            "sleeper:nfl_state": {"week": 2},
            "sleeper:league": league_payload(),
            "sleeper:users": users_payload(),
            "sleeper:rosters": rosters_payload(),
            "sleeper:matchups:2": matchups_payload(10, 9),
            "players:nfl": players_payload(),
        }
        self.set_calls: list[str] = []

    def get(self, key):
        return self.store.get(key)

    def get_stale(self, key):
        return self.store.get(key)

    def updated_at(self, key):
        return None

    def set(self, key, payload, ttl_seconds=None):
        self.set_calls.append(key)
        self.store[key] = payload


class FakeSleeperClient:
    def __init__(self, *, fail_matchups=False):
        self.fail_matchups = fail_matchups
        self.matchup_calls: list[int] = []
        self.players_calls = 0

    async def get_nfl_state(self):
        return {"week": 2}

    async def get_league(self, league_id):
        return league_payload()

    async def get_users(self, league_id):
        return users_payload()

    async def get_rosters(self, league_id):
        return rosters_payload()

    async def get_matchups(self, league_id, week):
        self.matchup_calls.append(week)
        if self.fail_matchups:
            raise RuntimeError("sleeper unavailable")
        return matchups_payload(42, 31)

    async def get_players(self):
        self.players_calls += 1
        return players_payload()


class FakeProjectionProvider:
    fail = False
    calls: list[tuple[str, int, bool]] = []

    def __init__(self, cache, *, stat_key="pts_ppr"):
        self.cache = cache
        self.stat_key = stat_key

    async def get_week_projections(self, season, week, player_ids, *, force_refresh=False):
        self.calls.append(("values", week, force_refresh))
        if self.fail:
            raise RuntimeError("projection source unavailable")
        return {player_id: 12.0 for player_id in player_ids}

    async def get_week_projection_records(self, season, week, *, force_refresh=False):
        self.calls.append(("records", week, force_refresh))
        if self.fail:
            raise RuntimeError("projection source unavailable")
        return [{"player_id": "p1", "opponent": "ZZZ"}]


@pytest.fixture(autouse=True)
def reset_projection_provider(monkeypatch):
    FakeProjectionProvider.fail = False
    FakeProjectionProvider.calls = []
    monkeypatch.setattr(dashboard_module, "SleeperProjectionProvider", FakeProjectionProvider)


@pytest.mark.asyncio
async def test_manual_refresh_bypasses_weekly_matchup_cache_and_keeps_player_cache():
    cache = MemoryCache()
    client = FakeSleeperClient()
    service = DashboardDataService(client=client, cache=cache)

    result = await service.matchup_board(2, force_refresh=True)

    assert result.refreshed is True
    assert client.matchup_calls == [2]
    assert client.players_calls == 0
    assert "sleeper:matchups:2" in cache.set_calls
    assert cache.store["sleeper:matchups:2"][0]["points"] == 42
    assert result.board.matchups[0].team_a.actual_points == 42
    assert ("values", 2, True) in FakeProjectionProvider.calls


@pytest.mark.asyncio
async def test_projection_failure_does_not_prevent_actual_score_refresh():
    FakeProjectionProvider.fail = True
    cache = MemoryCache()
    client = FakeSleeperClient()
    service = DashboardDataService(client=client, cache=cache)

    result = await service.matchup_board(2, force_refresh=True)

    assert result.refreshed is True
    assert result.board.matchups[0].team_a.actual_points == 42
    assert result.board.matchups[0].team_a.projected_points is None
    assert "Projections are temporarily unavailable" in (result.warning or "")


@pytest.mark.asyncio
async def test_sleeper_refresh_failure_preserves_cached_matchup_data():
    cache = MemoryCache()
    client = FakeSleeperClient(fail_matchups=True)
    service = DashboardDataService(client=client, cache=cache)

    result = await service.matchup_board(2, force_refresh=True)

    assert result.refreshed is False
    assert result.board.matchups[0].team_a.actual_points == 10
    assert "Unable to refresh Sleeper right now. Showing existing data." in (result.warning or "")


@pytest.mark.asyncio
async def test_manual_refresh_does_not_persist_power_ranking_snapshot():
    class SnapshotGuardService(DashboardDataService):
        def _persist_ranking_snapshot(self, season, week, rankings):
            raise AssertionError("refresh should not persist rankings")

    service = SnapshotGuardService(client=FakeSleeperClient(), cache=MemoryCache())

    result = await service.matchup_board(2, force_refresh=True)

    assert result.refreshed is True
