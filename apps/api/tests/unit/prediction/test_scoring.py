from datetime import date, datetime, timedelta

import pytest

from citypulse.prediction.scoring import CityObservations, score_city

FULL_HIGH = {
    "content_growth": 84,
    "search_growth": 79,
    "event_trigger": 76,
    "accessibility": 66,
    "supply_capacity": 61,
    "weather_fit": 72,
    "novelty": 86,
    "cross_region_spread": 82,
}
LOW = {name: 25 for name in FULL_HIGH}


def observations(
    values: dict[str, float],
    *,
    days_ago: int = 1,
    recent: dict[str, float] | None = None,
    baseline: dict[str, float] | None = None,
) -> CityObservations:
    return CityObservations(
        city_code="222401",
        values=values,
        recent_values=recent or values,
        baseline_values=baseline or values,
        last_available_at=datetime.combine(
            date.today() - timedelta(days=days_ago), datetime.min.time()
        ),
        source_share=1.0,
    )


def test_full_fresh_high_signals_map_to_high_priority() -> None:
    scored = score_city(observations({**FULL_HIGH, "risk_pressure": 28}), as_of=date.today())

    assert scored.trend_score == 76.7
    assert scored.evidence_coverage == 1.0
    assert scored.action_priority == "high"
    assert scored.blockers == []


def test_low_signals_map_to_watch() -> None:
    scored = score_city(observations({**LOW, "risk_pressure": 20}), as_of=date.today())

    assert scored.action_priority == "watch"


def test_safety_risk_blocks_regardless_of_trend() -> None:
    scored = score_city(
        observations({**FULL_HIGH, "risk_pressure": 85}), as_of=date.today()
    )

    assert scored.action_priority == "blocked"
    assert scored.trend_score == 76.7


def test_low_evidence_caps_priority_at_watch() -> None:
    partial = {"content_growth": 90, "search_growth": 90}
    scored = score_city(observations(partial), as_of=date.today())

    assert scored.evidence_coverage == 0.25
    assert scored.action_priority == "watch"
    assert any("evidence" in blocker for blocker in scored.blockers)


def test_stale_data_cannot_be_high() -> None:
    scored = score_city(
        observations({**FULL_HIGH, "risk_pressure": 28}, days_ago=30), as_of=date.today()
    )

    assert scored.data_stale is True
    assert scored.action_priority == "medium"
    assert any("freshness" in blocker for blocker in scored.blockers)


def test_missing_metrics_are_renormalized_not_zero_filled() -> None:
    scored = score_city(
        observations({"content_growth": 100, "search_growth": 100}), as_of=date.today()
    )

    assert scored.trend_score == 100.0
    assert scored.evidence_coverage == 0.25


def test_momentum_flags_accelerating_cities() -> None:
    baseline = {name: 40.0 for name in FULL_HIGH}
    recent = {name: 70.0 for name in FULL_HIGH}
    scored = score_city(
        observations({**FULL_HIGH, "risk_pressure": 28}, recent=recent, baseline=baseline),
        as_of=date.today(),
    )

    assert scored.momentum == pytest.approx(1.75)
    assert scored.accelerating is True


def test_momentum_none_without_baseline_history() -> None:
    scored = score_city(observations({**FULL_HIGH, "risk_pressure": 28}), as_of=date.today())

    assert scored.momentum == pytest.approx(1.0)
    assert scored.accelerating is False


def test_flat_cities_are_not_flagged() -> None:
    flat = {name: 60.0 for name in FULL_HIGH}
    scored = score_city(
        observations({**flat, "risk_pressure": 28}, recent=flat, baseline=flat),
        as_of=date.today(),
    )

    assert scored.momentum == pytest.approx(1.0)
    assert scored.accelerating is False
