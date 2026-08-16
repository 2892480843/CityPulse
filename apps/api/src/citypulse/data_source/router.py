import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from citypulse.audit import service as audit
from citypulse.data_source.models import DataSource
from citypulse.data_source.sync import ensure_sources_seeded, run_sync
from citypulse.identity.rbac import Identity, require_roles
from citypulse.jobs.service import record_job
from citypulse.shared.db import get_session

router = APIRouter(prefix="/api/v1/data-sources", tags=["data-sources"])


class DataSourceView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: Literal["admin_divisions", "open_meteo_weather"]
    label: str
    source_url: str
    is_enabled: bool
    last_synced_at: datetime | None
    last_status: str | None
    last_summary: str | None
    created_at: datetime


class DataSourceListResponse(BaseModel):
    items: list[DataSourceView]
    total: int


class SyncResponse(BaseModel):
    source: DataSourceView
    result: dict[str, object]


def _view(source: DataSource) -> DataSourceView:
    return DataSourceView.model_validate(source)


@router.get("", response_model=DataSourceListResponse)
async def list_sources(
    identity: Annotated[Identity, Depends(require_roles("admin", "analyst"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> DataSourceListResponse:
    sources = await ensure_sources_seeded(db)
    await db.commit()
    items = [_view(source) for source in sources]
    return DataSourceListResponse(items=items, total=len(items))


@router.post("/{source_id}/sync", response_model=SyncResponse)
async def sync_source(
    request: Request,
    source_id: uuid.UUID,
    identity: Annotated[Identity, Depends(require_roles("analyst"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> SyncResponse:
    sources = {source.id: source for source in await ensure_sources_seeded(db)}
    source = sources.get(source_id)
    if source is None:
        from citypulse.shared.errors import AppError

        raise AppError(
            code="SOURCE_NOT_FOUND", message="The data source does not exist.", status_code=404
        )
    if not source.is_enabled:
        raise AppError(
            code="SOURCE_DISABLED", message="The data source is disabled.", status_code=409
        )

    settings = request.app.state.settings
    try:
        result = await run_sync(
            db,
            source,
            snapshot_dir=Path(settings.official_data_dir),
            upload_dir=Path(settings.upload_dir),
        )
    except Exception as error:
        from datetime import UTC

        from citypulse.shared.errors import AppError

        source.last_synced_at = datetime.now(UTC)
        source.last_status = "failed"
        source.last_summary = str(error)[:300]
        await record_job(
            db,
            job_type="source_sync",
            status="failed",
            created_by=identity.user_id,
            summary=f"source_sync {source.kind}",
            error=str(error)[:500],
        )
        await db.commit()
        if isinstance(error, AppError):
            raise
        raise

    await record_job(
        db,
        job_type="source_sync",
        status="succeeded",
        created_by=identity.user_id,
        ref_type="data_source",
        ref_id=source.id,
        summary=f"source_sync {source.kind}: {source.last_summary}",
    )
    await audit.record(
        db,
        action="data_source_synced",
        object_type="data_source",
        object_id=str(source.id),
        actor_id=identity.user_id,
        actor_username=identity.username,
        detail={"kind": source.kind},
    )
    await db.commit()
    return SyncResponse(source=_view(source), result=result)  # type: ignore[arg-type]
