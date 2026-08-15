"""Identity, audit, city catalog, and ingestion tables with seed data."""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_identity_data"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEED_ROLES = [
    ("admin", "Manage users, data sources, configuration, and audit logs"),
    ("analyst", "Govern data, features, predictions, and backtests"),
    ("operator", "Review candidate cities and manage action plans"),
]

SEED_CITIES = [
    ("230100", "哈尔滨", "黑龙江"),
    ("140200", "大同", "山西"),
    ("222401", "延吉", "吉林"),
    ("331000", "台州", "浙江"),
    ("350500", "泉州", "福建"),
    ("360302", "景德镇", "江西"),
    ("410200", "开封", "河南"),
    ("450200", "柳州", "广西"),
    ("511500", "宜宾", "四川"),
    ("520300", "遵义", "贵州"),
    ("533103", "芒市", "云南"),
    ("370300", "淄博", "山东"),
    ("620500", "天水", "甘肃"),
]


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(16), nullable=False, unique=True),
        sa.Column("description", sa.String(200), nullable=False, server_default=""),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("username", sa.String(32), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("display_name", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "user_roles",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "role_id",
            sa.Integer(),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True, index=True),
        sa.Column("actor_username", sa.String(32), nullable=True),
        sa.Column("action", sa.String(64), nullable=False, index=True),
        sa.Column("object_type", sa.String(32), nullable=False),
        sa.Column("object_id", sa.String(64), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
    )
    op.create_table(
        "cities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(12), nullable=False, unique=True),
        sa.Column("name", sa.String(64), nullable=False, index=True),
        sa.Column("province", sa.String(32), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
    )
    op.create_table(
        "city_aliases",
        sa.Column(
            "city_id",
            sa.Uuid(),
            sa.ForeignKey("cities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("alias", sa.String(64), primary_key=True),
    )
    op.create_table(
        "datasets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_name", sa.String(120), nullable=False),
        sa.Column("legal_basis", sa.String(300), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(64), nullable=False, unique=True),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, index=True),
        sa.Column("report", sa.JSON(), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "dataset_id",
            sa.Uuid(),
            sa.ForeignKey("datasets.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("committed_by", sa.Uuid(), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        sa.UniqueConstraint("dataset_id", "version_no"),
    )
    op.create_table(
        "signal_observations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "dataset_version_id",
            sa.Uuid(),
            sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("city_code", sa.String(12), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("metric_name", sa.String(48), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "dataset_version_id",
            "city_code",
            "metric_date",
            "metric_name",
        ),
    )

    roles_table = sa.table(
        "roles", sa.column("name", sa.String), sa.column("description", sa.String)
    )
    op.bulk_insert(roles_table, [{"name": name, "description": desc} for name, desc in SEED_ROLES])

    cities_table = sa.table(
        "cities",
        sa.column("id", sa.Uuid),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("province", sa.String),
    )
    op.bulk_insert(
        cities_table,
        [
            {
                "id": uuid.uuid5(uuid.NAMESPACE_OID, f"citypulse-city-{code}"),
                "code": code,
                "name": name,
                "province": province,
            }
            for code, name, province in SEED_CITIES
        ],
    )


def downgrade() -> None:
    op.drop_table("signal_observations")
    op.drop_table("dataset_versions")
    op.drop_table("datasets")
    op.drop_table("city_aliases")
    op.drop_table("cities")
    op.drop_table("audit_logs")
    op.drop_table("auth_sessions")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("roles")
