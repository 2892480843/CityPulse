import csv
import hashlib
import io
import uuid
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from citypulse.city_catalog.service import known_city_codes
from citypulse.ingestion.contract import (
    ValidationReport,
    validate_observations,
)
from citypulse.ingestion.models import Dataset, DatasetVersion, SignalObservation
from citypulse.shared.errors import AppError

ALLOWED_EXTENSIONS = frozenset({".csv", ".xlsx"})
CSV_SNIFF_LIMIT = 8192


class IngestionServiceError(AppError):
    pass


def _reject_upload(filename: str | None, content_type: str | None) -> None:
    if not filename:
        raise IngestionServiceError(
            code="MISSING_FILENAME", message="The upload has no filename.", status_code=400
        )
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise IngestionServiceError(
            code="UNSUPPORTED_FORMAT",
            message="Only .csv and .xlsx uploads are accepted.",
            status_code=400,
        )
    declared = (content_type or "").lower()
    if declared and declared not in {
        "text/csv",
        "application/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
    }:
        raise IngestionServiceError(
            code="UNSUPPORTED_FORMAT",
            message="The declared content type is not accepted.",
            status_code=400,
        )


async def store_upload(
    upload: UploadFile,
    *,
    upload_dir: Path,
    max_bytes: int,
) -> tuple[bytes, str, str]:
    _reject_upload(upload.filename, upload.content_type)
    content = await upload.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise IngestionServiceError(
            code="FILE_TOO_LARGE",
            message="The file exceeds the configured upload size limit.",
            status_code=413,
        )
    if not content:
        raise IngestionServiceError(
            code="EMPTY_FILE", message="The uploaded file is empty.", status_code=400
        )
    extension = Path(upload.filename or "").suffix.lower()
    if extension == ".csv":
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise IngestionServiceError(
                code="ENCODING_ERROR",
                message="CSV uploads must be UTF-8 encoded.",
                status_code=400,
            ) from error
    elif not content.startswith(b"PK\x03\x04"):
        raise IngestionServiceError(
            code="UNSUPPORTED_FORMAT",
            message="The file signature does not match an .xlsx workbook.",
            status_code=400,
        )

    digest = hashlib.sha256(content).hexdigest()
    stored_filename = f"{uuid.uuid4().hex}{extension}"
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / stored_filename).write_bytes(content)
    return content, digest, stored_filename


def _read_rows(
    content: bytes, stored_filename: str, *, max_rows: int
) -> list[dict[str, str | None]]:
    if stored_filename.endswith(".csv"):
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        rows: list[dict[str, str | None]] = []
        for row in reader:
            if len(rows) >= max_rows:
                raise IngestionServiceError(
                    code="TOO_MANY_ROWS",
                    message=f"Uploads may contain at most {max_rows} data rows.",
                    status_code=400,
                )
            rows.append({(key or "").strip(): value for key, value in row.items()})
        return rows

    import openpyxl

    workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        worksheet = workbook.worksheets[0]
        rows = []
        header: list[str] | None = None
        for raw_row in worksheet.iter_rows(values_only=True):
            values = ["" if cell is None else str(cell) for cell in raw_row]
            if header is None:
                if not any(values):
                    continue
                header = [value.strip() for value in values]
                continue
            if not any(values):
                continue
            if len(rows) >= max_rows:
                raise IngestionServiceError(
                    code="TOO_MANY_ROWS",
                    message=f"Uploads may contain at most {max_rows} data rows.",
                    status_code=400,
                )
            padded = values + [""] * (len(header) - len(values))
            rows.append({name: padded[index] for index, name in enumerate(header)})
        return rows
    finally:
        workbook.close()


async def get_dataset(db: AsyncSession, dataset_id: uuid.UUID) -> Dataset:
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if dataset is None:
        raise IngestionServiceError(
            code="DATASET_NOT_FOUND", message="The dataset does not exist.", status_code=404
        )
    return dataset


