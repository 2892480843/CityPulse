from fastapi.testclient import TestClient

from tests.conftest import ANALYST_PASSWORD, commit_dataset, fresh_csv, login


def test_demo_summary_is_public_and_disclaims(app_client: TestClient) -> None:
    response = app_client.get("/api/v1/demo/summary")

    assert response.status_code == 200
    payload = response.json()
    assert "不构成真实预测" in payload["disclaimer"]
    assert payload["leaderboard"] == []
    assert payload["city_catalog_size"] >= 3


def test_demo_summary_aggregates_latest_artifacts(app_client: TestClient) -> None:
    commit_dataset(app_client, fresh_csv(), name="fresh.csv")
    headers = login(app_client, "analyst", ANALYST_PASSWORD)
    run = app_client.post(
        "/api/v1/prediction-runs", json={"window_days": 14}, headers=headers
    ).json()
    results = app_client.get(f"/api/v1/prediction-runs/{run['id']}/results").json()
    plan = app_client.post(
        "/api/v1/action-plans",
        json={"prediction_result_id": results["items"][0]["id"]},
        headers=headers,
    ).json()
    app_client.post(f"/api/v1/action-plans/{plan['id']}/submit", headers=headers)

    response = app_client.get("/api/v1/demo/summary")

    payload = response.json()
    assert payload["latest_run"]["window_days"] == 14
    assert payload["leaderboard"][0]["city_name"] == "延吉"
    assert payload["leaderboard"][0]["accelerating"] is False
    assert payload["observation_count"] > 0
    featured = payload["featured_plans"][0]
    assert featured["city_name"] == plan["city_name"]
    assert "actor" not in featured and "created_by" not in featured
