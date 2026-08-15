import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from citypulse.identity.rbac import Identity, require_roles
from citypulse.jobs.service import list_jobs
from citypulse.shared.db import get_session

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


class JobView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_type: Literal["prediction_run", "backtest_run", "action_generation"]
    status: Literal["queued", "running", "succeeded", "failed"]
    ref_type: str | None
    ref_id: uuid.UUID | None
    summary: str | None
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class JobListResponse(BaseModel):
    items: list[JobView]
    total: int


@router.get("", response_model=JobListResponse)
async def jobs(
    _identity: Annotated[Identity, Depends(require_roles("admin", "analyst"))],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> JobListResponse:
    jobs = await list_jobs(db, limit=limit)
    items = [JobView.model_validate(job) for job in jobs]
    return JobListResponse(items=items, total=len(items))
