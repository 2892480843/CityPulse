import hashlib
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from citypulse.city_catalog.models import City
from citypulse.ingestion.models import SignalObservation
from citypulse.prediction.models import PredictionResult, PredictionRun, ScoringVersion
from citypulse.prediction.scoring import CityObservations, score_city
from citypulse.shared.errors import AppError
from citypulse.shared.timeutil import as_utc

MAX_METRIC_HISTORY = 3


async def ensure_scoring_version(db: AsyncSession) -> ScoringVersion:
    from citypulse.prediction.scoring import (
        ACTION_THRESHOLD,
        BLOCKED_RISK_THRESHOLD,
        EVIDENCE_PUBLISH_THRESHOLD,
        RISK_WEIGHT,
        TREND_WEIGHTS,
        WATCH_THRESHOLD,
    )

    result = await db.execute(
        select(ScoringVersion).where(ScoringVersion.is_active).order_by(ScoringVersion.version_no)
    )
    existing = result.scalars().first()
    if existing is not None:
        return existing
    version = ScoringVersion(
        version_no=1,
        label="transparent-baseline-v1",
        weights={**TREND_WEIGHTS, "risk_weight": RISK_WEIGHT},
        thresholds={
            "action": ACTION_THRESHOLD,
            "watch": WATCH_THRESHOLD,
            "blocked_risk": BLOCKED_RISK_THRESHOLD,
            "evidence_publish": EVIDENCE_PUBLISH_THRESHOLD,
        },
    )
    db.add(version)
    await db.flush()
    return version


def _observations_query(
    *,
    window_start: date | None = None,
    available_at_cutoff: datetime | None = None,
) -> sa.Select:
    statement = select(SignalObservation)
    if window_start is not None:
        statement = statement.where(SignalObservation.metric_date >= window_start)
    if available_at_cutoff is not None:
        statement = statement.where(SignalObservation.available_at <= available_at_cutoff)
    return statement


async def collect_city_observations(
    db: AsyncSession,
    *,
    window_start: date | None = None,
    available_at_cutoff: datetime | None = None,
) -> dict[str, CityObservations]:
    rows = (
        await db.execute(
            _observations_query(
                window_start=window_start, available_at_cutoff=available_at_cutoff
            )
        )
    ).scalars().all()

    grouped: dict[str, dict[str, list[tuple[date, float]]]] = {}
    latest_available: dict[str, datetime] = {}
    sourced: dict[str, int] = {}
    totals: dict[str, int] = {}

    for row in rows:
        grouped.setdefault(row.city_code, {}).setdefault(row.metric_name, []).append(
            (row.metric_date, row.value)
        )
        available = as_utc(row.available_at)
        current = latest_available.get(row.city_code)
        if current is None or available > current:
            latest_available[row.city_code] = available
        totals[row.city_code] = totals.get(row.city_code, 0) + 1
        if row.source_url:
            sourced[row.city_code] = sourced.get(row.city_code, 0) + 1

    observations: dict[str, CityObservations] = {}
    for city_code, metrics in grouped.items():
        values: dict[str, float] = {}
        for metric, history in metrics.items():
            history.sort(key=lambda item: item[0], reverse=True)
            recent = history[:MAX_METRIC_HISTORY]
            values[metric] = sum(value for _date, value in recent) / len(recent)
        total = totals.get(city_code, 0)
        observations[city_code] = CityObservations(
            city_code=city_code,
            values=values,
            last_available_at=latest_available.get(city_code),
            source_share=(sourced.get(city_code, 0) / total) if total else 0.0,
        )
    return observations


