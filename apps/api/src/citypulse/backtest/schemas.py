import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BacktestCreateRequest(BaseModel):
    t0: date
    target_city_codes: list[str] = Field(min_length=1, max_length=10)
    control_city_codes: list[str] = Field(default_factory=list, max_length=20)
    window_days: Literal[7, 14, 30] = 14
    cutoff_offsets: list[int] = Field(default=[30, 14, 7])


class BacktestRunView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    t0: date
    cutoff_offsets: list[int]
    window_days: int
    target_city_codes: list[str]
    control_city_codes: list[str]
    status: Literal["queued", "running", "succeeded", "failed"]
    metrics: dict[str, Any] | None
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class BacktestListResponse(BaseModel):
    items: list[BacktestRunView]
    total: int
