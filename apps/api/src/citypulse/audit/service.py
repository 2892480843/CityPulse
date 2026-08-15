import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from citypulse.audit.models import AuditLog

logger = structlog.get_logger(__name__)

ACTION_LOGIN_SUCCEEDED = "login_succeeded"
ACTION_LOGIN_FAILED = "login_failed"
ACTION_LOGOUT = "logout"
ACTION_USER_CREATED = "user_created"
ACTION_USER_UPDATED = "user_updated"
ACTION_DATASET_UPLOADED = "dataset_uploaded"
ACTION_DATASET_VALIDATED = "dataset_validated"
ACTION_DATASET_COMMITTED = "dataset_committed"


async def record(
    db: AsyncSession,
    *,
    action: str,
    object_type: str,
    actor_id: uuid.UUID | None = None,
    actor_username: str | None = None,
    object_id: str | None = None,
    detail: dict[str, Any] | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        actor_username=actor_username,
        action=action,
        object_type=object_type,
        object_id=object_id,
        detail=detail,
        request_id=request_id,
        ip_address=ip_address,
    )
    db.add(entry)
    await db.flush()
    return entry
