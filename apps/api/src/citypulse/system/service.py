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
        check_status = "ok"
    except Exception as error:
        check_status = "error"
        await logger.awarning("database_readiness_failed", error_type=type(error).__name__)
    return CheckResult(
        status=check_status,
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
    )


async def check_redis(client: Redis) -> CheckResult:
    started = time.perf_counter()
    try:
        await client.ping()
        check_status = "ok"
    except Exception as error:
        check_status = "error"
        await logger.awarning("redis_readiness_failed", error_type=type(error).__name__)
    return CheckResult(
        status=check_status,
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
    )


async def collect_readiness(
    *, engine: AsyncEngine, redis_client: Redis, version: str
) -> ReadinessResponse:
    database, redis = await asyncio.gather(
        check_database(engine),
        check_redis(redis_client),
    )
    checks = {"database": database, "redis": redis}
    overall_status = "ok" if all(check.status == "ok" for check in checks.values()) else "degraded"
    return ReadinessResponse(status=overall_status, version=version, checks=checks)
