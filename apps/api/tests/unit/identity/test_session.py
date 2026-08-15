from datetime import UTC, datetime, timedelta

from citypulse.identity.session import (
    SESSION_ABSOLUTE_TIMEOUT,
    SESSION_IDLE_TIMEOUT,
    SessionExpiry,
    hash_session_token,
    is_session_expired,
    new_csrf_token,
    new_session_token,
)


def test_session_tokens_are_unique_and_hashable() -> None:
    first = new_session_token()
    second = new_session_token()

    assert first != second
    assert hash_session_token(first) == hash_session_token(first)
    assert hash_session_token(first) != hash_session_token(second)
    assert len(hash_session_token(first)) == 64


def test_csrf_tokens_are_unique() -> None:
    assert new_csrf_token() != new_csrf_token()


def test_session_expires_after_idle_timeout() -> None:
    created = datetime.now(UTC)
    expiry = SessionExpiry(
        created_at=created,
        last_seen_at=created,
        expires_at=created + SESSION_ABSOLUTE_TIMEOUT,
    )

    assert not is_session_expired(expiry, created + SESSION_IDLE_TIMEOUT - timedelta(seconds=1))
    assert is_session_expired(expiry, created + SESSION_IDLE_TIMEOUT + timedelta(seconds=1))


def test_session_expires_at_absolute_deadline() -> None:
    created = datetime.now(UTC)
    expiry = SessionExpiry(
        created_at=created,
        last_seen_at=created + SESSION_ABSOLUTE_TIMEOUT - timedelta(minutes=1),
        expires_at=created + SESSION_ABSOLUTE_TIMEOUT,
    )

    assert is_session_expired(expiry, created + SESSION_ABSOLUTE_TIMEOUT)


def test_naive_timestamps_are_treated_as_utc() -> None:
    created = datetime(2026, 8, 16, 12, 0, 0)
    expiry = SessionExpiry(created_at=created, last_seen_at=created, expires_at=created)

    assert is_session_expired(expiry, datetime(2026, 8, 16, 12, 0, 1, tzinfo=UTC))
