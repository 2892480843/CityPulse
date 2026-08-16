import uuid
from datetime import UTC, datetime
from typing import Literal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from citypulse.shared.orm import Base

SourceKind = Literal["admin_divisions", "open_meteo_weather"]


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    kind: Mapped[SourceKind] = mapped_column(sa.String(32), unique=True)
    label: Mapped[str] = mapped_column(sa.String(120))
    source_url: Mapped[str] = mapped_column(sa.String(300))
    is_enabled: Mapped[bool] = mapped_column(default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(sa.String(16))
    last_summary: Mapped[str | None] = mapped_column(sa.String(300))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
