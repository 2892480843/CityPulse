import io
import json

import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient

from citypulse.shared.errors import AppError, install_exception_handlers
from citypulse.shared.http import RequestContextMiddleware
from citypulse.shared.logging import configure_logging


def build_test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    install_exception_handlers(app)

    @app.get("/ok")
    async def ok() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/broken")
    async def broken() -> None:
        raise AppError(code="SAMPLE_CONFLICT", message="sample conflict", status_code=409)

    return app


def test_request_id_is_generated_and_returned() -> None:
    with TestClient(build_test_app()) as client:
        response = client.get("/ok")

    assert response.status_code == 200
    assert len(response.headers["X-Request-ID"]) == 32


def test_valid_request_id_is_propagated_into_error_response() -> None:
    request_id = "a" * 32

    with TestClient(build_test_app()) as client:
        response = client.get("/broken", headers={"X-Request-ID": request_id})

    assert response.status_code == 409
    assert response.headers["X-Request-ID"] == request_id
    assert response.json() == {
        "code": "SAMPLE_CONFLICT",
        "message": "sample conflict",
        "request_id": request_id,
    }


def test_logging_is_json_and_identifies_the_service() -> None:
    stream = io.StringIO()
    configure_logging("INFO", "citypulse-test", stream=stream)

    structlog.get_logger("test").info("sample_event", item_count=2)
    payload = json.loads(stream.getvalue())

    assert payload["event"] == "sample_event"
    assert payload["service"] == "citypulse-test"
    assert payload["item_count"] == 2
