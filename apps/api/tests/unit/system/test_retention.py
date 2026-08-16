import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from citypulse.audit.models import AuditLog
from citypulse.ingestion.models import Dataset
from citypulse.shared.orm import Base
from citypulse.system.retention import run_retention


@pytest.fixture
async def retention_db(tmp_path: Path) -> async_sessionmaker:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'retention.db'}"
    sync_engine = sa.create_engine(database_url.replace("+aiosqlite", ""))
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()

    engine = create_async_engine(database_url)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


async def test_retention_removes_expired_audit_rows_and_files(
    retention_db: async_sessionmaker, tmp_path: Path
) -> None:
    now = datetime.now(UTC)

    stale_file = tmp_path / "stale.csv"
    stale_file.write_text("old")
    fresh_file = tmp_path / "fresh.csv"
    fresh_file.write_text("new")

    async with retention_db() as db:
        db.add(
            AuditLog(
                action="login_failed",
                object_type="user",
                created_at=now - timedelta(days=400),
            )
        )
        db.add(
            AuditLog(
                action="login_succeeded",
                object_type="user",
                created_at=now - timedelta(days=1),
            )
        )
        db.add(
            Dataset(
                source_type="analyst_upload",
                source_name="旧数据集",
                legal_basis="公开",
                original_filename="a.csv",
                stored_filename="stale.csv",
                sha256=uuid.uuid4().hex,
                byte_size=3,
                status="committed",
                created_at=now - timedelta(days=120),
            )
        )
        db.add(
            Dataset(
                source_type="analyst_upload",
                source_name="新数据集",
                legal_basis="公开",
                original_filename="b.csv",
                stored_filename="fresh.csv",
                sha256=uuid.uuid4().hex,
                byte_size=3,
                status="committed",
                created_at=now - timedelta(days=5),
            )
        )
        await db.commit()

    async with retention_db() as db:
        result = await run_retention(
            db,
            upload_dir=tmp_path,
            now=now,
            audit_retention_days=365,
            upload_retention_days=90,
        )

    assert result["audit_rows_deleted"] == 1
    assert result["upload_files_removed"] == 1
    assert result["removed_files"] == ["stale.csv"]
    assert not stale_file.exists()
    assert fresh_file.exists()

    async with retention_db() as db:
        datasets = list((await db.execute(sa.select(Dataset))).scalars())
        assert len(datasets) == 2  # metadata survives file cleanup
        logs = list((await db.execute(sa.select(AuditLog))).scalars())
        assert len(logs) == 1
        assert logs[0].action == "login_succeeded"
