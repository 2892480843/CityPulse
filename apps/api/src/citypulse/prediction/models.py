import uuid
from datetime import UTC, date, datetime
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from citypulse.shared.orm import Base

RunStatus = Literal["queued", "running", "succeeded", "failed"]


class ScoringVersion(Base):
    __tablename__ = "scoring_versions"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    version_no: Mapped[int] = mapped_column(sa.Integer(), unique=True)
    label: Mapped[str] = mapped_column(sa.String(64))
    weights: Mapped[dict[str, Any]] = mapped_column(sa.JSON)
    thresholds: Mapped[dict[str, Any]] = mapped_column(sa.JSON)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class PredictionRun(Base):
    __tablename__ = "prediction_runs"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    window_days: Mapped[int] = mapped_column(sa.Integer())
    status: Mapped[RunStatus] = mapped_column(sa.String(12), default="queued", index=True)
    scoring_version_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid())
    data_fingerprint: Mapped[str] = mapped_column(sa.String(64))
    city_count: Mapped[int] = mapped_column(sa.Integer(), default=0)
    as_of_date: Mapped[date] = mapped_column(sa.Date())
    created_by: Mapped[uuid.UUID] = mapped_column(sa.Uuid())
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(sa.Text())


class PredictionResult(Base):
    __tablename__ = "prediction_results"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("prediction_runs.id", ondelete="CASCADE"), index=True
    )
    city_code: Mapped[str] = mapped_column(sa.String(12))
    city_name: Mapped[str] = mapped_column(sa.String(64))
    province: Mapped[str] = mapped_column(sa.String(32))
    trend_rank: Mapped[int] = mapped_column(sa.Integer())
    trend_score: Mapped[float] = mapped_column(sa.Float())
    risk_pressure: Mapped[float] = mapped_column(sa.Float())
    evidence_coverage: Mapped[float] = mapped_column(sa.Float())
    action_priority: Mapped[str] = mapped_column(sa.String(12))
    data_stale: Mapped[bool] = mapped_column(default=False)
    factors: Mapped[dict[str, Any]] = mapped_column(sa.JSON)
    blockers: Mapped[list[Any]] = mapped_column(sa.JSON, default=list)

    __table_args__ = (sa.UniqueConstraint("run_id", "city_code"),)
