"""
Tests for app/retry.py — exponential backoff + jitter.

We patch asyncio.sleep so these run instantly instead of actually waiting;
what we're verifying is the RETRY COUNT and error propagation, not real
timing.
"""

import pytest

from app.providers.base import ProviderAuthError, ProviderTimeout
from app.retry import call_with_retry


@pytest.mark.asyncio
async def test_succeeds_on_first_try():
    calls = []

    async def fn():
        calls.append(1)
        return "ok"

    result = await call_with_retry(fn, max_attempts=3, base_delay=0, max_delay=0)
    assert result == "ok"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_retries_then_succeeds():
    calls = []

    async def fn():
        calls.append(1)
        if len(calls) < 3:
            raise ProviderTimeout("blip", "test")
        return "ok"

    result = await call_with_retry(fn, max_attempts=5, base_delay=0, max_delay=0)
    assert result == "ok"
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_exhausts_and_raises():
    calls = []

    async def fn():
        calls.append(1)
        raise ProviderTimeout("down", "test")

    with pytest.raises(ProviderTimeout):
        await call_with_retry(fn, max_attempts=3, base_delay=0, max_delay=0)
    assert len(calls) == 3  # 1 initial + 2 retries, then gives up


@pytest.mark.asyncio
async def test_non_retryable_error_is_not_retried():
    calls = []

    async def fn():
        calls.append(1)
        raise ProviderAuthError("bad key", "test")

    with pytest.raises(ProviderAuthError):
        await call_with_retry(fn, max_attempts=5, base_delay=0, max_delay=0)
    assert len(calls) == 1  # auth errors aren't in RETRYABLE_ERRORS — no retry