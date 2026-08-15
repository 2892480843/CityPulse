import uuid
from datetime import UTC, datetime
from typing import Literal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from citypulse.shared.orm import Base

JobStatus = Literal["queued", "running", "succeeded", "failed"]
JobType = Literal["prediction_run", "backtest_run", "action_generation"]


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    job_type: Mapped[JobType] = mapped_column(sa.String(32), index=True)
    status: Mapped[JobStatus] = mapped_column(sa.String(12), default="queued", index=True)
    ref_type: Mapped[str | None] = mapped_column(sa.String(32))
    ref_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid())
    summary: Mapped[str | None] = mapped_column(sa.String(300))
    error: Mapped[str | None] = mapped_column(sa.Text())
    created_by: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid())
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
