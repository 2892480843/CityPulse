import pytest

from citypulse.calibration.service import (
    brier_score,
    expected_calibration_error,
    reliability_bins,
    verdict_for,
)


def test_brier_score_matches_definition() -> None:
    samples = [(1.0, 1), (0.0, 0), (0.5, 1), (0.5, 0)]

    assert brier_score(samples) == pytest.approx((0 + 0 + 0.25 + 0.25) / 4)


def test_perfect_scores_have_zero_brier() -> None:
    assert brier_score([(1.0, 1), (0.0, 0)]) == pytest.approx(0.0)


def test_reliability_bins_group_by_decile() -> None:
    samples = [(0.05, 0), (0.15, 0), (0.95, 1)]

    bins = reliability_bins(samples)

    assert [(b["bin_low"], b["count"]) for b in bins] == [(0.0, 1), (0.1, 1), (0.9, 1)]
    assert bins[2]["observed_rate"] == 1.0


def test_ece_is_zero_for_aligned_bins() -> None:
    samples = [(0.0, 0)] * 10 + [(1.0, 1)] * 10

    assert expected_calibration_error(samples) == pytest.approx(0.0, abs=1e-9)


def test_ece_penalizes_miscalibration() -> None:
    aligned = [(0.1, 0)] * 10 + [(0.9, 1)] * 10
    miscalibrated = [(0.1, 1)] * 10 + [(0.9, 0)] * 10

    assert expected_calibration_error(miscalibrated) > expected_calibration_error(aligned)


def test_verdict_requires_minimum_sample_size() -> None:
    assert verdict_for(6, 0.2) == "insufficient_samples"
    assert verdict_for(120, 0.05) == "eligible_for_validation"
