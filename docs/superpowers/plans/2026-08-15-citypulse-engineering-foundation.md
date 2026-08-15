# CityPulse Engineering Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first production-platform increment: a testable React/FastAPI foundation with validated configuration, PostgreSQL and Redis readiness checks, Celery processes, migrations, structured logging, and a Docker Compose topology that starts on macOS and Linux.

**Architecture:** Keep the existing static prototype and submission assets unchanged, and add a feature-first monorepo under `apps/`. The FastAPI process owns HTTP concerns and shared infrastructure adapters; Celery imports the same settings and task modules; React talks to same-origin REST endpoints through a typed fetch boundary. Database migrations remain an explicit release step and never run implicitly at API startup.

**Tech Stack:** React 19, TypeScript, Vite, TanStack Query, Vitest, FastAPI, Pydantic Settings, SQLAlchemy, Alembic, PostgreSQL, Redis, Celery, structlog, Nginx, Docker Compose, pytest, GitHub Actions.

---

## Scope and architectural decisions

This plan implements only stage 1 from `docs/superpowers/specs/2026-08-15-citypulse-production-platform-design.md`. Identity, data ingestion, prediction, action plans, and backtesting remain separate later plans.

| Decision | Choice | Reason |
|---|---|---|
| Project layout | Feature-first `apps/api/src/citypulse/<feature>` and `apps/web/src/features/<feature>` | Keeps domain boundaries visible and avoids layer-wide directories growing together |
| Service shape | Modular monolith plus separate Celery processes | Preserves transaction simplicity while isolating long-running work |
| API boundary | REST/OpenAPI with a typed fetch wrapper in stage 1 | Python and TypeScript cannot share types directly; the wrapper establishes one boundary without premature code generation |
| Authentication | Server-side session, secure cookie, and CSRF in stage 2 | The design decision is fixed, but stage 1 only validates the security-related configuration |
| Real-time behavior | Five-second polling in the later task-center plan | Current stage has no user task stream and does not need SSE or WebSocket infrastructure |
| Error model | Typed application errors plus one global FastAPI handler | Produces stable `code`, `message`, and `request_id` responses without leaking traces |
| Database changes | Explicit Alembic migration command | Startup remains deterministic and cannot mutate a production schema implicitly |
| Frontend server state | TanStack Query | Provides request deduplication, loading/error states, and controlled retry behavior |

## File map

```text
CityPulse/
├── .env.example
├── .github/workflows/engineering-foundation.yml
├── compose.yaml
├── compose.dev.yaml
├── apps/
│   ├── api/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── alembic.ini
│   │   ├── migrations/
│   │   │   ├── env.py
│   │   │   └── versions/0001_baseline.py
│   │   ├── src/citypulse/
│   │   │   ├── main.py
│   │   │   ├── worker.py
│   │   │   ├── shared/{config,database,errors,http,logging,redis}.py
│   │   │   └── system/{router,schemas,service,tasks}.py
│   │   └── tests/
│   └── web/
│       ├── Dockerfile
│       ├── package.json
│       ├── vite.config.ts
│       ├── nginx.conf
│       └── src/
│           ├── app/App.tsx
│           ├── features/system/{api,SystemStatusPage}.tsx
│           └── shared/api/client.ts
├── infra/proxy/nginx.conf
└── scripts/smoke-compose.sh
```

## Task 1: Create the backend package and fail-fast configuration

**Files:**
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/src/citypulse/__init__.py`
- Create: `apps/api/src/citypulse/shared/__init__.py`
- Create: `apps/api/src/citypulse/shared/config.py`
- Create: `apps/api/tests/unit/shared/test_config.py`
- Modify: `.gitignore`

- [ ] **Step 1: Add Python packaging and test dependencies**

Create `apps/api/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.build_meta"

[project]
name = "citypulse-api"
version = "0.1.0"
description = "CityPulse production platform API"
requires-python = ">=3.13,<3.15"
dependencies = [
  "alembic>=1.14,<2",
  "celery[redis]>=5.4,<6",
  "fastapi>=0.115,<1",
  "psycopg[binary]>=3.2,<4",
  "pydantic-settings>=2.7,<3",
  "redis>=5.2,<7",
  "sqlalchemy[asyncio]>=2.0,<3",
  "structlog>=24.4,<27",
  "uvicorn[standard]>=0.34,<1",
]

