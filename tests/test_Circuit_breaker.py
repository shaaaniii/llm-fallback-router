"""Tests for app/circuit_breaker.py — using the in-memory store (no Redis needed)."""

import asyncio

import pytest

from app.circuit_breaker import InMemoryHealthStore


@pytest.mark.asyncio
async def test_closed_by_default():
    store = InMemoryHealthStore(failure_threshold=3, window_seconds=60, cooldown_seconds=30)
    assert await store.is_open("groq") is False


@pytest.mark.asyncio
async def test_trips_after_threshold():
    store = InMemoryHealthStore(failure_threshold=3, window_seconds=60, cooldown_seconds=30)
    await store.record_failure("groq")
    await store.record_failure("groq")
    assert await store.is_open("groq") is False  # not yet at threshold
    await store.record_failure("groq")
    assert await store.is_open("groq") is True


@pytest.mark.asyncio
async def test_success_resets_failures():
    store = InMemoryHealthStore(failure_threshold=3, window_seconds=60, cooldown_seconds=30)
    await store.record_failure("groq")
    await store.record_failure("groq")
    await store.record_success("groq")
    await store.record_failure("groq")
    await store.record_failure("groq")
    assert await store.is_open("groq") is False  # count was reset, only 2 since


@pytest.mark.asyncio
async def test_cooldown_expires_to_half_open():
    store = InMemoryHealthStore(failure_threshold=1, window_seconds=60, cooldown_seconds=0.1)
    await store.record_failure("groq")
    assert await store.is_open("groq") is True
    await asyncio.sleep(0.15)
    assert await store.is_open("groq") is False


@pytest.mark.asyncio
async def test_providers_are_independent():
    store = InMemoryHealthStore(failure_threshold=1, window_seconds=60, cooldown_seconds=30)
    await store.record_failure("groq")
    assert await store.is_open("groq") is True
    assert await store.is_open("gemini") is False