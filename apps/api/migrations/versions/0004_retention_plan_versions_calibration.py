"""Action plan versions, calibration reports, and audit retention index."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_hardening"
down_revision: str | None = "0003_prediction"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "action_plan_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "plan_id",
            sa.Uuid(),
            sa.ForeignKey("action_plans.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("event", sa.String(24), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("plan_id", "version_no"),
    )
    op.create_table(
        "calibration_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("backtest_run_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("brier", sa.Float(), nullable=False),
        sa.Column("ece", sa.Float(), nullable=False),
        sa.Column("bins", sa.JSON(), nullable=False),
        sa.Column("verdict", sa.String(32), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_audit_logs_created_at_retention",
        "audit_logs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at_retention", table_name="audit_logs")
    op.drop_table("calibration_reports")
    op.drop_table("action_plan_versions")
