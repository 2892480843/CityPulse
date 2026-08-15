import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from citypulse.shared.orm import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid(), index=True)
    actor_username: Mapped[str | None] = mapped_column(sa.String(32))
    action: Mapped[str] = mapped_column(sa.String(64), index=True)
    object_type: Mapped[str] = mapped_column(sa.String(32))
    object_id: Mapped[str | None] = mapped_column(sa.String(64))
    detail: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON)
    request_id: Mapped[str | None] = mapped_column(sa.String(64))
    ip_address: Mapped[str | None] = mapped_column(sa.String(64))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )
