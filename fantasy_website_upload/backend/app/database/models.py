from datetime import datetime

from sqlmodel import Field, SQLModel


class CacheEntry(SQLModel, table=True):
    key: str = Field(primary_key=True)
    payload: str
    updated_at: datetime
    expires_at: datetime | None = None


class PowerRankingHistory(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    week: int = Field(index=True)
    roster_id: int = Field(index=True)
    rank: int
    score: float
    components_json: str
    created_at: datetime


class PowerRankingSnapshot(SQLModel, table=True):
    __tablename__ = "power_ranking_snapshots"

    id: int | None = Field(default=None, primary_key=True)
    season: str = Field(index=True)
    week: int = Field(index=True)
    roster_id: int = Field(index=True)
    rank: int
    power_score: float
    season_scoring_score: float
    projected_strength_score: float
    recent_form_score: float
    record_score: float
    health_score: float
    projected_points_lost: float
    created_at: datetime
