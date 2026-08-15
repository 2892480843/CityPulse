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
        response_status_code = 500

        try:
            response = await call_next(request)
            response_status_code = response.status_code
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            await logger.ainfo(
                "http_request",
                method=request.method,
                path=request.url.path,
                status_code=response_status_code,
                duration_ms=duration_ms,
            )

        response.headers["X-Request-ID"] = request_id
        return response
