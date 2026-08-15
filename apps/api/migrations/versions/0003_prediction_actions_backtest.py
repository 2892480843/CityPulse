"""Prediction runs, action plans, backtests, jobs, and scoring versions."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0003_prediction"
down_revision: str | None = "0002_identity_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TREND_WEIGHTS = {
    "content_growth": 0.22,
    "search_growth": 0.18,
    "event_trigger": 0.12,
    "accessibility": 0.12,
    "supply_capacity": 0.10,
    "weather_fit": 0.08,
    "novelty": 0.08,
    "cross_region_spread": 0.10,
}


def upgrade() -> None:
    op.create_table(
        "scoring_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("version_no", sa.Integer(), nullable=False, unique=True),
        sa.Column("label", sa.String(64), nullable=False),
        sa.Column("weights", sa.JSON(), nullable=False),
        sa.Column("thresholds", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_type", sa.String(32), nullable=False, index=True),
        sa.Column("status", sa.String(12), nullable=False, index=True),
        sa.Column("ref_type", sa.String(32), nullable=True),
        sa.Column("ref_id", sa.Uuid(), nullable=True),
        sa.Column("summary", sa.String(300), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "prediction_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, index=True),
        sa.Column("scoring_version_id", sa.Uuid(), nullable=False),
        sa.Column("data_fingerprint", sa.String(64), nullable=False),
        sa.Column("city_count", sa.Integer(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_table(
        "prediction_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Uuid(),
            sa.ForeignKey("prediction_runs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("city_code", sa.String(12), nullable=False),
        sa.Column("city_name", sa.String(64), nullable=False),
        sa.Column("province", sa.String(32), nullable=False),
        sa.Column("trend_rank", sa.Integer(), nullable=False),
        sa.Column("trend_score", sa.Float(), nullable=False),
        sa.Column("risk_pressure", sa.Float(), nullable=False),
        sa.Column("evidence_coverage", sa.Float(), nullable=False),
        sa.Column("action_priority", sa.String(12), nullable=False),
        sa.Column("data_stale", sa.Boolean(), nullable=False),
        sa.Column("factors", sa.JSON(), nullable=False),
        sa.Column("blockers", sa.JSON(), nullable=False),
        sa.UniqueConstraint("run_id", "city_code"),
    )
    op.create_table(
        "action_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("prediction_result_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("run_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("city_code", sa.String(12), nullable=False),
        sa.Column("city_name", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, index=True),
        sa.Column("generator_type", sa.String(16), nullable=False),
        sa.Column("generation_note", sa.String(300), nullable=True),
        sa.Column("target_segment", sa.String(120), nullable=False),
        sa.Column("action_window_start", sa.Date(), nullable=True),
        sa.Column("action_window_end", sa.Date(), nullable=True),
        sa.Column("product_bundle", sa.JSON(), nullable=False),
        sa.Column("campaign_theme", sa.String(300), nullable=False),
        sa.Column("supply_actions", sa.JSON(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("risk_notes", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_comment", sa.String(300), nullable=True),
    )
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("t0", sa.Date(), nullable=False),
        sa.Column("cutoff_offsets", sa.JSON(), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("target_city_codes", sa.JSON(), nullable=False),
        sa.Column("control_city_codes", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, index=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    scoring_table = sa.table(
        "scoring_versions",
        sa.column("id", sa.Uuid),
        sa.column("version_no", sa.Integer),
        sa.column("label", sa.String),
        sa.column("weights", sa.JSON),
        sa.column("thresholds", sa.JSON),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        scoring_table,
        [
            {
                "id": uuid.uuid5(uuid.NAMESPACE_OID, "citypulse-scoring-v1"),
                "version_no": 1,
                "created_at": datetime.now(UTC),
                "label": "transparent-baseline-v1",
                "weights": {**TREND_WEIGHTS, "risk_weight": 0.15},
                "thresholds": {
                    "action": 68.0,
                    "watch": 58.0,
                    "blocked_risk": 80.0,
                    "evidence_publish": 0.5,
                },
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("backtest_runs")
    op.drop_table("action_plans")
    op.drop_table("prediction_results")
    op.drop_table("prediction_runs")
    op.drop_table("jobs")
    op.drop_table("scoring_versions")
