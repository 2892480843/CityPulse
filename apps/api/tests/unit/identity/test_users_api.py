from fastapi.testclient import TestClient

from tests.conftest import ADMIN_PASSWORD, login

NEW_USER = {
    "username": "shenjunhao",
    "password": "dragon-lake-77",
    "display_name": "沈均皓",
    "roles": ["analyst"],
}


def test_admin_can_create_and_list_users(admin_client: TestClient) -> None:
    headers = login(admin_client, "admin", ADMIN_PASSWORD)

    created = admin_client.post("/api/v1/admin/users", json=NEW_USER, headers=headers)

    assert created.status_code == 201, created.text
    assert created.json()["username"] == "shenjunhao"
    assert created.json()["roles"] == ["analyst"]

    listed = admin_client.get("/api/v1/admin/users")
    assert listed.status_code == 200
    usernames = [item["username"] for item in listed.json()["items"]]
    assert {"admin", "analyst", "operator", "shenjunhao"} <= set(usernames)


def test_analyst_cannot_manage_users(analyst_client: TestClient) -> None:
    headers = login(analyst_client, "analyst", "signal-keeper-88")

    response = analyst_client.post("/api/v1/admin/users", json=NEW_USER, headers=headers)

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    assert analyst_client.get("/api/v1/admin/users").status_code == 403


def test_create_user_rejects_weak_password(admin_client: TestClient) -> None:
    headers = login(admin_client, "admin", ADMIN_PASSWORD)
    payload = {**NEW_USER, "password": "1234567890"}

    response = admin_client.post("/api/v1/admin/users", json=payload, headers=headers)

    assert response.status_code == 400
    assert response.json()["code"] == "WEAK_PASSWORD"


def test_create_user_rejects_duplicate_username(admin_client: TestClient) -> None:
    headers = login(admin_client, "admin", ADMIN_PASSWORD)
    payload = {**NEW_USER, "username": "analyst"}

    response = admin_client.post("/api/v1/admin/users", json=payload, headers=headers)

    assert response.status_code == 400
    assert response.json()["code"] == "USERNAME_TAKEN"


def test_write_requests_require_csrf_token(admin_client: TestClient) -> None:
    response = admin_client.post("/api/v1/admin/users", json=NEW_USER)

    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_TOKEN_INVALID"


def test_disabling_user_revokes_their_sessions(
    admin_client: TestClient, app_client: TestClient
) -> None:
    admin_headers = login(admin_client, "admin", ADMIN_PASSWORD)
    created = admin_client.post("/api/v1/admin/users", json=NEW_USER, headers=admin_headers)
    user_id = created.json()["id"]

    login(app_client, "shenjunhao", "dragon-lake-77")
    victim_session = app_client.cookies.get("citypulse_session")
    assert app_client.get("/api/v1/auth/me").json()["username"] == "shenjunhao"

    admin_headers = login(admin_client, "admin", ADMIN_PASSWORD)
    disabled = admin_client.patch(
        f"/api/v1/admin/users/{user_id}", json={"is_active": False}, headers=admin_headers
    )

    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False

    app_client.cookies.set("citypulse_session", victim_session)
    assert app_client.get("/api/v1/auth/me").status_code == 401


def test_admin_cannot_disable_self(admin_client: TestClient) -> None:
    headers = login(admin_client, "admin", ADMIN_PASSWORD)
    users = admin_client.get("/api/v1/admin/users").json()["items"]
    admin_id = next(item["id"] for item in users if item["username"] == "admin")

    response = admin_client.patch(
        f"/api/v1/admin/users/{admin_id}", json={"is_active": False}, headers=headers
    )

    assert response.status_code == 400
    assert response.json()["code"] == "CANNOT_DISABLE_SELF"
