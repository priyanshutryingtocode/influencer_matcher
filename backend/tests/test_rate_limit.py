import pytest

from api.rate_limit import RateLimitExceeded, SlidingWindowRateLimiter


def test_rate_limiter_blocks_after_limit_and_resets_with_window():
    now = [0.0]
    limiter = SlidingWindowRateLimiter(2, window_seconds=60, clock=lambda: now[0])

    limiter.check("client")
    limiter.check("client")
    with pytest.raises(RateLimitExceeded):
        limiter.check("client")

    now[0] = 61.0
    limiter.check("client")


def test_rate_limiter_keys_are_independent():
    limiter = SlidingWindowRateLimiter(1, window_seconds=60, clock=lambda: 0.0)

    limiter.check("first")
    limiter.check("second")
    with pytest.raises(RateLimitExceeded):
        limiter.check("first")
