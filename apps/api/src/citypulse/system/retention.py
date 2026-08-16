"""Retention cleanup for audit rows and expired raw upload files.

Only expired rows/files are removed; committed observations and dataset
metadata stay intact, and every run records what it deleted.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from citypulse.audit.models import AuditLog
from citypulse.ingestion.models import Dataset


async def run_retention(
    db: AsyncSession,
    *,
    upload_dir: Path,
    now: datetime,
    audit_retention_days: int,
    upload_retention_days: int,
) -> dict[str, object]:
    audit_cutoff = now - timedelta(days=audit_retention_days)
    audit_result = await db.execute(
        sa.delete(AuditLog).where(AuditLog.created_at < audit_cutoff)
    )
    audit_deleted = audit_result.rowcount or 0

    upload_cutoff = now - timedelta(days=upload_retention_days)
    datasets = (
        await db.execute(
            select(Dataset).where(
                Dataset.status == "committed",
                Dataset.created_at < upload_cutoff,
                Dataset.stored_filename.is_not(None),
            )
        )
    ).scalars().all()

    files_removed: list[str] = []
    for dataset in datasets:
        path = upload_dir / dataset.stored_filename
        if path.is_file():
            path.unlink()
            files_removed.append(dataset.stored_filename)

    await db.commit()
    return {
        "audit_rows_deleted": audit_deleted,
        "upload_files_removed": len(files_removed),
        "removed_files": files_removed,
        "audit_cutoff": audit_cutoff.isoformat(),
        "upload_cutoff": upload_cutoff.isoformat(),
        "ran_at": datetime.now(UTC).isoformat(),
    }
