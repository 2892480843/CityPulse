from fastapi.testclient import TestClient

from tests.conftest import ANALYST_PASSWORD, commit_dataset, fresh_csv, login


def _seed_top(app_client: TestClient) -> dict:
    commit_dataset(app_client, fresh_csv(), name="fresh.csv")
    headers = login(app_client, "analyst", ANALYST_PASSWORD)
    run = app_client.post(
        "/api/v1/prediction-runs", json={"window_days": 14}, headers=headers
    ).json()
    results = app_client.get(f"/api/v1/prediction-runs/{run['id']}/results").json()
    return results["items"][0]


def test_plan_lifecycle_records_version_history(app_client: TestClient) -> None:
    top = _seed_top(app_client)
    headers = login(app_client, "analyst", ANALYST_PASSWORD)

    plan = app_client.post(
        "/api/v1/action-plans", json={"prediction_result_id": top["id"]}, headers=headers
    ).json()

    app_client.patch(
        f"/api/v1/action-plans/{plan['id']}",
        json={"campaign_theme": "第二版主题"},
        headers=headers,
    )
    app_client.post(f"/api/v1/action-plans/{plan['id']}/submit", headers=headers)

    operator_headers = login(app_client, "operator", "market-ops-3345")
    app_client.post(
        f"/api/v1/action-plans/{plan['id']}/approve",
        json={"comment": "通过"},
        headers=operator_headers,
    )

    versions = app_client.get(f"/api/v1/action-plans/{plan['id']}/versions").json()

    assert [v["event"] for v in versions["items"]] == [
        "generated",
        "edited",
        "submitted",
        "approved",
    ]
    statuses = [v["snapshot"]["status"] for v in versions["items"]]
    assert statuses == ["draft", "draft", "pending_review", "approved"]
    assert versions["items"][1]["snapshot"]["campaign_theme"] == "第二版主题"
    assert versions["items"][3]["note"] == "通过"
