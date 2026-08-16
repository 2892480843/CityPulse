from celery import shared_task


@shared_task(name="citypulse.system.ping")
def ping() -> dict[str, str]:
    return {"service": "citypulse-worker", "status": "ok"}


@shared_task(name="citypulse.system.retention")
def retention() -> dict[str, object]:
    import asyncio
    from datetime import UTC, datetime
    from pathlib import Path

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from citypulse.shared.config import get_settings
    from citypulse.system.retention import run_retention

    settings = get_settings()

    async def _run() -> dict[str, object]:
        from citypulse.shared.database import create_database_engine

        engine = create_database_engine(settings.database_url)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            result = await run_retention(
                session,
                upload_dir=Path(settings.upload_dir),
                now=datetime.now(UTC),
                audit_retention_days=settings.audit_retention_days,
                upload_retention_days=settings.upload_retention_days,
            )
        await engine.dispose()
        return result

    return asyncio.run(_run())
