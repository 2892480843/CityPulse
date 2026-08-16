from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import ANALYST_PASSWORD, commit_dataset, fresh_csv, login


def _snapshot(tmp: Path) -> Path:
    directory = tmp / "official"
    directory.mkdir()
    (directory / "admin_divisions_cn.csv").write_text(
        "code,name,province\n110100,北京市,北京市\n130100,石家庄,河北省\n", encoding="utf-8"
    )
    return directory


def test_sources_seed_on_first_list(analyst_client: TestClient, tmp_path: Path) -> None:
    analyst_client.app.state.settings.official_data_dir = _snapshot(tmp_path)  # type: ignore[attr-defined]
    login(analyst_client, "analyst", ANALYST_PASSWORD)

    response = analyst_client.get("/api/v1/data-sources")

    assert response.status_code == 200
    kinds = {item["kind"] for item in response.json()["items"]}
    assert kinds == {"admin_divisions", "open_meteo_weather"}


def test_admin_divisions_sync_imports_cities(analyst_client: TestClient, tmp_path: Path) -> None:
    analyst_client.app.state.settings.official_data_dir = _snapshot(tmp_path)  # type: ignore[attr-defined]
    headers = login(analyst_client, "analyst", ANALYST_PASSWORD)
    sources = analyst_client.get("/api/v1/data-sources").json()["items"]
    divisions = next(item for item in sources if item["kind"] == "admin_divisions")

    synced = analyst_client.post(f"/api/v1/data-sources/{divisions['id']}/sync", headers=headers)

    assert synced.status_code == 200, synced.text
    result = synced.json()["result"]
    assert result["total_units"] == 2
    assert result["created"] == 2

    cities = analyst_client.get("/api/v1/cities", params={"q": "北京"}).json()["items"]
    assert any(item["code"] == "110100" for item in cities)

    again = analyst_client.post(
        f"/api/v1/data-sources/{divisions['id']}/sync", headers=headers
    ).json()["result"]
    assert again["created"] == 0
    assert again["updated"] == 0


def test_weather_sync_flows_through_ingestion_contract(
    analyst_client: TestClient, tmp_path: Path
) -> None:
    analyst_client.app.state.settings.official_data_dir = _snapshot(tmp_path)  # type: ignore[attr-defined]
    headers = login(analyst_client, "analyst", ANALYST_PASSWORD)
    commit_dataset(analyst_client, fresh_csv(), name="fresh.csv")
    headers = login(analyst_client, "analyst", ANALYST_PASSWORD)

    from citypulse.data_source import sync as sync_module

    def fake_fetcher(city_name: str, *, end_date: date) -> list[tuple[date, float]]:
        day = end_date
        return [(day - timedelta(days=1), 88.0), (day, 92.0)]

    original = sync_module.fetch_weather_rows
    sync_module.fetch_weather_rows = fake_fetcher  # type: ignore[assignment]
    try:
        sources = analyst_client.get("/api/v1/data-sources").json()["items"]
        weather = next(item for item in sources if item["kind"] == "open_meteo_weather")
        synced = analyst_client.post(
            f"/api/v1/data-sources/{weather['id']}/sync", headers=headers
        )
    finally:
        sync_module.fetch_weather_rows = original  # type: ignore[assignment]

    assert synced.status_code == 200, synced.text
    result = synced.json()["result"]
    assert result["observation_count"] == 4  # 2 cities x 2 days
    assert set(result["synced_cities"]) == {"延吉", "淄博"}

    datasets = analyst_client.get("/api/v1/datasets").json()["items"]
    weather_ds = next(d for d in datasets if d["source_type"] == "official_sync")
    assert weather_ds["status"] == "committed"
    assert weather_ds["legal_basis"].startswith("Open-Meteo")


def test_operator_cannot_sync(operator_client: TestClient, tmp_path: Path) -> None:
    operator_client.app.state.settings.official_data_dir = _snapshot(tmp_path)  # type: ignore[attr-defined]
    login(operator_client, "operator", "market-ops-3345")

    response = operator_client.get("/api/v1/data-sources")

    assert response.status_code == 403
