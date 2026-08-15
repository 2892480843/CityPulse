import uuid
from datetime import UTC, date, datetime
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from citypulse.shared.orm import Base

DatasetStatus = Literal["uploaded", "validating", "valid", "invalid", "committed", "archived"]
SourceType = Literal["official_sync", "analyst_upload"]


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    source_type: Mapped[SourceType] = mapped_column(sa.String(32))
    source_name: Mapped[str] = mapped_column(sa.String(120))
    legal_basis: Mapped[str] = mapped_column(sa.String(300))
    original_filename: Mapped[str] = mapped_column(sa.String(255))
    stored_filename: Mapped[str] = mapped_column(sa.String(64), unique=True)
    sha256: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True)
    byte_size: Mapped[int] = mapped_column(sa.Integer)
    status: Mapped[DatasetStatus] = mapped_column(sa.String(16), default="uploaded", index=True)
    report: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid())
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    validated_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    committed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("datasets.id", ondelete="RESTRICT"), index=True
    )
    version_no: Mapped[int] = mapped_column(sa.Integer)
    committed_by: Mapped[uuid.UUID] = mapped_column(sa.Uuid())
    committed_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    observation_count: Mapped[int] = mapped_column(sa.Integer, default=0)

    __table_args__ = (sa.UniqueConstraint("dataset_id", "version_no"),)


class SignalObservation(Base):
    __tablename__ = "signal_observations"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"), index=True
    )
    city_code: Mapped[str] = mapped_column(sa.String(12))
    metric_date: Mapped[date] = mapped_column(sa.Date)
    metric_name: Mapped[str] = mapped_column(sa.String(48))
    value: Mapped[float] = mapped_column(sa.Float)
    source_url: Mapped[str | None] = mapped_column(sa.String(500))
    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    observed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint(
            "dataset_version_id",
            "city_code",
            "metric_date",
            "metric_name",
        ),
    )