[project.optional-dependencies]
dev = [
  "httpx>=0.28,<1",
  "pytest>=8.3,<10",
  "pytest-asyncio>=0.25,<2",
  "ruff>=0.9,<1",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
addopts = "-q"
asyncio_mode = "auto"
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
```

Create empty `__init__.py` files at `apps/api/src/citypulse/__init__.py` and `apps/api/src/citypulse/shared/__init__.py`.

Run:

```bash
python3 -m venv apps/api/.venv
apps/api/.venv/bin/python -m pip install --upgrade pip
apps/api/.venv/bin/python -m pip install -e 'apps/api[dev]'
```

Expected: installation exits with status `0`, and `apps/api/.venv/bin/python -c "import fastapi"` exits with status `0`.

- [ ] **Step 2: Write failing configuration tests**

Create `apps/api/tests/unit/shared/test_config.py`:

```python
import pytest
from pydantic import ValidationError

from citypulse.shared.config import Settings


def test_development_defaults_are_explicit() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.debug is False
    assert settings.cookie_secure is False
    assert settings.app_version == "0.1.0"


@pytest.mark.parametrize(
    ("overrides", "expected_fragment"),
    [
        ({"debug": True}, "debug must be disabled"),
        ({"cookie_secure": False}, "secure cookies are required"),
        (
            {"session_secret": "local-development-only-change-me"},
            "replace the development session secret",
        ),
    ],
)
def test_production_rejects_unsafe_settings(
    overrides: dict[str, object], expected_fragment: str
) -> None:
    values: dict[str, object] = {
        "environment": "production",
        "debug": False,
        "cookie_secure": True,
        "session_secret": "production-secret-with-at-least-32-characters",
    }
    values.update(overrides)

    with pytest.raises(ValidationError, match=expected_fragment):
        Settings(**values, _env_file=None)
```

Run:

```bash
apps/api/.venv/bin/pytest apps/api/tests/unit/shared/test_config.py -q
```

Expected: collection fails because `citypulse.shared.config` does not exist.

- [ ] **Step 3: Implement validated settings**

Create `apps/api/src/citypulse/shared/config.py`:

```python
from functools import lru_cache
from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


Environment = Literal["development", "test", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CITYPULSE_",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Environment = "development"
    debug: bool = False
    app_version: str = "0.1.0"
    log_level: LogLevel = "INFO"
    database_url: str = "postgresql+psycopg://citypulse:citypulse@localhost:5432/citypulse"
    redis_url: str = "redis://localhost:6379/0"
    session_secret: SecretStr = SecretStr("local-development-only-change-me")
    cookie_secure: bool = False

    @model_validator(mode="after")
    def reject_unsafe_production_settings(self) -> Self:
        if self.environment != "production":
            return self
        if self.debug:
            raise ValueError("debug must be disabled in production")
        if not self.cookie_secure:
            raise ValueError("secure cookies are required in production")
        if self.session_secret.get_secret_value() == "local-development-only-change-me":
            raise ValueError("replace the development session secret in production")
        if len(self.session_secret.get_secret_value()) < 32:
            raise ValueError("the production session secret must contain at least 32 characters")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

Run:

```bash
apps/api/.venv/bin/pytest apps/api/tests/unit/shared/test_config.py -q
apps/api/.venv/bin/ruff check apps/api/src apps/api/tests
```

Expected: both configuration tests pass and Ruff reports no violations.

- [ ] **Step 4: Ignore generated and secret-bearing files**

Append these entries to `.gitignore` without removing the existing rules:

```gitignore
.env
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
*.py[cod]
node_modules/
dist/
coverage/
```

Run:

```bash
git check-ignore apps/api/.venv .env
```

Expected: both paths are printed.

- [ ] **Step 5: Commit the backend configuration foundation**

```bash
git add .gitignore apps/api/pyproject.toml apps/api/src apps/api/tests
git commit -m "build: scaffold validated API configuration"
```

## Task 2: Add structured logging, request IDs, and typed errors

**Files:**
- Create: `apps/api/src/citypulse/shared/errors.py`
- Create: `apps/api/src/citypulse/shared/logging.py`
- Create: `apps/api/src/citypulse/shared/http.py`
- Create: `apps/api/src/citypulse/main.py`
- Create: `apps/api/tests/unit/shared/test_http.py`

- [ ] **Step 1: Write failing HTTP-boundary tests**

Create `apps/api/tests/unit/shared/test_http.py`:

```python
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
```

Run:

```bash
apps/api/.venv/bin/pytest apps/api/tests/unit/shared/test_http.py -q
```

Expected: collection fails because the shared HTTP modules do not exist.

- [ ] **Step 2: Implement the typed error handler**

Create `apps/api/src/citypulse/shared/errors.py`:

```python
from typing import Any, TextIO

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


logger = structlog.get_logger(__name__)


class AppError(Exception):
    def __init__(self, *, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unavailable"))


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, error: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={
                "code": error.code,
                "message": error.message,
                "request_id": _request_id(request),
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
        await logger.aexception(
            "unhandled_exception",
            request_id=_request_id(request),
            error_type=type(error).__name__,
        )
        content: dict[str, Any] = {
            "code": "INTERNAL_ERROR",
            "message": "The service encountered an unexpected error.",
            "request_id": _request_id(request),
        }
        return JSONResponse(status_code=500, content=content)
```

- [ ] **Step 3: Implement JSON logging and request context middleware**

Create `apps/api/src/citypulse/shared/logging.py`:

```python
import logging
from collections.abc import MutableMapping
from typing import Any

import structlog


def configure_logging(level: str, service: str, stream: TextIO | None = None) -> None:
    def add_service(
        _logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]
    ) -> MutableMapping[str, Any]:
        event_dict.setdefault("service", service)
        return event_dict

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        add_service,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )
    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
```

Create `apps/api/src/citypulse/shared/http.py`:

```python
import re
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


logger = structlog.get_logger(__name__)
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        supplied = request.headers.get("X-Request-ID", "")
        request_id = supplied if REQUEST_ID_PATTERN.fullmatch(supplied) else uuid.uuid4().hex
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            await logger.ainfo(
                "http_request",
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                duration_ms=duration_ms,
            )

        response.headers["X-Request-ID"] = request_id
        return response
```

- [ ] **Step 4: Create the application factory**

Create `apps/api/src/citypulse/main.py`:

```python
from fastapi import FastAPI

from citypulse.shared.config import get_settings
from citypulse.shared.errors import install_exception_handlers
from citypulse.shared.http import RequestContextMiddleware
from citypulse.shared.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, "citypulse-api")
    app = FastAPI(
        title="CityPulse API",
        version=settings.app_version,
        debug=settings.debug,
        docs_url="/api/docs" if settings.environment != "production" else None,
        openapi_url="/api/openapi.json" if settings.environment != "production" else None,
    )
    app.add_middleware(RequestContextMiddleware)
    install_exception_handlers(app)
    return app


app = create_app()
```

Run:

```bash
apps/api/.venv/bin/pytest apps/api/tests/unit/shared/test_http.py -q
apps/api/.venv/bin/ruff check apps/api/src apps/api/tests
```

Expected: all three tests pass and Ruff reports no violations.

- [ ] **Step 5: Commit the shared HTTP foundation**

```bash
git add apps/api/src/citypulse apps/api/tests/unit/shared/test_http.py
git commit -m "feat: add request tracing and typed API errors"
```

## Task 3: Add PostgreSQL, Redis, and health endpoints

**Files:**
- Create: `apps/api/src/citypulse/shared/database.py`
- Create: `apps/api/src/citypulse/shared/redis.py`
- Create: `apps/api/src/citypulse/system/__init__.py`
- Create: `apps/api/src/citypulse/system/schemas.py`
- Create: `apps/api/src/citypulse/system/service.py`
- Create: `apps/api/src/citypulse/system/router.py`
- Modify: `apps/api/src/citypulse/main.py`
- Create: `apps/api/tests/unit/system/test_health.py`

- [ ] **Step 1: Write failing endpoint tests**

Create `apps/api/tests/unit/system/test_health.py`:

```python
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
```

Run:

```bash
apps/api/.venv/bin/pytest apps/api/tests/unit/system/test_health.py -q
```

Expected: collection fails because the `citypulse.system` package does not exist.

- [ ] **Step 2: Implement infrastructure clients**

Create `apps/api/src/citypulse/shared/database.py`:

```python
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def create_database_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=10,
        pool_timeout=10,
    )
```

Create `apps/api/src/citypulse/shared/redis.py`:

```python
from redis.asyncio import Redis


def create_redis_client(redis_url: str) -> Redis:
    return Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
```

- [ ] **Step 3: Implement health schemas and dependency checks**

Create an empty `apps/api/src/citypulse/system/__init__.py`.

Create `apps/api/src/citypulse/system/schemas.py`:

```python
from typing import Literal

from pydantic import BaseModel


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "citypulse-api"
    version: str


class CheckResult(BaseModel):
    status: Literal["ok", "error"]
    latency_ms: float


class ReadinessResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    checks: dict[str, CheckResult]


class VersionResponse(BaseModel):
    service: str = "citypulse-api"
    version: str
```

Create `apps/api/src/citypulse/system/service.py`:

```python
import asyncio
import time

import structlog
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from citypulse.system.schemas import CheckResult, ReadinessResponse


logger = structlog.get_logger(__name__)


async def check_database(engine: AsyncEngine) -> CheckResult:
    started = time.perf_counter()
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        status = "ok"
    except Exception as error:
        status = "error"
        await logger.awarning("database_readiness_failed", error_type=type(error).__name__)
    return CheckResult(status=status, latency_ms=round((time.perf_counter() - started) * 1000, 2))


async def check_redis(client: Redis) -> CheckResult:
    started = time.perf_counter()
    try:
        await client.ping()
        status = "ok"
    except Exception as error:
        status = "error"
        await logger.awarning("redis_readiness_failed", error_type=type(error).__name__)
    return CheckResult(status=status, latency_ms=round((time.perf_counter() - started) * 1000, 2))


async def collect_readiness(
    *, engine: AsyncEngine, redis_client: Redis, version: str
) -> ReadinessResponse:
    database, redis = await asyncio.gather(
        check_database(engine),
        check_redis(redis_client),
    )
    checks = {"database": database, "redis": redis}
    overall = "ok" if all(check.status == "ok" for check in checks.values()) else "degraded"
    return ReadinessResponse(status=overall, version=version, checks=checks)
```

- [ ] **Step 4: Implement system routes and lifecycle ownership**

Create `apps/api/src/citypulse/system/router.py`:

```python
from fastapi import APIRouter, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from citypulse.shared.config import Settings
from citypulse.system.schemas import LivenessResponse, ReadinessResponse, VersionResponse
from citypulse.system.service import collect_readiness


router = APIRouter(tags=["system"])


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _engine(request: Request) -> AsyncEngine:
    return request.app.state.database_engine


def _redis(request: Request) -> Redis:
    return request.app.state.redis_client


@router.get("/health/live", response_model=LivenessResponse)
async def liveness(request: Request) -> LivenessResponse:
    return LivenessResponse(version=_settings(request).app_version)


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(request: Request, response: Response) -> ReadinessResponse:
    result = await collect_readiness(
        engine=_engine(request),
        redis_client=_redis(request),
        version=_settings(request).app_version,
    )
    if result.status == "degraded":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result


@router.get("/api/v1/system/version", response_model=VersionResponse)
async def version(request: Request) -> VersionResponse:
    return VersionResponse(version=_settings(request).app_version)
```

Replace `apps/api/src/citypulse/main.py` with:

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from citypulse.shared.config import get_settings
from citypulse.shared.database import create_database_engine
from citypulse.shared.errors import install_exception_handlers
from citypulse.shared.http import RequestContextMiddleware
from citypulse.shared.logging import configure_logging
from citypulse.shared.redis import create_redis_client
from citypulse.system.router import router as system_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    app.state.database_engine = create_database_engine(settings.database_url)
    app.state.redis_client = create_redis_client(settings.redis_url)
    try:
        yield
    finally:
        await app.state.redis_client.aclose()
        await app.state.database_engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, "citypulse-api")
    app = FastAPI(
        title="CityPulse API",
        version=settings.app_version,
        debug=settings.debug,
        docs_url="/api/docs" if settings.environment != "production" else None,
        openapi_url="/api/openapi.json" if settings.environment != "production" else None,
        lifespan=lifespan,
    )
    app.add_middleware(RequestContextMiddleware)
    install_exception_handlers(app)
    app.include_router(system_router)
    return app


app = create_app()
```

Run:

```bash
apps/api/.venv/bin/pytest apps/api/tests/unit/system/test_health.py -q
apps/api/.venv/bin/pytest apps/api/tests -q
apps/api/.venv/bin/ruff check apps/api/src apps/api/tests
```

Expected: all tests pass and Ruff reports no violations.

- [ ] **Step 5: Commit health infrastructure**

```bash
git add apps/api/src/citypulse apps/api/tests/unit/system
git commit -m "feat: add dependency-aware health endpoints"
```

## Task 4: Establish explicit Alembic migrations

**Files:**
- Create: `apps/api/alembic.ini`
- Create: `apps/api/migrations/env.py`
- Create: `apps/api/migrations/script.py.mako`
- Create: `apps/api/migrations/versions/0001_baseline.py`
- Create: `apps/api/tests/unit/shared/test_migrations.py`

- [ ] **Step 1: Write a failing migration-chain test**

Create `apps/api/tests/unit/shared/test_migrations.py`:

```python
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_migration_history_has_one_baseline_head() -> None:
    api_root = Path(__file__).resolve().parents[3]
    config = Config(api_root / "alembic.ini")
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_heads() == ["0001_baseline"]
    assert scripts.get_revision("0001_baseline").down_revision is None
```

Run:

```bash
apps/api/.venv/bin/pytest apps/api/tests/unit/shared/test_migrations.py -q
```

Expected: failure because `apps/api/alembic.ini` does not exist.

- [ ] **Step 2: Configure Alembic without implicit application startup migration**

Create `apps/api/alembic.ini`:

```ini
[alembic]
script_location = %(here)s/migrations
prepend_sys_path = %(here)s/src
path_separator = os

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

Create `apps/api/migrations/env.py`:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from citypulse.shared.config import get_settings


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = None


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Create `apps/api/migrations/script.py.mako`:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

Create `apps/api/migrations/versions/0001_baseline.py`:

```python
"""Create an empty, explicit schema baseline."""

from collections.abc import Sequence


revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
```

- [ ] **Step 3: Verify the chain and offline SQL generation**

Run:

```bash
apps/api/.venv/bin/pytest apps/api/tests/unit/shared/test_migrations.py -q
cd apps/api && .venv/bin/alembic upgrade head --sql && cd ../..
```

Expected: the test passes and Alembic emits SQL that creates and updates `alembic_version` without contacting PostgreSQL.

- [ ] **Step 4: Commit migration infrastructure**

```bash
git add apps/api/alembic.ini apps/api/migrations apps/api/tests/unit/shared/test_migrations.py
git commit -m "build: establish explicit database migrations"
```

## Task 5: Add the Celery worker and deterministic system task

**Files:**
- Create: `apps/api/src/citypulse/system/tasks.py`
- Create: `apps/api/src/citypulse/worker.py`
- Create: `apps/api/tests/unit/system/test_tasks.py`

- [ ] **Step 1: Write a failing task registration test**

Create `apps/api/tests/unit/system/test_tasks.py`:

```python
from citypulse.worker import celery_app


def test_system_ping_task_is_registered_and_deterministic() -> None:
    result = celery_app.tasks["citypulse.system.ping"].apply()

    assert result.successful()
    assert result.get() == {"service": "citypulse-worker", "status": "ok"}
```

Run:

```bash
apps/api/.venv/bin/pytest apps/api/tests/unit/system/test_tasks.py -q
```

Expected: collection fails because `citypulse.worker` does not exist.

- [ ] **Step 2: Implement Celery configuration and ping task**

Create `apps/api/src/citypulse/system/tasks.py`:

```python
from celery import shared_task


@shared_task(name="citypulse.system.ping")
def ping() -> dict[str, str]:
    return {"service": "citypulse-worker", "status": "ok"}
```

Create `apps/api/src/citypulse/worker.py`:

```python
from celery import Celery
from celery.signals import after_setup_logger

from citypulse.shared.config import get_settings
from citypulse.shared.logging import configure_logging


settings = get_settings()
celery_app = Celery(
    "citypulse",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["citypulse.system.tasks"],
)
celery_app.conf.update(
    accept_content=["json"],
    enable_utc=True,
    result_serializer="json",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_serializer="json",
    timezone="Asia/Shanghai",
    worker_prefetch_multiplier=1,
)


@after_setup_logger.connect
def configure_job_process_logging(**_: object) -> None:
    configure_logging(settings.log_level, "citypulse-jobs")
```

Run:

```bash
apps/api/.venv/bin/pytest apps/api/tests/unit/system/test_tasks.py -q
apps/api/.venv/bin/pytest apps/api/tests -q
```

Expected: all tests pass without connecting to Redis because `.apply()` executes synchronously in-process.

- [ ] **Step 3: Commit worker foundation**

```bash
git add apps/api/src/citypulse/system/tasks.py apps/api/src/citypulse/worker.py apps/api/tests/unit/system/test_tasks.py
git commit -m "feat: add Celery worker foundation"
```

## Task 6: Build the React system-status shell

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/package-lock.json` through `npm install`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/tsconfig.app.json`
- Create: `apps/web/tsconfig.node.json`
- Create: `apps/web/vite.config.ts`
- Create: `apps/web/vitest.config.ts`
- Create: `apps/web/index.html`
- Create: `apps/web/src/main.tsx`
- Create: `apps/web/src/app/App.tsx`
- Create: `apps/web/src/shared/api/client.ts`
- Create: `apps/web/src/features/system/api.ts`
- Create: `apps/web/src/features/system/SystemStatusPage.tsx`
- Create: `apps/web/src/styles.css`
- Create: `apps/web/src/test/setup.ts`
- Create: `apps/web/src/features/system/SystemStatusPage.test.tsx`

- [ ] **Step 1: Create the Vite/TypeScript package**

Create `apps/web/package.json`:

```json
{
  "name": "citypulse-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest run",
    "typecheck": "tsc -b --pretty false"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.85.0",
    "react": "^19.1.0",
    "react-dom": "^19.1.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.6.4",
    "@testing-library/react": "^16.3.0",
    "@types/node": "^22.15.0",
    "@types/react": "^19.1.0",
    "@types/react-dom": "^19.1.0",
    "@vitejs/plugin-react": "^5.0.0",
    "jsdom": "^26.1.0",
    "typescript": "~5.8.3",
    "vite": "^7.1.0",
    "vitest": "^3.2.4"
  }
}
```

Run:

```bash
npm --prefix apps/web install
```

Expected: npm creates `apps/web/package-lock.json` and exits with status `0`.

Create `apps/web/tsconfig.json`:

```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ]
}
```

Create `apps/web/tsconfig.app.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src"]
}
```

Create `apps/web/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "allowImportingTsExtensions": true,
    "noEmit": true,
    "strict": true
  },
  "include": ["vite.config.ts", "vitest.config.ts"]
}
```

Create `apps/web/vite.config.ts`:

```typescript
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
})
```

Create `apps/web/vitest.config.ts`:

```typescript
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
```

- [ ] **Step 2: Write the failing status-page test**

Create `apps/web/src/test/setup.ts`:

```typescript
import '@testing-library/jest-dom/vitest'
```

Create `apps/web/src/features/system/SystemStatusPage.test.tsx`:

```typescript
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'

import { SystemStatusPage } from './SystemStatusPage'
import * as systemApi from './api'

vi.mock('./api')

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <SystemStatusPage />
    </QueryClientProvider>,
  )
}

test('shows API and dependency health with text labels', async () => {
  vi.mocked(systemApi.getLiveness).mockResolvedValue({
    status: 'ok',
    service: 'citypulse-api',
    version: '0.1.0',
  })
  vi.mocked(systemApi.getReadiness).mockResolvedValue({
    status: 'ok',
    version: '0.1.0',
    checks: {
      database: { status: 'ok', latency_ms: 2.1 },
      redis: { status: 'ok', latency_ms: 1.3 },
    },
  })

  renderPage()

  expect(await screen.findByText('API 进程正常')).toBeInTheDocument()
  expect(screen.getByText('PostgreSQL 正常')).toBeInTheDocument()
  expect(screen.getByText('Redis 正常')).toBeInTheDocument()
  expect(screen.getByText('版本 0.1.0')).toBeInTheDocument()
})

test('shows the failed dependency when readiness is degraded', async () => {
  vi.mocked(systemApi.getLiveness).mockResolvedValue({
    status: 'ok',
    service: 'citypulse-api',
    version: '0.1.0',
  })
  vi.mocked(systemApi.getReadiness).mockResolvedValue({
    status: 'degraded',
    version: '0.1.0',
    checks: {
      database: { status: 'ok', latency_ms: 2.1 },
      redis: { status: 'error', latency_ms: 2_000 },
    },
  })

  renderPage()

  expect(await screen.findByText('Redis 异常')).toBeInTheDocument()
  expect(screen.getByText('PostgreSQL 正常')).toBeInTheDocument()
})
```

Run:

```bash
npm --prefix apps/web test
```

Expected: test fails because the status-page and API modules do not exist.

- [ ] **Step 3: Implement the typed API boundary**

Create `apps/web/src/shared/api/client.ts`:

```typescript
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly requestId?: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

type ErrorPayload = {
  code?: string
  message?: string
  request_id?: string
}

export async function getJson<T>(
  path: string,
  acceptedErrorStatuses: readonly number[] = [],
): Promise<T> {
  const response = await fetch(path, {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!response.ok && !acceptedErrorStatuses.includes(response.status)) {
    const body = (await response.json().catch(() => ({}))) as ErrorPayload
    throw new ApiError(
      response.status,
      body.code ?? 'HTTP_ERROR',
      body.message ?? '服务暂时不可用',
      body.request_id,
    )
  }
  return (await response.json()) as T
}
```

Create `apps/web/src/features/system/api.ts`:

```typescript
import { getJson } from '../../shared/api/client'

export type Liveness = {
  status: 'ok'
  service: string
  version: string
}

export type CheckResult = {
  status: 'ok' | 'error'
  latency_ms: number
}

export type Readiness = {
  status: 'ok' | 'degraded'
  version: string
  checks: Record<'database' | 'redis', CheckResult>
}

export const getLiveness = () => getJson<Liveness>('/health/live')
export const getReadiness = () => getJson<Readiness>('/health/ready', [503])
```

- [ ] **Step 4: Implement the status page and application shell**

Create `apps/web/src/features/system/SystemStatusPage.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query'

import { getLiveness, getReadiness } from './api'

export function SystemStatusPage() {
  const live = useQuery({ queryKey: ['system', 'live'], queryFn: getLiveness })
  const ready = useQuery({ queryKey: ['system', 'ready'], queryFn: getReadiness })

  if (live.isPending || ready.isPending) {
    return <main aria-busy="true">正在检查 CityPulse 服务…</main>
  }

  if (live.isError || ready.isError) {
    return (
      <main>
        <h1>CityPulse 工程基础</h1>
        <p role="alert">健康检查失败，请核对 API、PostgreSQL 和 Redis 运行状态。</p>
      </main>
    )
  }

  const checks = ready.data.checks
  return (
    <main>
      <header>
        <p className="eyebrow">CITYPULSE / SYSTEM STATUS</p>
        <h1>工程基础已连接</h1>
        <p>版本 {live.data.version}</p>
      </header>
      <section aria-label="服务健康状态" className="status-grid">
        <article>
          <h2>API 进程正常</h2>
          <p>存活检查不依赖外部服务。</p>
        </article>
        <article>
          <h2>PostgreSQL {checks.database.status === 'ok' ? '正常' : '异常'}</h2>
          <p>响应 {checks.database.latency_ms.toFixed(1)} ms</p>
        </article>
        <article>
          <h2>Redis {checks.redis.status === 'ok' ? '正常' : '异常'}</h2>
          <p>响应 {checks.redis.latency_ms.toFixed(1)} ms</p>
        </article>
      </section>
    </main>
  )
}
```

Create `apps/web/src/app/App.tsx`:

```tsx
import { SystemStatusPage } from '../features/system/SystemStatusPage'

export function App() {
  return <SystemStatusPage />
}
```

Create `apps/web/src/main.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from './app/App'
import { ApiError } from './shared/api/client'
import './styles.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        if (error instanceof ApiError) {
          return error.status >= 500 && failureCount < 2
        }
        return failureCount < 2
      },
      staleTime: 30_000,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
```

Create `apps/web/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="CityPulse 旅游趋势分析与运营决策平台" />
    <title>CityPulse 工程基础</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `apps/web/src/styles.css`:

```css
:root {
  color: #17212b;
  background: #f4f1e9;
  font-family: Inter, "PingFang SC", "Microsoft YaHei", sans-serif;
  font-synthesis: none;
}

* { box-sizing: border-box; }
body { margin: 0; min-width: 320px; min-height: 100vh; }
main { width: min(1120px, calc(100% - 48px)); margin: 0 auto; padding: 96px 0; }
header { max-width: 720px; }
h1 { margin: 12px 0; font-size: clamp(2.4rem, 7vw, 5.5rem); line-height: 0.98; }
.eyebrow { color: #b54b2a; font-size: 0.78rem; font-weight: 700; letter-spacing: 0.16em; }
.status-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 56px; }
article { border: 1px solid #d8d1c4; border-radius: 18px; background: #fffdf8; padding: 24px; }
article h2 { margin: 0 0 28px; font-size: 1rem; }
article p { margin: 0; color: #687078; }
[role="alert"] { border-left: 4px solid #b54b2a; padding: 16px; background: #fffdf8; }

@media (max-width: 760px) {
  main { width: min(100% - 32px, 1120px); padding: 56px 0; }
  .status-grid { grid-template-columns: 1fr; }
}
```

Run:

```bash
npm --prefix apps/web test
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
```

Expected: both tests pass, TypeScript reports no errors, and Vite creates `apps/web/dist`.

- [ ] **Step 5: Commit the React shell**

```bash
git add apps/web
git commit -m "feat: add React system status shell"
```

## Task 7: Compose the production-shaped local topology

**Files:**
- Create: `.env.example`
- Create: `apps/api/Dockerfile`
- Create: `apps/api/.dockerignore`
- Create: `apps/web/Dockerfile`
- Create: `apps/web/.dockerignore`
- Create: `apps/web/nginx.conf`
- Create: `infra/proxy/nginx.conf`
- Create: `compose.yaml`
- Create: `compose.dev.yaml`

- [ ] **Step 1: Write environment contract and container images**

Create `.env.example`:

```dotenv
POSTGRES_DB=citypulse
POSTGRES_USER=citypulse
POSTGRES_PASSWORD=local-development-database-password
CITYPULSE_ENVIRONMENT=development
CITYPULSE_DEBUG=false
CITYPULSE_APP_VERSION=0.1.0
CITYPULSE_LOG_LEVEL=INFO
CITYPULSE_DATABASE_URL=postgresql+psycopg://citypulse:local-development-database-password@postgres:5432/citypulse
CITYPULSE_REDIS_URL=redis://redis:6379/0
CITYPULSE_SESSION_SECRET=local-development-only-change-me
CITYPULSE_COOKIE_SECURE=false
CITYPULSE_HTTP_PORT=8080
```

Create `apps/api/.dockerignore`:

```dockerignore
.venv
__pycache__
.pytest_cache
.ruff_cache
tests
```

Create `apps/api/Dockerfile`:

```dockerfile
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN addgroup --system citypulse && adduser --system --ingroup citypulse citypulse
COPY pyproject.toml ./
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .
USER citypulse
EXPOSE 8000
CMD ["uvicorn", "citypulse.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
```

Create `apps/web/.dockerignore`:

```dockerignore
node_modules
dist
```

Create `apps/web/Dockerfile`:

```dockerfile
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
```

Create `apps/web/nginx.conf`:

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    location = /web-health {
        access_log off;
        add_header Content-Type text/plain;
        return 200 "ok\n";
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 2: Configure the same-origin reverse proxy**

Create `infra/proxy/nginx.conf`:

```nginx
server {
    listen 80;
    server_name _;
    client_max_body_size 20m;

    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header X-Frame-Options "DENY" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'" always;

    location /api/ {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;
    }

    location /health/ {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;
    }

    location / {
        proxy_pass http://web:80;
        proxy_set_header Host $host;
    }
}
```

- [ ] **Step 3: Define production-shaped and development Compose files**

Create `compose.yaml`:

```yaml
name: citypulse

x-api-common: &api-common
  build:
    context: ./apps/api
  env_file:
    - ${CITYPULSE_ENV_FILE:-.env}
  restart: unless-stopped

services:
  postgres:
    image: postgres:17-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 5s
      timeout: 3s
      retries: 20
    restart: unless-stopped

  redis:
    image: redis:7.4-alpine
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 20
    restart: unless-stopped

  migrate:
    <<: *api-common
    command: ["alembic", "upgrade", "head"]
    restart: "no"
    depends_on:
      postgres:
        condition: service_healthy
    profiles: ["tools"]

  api:
    <<: *api-common
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2)"]
      interval: 5s
      timeout: 3s
      retries: 20

  worker:
    <<: *api-common
    command: ["celery", "-A", "citypulse.worker:celery_app", "worker", "--loglevel=INFO"]
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  scheduler:
    <<: *api-common
    command: ["celery", "-A", "citypulse.worker:celery_app", "beat", "--loglevel=INFO"]
    depends_on:
      redis:
        condition: service_healthy

  web:
    build:
      context: ./apps/web
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://127.0.0.1/web-health"]
      interval: 5s
      timeout: 3s
      retries: 20
    restart: unless-stopped

  proxy:
    image: nginx:1.27-alpine
    ports:
      - "${CITYPULSE_HTTP_PORT:-8080}:80"
    volumes:
      - ./infra/proxy/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      api:
        condition: service_healthy
      web:
        condition: service_healthy
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

Create `compose.dev.yaml`:

```yaml
services:
  postgres:
    ports:
      - "127.0.0.1:5432:5432"
  redis:
    ports:
      - "127.0.0.1:6379:6379"
  api:
    ports:
      - "127.0.0.1:8000:8000"
```

- [ ] **Step 4: Validate the Compose model before starting containers**

Run:

```bash
CITYPULSE_ENV_FILE=.env.example docker compose --env-file .env.example config --quiet
CITYPULSE_ENV_FILE=.env.example docker compose --env-file .env.example -f compose.yaml -f compose.dev.yaml config --quiet
```

Expected: both commands exit with status `0`; PostgreSQL and Redis have no host ports in the base model, while the development overlay binds them only to `127.0.0.1`.

- [ ] **Step 5: Commit container topology**

```bash
git add .env.example apps/api/Dockerfile apps/api/.dockerignore apps/web/Dockerfile apps/web/.dockerignore apps/web/nginx.conf infra compose.yaml compose.dev.yaml
git commit -m "build: add production-shaped Compose topology"
```

## Task 8: Add a repeatable smoke test and operator documentation

**Files:**
- Create: `scripts/smoke-compose.sh`
- Modify: `README.md`

- [ ] **Step 1: Write the scoped Compose smoke test**

Create `scripts/smoke-compose.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

project_name="${CITYPULSE_SMOKE_PROJECT:-citypulse-smoke}"
http_port="${CITYPULSE_HTTP_PORT:-18080}"

if [[ ! "$project_name" =~ ^citypulse-smoke([a-z0-9-]*)$ ]]; then
  echo "CITYPULSE_SMOKE_PROJECT must start with citypulse-smoke and contain lowercase letters, digits, or hyphens." >&2
  exit 2
fi
if [[ ! "$http_port" =~ ^[0-9]{4,5}$ ]]; then
  echo "CITYPULSE_HTTP_PORT must be a four- or five-digit port." >&2
  exit 2
fi

export CITYPULSE_ENV_FILE=.env.example
export CITYPULSE_HTTP_PORT="$http_port"
compose=(docker compose --env-file .env.example -p "$project_name")

cleanup() {
  "${compose[@]}" down --volumes --remove-orphans
}
trap cleanup EXIT

"${compose[@]}" config --quiet
"${compose[@]}" build
"${compose[@]}" up -d postgres redis
"${compose[@]}" run --rm migrate
"${compose[@]}" up -d api worker scheduler web proxy

for attempt in $(seq 1 60); do
  if curl --fail --silent "http://127.0.0.1:${http_port}/health/ready" >/dev/null; then
    break
  fi
  if [[ "$attempt" == "60" ]]; then
    "${compose[@]}" ps
    "${compose[@]}" logs --no-color api worker postgres redis
    exit 1
  fi
  sleep 2
done

curl --fail --silent "http://127.0.0.1:${http_port}/health/live" | grep '"status":"ok"'
curl --fail --silent "http://127.0.0.1:${http_port}/health/ready" | grep '"status":"ok"'
curl --fail --silent "http://127.0.0.1:${http_port}/api/v1/system/version" | grep '"version":"0.1.0"'
curl --fail --silent "http://127.0.0.1:${http_port}/" | grep 'CityPulse'
"${compose[@]}" exec -T worker celery -A citypulse.worker:celery_app inspect ping
```

Make it executable and run it:

```bash
chmod +x scripts/smoke-compose.sh
./scripts/smoke-compose.sh
```

Expected: migrations reach `0001_baseline`, all four HTTP assertions succeed, Celery reports one responding worker, and the script removes only the validated `citypulse-smoke` project and its test volumes on exit.

- [ ] **Step 2: Document local and container workflows**

Append this section to `README.md`:

````markdown
## 生产平台工程基础

> 新工程与上方静态演示原型分开。当前阶段只提供系统健康、配置、迁移、任务进程和容器基础，不代表身份、数据或预测功能已完成。

### Docker Compose 启动

```bash
cp .env.example .env
docker compose --env-file .env run --rm migrate
docker compose --env-file .env up --build -d
curl http://127.0.0.1:8080/health/ready
```

打开 `http://127.0.0.1:8080`。数据库迁移必须显式执行，API 启动时不会自动修改 Schema（数据库结构）。

### 本地进程开发

```bash
cp .env.example .env
docker compose --env-file .env -f compose.yaml -f compose.dev.yaml up -d postgres redis
apps/api/.venv/bin/uvicorn citypulse.main:app --app-dir apps/api/src --reload
npm --prefix apps/web run dev
```

### 验收

```bash
apps/api/.venv/bin/pytest apps/api/tests -q
npm --prefix apps/web test
npm --prefix apps/web run build
./scripts/smoke-compose.sh
```
````

Run:

```bash
rg -n "生产平台工程基础|smoke-compose" README.md
```

Expected: both the section heading and smoke-test command are found.

- [ ] **Step 3: Commit smoke test and documentation**

```bash
git add scripts/smoke-compose.sh README.md
git commit -m "test: add Compose smoke acceptance path"
```

## Task 9: Validate on Linux through CI

**Files:**
- Create: `.github/workflows/engineering-foundation.yml`

- [ ] **Step 1: Add the Linux quality gates**

Create `.github/workflows/engineering-foundation.yml`:

```yaml
name: Engineering foundation

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  quality:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: apps/web/package-lock.json
      - name: Install API dependencies
        run: python -m pip install -e 'apps/api[dev]'
      - name: Lint and test API
        run: |
          ruff check apps/api/src apps/api/tests
          pytest apps/api/tests -q
      - name: Install, test, and build Web
        run: |
          npm --prefix apps/web ci
          npm --prefix apps/web test
          npm --prefix apps/web run typecheck
          npm --prefix apps/web run build
      - name: Validate Compose model
        env:
          CITYPULSE_ENV_FILE: .env.example
        run: docker compose --env-file .env.example config --quiet
      - name: Run Linux container smoke test
        run: ./scripts/smoke-compose.sh
```

- [ ] **Step 2: Run every local quality gate once more**

```bash
apps/api/.venv/bin/ruff check apps/api/src apps/api/tests
apps/api/.venv/bin/pytest apps/api/tests -q
npm --prefix apps/web test
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
CITYPULSE_ENV_FILE=.env.example docker compose --env-file .env.example config --quiet
./scripts/smoke-compose.sh
git status --short
```

Expected: lint, tests, typecheck, build, Compose validation, and smoke test all pass. `git status --short` lists only intentionally uncommitted design/plan files, if those have not yet been committed.

- [ ] **Step 3: Commit Linux CI validation**

```bash
git add .github/workflows/engineering-foundation.yml
git commit -m "ci: verify engineering foundation on Linux"
```

## Final stage-1 acceptance

- [ ] `GET /health/live` succeeds without querying PostgreSQL or Redis.
- [ ] `GET /health/ready` returns `200` only when both dependencies respond and `503` otherwise.
- [ ] Every API response includes a valid `X-Request-ID`; typed errors include the same ID in JSON.
- [ ] Production-mode unsafe configuration fails validation before serving requests.
- [ ] `alembic upgrade head` is explicit and API startup does not run migrations.
- [ ] Worker and scheduler are separate processes using Redis; the deterministic worker ping responds.
- [ ] React displays loading, dependency status, failure, and version as text rather than color alone.
- [ ] The base Compose model exposes only the reverse proxy; database and Redis remain internal.
- [ ] The development overlay binds infrastructure ports to `127.0.0.1` only.
- [ ] macOS Docker Desktop smoke validation and Ubuntu CI validation both pass.
- [ ] Existing `index.html`, sample data, scoring baseline, screenshots, and competition deliverables remain byte-for-byte unchanged.

## Self-review record

- **Spec coverage:** Stage-1 React/FastAPI scaffolding, Compose services, validated configuration, migrations, health checks, logging, worker/scheduler, macOS execution, and Linux validation each map to a task above.
- **Deferred by scope:** RBAC, session persistence, CSRF, domain schemas, ingestion, prediction, action generation, backtesting, full security testing, and backup/restore belong to stages 2-5 and are not stubbed here.
- **Boundary consistency:** Health payload field names match Python response models, TypeScript types, frontend rendering, curl assertions, and readiness semantics.
- **Safety:** The smoke script validates the project-name prefix before its cleanup trap and operates on a dedicated test Compose project only.
