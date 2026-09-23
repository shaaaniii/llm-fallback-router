"""
PHASE 5 — Rate limiting.

Fixed-window counter per API key: INCR a Redis key named for the current
minute; the FIRST increment sets a 60s TTL. When the window rolls over,
the key expires and the count starts fresh — the TTL does the "reset"
for us, same trick as the circuit breaker.

Fixed-window is the simplest correct rate limiter and is fine for a
portfolio project; it can allow a short burst right at a window boundary
(worst case ~2x the limit for a moment). A sliding-window log fixes that
at the cost of more Redis calls — a reasonable follow-up, not needed here.
"""

import time
from abc import ABC, abstractmethod

try:
    import redis.asyncio as redis
except ImportError:
    redis = None


class RateLimiter(ABC):
    @abstractmethod
    async def check(self, key: str, limit_per_minute: int) -> tuple[bool, int]:
        """Returns (allowed, remaining_in_window)."""


class InMemoryRateLimiter(RateLimiter):
    def __init__(self):
        self._windows: dict[str, tuple[int, int]] = {}  # key -> (window_id, count)

    async def check(self, key: str, limit_per_minute: int) -> tuple[bool, int]:
        window_id = int(time.time() // 60)
        stored_window, count = self._windows.get(key, (window_id, 0))
        if stored_window != window_id:
            count = 0  # new minute — fresh window
        count += 1
        self._windows[key] = (window_id, count)
        allowed = count <= limit_per_minute
        return allowed, max(0, limit_per_minute - count)


class RedisRateLimiter(RateLimiter):
    def __init__(self, redis_url: str):
        if redis is None:
            raise RuntimeError("redis package not installed — pip install redis")
        self._r = redis.from_url(redis_url, decode_responses=True)

    async def check(self, key: str, limit_per_minute: int) -> tuple[bool, int]:
        window_id = int(time.time() // 60)
        redis_key = f"rl:{key}:{window_id}"
        count = await self._r.incr(redis_key)
        if count == 1:
            await self._r.expire(redis_key, 60)
        allowed = count <= limit_per_minute
        return allowed, max(0, limit_per_minute - count)

    async def aclose(self) -> None:
        await self._r.aclose()


def build_rate_limiter(redis_url: str | None) -> RateLimiter:
    if redis_url and redis is not None:
        return RedisRateLimiter(redis_url)
    return InMemoryRateLimiter()