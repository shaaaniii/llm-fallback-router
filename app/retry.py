"""
PHASE 4 — Retry logic with exponential backoff + jitter.

Exponential backoff: each retry waits longer than the last one
(base_delay * 2^attempt). A provider having a bad second gets breathing
room instead of being hit again immediately.

Jitter: without randomness, if 100 requests fail at the same instant, they
ALL retry at exactly 2s, then all at 4s, then all at 8s — perfectly
synchronized, which re-creates the exact spike that caused the failure.
This is the "thundering herd" problem. We use FULL JITTER (sleep a random
duration between 0 and the computed ceiling), which is what AWS's
architecture blog recommends for exactly this reason.

Only RETRYABLE_ERRORS trigger a retry. An auth error or a malformed
request will fail identically on attempt 2 as on attempt 1 — retrying
just wastes time and makes the caller wait longer for the same failure.
"""

import asyncio
import random
from typing import Awaitable, Callable, TypeVar

from app.providers.base import RETRYABLE_ERRORS

T = TypeVar("T")


async def call_with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
) -> T:
    """
    Call `fn()` (a zero-arg async callable), retrying on retryable
    provider errors. Re-raises the last error if all attempts fail.

    max_attempts=3 means: 1 initial try + 2 retries.
    """
    attempt = 0
    while True:
        try:
            return await fn()
        except RETRYABLE_ERRORS:
            attempt += 1
            if attempt >= max_attempts:
                raise  # exhausted — let the caller (router) decide what's next
            ceiling = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay = random.uniform(0, ceiling)
            await asyncio.sleep(delay)