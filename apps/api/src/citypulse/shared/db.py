from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from citypulse.shared.errors import AppError


def create_database_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


def create_sqlite_test_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    maker: async_sessionmaker[AsyncSession] | None = getattr(
        request.app.state, "sessionmaker", None
    )
    if maker is None:
        raise AppError(
            code="DATABASE_UNAVAILABLE",
            message="The database session factory is not configured.",
            status_code=503,
        )
    async with maker() as session:
        yield session
