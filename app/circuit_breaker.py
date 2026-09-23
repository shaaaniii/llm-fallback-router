"""
PHASE 4 — Circuit breaker, backed by Redis (with an in-memory fallback).

Why a circuit breaker on top of retries: retries handle a BLIP. A circuit
breaker handles an OUTAGE. If a provider is fully down, hammering it with
retries on every single incoming request wastes time on every request AND
keeps load on a service that needs to recover. The breaker "trips" after
enough failures and skips that provider entirely for a cooldown window —
this is what actually protects your app's latency during an outage.

Three states, implemented with two keys + Redis TTL (no separate timer
needed — TTL expiry IS the state transition):

    CLOSED     — normal. Requests flow. Failures are counted in a rolling
                 window (the fail-count key expires after `window_seconds`).
    OPEN       — too many failures. The provider is skipped entirely.
                 This state IS the `open` key's existence; when the key's
                 TTL (`cooldown_seconds`) expires, we're back to trying.
    HALF-OPEN  — implicit: the moment the `open` key expires, the very next
                 request is a live trial. Success clears the failure count;
                 failure re-opens the circuit.

Redis makes this state SHARED across every process/replica of your API —
important once you run more than one instance, which a single Python
dict never could do. The in-memory fallback exists so the project still
runs with zero external services for local development; swap in Redis by
setting REDIS_URL and nothing else in your code changes.
"""

import time
from abc import ABC, abstractmethod

try:
    import redis.asyncio as redis
except ImportError:  # redis package not installed — in-memory-only mode
    redis = None


class HealthStore(ABC):
    """Interface used by the router. Two implementations below."""

    @abstractmethod
    async def is_open(self, provider: str) -> bool:
        """True if this provider's circuit is open (should be skipped)."""

    @abstractmethod
    async def record_success(self, provider: str) -> None:
        """Clear failure history — the provider is healthy again."""

    @abstractmethod
    async def record_failure(self, provider: str) -> None:
        """Count a failure; trip the circuit if the threshold is hit."""


class InMemoryHealthStore(HealthStore):
    """
    Same state machine as RedisHealthStore, using a plain dict + wall clock
    instead of Redis TTLs. Good enough for local dev / a single process.
    """

    def __init__(self, failure_threshold: int = 3, window_seconds: float = 60,
                 cooldown_seconds: float = 30):
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds
        self._fail_counts: dict[str, tuple[int, float]] = {}   # name -> (count, expires_at)
        self._opened_until: dict[str, float] = {}              # name -> expires_at

    async def is_open(self, provider: str) -> bool:
        expires_at = self._opened_until.get(provider)
        if expires_at is None:
            return False
        if time.monotonic() >= expires_at:
            del self._opened_until[provider]  # cooldown elapsed -> half-open
            return False
        return True

    async def record_success(self, provider: str) -> None:
        self._fail_counts.pop(provider, None)
        self._opened_until.pop(provider, None)

    async def record_failure(self, provider: str) -> None:
        now = time.monotonic()
        count, expires_at = self._fail_counts.get(provider, (0, 0))
        if now >= expires_at:  # window elapsed, start a fresh count
            count = 0
        count += 1
        self._fail_counts[provider] = (count, now + self.window_seconds)
        if count >= self.failure_threshold:
            self._opened_until[provider] = now + self.cooldown_seconds


class RedisHealthStore(HealthStore):
    """
    Same logic as above, implemented with two Redis keys per provider:

        cb:{provider}:fails   INCR'd on failure, TTL = window_seconds
        cb:{provider}:open    SET on trip,        TTL = cooldown_seconds

    TTL does the cleanup for us — no background job needed to "reset" an
    old failure count or "close" an expired circuit.
    """

    def __init__(self, redis_url: str, failure_threshold: int = 3,
                 window_seconds: float = 60, cooldown_seconds: float = 30):
        if redis is None:
            raise RuntimeError("redis package not installed — pip install redis")
        self._r = redis.from_url(redis_url, decode_responses=True)
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds

    def _open_key(self, provider: str) -> str:
        return f"cb:{provider}:open"

    def _fail_key(self, provider: str) -> str:
        return f"cb:{provider}:fails"

    async def is_open(self, provider: str) -> bool:
        return bool(await self._r.exists(self._open_key(provider)))

    async def record_success(self, provider: str) -> None:
        await self._r.delete(self._fail_key(provider), self._open_key(provider))

    async def record_failure(self, provider: str) -> None:
        fail_key = self._fail_key(provider)
        count = await self._r.incr(fail_key)
        if count == 1:
            await self._r.expire(fail_key, int(self.window_seconds))
        if count >= self.failure_threshold:
            await self._r.set(self._open_key(provider), "1", ex=int(self.cooldown_seconds))

    async def aclose(self) -> None:
        await self._r.aclose()


def build_health_store(
    redis_url: str | None,
    failure_threshold: int,
    window_seconds: float,
    cooldown_seconds: float,
) -> HealthStore:
    """Factory: Redis if configured, in-memory otherwise. Router doesn't care which."""
    if redis_url and redis is not None:
        return RedisHealthStore(redis_url, failure_threshold, window_seconds, cooldown_seconds)
    return InMemoryHealthStore(failure_threshold, window_seconds, cooldown_seconds)