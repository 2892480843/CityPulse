import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from citypulse.backtest.models import BacktestRun
from citypulse.city_catalog.service import known_city_codes
from citypulse.prediction.scoring import (
    ACTION_THRESHOLD,
    CityObservations,
    score_city,
)
from citypulse.prediction.service import collect_city_observations
from citypulse.shared.errors import AppError

DEFAULT_CUTOFF_OFFSETS = [30, 14, 7]
HIT_K = 5


def cutoff_moment(t0: date, offset_days: int) -> datetime:
    day = t0 - timedelta(days=offset_days)
    return datetime.combine(day, time(23, 59, 59), tzinfo=UTC)


def _rank_snapshot(
    observations: dict[str, CityObservations],
    *,
    as_of: date,
    candidates: set[str],
) -> list[tuple[str, float]]:
    scored = [
        score_city(item, as_of=as_of)
        for item in observations.values()
        if item.city_code in candidates
    ]
    scored.sort(key=lambda item: item.trend_score, reverse=True)
    return [(item.city_code, item.trend_score) for item in scored]


def _metrics_from_snapshots(
    *,
    t0: date,
    targets: list[str],
    controls: list[str],
    snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate_codes = set(targets) | set(controls)

    hits = 0
    leads: list[int] = []
    false_alert_city_cutoffs = 0
    control_total = 0
    evidence_values: list[float] = []

    for target in targets:
        crossed: int | None = None
        for snapshot in snapshots:
            if crossed is not None:
                break
            ranking = snapshot["ranking"]
            score = next(
                (entry["trend_score"] for entry in ranking if entry["city_code"] == target),
                None,
            )
            if score is not None and score >= ACTION_THRESHOLD:
                crossed = snapshot["offset_days"]
        if crossed is not None:
            leads.append(crossed)

    for snapshot in snapshots:
        ranking = snapshot["ranking"]
        top_codes = [entry["city_code"] for entry in ranking[:HIT_K]]
        for target in targets:
            if target in top_codes:
                hits += 1
                break
        for control in controls:
            control_total += 1
            score = next(
                (entry["trend_score"] for entry in ranking if entry["city_code"] == control), None
            )
            if score is not None and score >= ACTION_THRESHOLD:
                false_alert_city_cutoffs += 1
        evidence_values.append(snapshot["evidence_coverage"])

    target_count = len(targets)
    snapshot_count = len(snapshots)
    per_100 = round(false_alert_city_cutoffs / control_total * 100, 2) if control_total else None

    hit_rate = (
        round(hits / (target_count * snapshot_count), 3)
        if target_count and snapshot_count
        else None
    )
    return {
        "hit_at_5": hit_rate,
        "hit_at_5_note": "descriptive only when candidates < 6"
        if len(candidate_codes) < HIT_K + 1
        else None,
        "mean_lead_days": round(sum(leads) / len(leads), 1) if leads else None,
        "lead_days": leads,
        "false_alerts_per_100": per_100,
        "evidence_coverage": (
            round(sum(evidence_values) / len(evidence_values), 3) if evidence_values else None
        ),
        "thresholds": {"action": ACTION_THRESHOLD, "hit_k": HIT_K},
        "candidate_count": len(candidate_codes),
    }


async def execute_backtest(
    db: AsyncSession,
    *,
    t0: date,
    targets: list[str],
    controls: list[str],
    window_days: int,
    created_by: uuid.UUID,
    cutoff_offsets: list[int] | None = None,
) -> BacktestRun:
    codes = await known_city_codes(db)
    unknown = [code for code in [*targets, *controls] if code not in codes]
    if unknown:
        raise AppError(
            code="UNKNOWN_CITY",
            message=f"City codes not in catalog: {', '.join(unknown)}.",
            status_code=400,
        )
    if not targets:
        raise AppError(
            code="NO_TARGET_CITIES",
            message="At least one target city is required.",
            status_code=400,
        )

    offsets = cutoff_offsets or DEFAULT_CUTOFF_OFFSETS
    run = BacktestRun(
        t0=t0,
        cutoff_offsets=offsets,
        window_days=window_days,
        target_city_codes=targets,
        control_city_codes=controls,
        status="running",
        created_by=created_by,
    )
    db.add(run)
    await db.flush()

    snapshots: list[dict[str, Any]] = []
    try:
        candidates = set(targets) | set(controls)
        for offset in offsets:
            moment = cutoff_moment(t0, offset)
            observations = await collect_city_observations(
                db,
                window_start=t0 - timedelta(days=offset + window_days),
                available_at_cutoff=moment,
            )
            as_of = moment.date()
            ranking = _rank_snapshot(observations, as_of=as_of, candidates=candidates)
            evidence = [
                score_city(item, as_of=as_of).evidence_coverage
                for item in observations.values()
                if item.city_code in candidates
            ]
            snapshots.append(
                {
                    "offset_days": offset,
                    "cutoff_at": moment.isoformat(),
                    "ranking": [
                        {"city_code": code, "trend_score": score} for code, score in ranking
                    ],
                    "evidence_coverage": (
                        round(sum(evidence) / len(evidence), 3) if evidence else 0.0
                    ),
                }
            )
    except AppError as error:
        run.status = "failed"
        run.error = error.message
        await db.flush()
        raise

    run.metrics = {
        **_metrics_from_snapshots(t0=t0, targets=targets, controls=controls, snapshots=snapshots),
        "snapshots": snapshots,
    }
    run.status = "succeeded"
    run.finished_at = datetime.now(UTC)
    await db.flush()
    return run


async def get_backtest(db: AsyncSession, run_id: uuid.UUID) -> BacktestRun:
    result = await db.execute(select(BacktestRun).where(BacktestRun.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise AppError(
            code="BACKTEST_NOT_FOUND", message="The backtest run does not exist.", status_code=404
        )
    return run


async def list_backtests(db: AsyncSession, *, limit: int = 20) -> list[BacktestRun]:
    result = await db.execute(
        select(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(limit)
    )
    return list(result.scalars())
