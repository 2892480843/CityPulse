"""Transparent baseline scoring with separated trend, risk, and action outputs.

The weights mirror the stage-1 demo contract (src/scoring.py and the XLSX
parameter sheet). They produce a ranking score, never a probability.
"""

from dataclasses import dataclass
from datetime import date, datetime

TREND_WEIGHTS: dict[str, float] = {
    "content_growth": 0.22,
    "search_growth": 0.18,
    "event_trigger": 0.12,
    "accessibility": 0.12,
    "supply_capacity": 0.10,
    "weather_fit": 0.08,
    "novelty": 0.08,
    "cross_region_spread": 0.10,
}
RISK_METRIC = "risk_pressure"
RISK_WEIGHT = 0.15

ACTION_THRESHOLD = 68.0
WATCH_THRESHOLD = 58.0
BLOCKED_RISK_THRESHOLD = 80.0
EVIDENCE_PUBLISH_THRESHOLD = 0.5
DATA_FRESHNESS_DAYS = 14
ACCELERATION_RATIO = 1.15

ActionPriority = str  # "high" | "medium" | "watch" | "blocked"


@dataclass(frozen=True, slots=True)
class CityObservations:
    city_code: str
    values: dict[str, float]
    recent_values: dict[str, float]
    baseline_values: dict[str, float]
    last_available_at: datetime | None
    source_share: float


@dataclass(frozen=True, slots=True)
class CityScore:
    city_code: str
    trend_score: float
    risk_pressure: float
    evidence_coverage: float
    action_priority: ActionPriority
    data_stale: bool
    momentum: float | None
    accelerating: bool
    factors: dict[str, float]
    blockers: list[str]


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def data_is_stale(last_available_at: datetime | None, as_of: date) -> bool:
    if last_available_at is None:
        return True
    from citypulse.shared.timeutil import as_utc

    moment = as_utc(last_available_at).date()
    return (as_of - moment).days > DATA_FRESHNESS_DAYS


def momentum_ratio(observations: CityObservations) -> float | None:
    """Lightweight acceleration screen: weighted recent mean over window baseline.

    Only trend metrics present in both the recent tail and the earlier
    baseline participate; None means the history is too short to judge.
    """
    shared = [
        name
        for name in TREND_WEIGHTS
        if name in observations.recent_values and name in observations.baseline_values
    ]
    if not shared:
        return None
    baseline = sum(TREND_WEIGHTS[name] * observations.baseline_values[name] for name in shared)
    recent = sum(TREND_WEIGHTS[name] * observations.recent_values[name] for name in shared)
    if baseline <= 0:
        return None
    return round(recent / baseline, 3)


def score_city(observations: CityObservations, *, as_of: date) -> CityScore:
    present = {name: value for name, value in observations.values.items() if name in TREND_WEIGHTS}
    coverage = len(present) / len(TREND_WEIGHTS)

    if present:
        raw = sum(TREND_WEIGHTS[name] * value for name, value in present.items())
        weight_sum = sum(TREND_WEIGHTS[name] for name in present)
        trend = _clamp(raw / weight_sum if weight_sum else 0.0)
    else:
        trend = 0.0

    risk = _clamp(observations.values.get(RISK_METRIC, 0.0))
    stale = data_is_stale(observations.last_available_at, as_of)

    blockers: list[str] = []
    if risk >= BLOCKED_RISK_THRESHOLD:
        priority: ActionPriority = "blocked"
        blockers.append("risk_pressure >= 80")
    elif coverage < EVIDENCE_PUBLISH_THRESHOLD:
        priority = "watch"
        blockers.append("evidence coverage below publish threshold")
    elif trend >= ACTION_THRESHOLD:
        priority = "high" if not stale else "medium"
        if stale:
            blockers.append("data older than freshness window")
    elif trend >= WATCH_THRESHOLD:
        priority = "medium" if not stale else "watch"
        if stale:
            blockers.append("data older than freshness window")
    else:
        priority = "watch"

    momentum = momentum_ratio(observations)
    accelerating = momentum is not None and momentum >= ACCELERATION_RATIO

    return CityScore(
        city_code=observations.city_code,
        trend_score=round(trend, 1),
        risk_pressure=round(risk, 1),
        evidence_coverage=round(coverage, 3),
        action_priority=priority,
        data_stale=stale,
        momentum=momentum,
        accelerating=accelerating,
        factors={name: round(value, 1) for name, value in sorted(present.items())},
        blockers=blockers,
    )
