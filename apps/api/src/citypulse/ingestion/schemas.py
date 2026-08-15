import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DatasetValidationIssue(BaseModel):
    code: str
    message: str
    row: int | None = None
    column: str | None = None


class DatasetReport(BaseModel):
    row_count: int
    city_count: int
    metric_date_min: date | None
    metric_date_max: date | None
    errors: list[DatasetValidationIssue]
    warnings: list[DatasetValidationIssue]


class DatasetView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_type: Literal["official_sync", "analyst_upload"]
    source_name: str
    legal_basis: str
    original_filename: str
    stored_filename: str
    sha256: str
    byte_size: int
    status: Literal["uploaded", "validating", "valid", "invalid", "committed", "archived"]
    report: DatasetReport | None
    created_at: datetime
    validated_at: datetime | None
    committed_at: datetime | None


class DatasetCreateResponse(BaseModel):
    dataset: DatasetView
    already_exists: bool


class DatasetListResponse(BaseModel):
    items: list[DatasetView]
    total: int


class DatasetValidateResponse(BaseModel):
    dataset: DatasetView
    report: DatasetReport


class DatasetCommitResponse(BaseModel):
    dataset: DatasetView
    version_no: int
    observation_count: int
    already_committed: bool


class ObservationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    city_code: str
    metric_date: date
    metric_name: str
    value: float
    source_url: str | None
    published_at: datetime | None
    observed_at: datetime | None
    available_at: datetime


class ObservationListResponse(BaseModel):
    items: list[ObservationView]
    limit: int = Field(default=50)
