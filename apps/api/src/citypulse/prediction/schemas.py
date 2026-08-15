import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ActionPriorityName = Literal["high", "medium", "watch", "blocked"]


class PredictionRunCreate(BaseModel):
    window_days: Literal[7, 14, 30] = 14


class PredictionRunView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    window_days: int
    status: Literal["queued", "running", "succeeded", "failed"]
    as_of_date: date
    city_count: int
    scoring_version_id: uuid.UUID
    data_fingerprint: str
    created_at: datetime
    finished_at: datetime | None
    error: str | None


class PredictionRunListResponse(BaseModel):
    items: list[PredictionRunView]
    total: int


class PredictionResultView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    city_code: str
    city_name: str
    province: str
    trend_rank: int
    trend_score: float
    risk_pressure: float
    evidence_coverage: float
    action_priority: ActionPriorityName
    data_stale: bool
    factors: dict[str, float]
    blockers: list[str]


class PredictionResultsResponse(BaseModel):
    run: PredictionRunView
    items: list[PredictionResultView]


class CityTrendSeriesPoint(BaseModel):
    metric_date: date
    value: float


class CityTrendResponse(BaseModel):
    city_code: str
    city_name: str
    province: str
    result: PredictionResultView | None
    series: dict[str, list[CityTrendSeriesPoint]]
    series_window_days: int
