import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

SESSION_COOKIE = "citypulse_session"
CSRF_COOKIE = "citypulse_csrf"

SESSION_IDLE_TIMEOUT = timedelta(minutes=30)
SESSION_ABSOLUTE_TIMEOUT = timedelta(hours=12)
SESSION_TOUCH_INTERVAL = timedelta(seconds=60)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment


@dataclass(frozen=True, slots=True)
class SessionExpiry:
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime


def is_session_expired(expiry: SessionExpiry, now: datetime) -> bool:
    now = as_utc(now)
    return now >= as_utc(expiry.expires_at) or (
        now - as_utc(expiry.last_seen_at) >= SESSION_IDLE_TIMEOUT
    )


def session_cookie_max_age() -> int:
    return int(SESSION_ABSOLUTE_TIMEOUT.total_seconds())
