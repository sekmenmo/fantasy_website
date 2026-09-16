import pytest

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
