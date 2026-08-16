import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from citypulse.shared.orm import Base


class CalibrationReport(Base):
    __tablename__ = "calibration_reports"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    backtest_run_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), index=True)
    sample_size: Mapped[int] = mapped_column(sa.Integer())
    brier: Mapped[float] = mapped_column(sa.Float())
    ece: Mapped[float] = mapped_column(sa.Float())
    bins: Mapped[list[dict[str, Any]]] = mapped_column(sa.JSON)
    verdict: Mapped[str] = mapped_column(sa.String(32))
    created_by: Mapped[uuid.UUID] = mapped_column(sa.Uuid())
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
