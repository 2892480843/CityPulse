from fastapi.testclient import TestClient


def test_cities_require_authentication(app_client: TestClient) -> None:
    response = app_client.get("/api/v1/cities")

    assert response.status_code == 401


def test_operator_can_search_cities_by_name(operator_client: TestClient) -> None:
    response = operator_client.get("/api/v1/cities", params={"q": "淄博"})

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["code"] == "370300"
    assert items[0]["province"] == "山东"


def test_city_search_matches_code_prefix(analyst_client: TestClient) -> None:
    response = analyst_client.get("/api/v1/cities", params={"q": "2224"})

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["items"]] == ["延吉"]
