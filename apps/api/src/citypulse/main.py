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
