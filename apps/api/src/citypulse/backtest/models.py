import uuid
from datetime import UTC, date, datetime
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from citypulse.shared.orm import Base

BacktestStatus = Literal["queued", "running", "succeeded", "failed"]


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    t0: Mapped[date] = mapped_column(sa.Date())
    cutoff_offsets: Mapped[list[int]] = mapped_column(sa.JSON)
    window_days: Mapped[int] = mapped_column(sa.Integer(), default=14)
    target_city_codes: Mapped[list[str]] = mapped_column(sa.JSON)
    control_city_codes: Mapped[list[str]] = mapped_column(sa.JSON)
    status: Mapped[BacktestStatus] = mapped_column(sa.String(12), default="queued", index=True)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON)
    error: Mapped[str | None] = mapped_column(sa.Text())
    created_by: Mapped[uuid.UUID] = mapped_column(sa.Uuid())
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
