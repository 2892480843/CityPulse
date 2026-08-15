import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from citypulse.audit import service as audit
from citypulse.city_catalog.models import City
from citypulse.identity.rbac import Identity, require_roles, resolve_identity
from citypulse.jobs.service import record_job
from citypulse.prediction import service
from citypulse.prediction.models import PredictionResult
from citypulse.prediction.schemas import (
    CityTrendResponse,
    CityTrendSeriesPoint,
    PredictionResultsResponse,
    PredictionResultView,
    PredictionRunCreate,
    PredictionRunListResponse,
    PredictionRunView,
)
from citypulse.shared.db import get_session
from citypulse.shared.errors import AppError

router = APIRouter(prefix="/api/v1/prediction-runs", tags=["prediction"])


def _run_view(run) -> PredictionRunView:
    return PredictionRunView.model_validate(run)


@router.post("", response_model=PredictionRunView, status_code=201)
async def create_run(
    payload: PredictionRunCreate,
    identity: Annotated[Identity, Depends(require_roles("analyst"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> PredictionRunView:
    try:
        run, results = await service.execute_run(
            db, window_days=payload.window_days, created_by=identity.user_id
        )
    except AppError as error:
        await record_job(
            db,
            job_type="prediction_run",
            status="failed",
            created_by=identity.user_id,
            summary=f"window={payload.window_days}d",
            error=error.message,
        )
        await db.commit()
        raise
    await record_job(
        db,
        job_type="prediction_run",
        status="succeeded",
        created_by=identity.user_id,
        ref_type="prediction_run",
        ref_id=run.id,
        summary=f"window={run.window_days}d cities={run.city_count}",
    )
    await audit.record(
        db,
        action="prediction_run_created",
        object_type="prediction_run",
        object_id=str(run.id),
        actor_id=identity.user_id,
        actor_username=identity.username,
        detail={"window_days": run.window_days, "city_count": run.city_count},
    )
    await db.commit()
    _ = results
    return _run_view(run)


@router.get("", response_model=PredictionRunListResponse)
async def list_runs(
    _identity: Annotated[Identity, Depends(resolve_identity)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> PredictionRunListResponse:
    runs = await service.list_runs(db)
    items = [_run_view(run) for run in runs]
    return PredictionRunListResponse(items=items, total=len(items))


@router.get("/{run_id}", response_model=PredictionRunView)
async def get_run(
    run_id: uuid.UUID,
    _identity: Annotated[Identity, Depends(resolve_identity)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> PredictionRunView:
    return _run_view(await service.get_run(db, run_id))


@router.get("/{run_id}/results", response_model=PredictionResultsResponse)
async def run_results(
    run_id: uuid.UUID,
    _identity: Annotated[Identity, Depends(resolve_identity)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> PredictionResultsResponse:
    run = await service.get_run(db, run_id)
    results = await service.run_results(db, run_id)
    return PredictionResultsResponse(
        run=_run_view(run),
        items=[PredictionResultView.model_validate(result) for result in results],
    )


@router.get("/{run_id}/results/{result_id}", response_model=PredictionResultView)
async def get_result(
    run_id: uuid.UUID,
    result_id: uuid.UUID,
    _identity: Annotated[Identity, Depends(resolve_identity)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> PredictionResultView:
    result = await service.get_result(db, result_id)
    if result.run_id != run_id:
        from citypulse.shared.errors import AppError

        raise AppError(
            code="RESULT_NOT_IN_RUN",
            message="The result does not belong to this run.",
            status_code=404,
        )
    return PredictionResultView.model_validate(result)


city_router = APIRouter(prefix="/api/v1/cities", tags=["prediction"])


@city_router.get("/{city_code}/trend", response_model=CityTrendResponse)
async def city_trend(
    city_code: str,
    _identity: Annotated[Identity, Depends(resolve_identity)],
    db: Annotated[AsyncSession, Depends(get_session)],
    run_id: Annotated[uuid.UUID | None, Query()] = None,
    window_days: Annotated[int, Query(ge=7, le=30)] = 14,
) -> CityTrendResponse:
    city_result = await db.execute(select(City).where(City.code == city_code))
    city = city_result.scalar_one_or_none()
    if city is None:
        raise AppError(
            code="CITY_NOT_FOUND", message="The city code is unknown.", status_code=404
        )

    result_view: PredictionResultView | None = None
    if run_id is not None:
        results = await db.execute(
            select(PredictionResult).where(
                PredictionResult.run_id == run_id,
                PredictionResult.city_code == city_code,
            )
        )
        result = results.scalar_one_or_none()
        if result is not None:
            result_view = PredictionResultView.model_validate(result)

    series = await service.city_series(db, city_code=city_code, window_days=window_days)
    series_view = {
        metric: [
            CityTrendSeriesPoint(metric_date=point[0], value=point[1]) for point in points
        ]
        for metric, points in series.items()
    }
    return CityTrendResponse(
        city_code=city.code,
        city_name=city.name,
        province=city.province,
        result=result_view,
        series=series_view,
        series_window_days=window_days,
    )
