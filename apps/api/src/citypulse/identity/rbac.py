import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from citypulse.identity.models import RoleName
from citypulse.identity.service import load_active_session
from citypulse.shared.db import get_session
from citypulse.shared.errors import AppError

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


@dataclass(frozen=True, slots=True)
class Identity:
    user_id: uuid.UUID
    username: str
    display_name: str
    roles: tuple[RoleName, ...]
    csrf_token: str


async def resolve_identity(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Identity:
    token = request.cookies.get("citypulse_session")
    if token is None:
        raise AppError(code="UNAUTHENTICATED", message="Sign in to continue.", status_code=401)
    loaded = await load_active_session(db, token=token, now=datetime.now(UTC))
    if loaded is None:
        raise AppError(code="SESSION_INVALID", message="The session expired.", status_code=401)
    session, user = loaded
    identity = Identity(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        roles=tuple(sorted(role.name for role in user.roles)),
        csrf_token=session.csrf_token,
    )
    request.state.identity = identity
    return identity


def enforce_csrf(request: Request, identity: Identity) -> None:
    if request.method not in UNSAFE_METHODS:
        return
    supplied = request.headers.get("X-CSRF-Token", "")
    if not supplied or supplied != identity.csrf_token:
        raise AppError(
            code="CSRF_TOKEN_INVALID",
            message="The request is missing a valid CSRF token.",
            status_code=403,
        )


def require_roles(*allowed: RoleName):
    if not allowed:
        raise ValueError("require_roles needs at least one role")

    async def dependency(
        request: Request,
        identity: Annotated[Identity, Depends(resolve_identity)],
    ) -> Identity:
        if not set(identity.roles) & set(allowed):
            raise AppError(
                code="FORBIDDEN",
                message="Your role cannot perform this operation.",
                status_code=403,
            )
        enforce_csrf(request, identity)
        return identity

    return dependency
