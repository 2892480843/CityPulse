from fastapi.testclient import TestClient

from tests.conftest import ANALYST_PASSWORD, T0, backtest_csv, commit_dataset, login


def test_backtest_respects_available_at_and_reports_metrics(analyst_client: TestClient) -> None:
    commit_dataset(analyst_client, backtest_csv(), name="history.csv")
    headers = login(analyst_client, "analyst", ANALYST_PASSWORD)

    created = analyst_client.post(
        "/api/v1/backtest-runs",
        json={
            "t0": T0,
            "target_city_codes": ["222401"],
            "control_city_codes": ["370300"],
            "window_days": 14,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    run = created.json()
    assert run["status"] == "succeeded"

    metrics = run["metrics"]
    snapshots = metrics["snapshots"]

    earliest = snapshots[0]
    target_early = next(
        entry for entry in earliest["ranking"] if entry["city_code"] == "222401"
    )
    assert target_early["trend_score"] < 58

    latest = snapshots[-1]
    target_late = next(
        entry for entry in latest["ranking"] if entry["city_code"] == "222401"
    )
    assert target_late["trend_score"] >= 68

    assert metrics["hit_at_5"] >= 0.5
    assert metrics["mean_lead_days"] is not None and metrics["mean_lead_days"] <= 14
    assert metrics["false_alerts_per_100"] == 0.0
    assert metrics["evidence_coverage"] == 1.0


def test_backtest_rejects_unknown_city(analyst_client: TestClient) -> None:
    headers = login(analyst_client, "analyst", ANALYST_PASSWORD)

    response = analyst_client.post(
        "/api/v1/backtest-runs",
        json={"t0": T0, "target_city_codes": ["999999"]},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "UNKNOWN_CITY"


def test_operator_cannot_run_backtests(operator_client: TestClient) -> None:
    headers = login(operator_client, "operator", "market-ops-3345")

    response = operator_client.post(
        "/api/v1/backtest-runs",
        json={"t0": T0, "target_city_codes": ["222401"]},
        headers=headers,
    )

    assert response.status_code == 403
