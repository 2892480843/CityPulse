import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

PlanStatusName = Literal["draft", "pending_review", "approved", "rejected", "archived"]


class ActionGenerateRequest(BaseModel):
    prediction_result_id: uuid.UUID


class ActionPlanView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    prediction_result_id: uuid.UUID
    run_id: uuid.UUID
    city_code: str
    city_name: str
    status: PlanStatusName
    generator_type: Literal["rule_fallback", "deepseek"]
    generation_note: str | None
    target_segment: str
    action_window_start: date | None
    action_window_end: date | None
    product_bundle: list[dict[str, Any]]
    campaign_theme: str
    supply_actions: list[str]
    assumptions: list[str]
    risk_notes: str
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    review_comment: str | None


class ActionPlanListResponse(BaseModel):
    items: list[ActionPlanView]
    total: int


class ActionPlanUpdateRequest(BaseModel):
    target_segment: str | None = Field(default=None, max_length=120)
    campaign_theme: str | None = Field(default=None, max_length=300)
    risk_notes: str | None = Field(default=None, max_length=1000)
    action_window_start: date | None = None
    action_window_end: date | None = None
    supply_actions: list[str] | None = Field(default=None, max_length=8)


class ReviewRequest(BaseModel):
    comment: str | None = Field(default=None, max_length=300)


class ActionPlanVersionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_id: uuid.UUID
    version_no: int
    event: Literal[
        "generated", "edited", "submitted", "approved", "rejected"
    ]
    snapshot: dict[str, Any]
    actor_id: uuid.UUID | None
    note: str | None
    created_at: datetime


class ActionPlanVersionsResponse(BaseModel):
    items: list[ActionPlanVersionView]
    total: int
