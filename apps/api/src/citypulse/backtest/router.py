import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from citypulse.audit import service as audit
from citypulse.backtest import service
from citypulse.backtest.schemas import (
    BacktestCreateRequest,
    BacktestListResponse,
    BacktestRunView,
)
from citypulse.identity.rbac import Identity, require_roles
from citypulse.jobs.service import record_job
from citypulse.shared.db import get_session
from citypulse.shared.errors import AppError

router = APIRouter(prefix="/api/v1/backtest-runs", tags=["backtest"])


@router.post("", response_model=BacktestRunView, status_code=201)
async def create_backtest(
    payload: BacktestCreateRequest,
    identity: Annotated[Identity, Depends(require_roles("analyst"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> BacktestRunView:
    try:
        run = await service.execute_backtest(
            db,
            t0=payload.t0,
            targets=payload.target_city_codes,
            controls=payload.control_city_codes,
            window_days=payload.window_days,
            created_by=identity.user_id,
            cutoff_offsets=payload.cutoff_offsets,
        )
    except AppError as error:
        await record_job(
            db,
            job_type="backtest_run",
            status="failed",
            created_by=identity.user_id,
            summary=f"t0={payload.t0}",
            error=error.message,
        )
        await db.commit()
        raise
    await record_job(
        db,
        job_type="backtest_run",
        status="succeeded",
        created_by=identity.user_id,
        ref_type="backtest_run",
        ref_id=run.id,
        summary=f"t0={run.t0} targets={len(run.target_city_codes)}",
    )
    await audit.record(
        db,
        action="backtest_run_created",
        object_type="backtest_run",
        object_id=str(run.id),
        actor_id=identity.user_id,
        actor_username=identity.username,
        detail={"t0": run.t0.isoformat(), "targets": run.target_city_codes},
    )
    await db.commit()
    return BacktestRunView.model_validate(run)


@router.get("", response_model=BacktestListResponse)
async def list_backtests(
    _identity: Annotated[Identity, Depends(require_roles("admin", "analyst"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> BacktestListResponse:
    runs = await service.list_backtests(db)
    items = [BacktestRunView.model_validate(run) for run in runs]
    return BacktestListResponse(items=items, total=len(items))


@router.get("/{run_id}", response_model=BacktestRunView)
async def get_backtest(
    run_id: uuid.UUID,
    _identity: Annotated[Identity, Depends(require_roles("admin", "analyst"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> BacktestRunView:
    return BacktestRunView.model_validate(await service.get_backtest(db, run_id))
