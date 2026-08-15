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
