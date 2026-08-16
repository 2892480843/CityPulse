"""Momentum and acceleration columns on prediction results."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_momentum"
down_revision: str | None = "0004_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "prediction_results",
        sa.Column("momentum", sa.Float(), nullable=True),
    )
    op.add_column(
        "prediction_results",
        sa.Column("accelerating", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("prediction_results", "accelerating")
    op.drop_column("prediction_results", "momentum")
