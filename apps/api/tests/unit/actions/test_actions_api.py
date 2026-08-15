from fastapi.testclient import TestClient

from tests.conftest import ANALYST_PASSWORD, commit_dataset, fresh_csv, login


def _seed_run(analyst_client: TestClient) -> dict:
    commit_dataset(analyst_client, fresh_csv(), name="fresh.csv")
    headers = login(analyst_client, "analyst", ANALYST_PASSWORD)
    run = analyst_client.post(
        "/api/v1/prediction-runs", json={"window_days": 14}, headers=headers
    ).json()
    results = analyst_client.get(f"/api/v1/prediction-runs/{run['id']}/results").json()
    return results["items"][0]


def test_generate_edit_submit_approve_workflow(app_client: TestClient) -> None:
    top = _seed_run(app_client)
    analyst_headers = login(app_client, "analyst", ANALYST_PASSWORD)

    generated = app_client.post(
        "/api/v1/action-plans",
        json={"prediction_result_id": top["id"]},
        headers=analyst_headers,
    )
    assert generated.status_code == 201, generated.text
    plan = generated.json()
    assert plan["status"] == "draft"
    assert plan["generator_type"] == "rule_fallback"
    assert plan["city_name"] == "延吉"
    assert plan["target_segment"]
    assert plan["product_bundle"]

    edited = app_client.patch(
        f"/api/v1/action-plans/{plan['id']}",
        json={"campaign_theme": "长白山脚下的朝鲜族风情抢先体验"},
        headers=analyst_headers,
    )
    assert edited.status_code == 200
    assert edited.json()["campaign_theme"] == "长白山脚下的朝鲜族风情抢先体验"

    submitted = app_client.post(
        f"/api/v1/action-plans/{plan['id']}/submit", headers=analyst_headers
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending_review"

    analyst_blocked = app_client.post(
        f"/api/v1/action-plans/{plan['id']}/approve",
        json={"comment": "越权审批"},
        headers=analyst_headers,
    )
    assert analyst_blocked.status_code == 403

    operator_headers = login(app_client, "operator", "market-ops-3345")
    approved = app_client.post(
        f"/api/v1/action-plans/{plan['id']}/approve",
        json={"comment": "证据充分，同意小流量上线"},
        headers=operator_headers,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["review_comment"] == "证据充分，同意小流量上线"


def test_drafts_cannot_skip_review_and_approved_plans_lock(app_client: TestClient) -> None:
    top = _seed_run(app_client)
    headers = login(app_client, "analyst", ANALYST_PASSWORD)
    plan = app_client.post(
        "/api/v1/action-plans", json={"prediction_result_id": top["id"]}, headers=headers
    ).json()

    operator_headers = login(app_client, "operator", "market-ops-3345")
    premature = app_client.post(
        f"/api/v1/action-plans/{plan['id']}/approve", json={}, headers=operator_headers
    )
    assert premature.status_code == 409

    headers = login(app_client, "analyst", ANALYST_PASSWORD)
    submitted = app_client.post(f"/api/v1/action-plans/{plan['id']}/submit", headers=headers)
    assert submitted.status_code == 200
    operator_headers = login(app_client, "operator", "market-ops-3345")
    rejected = app_client.post(
        f"/api/v1/action-plans/{plan['id']}/reject",
        json={"comment": "证据链不完整"},
        headers=operator_headers,
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    headers = login(app_client, "analyst", ANALYST_PASSWORD)
    edit_after_decision = app_client.patch(
        f"/api/v1/action-plans/{plan['id']}", json={"campaign_theme": "x"}, headers=headers
    )
    assert edit_after_decision.status_code == 409


def test_blocked_and_watch_results_get_matching_templates(app_client: TestClient) -> None:
    top = _seed_run(app_client)
    headers = login(app_client, "analyst", ANALYST_PASSWORD)
    quiet = None
    run_results = app_client.get(
        f"/api/v1/prediction-runs/{top['run_id']}/results"
    ).json()["items"]
    quiet = next(item for item in run_results if item["action_priority"] == "watch")

    plan = app_client.post(
        "/api/v1/action-plans", json={"prediction_result_id": quiet["id"]}, headers=headers
    ).json()

    assert "观察" in plan["risk_notes"]
    assert plan["supply_actions"]
