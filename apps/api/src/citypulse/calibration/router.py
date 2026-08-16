import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from citypulse.audit import service as audit
from citypulse.calibration import service
from citypulse.identity.rbac import Identity, require_roles
from citypulse.shared.db import get_session

router = APIRouter(prefix="/api/v1/calibration-reports", tags=["calibration"])

GATE_NOTE = service.GATE_NOTE


class CalibrationReportView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    backtest_run_id: uuid.UUID
    sample_size: int
    brier: float
    ece: float
    bins: list[dict[str, Any]]
    verdict: Literal["insufficient_samples", "eligible_for_validation", "not_eligible"]
    created_by: uuid.UUID
    created_at: datetime


class CalibrationListResponse(BaseModel):
    items: list[CalibrationReportView]
    total: int
    gate_note: str = GATE_NOTE


class CalibrationCreateRequest(BaseModel):
    backtest_run_id: uuid.UUID


@router.post("", response_model=CalibrationReportView, status_code=201)
async def create_report(
    payload: CalibrationCreateRequest,
    identity: Annotated[Identity, Depends(require_roles("analyst"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> CalibrationReportView:
    report = await service.create_report(
        db, backtest_run_id=payload.backtest_run_id, created_by=identity.user_id
    )
    await audit.record(
        db,
        action="calibration_report_created",
        object_type="calibration_report",
        object_id=str(report.id),
        actor_id=identity.user_id,
        actor_username=identity.username,
        detail={"brier": report.brier, "ece": report.ece, "verdict": report.verdict},
    )
    await db.commit()
    return CalibrationReportView.model_validate(report)


@router.get("", response_model=CalibrationListResponse)
async def list_reports(
    _identity: Annotated[Identity, Depends(require_roles("admin", "analyst"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> CalibrationListResponse:
    reports = await service.list_reports(db)
    items = [CalibrationReportView.model_validate(report) for report in reports]
    return CalibrationListResponse(items=items, total=len(items))


@router.get("/{report_id}", response_model=CalibrationReportView)
async def get_report(
    report_id: uuid.UUID,
    _identity: Annotated[Identity, Depends(require_roles("admin", "analyst"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> CalibrationReportView:
    return CalibrationReportView.model_validate(await service.get_report(db, report_id))