async def create_dataset(
    db: AsyncSession,
    *,
    source_type: str,
    source_name: str,
    legal_basis: str,
    original_filename: str,
    stored_filename: str,
    sha256: str,
    byte_size: int,
    uploaded_by: uuid.UUID,
) -> tuple[Dataset, bool]:
    result = await db.execute(select(Dataset).where(Dataset.sha256 == sha256))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing, True
    dataset = Dataset(
        source_type=source_type,  # type: ignore[arg-type]
        source_name=source_name,
        legal_basis=legal_basis,
        original_filename=original_filename,
        stored_filename=stored_filename,
        sha256=sha256,
        byte_size=byte_size,
        uploaded_by=uploaded_by,
    )
    db.add(dataset)
    await db.flush()
    return dataset, False


async def validate_dataset(
    db: AsyncSession,
    dataset: Dataset,
    *,
    upload_dir: Path,
    max_rows: int,
) -> ValidationReport:
    content = (upload_dir / dataset.stored_filename).read_bytes()
    rows = _read_rows(content, dataset.stored_filename, max_rows=max_rows)
    codes = await known_city_codes(db)
    observations, report = validate_observations(rows, known_city_codes=codes)
    dataset.status = "valid" if report.is_valid else "invalid"
    dataset.report = report.as_dict()
    dataset.validated_at = datetime.now(UTC)
    await db.flush()
    return report


def _next_version_no(existing: list[DatasetVersion]) -> int:
    return max((version.version_no for version in existing), default=0) + 1


async def commit_dataset(
    db: AsyncSession,
    dataset: Dataset,
    *,
    upload_dir: Path,
    max_rows: int,
    committed_by: uuid.UUID,
) -> tuple[DatasetVersion, bool]:
    result = await db.execute(
        select(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id)
    )
    versions = list(result.scalars())
    if dataset.status == "committed" and versions:
        return versions[0], True

    if dataset.status != "valid":
        raise IngestionServiceError(
            code="DATASET_NOT_VALID",
            message="Only datasets that passed validation can be committed.",
            status_code=409,
        )

    content = (upload_dir / dataset.stored_filename).read_bytes()
    rows = _read_rows(content, dataset.stored_filename, max_rows=max_rows)
    codes = await known_city_codes(db)
    observations, report = validate_observations(rows, known_city_codes=codes)
    if not report.is_valid:
        dataset.status = "invalid"
        dataset.report = report.as_dict()
        await db.flush()
        raise IngestionServiceError(
            code="VALIDATION_FAILED",
            message="The dataset no longer passes validation; rerun validation first.",
            status_code=409,
        )

    version = DatasetVersion(
        dataset_id=dataset.id,
        version_no=_next_version_no(versions),
        committed_by=committed_by,
        observation_count=len(observations),
    )
    db.add(version)
    await db.flush()

    db.add_all(
        SignalObservation(
            dataset_version_id=version.id,
            city_code=observation.city_code,
            metric_date=observation.metric_date,
            metric_name=observation.metric_name,
            value=observation.value,
            source_url=observation.source_url,
            published_at=observation.published_at,
            observed_at=observation.observed_at,
            available_at=observation.available_at,
        )
        for observation in observations
    )
    dataset.status = "committed"
    dataset.committed_at = version.committed_at
    await db.flush()
    return version, False


async def list_datasets(
    db: AsyncSession, *, limit: int = 50, offset: int = 0
) -> tuple[list[Dataset], int]:
    result = await db.execute(
        select(Dataset).order_by(sa.desc(Dataset.created_at)).offset(offset).limit(limit)
    )
    datasets = list(result.scalars())
    total_result = await db.execute(select(sa.func.count()).select_from(Dataset))
    return datasets, total_result.scalar_one()


async def observations_preview(
    db: AsyncSession, dataset_id: uuid.UUID, *, limit: int = 50
) -> list[SignalObservation]:
    result = await db.execute(
        select(SignalObservation)
        .join(DatasetVersion, SignalObservation.dataset_version_id == DatasetVersion.id)
        .where(DatasetVersion.dataset_id == dataset_id)
        .order_by(SignalObservation.city_code, SignalObservation.metric_date)
        .limit(limit)
    )
    return list(result.scalars())
