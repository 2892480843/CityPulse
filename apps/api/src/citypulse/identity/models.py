import uuid
from datetime import UTC, datetime
from typing import Literal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from citypulse.shared.orm import Base

RoleName = Literal["admin", "analyst", "operator"]
ROLE_NAMES: tuple[RoleName, ...] = ("admin", "analyst", "operator")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[RoleName] = mapped_column(sa.String(16), unique=True)
    description: Mapped[str] = mapped_column(sa.String(200), default="")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(sa.String(32), unique=True)
    password_hash: Mapped[str] = mapped_column(sa.String(256))
    display_name: Mapped[str] = mapped_column(sa.String(64))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    roles: Mapped[list[Role]] = relationship(
        secondary="user_roles", lazy="selectin", order_by=Role.name
    )


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(
        sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    csrf_token: Mapped[str] = mapped_column(sa.String(64))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    user: Mapped[User] = relationship(lazy="joined")
