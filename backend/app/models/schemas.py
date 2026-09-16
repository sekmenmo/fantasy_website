from __future__ import annotations

from pydantic import BaseModel, Field


class Team(BaseModel):
    roster_id: int
    owner_id: str | None
    owner_name: str
    team_name: str
    avatar_id: str | None = None
    avatar_url: str | None = None
    avatar_thumb_url: str | None = None
    wins: int = 0
    losses: int = 0
    ties: int = 0
    points_for: float = 0.0
    points_against: float = 0.0


class Player(BaseModel):
    player_id: str
    full_name: str
    first_name: str | None = None
    last_name: str | None = None
    position: str | None = None
    nfl_team: str | None = None
    injury_status: str | None = None
    status: str | None = None
    image_url: str | None = None


class WeeklyPlayer(BaseModel):
    player: Player | None
    player_id: str | None = None
    roster_slot: str
    projected_points: float | None = None
    actual_points: float | None = None
    opponent: str | None = None
    game_status: str | None = None
    is_starter: bool
    is_empty: bool = False


class WeeklyTeam(BaseModel):
    team: Team
    week: int
    matchup_id: int
    projected_points: float | None = None
    projection_complete: bool = False
    actual_points: float
    starters: list[WeeklyPlayer] = Field(default_factory=list)
    bench: list[WeeklyPlayer] = Field(default_factory=list)


class Matchup(BaseModel):
    matchup_id: int
    week: int
    team_a: WeeklyTeam
    team_b: WeeklyTeam
    projected_margin: float | None = None
    actual_margin: float
    status: str


class LeagueInfo(BaseModel):
    league_id: str
    name: str
    season: str
    status: str
    total_rosters: int
    roster_positions: list[str]
    scoring_settings: dict[str, float]
    avatar_id: str | None = None
    avatar_url: str | None = None


class LeagueSummary(BaseModel):
    week: int
    status: str
    matchup_count: int
    league_avg_projection: float | None = None
    highest_projection_team: str | None = None
    highest_projection: float | None = None
    lowest_projection_team: str | None = None
    lowest_projection: float | None = None
    closest_projected_matchup: str | None = None
    closest_projected_margin: float | None = None
    largest_projected_matchup: str | None = None
    largest_projected_margin: float | None = None
    league_avg_score: float | None = None
    highest_score_team: str | None = None
    highest_score: float | None = None
    lowest_score_team: str | None = None
    lowest_score: float | None = None
    closest_actual_matchup: str | None = None
    closest_actual_margin: float | None = None
    largest_blowout_matchup: str | None = None
    largest_blowout_margin: float | None = None


class MatchupBoard(BaseModel):
    league: LeagueInfo
    week: int
    status: str
    league_summary: LeagueSummary
    matchups: list[Matchup]


class StandingRow(BaseModel):
    rank: int
    team: Team
    record: str
    win_pct: float
    points_for: float
    points_against: float
    point_differential: float
    avg_points_per_week: float


class PowerRanking(BaseModel):
    week: int
    roster_id: int
    rank: int
    score: float
    previous_rank: int | None = None
    rank_change: int | None = None
    components: dict[str, float]
    component_points: dict[str, float] = Field(default_factory=dict)
    ppg: float = 0.0
    current_projection: float | None = None
    recent_form: float = 0.0
    projected_points_lost: float = 0.0
    baseline_notes: list[str] = Field(default_factory=list)
    team: Team | None = None
