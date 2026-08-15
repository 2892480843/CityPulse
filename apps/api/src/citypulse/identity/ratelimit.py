import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta


@dataclass(slots=True)
class _AttemptWindow:
    failures: deque[datetime] = field(default_factory=deque)
    locked_until: datetime | None = None


class LoginRateLimiter:
    def __init__(
        self,
        *,
        max_failures: int = 5,
        window: timedelta = timedelta(minutes=15),
        lockout: timedelta = timedelta(minutes=15),
    ) -> None:
        self._max_failures = max_failures
        self._window = window
        self._lockout = lockout
        self._attempts: dict[str, _AttemptWindow] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _remaining_seconds(state: _AttemptWindow, moment: datetime) -> int:
        if state.locked_until is None:
            return 0
        return max(0, int((state.locked_until - moment).total_seconds()))

    def retry_after_seconds(self, key: str, now: datetime | None = None) -> int:
        moment = now or self._now()
        with self._lock:
            state = self._attempts.get(key)
            if state is None:
                return 0
            return self._remaining_seconds(state, moment)

    def record_failure(self, key: str, now: datetime | None = None) -> int:
        moment = now or self._now()
        with self._lock:
            state = self._attempts.setdefault(key, _AttemptWindow())
            state.failures.append(moment)
            while state.failures and moment - state.failures[0] > self._window:
                state.failures.popleft()
            if len(state.failures) >= self._max_failures:
                state.locked_until = moment + self._lockout
                state.failures.clear()
            return self._remaining_seconds(state, moment)

    def record_success(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)
