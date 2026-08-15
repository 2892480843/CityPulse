import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from citypulse.identity.models import AuthSession, Role, RoleName, User
from citypulse.identity.password import hash_password, verify_password
from citypulse.identity.session import (
    SESSION_ABSOLUTE_TIMEOUT,
    SESSION_TOUCH_INTERVAL,
    SessionExpiry,
    as_utc,
    hash_session_token,
    is_session_expired,
    new_csrf_token,
    new_session_token,
)
from citypulse.shared.errors import AppError


class IdentityServiceError(AppError):
    def __init__(self, *, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(code=code, message=message, status_code=status_code)


async def ensure_roles_seeded(db: AsyncSession) -> dict[str, Role]:
    result = await db.execute(select(Role))
    roles = {role.name: role for role in result.scalars()}
    missing = [
        Role(name=name, description=description)
        for name, description in (
            ("admin", "Manage users, data sources, configuration, and audit logs"),
            ("analyst", "Govern data, features, predictions, and backtests"),
            ("operator", "Review candidate cities and manage action plans"),
        )
        if name not in roles
    ]
    if missing:
        db.add_all(missing)
        await db.flush()
        roles.update({role.name: role for role in missing})
    return roles


def user_role_names(user: User) -> list[RoleName]:
    return [role.name for role in user.roles]


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles))
        .where(sa.func.lower(User.username) == username.lower())
    )
    return result.scalar_one_or_none()


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise IdentityServiceError(
            code="USER_NOT_FOUND", message="The user does not exist.", status_code=404
        )
    return user


async def create_user(
    db: AsyncSession,
    *,
    username: str,
    password: str,
    display_name: str,
    roles: list[RoleName],
) -> User:
    from citypulse.identity.password import validate_password_policy

    if await get_user_by_username(db, username) is not None:
        raise IdentityServiceError(code="USERNAME_TAKEN", message="The username already exists.")
    validate_password_policy(password, username=username)
    role_map = await ensure_roles_seeded(db)
    user = User(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name,
        roles=[role_map[name] for name in sorted(set(roles))],
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def update_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    display_name: str | None = None,
    is_active: bool | None = None,
    roles: list[RoleName] | None = None,
) -> User:
    user = await get_user(db, user_id)
    if display_name is not None:
        user.display_name = display_name
    if roles is not None:
        role_map = await ensure_roles_seeded(db)
        user.roles = [role_map[name] for name in sorted(set(roles))]
    if is_active is not None and is_active != user.is_active:
        if not is_active:
            await revoke_user_sessions(db, user_id)
        user.is_active = is_active
    await db.flush()
    await db.refresh(user)
    return user


async def list_users(db: AsyncSession) -> list[User]:
    result = await db.execute(
        select(User).options(selectinload(User.roles)).order_by(User.created_at)
    )
    return list(result.scalars())


async def authenticate(
    db: AsyncSession, *, username: str, password: str, now: datetime
) -> User | None:
    user = await get_user_by_username(db, username)
    if user is None or not user.is_active:
        return None
    if not verify_password(user.password_hash, password):
        return None
    user.last_login_at = now
    await db.flush()
    return user


async def create_session(
    db: AsyncSession, *, user_id: uuid.UUID, now: datetime
) -> tuple[str, AuthSession]:
    token = new_session_token()
    session = AuthSession(
        id=hash_session_token(token),
        user_id=user_id,
        csrf_token=new_csrf_token(),
        created_at=now,
        last_seen_at=now,
        expires_at=now + SESSION_ABSOLUTE_TIMEOUT,
    )
    db.add(session)
    await db.flush()
    return token, session


async def load_active_session(
    db: AsyncSession, *, token: str, now: datetime
) -> tuple[AuthSession, User] | None:
    session_id = hash_session_token(token)
    result = await db.execute(
        select(AuthSession)
        .options(selectinload(AuthSession.user).selectinload(User.roles))
        .where(AuthSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        return None
    if is_session_expired(
        SessionExpiry(
            created_at=as_utc(session.created_at),
            last_seen_at=as_utc(session.last_seen_at),
            expires_at=as_utc(session.expires_at),
        ),
        now,
    ):
        await db.delete(session)
        await db.flush()
        return None
    if not session.user.is_active:
        return None
    if now - as_utc(session.last_seen_at) >= SESSION_TOUCH_INTERVAL:
        session.last_seen_at = now
        await db.flush()
    return session, session.user


async def delete_session(db: AsyncSession, *, token: str) -> None:
    await db.execute(
        sa.delete(AuthSession).where(AuthSession.id == hash_session_token(token))
    )
    await db.flush()


async def revoke_user_sessions(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        sa.delete(AuthSession).where(AuthSession.user_id == user_id)
    )
    await db.flush()
    return result.rowcount or 0
