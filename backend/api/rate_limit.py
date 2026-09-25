from collections import deque
from threading import Lock
from time import monotonic
from typing import Callable


class RateLimitExceeded(RuntimeError):
    pass


class SlidingWindowRateLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: int,
        clock: Callable[[], float] = monotonic,
    ):
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("Rate limit values must be positive")
        self._limit = limit
        self._window_seconds = window_seconds
        self._clock = clock
        self._lock = Lock()
        self._attempts: dict[str, deque[float]] = {}

    def check(self, key: str) -> None:
        now = self._clock()
        cutoff = now - self._window_seconds
        with self._lock:
            attempts = self._attempts.setdefault(key, deque())
            while attempts and attempts[0] <= cutoff:
                attempts.popleft()
            if len(attempts) >= self._limit:
                raise RateLimitExceeded("The hourly match limit has been reached.")
            attempts.append(now)
