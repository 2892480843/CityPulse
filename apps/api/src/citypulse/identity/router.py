import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from citypulse.audit import service as audit
from citypulse.identity.password import PasswordPolicyError
from citypulse.identity.rbac import Identity, require_roles, resolve_identity
from citypulse.identity.schemas import (
    CurrentUser,
    LoginRequest,
    LoginResponse,
    UserAdminView,
    UserCreateRequest,
    UserListResponse,
    UserUpdateRequest,
)
from citypulse.identity.service import (
    IdentityServiceError,
    authenticate,
    create_session,
    create_user,
    delete_session,
    get_user,
    list_users,
    update_user,
    user_role_names,
)
from citypulse.identity.session import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    session_cookie_max_age,
)
from citypulse.shared.db import get_session
from citypulse.shared.errors import AppError

router = APIRouter(tags=["identity"])
admin_router = APIRouter(prefix="/api/v1/admin", tags=["identity"])


def _request_id(request: Request) -> str | None:
    return str(getattr(request.state, "request_id", "")) or None


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _login_rate_limiter(request: Request):
    limiter = getattr(request.app.state, "login_rate_limiter", None)
    if limiter is None:
        raise AppError(
            code="SERVICE_MISCONFIGURED",
            message="The login rate limiter is not configured.",
            status_code=503,
        )
    return limiter


def _set_session_cookies(response: Response, *, token: str, csrf_token: str, secure: bool) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=session_cookie_max_age(),
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=session_cookie_max_age(),
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookies(response: Response) -> None:
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/")


@router.post("/api/v1/auth/login", response_model=LoginResponse)
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> LoginResponse:
    limiter = _login_rate_limiter(request)
    key = f"{payload.username.lower()}@{_client_ip(request) or 'unknown'}"
    retry_after = limiter.retry_after_seconds(key)
    if retry_after > 0:
        raise AppError(
            code="LOGIN_RATE_LIMITED",
            message="Too many failed sign-in attempts. Try again later.",
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )

    user = await authenticate(
        db, username=payload.username, password=payload.password, now=datetime.now(UTC)
    )
    if user is None:
        retry_after = limiter.record_failure(key)
        await audit.record(
            db,
            action=audit.ACTION_LOGIN_FAILED,
            object_type="user",
            object_id=payload.username,
            actor_username=payload.username,
            request_id=_request_id(request),
            ip_address=_client_ip(request),
        )
        await db.commit()
        if retry_after > 0:
            raise AppError(
                code="LOGIN_RATE_LIMITED",
                message="Too many failed sign-in attempts. Try again later.",
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
        raise AppError(
            code="INVALID_CREDENTIALS",
            message="Incorrect username or password.",
            status_code=401,
        )

    limiter.record_success(key)
    token, session = await create_session(db, user_id=user.id, now=datetime.now(UTC))
    await audit.record(
        db,
        action=audit.ACTION_LOGIN_SUCCEEDED,
        object_type="user",
        object_id=str(user.id),
        actor_id=user.id,
        actor_username=user.username,
        request_id=_request_id(request),
        ip_address=_client_ip(request),
    )
    await db.commit()
    _set_session_cookies(
        response,
        token=token,
        csrf_token=session.csrf_token,
        secure=bool(request.app.state.settings.cookie_secure),
    )
    return LoginResponse(
        user=CurrentUser(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            is_active=user.is_active,
            roles=user_role_names(user),
        )
    )


@router.post("/api/v1/auth/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    identity: Annotated[Identity, Depends(resolve_identity)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token is not None:
        await delete_session(db, token=token)
    await audit.record(
        db,
        action=audit.ACTION_LOGOUT,
        object_type="user",
        object_id=str(identity.user_id),
        actor_id=identity.user_id,
        actor_username=identity.username,
        request_id=_request_id(request),
        ip_address=_client_ip(request),
    )
    await db.commit()
    _clear_session_cookies(response)


@router.get("/api/v1/auth/me", response_model=CurrentUser)
async def me(identity: Annotated[Identity, Depends(resolve_identity)]) -> CurrentUser:
    return CurrentUser(
        id=identity.user_id,
        username=identity.username,
        display_name=identity.display_name,
        is_active=True,
        roles=list(identity.roles),
    )


@admin_router.get("/users", response_model=UserListResponse)
async def list_users_endpoint(
    _admin: Annotated[Identity, Depends(require_roles("admin"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> UserListResponse:
    users = await list_users(db)
    items = [
        UserAdminView(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            is_active=user.is_active,
            roles=user_role_names(user),
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        )
        for user in users
    ]
    return UserListResponse(items=items, total=len(items))


@admin_router.post("/users", response_model=UserAdminView, status_code=201)
async def create_user_endpoint(
    request: Request,
    payload: UserCreateRequest,
    admin: Annotated[Identity, Depends(require_roles("admin"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> UserAdminView:
    try:
        user = await create_user(
            db,
            username=payload.username,
            password=payload.password,
            display_name=payload.display_name,
            roles=payload.roles,
        )
    except PasswordPolicyError as error:
        raise AppError(code="WEAK_PASSWORD", message=str(error), status_code=400) from error
    except IdentityServiceError as error:
        raise error from error
    await audit.record(
        db,
        action=audit.ACTION_USER_CREATED,
        object_type="user",
        object_id=str(user.id),
        actor_id=admin.user_id,
        actor_username=admin.username,
        detail={"username": user.username, "roles": user_role_names(user)},
        request_id=_request_id(request),
        ip_address=_client_ip(request),
    )
    await db.commit()
    return UserAdminView(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        is_active=user.is_active,
        roles=user_role_names(user),
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@admin_router.patch("/users/{user_id}", response_model=UserAdminView)
async def update_user_endpoint(
    request: Request,
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    admin: Annotated[Identity, Depends(require_roles("admin"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> UserAdminView:
    if user_id == admin.user_id and payload.is_active is False:
        raise AppError(
            code="CANNOT_DISABLE_SELF",
            message="Administrators cannot disable their own account.",
            status_code=400,
        )
    try:
        user = await update_user(
            db,
            user_id,
            display_name=payload.display_name,
            is_active=payload.is_active,
            roles=payload.roles,
        )
    except IdentityServiceError as error:
        raise error from error
    await audit.record(
        db,
        action=audit.ACTION_USER_UPDATED,
        object_type="user",
        object_id=str(user.id),
        actor_id=admin.user_id,
        actor_username=admin.username,
        detail={
            "display_name": payload.display_name,
            "is_active": payload.is_active,
            "roles": payload.roles,
        },
        request_id=_request_id(request),
        ip_address=_client_ip(request),
    )
    await db.commit()
    return UserAdminView(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        is_active=user.is_active,
        roles=user_role_names(user),
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@admin_router.get("/users/{user_id}", response_model=UserAdminView)
async def get_user_endpoint(
    user_id: uuid.UUID,
    _admin: Annotated[Identity, Depends(require_roles("admin"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> UserAdminView:
    user = await get_user(db, user_id)
    return UserAdminView(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        is_active=user.is_active,
        roles=user_role_names(user),
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )
