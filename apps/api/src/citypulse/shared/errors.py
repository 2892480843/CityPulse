from typing import Any

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
