from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from citypulse.actions.router import router as actions_router
from citypulse.backtest.router import router as backtest_router
from citypulse.calibration.router import router as calibration_router
from citypulse.city_catalog.router import router as city_catalog_router
from citypulse.evidence.router import router as evidence_router
from citypulse.identity.ratelimit import LoginRateLimiter
from citypulse.identity.router import admin_router as identity_admin_router
from citypulse.identity.router import router as identity_router
from citypulse.ingestion.router import router as ingestion_router
from citypulse.jobs.router import router as jobs_router
from citypulse.prediction.router import city_router as prediction_city_router
from citypulse.prediction.router import router as prediction_router
from citypulse.shared.config import get_settings
from citypulse.shared.database import create_database_engine
from citypulse.shared.db import create_database_sessionmaker
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
    app.state.sessionmaker = create_database_sessionmaker(app.state.database_engine)
    app.state.redis_client = create_redis_client(settings.redis_url)
    app.state.login_rate_limiter = LoginRateLimiter()
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
    app.include_router(identity_router)
    app.include_router(identity_admin_router)
    app.include_router(city_catalog_router)
    app.include_router(ingestion_router)
    app.include_router(prediction_router)
    app.include_router(prediction_city_router)
    app.include_router(actions_router)
    app.include_router(backtest_router)
    app.include_router(jobs_router)
    app.include_router(calibration_router)
    app.include_router(evidence_router)
    return app


app = create_app()
