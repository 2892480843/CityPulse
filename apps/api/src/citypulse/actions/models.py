import uuid
from datetime import UTC, date, datetime
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from citypulse.shared.orm import Base

PlanStatus = Literal["draft", "pending_review", "approved", "rejected", "archived"]
GeneratorType = Literal["rule_fallback", "deepseek"]


class ActionPlan(Base):
    __tablename__ = "action_plans"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    prediction_result_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), index=True)
    city_code: Mapped[str] = mapped_column(sa.String(12))
    city_name: Mapped[str] = mapped_column(sa.String(64))
    status: Mapped[PlanStatus] = mapped_column(sa.String(16), default="draft", index=True)
    generator_type: Mapped[GeneratorType] = mapped_column(sa.String(16))
    generation_note: Mapped[str | None] = mapped_column(sa.String(300))
    target_segment: Mapped[str] = mapped_column(sa.String(120), default="")
    action_window_start: Mapped[date | None] = mapped_column(sa.Date())
    action_window_end: Mapped[date | None] = mapped_column(sa.Date())
    product_bundle: Mapped[list[dict[str, Any]]] = mapped_column(sa.JSON, default=list)
    campaign_theme: Mapped[str] = mapped_column(sa.String(300), default="")
    supply_actions: Mapped[list[str]] = mapped_column(sa.JSON, default=list)
    assumptions: Mapped[list[str]] = mapped_column(sa.JSON, default=list)
    risk_notes: Mapped[str] = mapped_column(sa.Text(), default="")
    created_by: Mapped[uuid.UUID] = mapped_column(sa.Uuid())
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid())
    reviewed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    review_comment: Mapped[str | None] = mapped_column(sa.String(300))
