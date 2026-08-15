import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from citypulse.audit import service as audit
from citypulse.identity.rbac import Identity, require_roles
from citypulse.ingestion import service
from citypulse.ingestion.schemas import (
    DatasetCommitResponse,
    DatasetCreateResponse,
    DatasetListResponse,
    DatasetReport,
    DatasetValidateResponse,
    DatasetView,
    ObservationListResponse,
    ObservationView,
)
from citypulse.shared.db import get_session
from citypulse.shared.errors import AppError

router = APIRouter(prefix="/api/v1/datasets", tags=["ingestion"])


def _upload_dir(request: Request) -> Path:
    return Path(request.app.state.settings.upload_dir)


def _max_rows(request: Request) -> int:
    return int(request.app.state.settings.max_csv_rows)


def _view(dataset) -> DatasetView:
    return DatasetView.model_validate(dataset)


@router.post("", response_model=DatasetCreateResponse, status_code=201)
async def upload_dataset(
    request: Request,
    response: Response,
    file: UploadFile,
    db: Annotated[AsyncSession, Depends(get_session)],
    identity: Annotated[Identity, Depends(require_roles("analyst"))],
    source_name: Annotated[str, Form(max_length=120)] = ...,
    legal_basis: Annotated[str, Form(max_length=300)] = ...,
    source_type: Annotated[str, Form(max_length=32)] = "analyst_upload",
) -> DatasetCreateResponse:
    if source_type not in ("official_sync", "analyst_upload"):
        raise AppError(
            code="INVALID_SOURCE_TYPE",
            message="source_type must be official_sync or analyst_upload.",
            status_code=400,
        )
    settings = request.app.state.settings
    content, digest, stored_filename = await service.store_upload(
        file,
        upload_dir=Path(settings.upload_dir),
        max_bytes=int(settings.max_upload_bytes),
    )
    dataset, already_exists = await service.create_dataset(
        db,
        source_type=source_type,
        source_name=source_name,
        legal_basis=legal_basis,
        original_filename=file.filename or "upload",
        stored_filename=stored_filename,
        sha256=digest,
        byte_size=len(content),
        uploaded_by=identity.user_id,
    )
    if not already_exists:
        await audit.record(
            db,
            action=audit.ACTION_DATASET_UPLOADED,
            object_type="dataset",
            object_id=str(dataset.id),
            actor_id=identity.user_id,
            actor_username=identity.username,
            detail={
                "source_name": dataset.source_name,
                "sha256": dataset.sha256[:12],
                "byte_size": dataset.byte_size,
            },
            request_id=str(getattr(request.state, "request_id", "")) or None,
        )
        await db.commit()
    if already_exists:
        response.status_code = 200
    return DatasetCreateResponse(dataset=_view(dataset), already_exists=already_exists)


@router.get("", response_model=DatasetListResponse)
async def list_datasets(
    _identity: Annotated[Identity, Depends(require_roles("admin", "analyst"))],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 50,
    offset: int = 0,
) -> DatasetListResponse:
    datasets, total = await service.list_datasets(db, limit=limit, offset=offset)
    return DatasetListResponse(items=[_view(dataset) for dataset in datasets], total=total)


@router.get("/{dataset_id}", response_model=DatasetView)
async def get_dataset(
    dataset_id: uuid.UUID,
    _identity: Annotated[Identity, Depends(require_roles("admin", "analyst"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> DatasetView:
    dataset = await service.get_dataset(db, dataset_id)
    return _view(dataset)


@router.post("/{dataset_id}/validate", response_model=DatasetValidateResponse)
async def validate_dataset(
    request: Request,
    dataset_id: uuid.UUID,
    identity: Annotated[Identity, Depends(require_roles("analyst"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> DatasetValidateResponse:
    dataset = await service.get_dataset(db, dataset_id)
    if dataset.status == "committed":
        raise AppError(
            code="DATASET_IMMUTABLE",
            message="Committed datasets are immutable; upload a new version instead.",
            status_code=409,
        )
    report = await service.validate_dataset(
        db,
        dataset,
        upload_dir=_upload_dir(request),
        max_rows=_max_rows(request),
    )
    await audit.record(
        db,
        action=audit.ACTION_DATASET_VALIDATED,
        object_type="dataset",
        object_id=str(dataset.id),
        actor_id=identity.user_id,
        actor_username=identity.username,
        detail={"valid": report.is_valid, "error_count": len(report.errors)},
        request_id=str(getattr(request.state, "request_id", "")) or None,
    )
    await db.commit()
    return DatasetValidateResponse(
        dataset=_view(dataset),
        report=DatasetReport.model_validate(report.as_dict()),
    )


@router.post("/{dataset_id}/commit", response_model=DatasetCommitResponse)
async def commit_dataset(
    request: Request,
    dataset_id: uuid.UUID,
    identity: Annotated[Identity, Depends(require_roles("analyst"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> DatasetCommitResponse:
    dataset = await service.get_dataset(db, dataset_id)
    version, already_committed = await service.commit_dataset(
        db,
        dataset,
        upload_dir=_upload_dir(request),
        max_rows=_max_rows(request),
        committed_by=identity.user_id,
    )
    if not already_committed:
        await audit.record(
            db,
            action=audit.ACTION_DATASET_COMMITTED,
            object_type="dataset",
            object_id=str(dataset.id),
            actor_id=identity.user_id,
            actor_username=identity.username,
            detail={"version_no": version.version_no, "observations": version.observation_count},
            request_id=str(getattr(request.state, "request_id", "")) or None,
        )
    await db.commit()
    return DatasetCommitResponse(
        dataset=_view(dataset),
        version_no=version.version_no,
        observation_count=version.observation_count,
        already_committed=already_committed,
    )


@router.get("/{dataset_id}/observations", response_model=ObservationListResponse)
async def list_observations(
    dataset_id: uuid.UUID,
    _identity: Annotated[Identity, Depends(require_roles("admin", "analyst"))],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 50,
) -> ObservationListResponse:
    dataset = await service.get_dataset(db, dataset_id)
    if dataset.status != "committed":
        return ObservationListResponse(items=[])
    rows = await service.observations_preview(db, dataset_id, limit=limit)
    return ObservationListResponse(items=[ObservationView.model_validate(row) for row in rows])
