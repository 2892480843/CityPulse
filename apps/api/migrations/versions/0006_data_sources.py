"""Data source registry for official open API sync adapters."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_data_sources"
down_revision: str | None = "0005_momentum"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False, unique=True),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("source_url", sa.String(300), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(16), nullable=True),
        sa.Column("last_summary", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("data_sources")