def _fingerprint(observations: dict[str, CityObservations]) -> str:
    payload = "\n".join(
        f"{code}:{metric}:{round(value, 3)}"
        for code, item in sorted(observations.items())
        for metric, value in sorted(item.values.items())
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def load_city_map(db: AsyncSession) -> dict[str, City]:
    result = await db.execute(select(City))
    return {city.code: city for city in result.scalars()}


async def execute_run(
    db: AsyncSession,
    *,
    window_days: int,
    created_by: uuid.UUID,
    as_of: date | None = None,
    available_at_cutoff: datetime | None = None,
) -> tuple[PredictionRun, list[PredictionResult]]:
    """Compute a full prediction run.

    available_at_cutoff is used by the backtest module to rebuild history
    without future information; production runs pass None.
    """
    scoring = await ensure_scoring_version(db)
    run_date = as_of or datetime.now(UTC).date()
    window_start = run_date - timedelta(days=window_days)

    observations = await collect_city_observations(
        db, window_start=window_start, available_at_cutoff=available_at_cutoff
    )
    if not observations:
        raise AppError(
            code="NO_COMMITTED_DATA",
            message="Commit at least one dataset before running predictions.",
            status_code=409,
        )

    cities = await load_city_map(db)
    scored = [
        score_city(item, as_of=run_date)
        for item in observations.values()
        if item.city_code in cities
    ]
    if not scored:
        raise AppError(
            code="NO_KNOWN_CITIES",
            message="Committed observations reference no city in the catalog.",
            status_code=409,
        )
    scored.sort(key=lambda item: item.trend_score, reverse=True)

    run = PredictionRun(
        window_days=window_days,
        status="running",
        scoring_version_id=scoring.id,
        data_fingerprint=_fingerprint(observations)[:32],
        as_of_date=run_date,
        created_by=created_by,
    )
    db.add(run)
    await db.flush()

    results: list[PredictionResult] = []
    for rank, city_score in enumerate(scored, start=1):
        city = cities[city_score.city_code]
        result = PredictionResult(
            run_id=run.id,
            city_code=city_score.city_code,
            city_name=city.name,
            province=city.province,
            trend_rank=rank,
            trend_score=city_score.trend_score,
            risk_pressure=city_score.risk_pressure,
            evidence_coverage=city_score.evidence_coverage,
            action_priority=city_score.action_priority,
            data_stale=city_score.data_stale,
            factors=city_score.factors,
            blockers=city_score.blockers,
        )
        db.add(result)
        results.append(result)

    run.status = "succeeded"
    run.city_count = len(results)
    run.finished_at = datetime.now(UTC)
    await db.flush()
    return run, results


async def get_run(db: AsyncSession, run_id: uuid.UUID) -> PredictionRun:
    result = await db.execute(select(PredictionRun).where(PredictionRun.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise AppError(
            code="RUN_NOT_FOUND", message="The prediction run does not exist.", status_code=404
        )
    return run


async def list_runs(db: AsyncSession, *, limit: int = 20) -> list[PredictionRun]:
    result = await db.execute(
        select(PredictionRun).order_by(sa.desc(PredictionRun.created_at)).limit(limit)
    )
    return list(result.scalars())


async def run_results(db: AsyncSession, run_id: uuid.UUID) -> list[PredictionResult]:
    result = await db.execute(
        select(PredictionResult)
        .where(PredictionResult.run_id == run_id)
        .order_by(PredictionResult.trend_rank)
    )
    return list(result.scalars())


async def get_result(db: AsyncSession, result_id: uuid.UUID) -> PredictionResult:
    result = await db.execute(
        select(PredictionResult).where(PredictionResult.id == result_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise AppError(
            code="RESULT_NOT_FOUND",
            message="The prediction result does not exist.",
            status_code=404,
        )
    return item


async def city_series(
    db: AsyncSession, *, city_code: str, window_days: int
) -> dict[str, list[tuple[date, float]]]:
    window_start = date.today() - timedelta(days=window_days)
    rows = (
        await db.execute(
            select(SignalObservation)
            .where(
                SignalObservation.city_code == city_code,
                SignalObservation.metric_date >= window_start,
            )
            .order_by(SignalObservation.metric_date)
        )
    ).scalars().all()
    series: dict[str, list[tuple[date, float]]] = {}
    for row in rows:
        series.setdefault(row.metric_name, []).append((row.metric_date, row.value))
    return series


def series_payload(series: dict[str, list[tuple[date, float]]]) -> dict[str, list[dict[str, Any]]]:
    return {
        metric: [{"metric_date": point[0].isoformat(), "value": point[1]} for point in points]
        for metric, points in series.items()
    }
