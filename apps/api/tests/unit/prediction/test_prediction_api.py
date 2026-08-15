from fastapi.testclient import TestClient

from tests.conftest import ANALYST_PASSWORD, commit_dataset, fresh_csv, login


def test_prediction_run_requires_committed_data(analyst_client: TestClient) -> None:
    headers = login(analyst_client, "analyst", ANALYST_PASSWORD)

    response = analyst_client.post(
        "/api/v1/prediction-runs", json={"window_days": 14}, headers=headers
    )

    assert response.status_code == 409
    assert response.json()["code"] == "NO_COMMITTED_DATA"


def test_prediction_run_ranks_cities_with_separated_outputs(analyst_client: TestClient) -> None:
    commit_dataset(analyst_client, fresh_csv(), name="fresh.csv")
    headers = login(analyst_client, "analyst", ANALYST_PASSWORD)

    created = analyst_client.post(
        "/api/v1/prediction-runs", json={"window_days": 14}, headers=headers
    )
    assert created.status_code == 201, created.text
    run = created.json()
    assert run["status"] == "succeeded"
    assert run["city_count"] == 2

    results = analyst_client.get(f"/api/v1/prediction-runs/{run['id']}/results")
    assert results.status_code == 200
    items = results.json()["items"]

    top = items[0]
    assert top["city_code"] == "222401"
    assert top["city_name"] == "延吉"
    assert top["trend_rank"] == 1
    assert top["trend_score"] == 76.7
    assert top["action_priority"] == "high"
    assert top["evidence_coverage"] == 1.0
    assert top["factors"]["content_growth"] == 84

    quiet = items[1]
    assert quiet["city_code"] == "370300"
    assert quiet["action_priority"] == "watch"


def test_operator_cannot_create_runs_but_can_read(operator_client: TestClient) -> None:
    headers = login(operator_client, "operator", "market-ops-3345")

    blocked = operator_client.post(
        "/api/v1/prediction-runs", json={"window_days": 14}, headers=headers
    )
    assert blocked.status_code == 403

    listing = operator_client.get("/api/v1/prediction-runs")
    assert listing.status_code == 200
    assert listing.json()["total"] == 0


def test_city_trend_includes_result_and_series(analyst_client: TestClient) -> None:
    commit_dataset(analyst_client, fresh_csv(), name="fresh.csv")
    headers = login(analyst_client, "analyst", ANALYST_PASSWORD)
    run = analyst_client.post(
        "/api/v1/prediction-runs", json={"window_days": 14}, headers=headers
    ).json()

    response = analyst_client.get(
        "/api/v1/cities/222401/trend",
        params={"run_id": run["id"], "window_days": 14},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["city_name"] == "延吉"
    assert payload["result"]["trend_score"] == 76.7
    assert set(payload["series"]) >= {"content_growth", "risk_pressure"}
    assert len(payload["series"]["content_growth"]) == 2


def test_jobs_records_the_prediction_run(analyst_client: TestClient) -> None:
    commit_dataset(analyst_client, fresh_csv(), name="fresh.csv")
    headers = login(analyst_client, "analyst", ANALYST_PASSWORD)
    analyst_client.post("/api/v1/prediction-runs", json={"window_days": 7}, headers=headers)

    jobs = analyst_client.get("/api/v1/jobs")

    assert jobs.status_code == 200
    items = jobs.json()["items"]
    assert any(
        item["job_type"] == "prediction_run" and item["status"] == "succeeded"
        for item in items
    )
