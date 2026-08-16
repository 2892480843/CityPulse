from fastapi.testclient import TestClient

from tests.conftest import (
    ANALYST_PASSWORD,
    T0,
    backtest_csv,
    commit_dataset,
    login,
)


def _create_backtest(analyst_client: TestClient) -> str:
    commit_dataset(analyst_client, backtest_csv(), name="history.csv")
    headers = login(analyst_client, "analyst", ANALYST_PASSWORD)
    run = analyst_client.post(
        "/api/v1/backtest-runs",
        json={
            "t0": T0,
            "target_city_codes": ["222401"],
            "control_city_codes": ["370300"],
            "window_days": 14,
        },
        headers=headers,
    )
    assert run.status_code == 201, run.text
    return run.json()["id"]


def test_calibration_report_from_backtest(analyst_client: TestClient) -> None:
    backtest_id = _create_backtest(analyst_client)
    headers = login(analyst_client, "analyst", ANALYST_PASSWORD)

    created = analyst_client.post(
        "/api/v1/calibration-reports",
        json={"backtest_run_id": backtest_id},
        headers=headers,
    )

    assert created.status_code == 201, created.text
    report = created.json()
    assert report["sample_size"] >= 3
    assert 0.0 <= report["brier"] <= 1.0
    assert 0.0 <= report["ece"] <= 1.0
    assert report["verdict"] == "insufficient_samples"
    assert report["bins"]

    listing = analyst_client.get("/api/v1/calibration-reports")
    assert listing.status_code == 200
    assert listing.json()["gate_note"].startswith("Calibration reports are experiments")
    assert listing.json()["total"] == 1


def test_operator_cannot_create_calibration_reports(
    analyst_client: TestClient, operator_client: TestClient
) -> None:
    backtest_id = _create_backtest(analyst_client)
    headers = login(operator_client, "operator", "market-ops-3345")

    response = operator_client.post(
        "/api/v1/calibration-reports",
        json={"backtest_run_id": backtest_id},
        headers=headers,
    )

    assert response.status_code == 403
