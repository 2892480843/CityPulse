import math
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from citypulse.backtest.models import BacktestRun
from citypulse.calibration.models import CalibrationReport
from citypulse.shared.errors import AppError

BIN_COUNT = 10
MIN_SAMPLE_SIZE = 100

VERDICT_INSUFFICIENT = "insufficient_samples"
VERDICT_ELIGIBLE = "eligible_for_validation"
VERDICT_INELIGIBLE = "not_eligible"

GATE_NOTE = (
    "Calibration reports are experiments only. Probability wording stays "
    "disabled until an admin publishes a calibrated scoring version that "
    "passed out-of-time validation."
)


def brier_score(samples: list[tuple[float, int]]) -> float:
    if not samples:
        raise ValueError("samples required")
    return sum((score - outcome) ** 2 for score, outcome in samples) / len(samples)


def reliability_bins(samples: list[tuple[float, int]]) -> list[dict[str, Any]]:
    bins: list[list[tuple[float, int]]] = [[] for _ in range(BIN_COUNT)]
    for score, outcome in samples:
        index = min(BIN_COUNT - 1, int(score * BIN_COUNT))
        bins[index].append((score, outcome))
    report = []
    for index, bucket in enumerate(bins):
        if not bucket:
            continue
        report.append(
            {
                "bin_low": round(index / BIN_COUNT, 2),
                "bin_high": round((index + 1) / BIN_COUNT, 2),
                "count": len(bucket),
                "mean_score": round(sum(s for s, _ in bucket) / len(bucket), 3),
                "observed_rate": round(sum(o for _, o in bucket) / len(bucket), 3),
            }
        )
    return report


def expected_calibration_error(samples: list[tuple[float, int]]) -> float:
    total = len(samples)
    error = 0.0
    for bucket in reliability_bins(samples):
        weight = bucket["count"] / total
        error += weight * abs(bucket["mean_score"] - bucket["observed_rate"])
    return round(error, 4)


def samples_from_backtest(run: BacktestRun) -> list[tuple[float, int]]:
    """(normalized trend score, outcome) per city-cutoff snapshot entry.

    Targets count as positive outcomes, controls as negatives — a coarse
    label fit for experiments, never for enabling production probabilities.
    """
    if not run.metrics:
        return []
    targets = set(run.target_city_codes)
    controls = set(run.control_city_codes)
    samples: list[tuple[float, int]] = []
    for snapshot in run.metrics.get("snapshots", []):
        for entry in snapshot.get("ranking", []):
            code = entry["city_code"]
            score = round(max(0.0, min(1.0, entry["trend_score"] / 100.0)), 3)
            if code in targets:
                samples.append((score, 1))
            elif code in controls:
                samples.append((score, 0))
    return samples


def verdict_for(sample_size: int, ece: float) -> str:
    if sample_size < MIN_SAMPLE_SIZE:
        return VERDICT_INSUFFICIENT
    if not math.isfinite(ece):
        return VERDICT_INELIGIBLE
    return VERDICT_ELIGIBLE


async def create_report(
    db: AsyncSession,
    *,
    backtest_run_id: uuid.UUID,
    created_by: uuid.UUID,
) -> CalibrationReport:
    result = await db.execute(select(BacktestRun).where(BacktestRun.id == backtest_run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise AppError(
            code="BACKTEST_NOT_FOUND",
            message="The backtest run does not exist.",
            status_code=404,
        )
    samples = samples_from_backtest(run)
    if not samples:
        raise AppError(
            code="NO_CALIBRATION_SAMPLES",
            message="The backtest has no labeled city-cutoff samples.",
            status_code=409,
        )
    brier = round(brier_score(samples), 4)
    ece = expected_calibration_error(samples)
    report = CalibrationReport(
        backtest_run_id=run.id,
        sample_size=len(samples),
        brier=brier,
        ece=ece,
        bins=reliability_bins(samples),
        verdict=verdict_for(len(samples), ece),
        created_by=created_by,
    )
    db.add(report)
    await db.flush()
    return report


async def list_reports(db: AsyncSession, *, limit: int = 20) -> list[CalibrationReport]:
    result = await db.execute(
        select(CalibrationReport).order_by(CalibrationReport.created_at.desc()).limit(limit)
    )
    return list(result.scalars())


async def get_report(db: AsyncSession, report_id: uuid.UUID) -> CalibrationReport:
    result = await db.execute(
        select(CalibrationReport).where(CalibrationReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise AppError(
            code="REPORT_NOT_FOUND",
            message="The calibration report does not exist.",
            status_code=404,
        )
    return report
