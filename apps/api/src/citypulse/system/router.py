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
