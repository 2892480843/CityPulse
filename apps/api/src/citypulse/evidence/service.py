from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from citypulse.ingestion.models import SignalObservation
from citypulse.prediction.scoring import TREND_WEIGHTS
from citypulse.shared.timeutil import as_utc

TREND_METRICS = set(TREND_WEIGHTS) | {"risk_pressure"}


def source_host(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.netloc or None


async def city_evidence_summary(db: AsyncSession, *, city_code: str) -> dict[str, object]:
    rows = (
        await db.execute(
            select(SignalObservation).where(SignalObservation.city_code == city_code)
        )
    ).scalars().all()

    if not rows:
        return {
            "city_code": city_code,
            "total_observations": 0,
            "sourced_share": 0.0,
            "metric_coverage": 0.0,
            "covered_metrics": [],
            "missing_metrics": sorted(TREND_METRICS),
            "date_min": None,
            "date_max": None,
            "latest_available_at": None,
            "sources": [],
        }

    total = len(rows)
    with_source = sum(1 for row in rows if row.source_url)
    hosts = sorted({host for row in rows if (host := source_host(row.source_url))})
    covered = sorted({row.metric_name for row in rows if row.metric_name in TREND_METRICS})
    dates = [row.metric_date for row in rows]
    latest = max(as_utc(row.available_at) for row in rows)

    return {
        "city_code": city_code,
        "total_observations": total,
        "sourced_share": round(with_source / total, 3),
        "metric_coverage": round(len(covered) / len(TREND_METRICS), 3),
        "covered_metrics": covered,
        "missing_metrics": sorted(TREND_METRICS - set(covered)),
        "date_min": min(dates).isoformat(),
        "date_max": max(dates).isoformat(),
        "latest_available_at": latest.isoformat(),
        "sources": hosts[:12],
    }
