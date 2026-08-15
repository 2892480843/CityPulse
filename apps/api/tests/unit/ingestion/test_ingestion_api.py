import io

from fastapi.testclient import TestClient

from tests.conftest import ANALYST_PASSWORD, VALID_CSV, login


def _upload(analyst_client: TestClient, content: str, name: str = "sample.csv") -> dict:
    headers = login(analyst_client, "analyst", ANALYST_PASSWORD)
    response = analyst_client.post(
        "/api/v1/datasets",
        files={"file": (name, io.BytesIO(content.encode("utf-8")), "text/csv")},
        data={"source_name": "演示导入", "legal_basis": "公开统计数据"},
        headers=headers,
    )
    assert response.status_code in (200, 201), response.text
    return response.json()


def test_full_upload_validate_commit_lifecycle(analyst_client: TestClient, tmp_path) -> None:
    created = _upload(analyst_client, VALID_CSV)
    dataset_id = created["dataset"]["id"]
    headers = login(analyst_client, "analyst", ANALYST_PASSWORD)
    assert created["dataset"]["status"] == "uploaded"

    validated = analyst_client.post(f"/api/v1/datasets/{dataset_id}/validate", headers=headers)
    assert validated.status_code == 200
    assert validated.json()["dataset"]["status"] == "valid"
    assert validated.json()["report"]["row_count"] == 3
    assert validated.json()["report"]["city_count"] == 2

    committed = analyst_client.post(f"/api/v1/datasets/{dataset_id}/commit", headers=headers)
    assert committed.status_code == 200
    assert committed.json()["dataset"]["status"] == "committed"
    assert committed.json()["version_no"] == 1
    assert committed.json()["observation_count"] == 3

    preview = analyst_client.get(f"/api/v1/datasets/{dataset_id}/observations")
    assert preview.status_code == 200
    assert len(preview.json()["items"]) == 3
    assert preview.json()["items"][0]["city_code"] == "222401"


def test_duplicate_upload_is_idempotent(analyst_client: TestClient) -> None:
    first = _upload(analyst_client, VALID_CSV)
    second = _upload(analyst_client, VALID_CSV)

    assert second["already_exists"] is True
    assert second["dataset"]["id"] == first["dataset"]["id"]


def test_commit_is_idempotent_for_committed_dataset(analyst_client: TestClient) -> None:
    created = _upload(analyst_client, VALID_CSV)
    dataset_id = created["dataset"]["id"]
    headers = login(analyst_client, "analyst", ANALYST_PASSWORD)
    analyst_client.post(f"/api/v1/datasets/{dataset_id}/validate", headers=headers)

    first = analyst_client.post(f"/api/v1/datasets/{dataset_id}/commit", headers=headers)
    second = analyst_client.post(f"/api/v1/datasets/{dataset_id}/commit", headers=headers)

    assert first.json()["version_no"] == 1
    assert second.json()["already_committed"] is True
    assert second.json()["version_no"] == 1


def test_invalid_rows_block_commit(analyst_client: TestClient) -> None:
    bad_csv = (
        "city_code,metric_date,metric_name,value,available_at\n"
        "999999,2026-07-01,content_growth,10,2026-07-02T08:00:00+08:00\n"
    )
    created = _upload(analyst_client, bad_csv)
    dataset_id = created["dataset"]["id"]
    headers = login(analyst_client, "analyst", ANALYST_PASSWORD)

    validated = analyst_client.post(f"/api/v1/datasets/{dataset_id}/validate", headers=headers)

    assert validated.json()["dataset"]["status"] == "invalid"
    assert validated.json()["report"]["errors"][0]["code"] == "UNKNOWN_CITY"

    committed = analyst_client.post(f"/api/v1/datasets/{dataset_id}/commit", headers=headers)
    assert committed.status_code == 409
    assert committed.json()["code"] == "DATASET_NOT_VALID"


def test_rejected_formats_and_encodings(analyst_client: TestClient) -> None:
    headers = login(analyst_client, "analyst", ANALYST_PASSWORD)

    exe = analyst_client.post(
        "/api/v1/datasets",
        files={"file": ("payload.exe", io.BytesIO(b"MZ..."), "application/octet-stream")},
        data={"source_name": "x", "legal_basis": "y"},
        headers=headers,
    )
    assert exe.status_code == 400
    assert exe.json()["code"] == "UNSUPPORTED_FORMAT"

    latin = "city_code,metric_date\n222401,2026-07-01\n".encode("latin-1")
    bad_encoding = analyst_client.post(
        "/api/v1/datasets",
        files={"file": ("bad.csv", io.BytesIO(b"\xff\xfe\x00bad"), "text/csv")},
        data={"source_name": "x", "legal_basis": "y"},
        headers=headers,
    )
    assert bad_encoding.status_code == 400
    assert bad_encoding.json()["code"] == "ENCODING_ERROR"
    assert latin  # sanity: latin-1 payload kept for readability


def test_operator_cannot_upload_but_admin_can_read(app_client: TestClient) -> None:
    analyst_headers = login(app_client, "analyst", ANALYST_PASSWORD)
    created = _upload(app_client, VALID_CSV)
    dataset_id = created["dataset"]["id"]

    operator_headers = login(app_client, "operator", "market-ops-3345")
    blocked = app_client.post(
        "/api/v1/datasets",
        files={"file": ("s.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
        data={"source_name": "x", "legal_basis": "y"},
        headers=operator_headers,
    )
    assert blocked.status_code == 403
    assert app_client.get("/api/v1/datasets").status_code == 403

    login(app_client, "admin", "guard-root-9173")
    readable = app_client.get("/api/v1/datasets")
    assert readable.status_code == 200
    assert [item["id"] for item in readable.json()["items"]] == [dataset_id]
    assert analyst_headers  # referenced to keep intent explicit
