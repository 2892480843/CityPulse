from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from citypulse.main import create_app
from citypulse.system.schemas import CheckResult, ReadinessResponse


def test_liveness_does_not_depend_on_infrastructure() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "citypulse-api"


def test_readiness_returns_503_when_a_dependency_is_unavailable(monkeypatch) -> None:
    degraded = ReadinessResponse(
        status="degraded",
        version="0.1.0",
        checks={
            "database": CheckResult(status="ok", latency_ms=1.2),
            "redis": CheckResult(status="error", latency_ms=2.3),
        },
    )
    monkeypatch.setattr(
        "citypulse.system.router.collect_readiness",
        AsyncMock(return_value=degraded),
    )

    with TestClient(create_app()) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == degraded.model_dump(mode="json")


def test_version_endpoint_exposes_no_secrets() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/system/version")

    assert response.status_code == 200
    assert response.json() == {"service": "citypulse-api", "version": "0.1.0"}
