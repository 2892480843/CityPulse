import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from citypulse.jobs.models import Job, JobStatus, JobType


async def record_job(
    db: AsyncSession,
    *,
    job_type: JobType,
    status: JobStatus,
    created_by: uuid.UUID | None = None,
    ref_type: str | None = None,
    ref_id: uuid.UUID | None = None,
    summary: str | None = None,
    error: str | None = None,
) -> Job:
    job = Job(
        job_type=job_type,
        status=status,
        created_by=created_by,
        ref_type=ref_type,
        ref_id=ref_id,
        summary=summary,
        error=error,
        finished_at=datetime.now(UTC) if status in ("succeeded", "failed") else None,
    )
    db.add(job)
    await db.flush()
    return job


async def list_jobs(db: AsyncSession, *, limit: int = 50) -> list[Job]:
    result = await db.execute(select(Job).order_by(sa.desc(Job.created_at)).limit(limit))
    return list(result.scalars())
