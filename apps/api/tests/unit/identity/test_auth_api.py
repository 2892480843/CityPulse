from fastapi.testclient import TestClient

from tests.conftest import ADMIN_PASSWORD, login


def test_login_sets_http_only_session_and_readable_csrf_cookie(app_client: TestClient) -> None:
    response = app_client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["user"]["username"] == "admin"
    assert response.json()["user"]["roles"] == ["admin"]
    set_cookie = response.headers["set-cookie"]
    assert "citypulse_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert app_client.cookies.get("citypulse_csrf") is not None


def test_login_rejects_wrong_password_with_generic_message(app_client: TestClient) -> None:
    response = app_client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong-password-1"}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


def test_login_locks_out_after_repeated_failures(app_client: TestClient) -> None:
    for _ in range(4):
        response = app_client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "wrong-password-1"}
        )
        assert response.status_code == 401

    lockout = app_client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong-password-1"}
    )

    assert lockout.status_code == 429
    assert lockout.json()["code"] == "LOGIN_RATE_LIMITED"
    assert "Retry-After" in lockout.headers

    response = app_client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD}
    )

    assert response.status_code == 429
    assert response.json()["code"] == "LOGIN_RATE_LIMITED"
    assert "Retry-After" in response.headers


def test_me_requires_authentication(app_client: TestClient) -> None:
    response = app_client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_me_returns_current_user(admin_client: TestClient) -> None:
    response = admin_client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["username"] == "admin"
    assert response.json()["roles"] == ["admin"]


def test_logout_invalidates_session(app_client: TestClient) -> None:
    headers = login(app_client, "admin", ADMIN_PASSWORD)

    response = app_client.post("/api/v1/auth/logout", headers=headers)

    assert response.status_code == 204
    assert app_client.get("/api/v1/auth/me").status_code == 401


def test_expired_or_deleted_session_cookie_is_rejected(app_client: TestClient) -> None:
    login(app_client, "admin", ADMIN_PASSWORD)
    app_client.cookies.delete("citypulse_session")

    response = app_client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
