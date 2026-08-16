from fastapi.testclient import TestClient

from tests.conftest import commit_dataset, fresh_csv, login


def test_evidence_summary_requires_authentication(app_client: TestClient) -> None:
    response = app_client.get("/api/v1/cities/222401/evidence")

    assert response.status_code == 401


def test_evidence_summary_reports_coverage_and_sources(
    analyst_client: TestClient,
) -> None:
    commit_dataset(analyst_client, fresh_csv(), name="fresh.csv")
    login(analyst_client, "analyst", "signal-keeper-88")

    response = analyst_client.get("/api/v1/cities/222401/evidence")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_observations"] >= 18
    assert payload["metric_coverage"] == 1.0
    assert payload["missing_metrics"] == []
    assert payload["sourced_share"] == 1.0
    assert payload["sources"] == ["example.gov.cn"]
    assert payload["date_min"] <= payload["date_max"]
    assert payload["latest_available_at"]


def test_evidence_summary_for_city_without_data(analyst_client: TestClient) -> None:
    login(analyst_client, "analyst", "signal-keeper-88")

    response = analyst_client.get("/api/v1/cities/370300/evidence")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_observations"] == 0
    assert payload["metric_coverage"] == 0.0
