"""
Tests for app/router.py — fallback chains, using fake providers so no
network or real API keys are needed.
"""

import pytest

from app.circuit_breaker import InMemoryHealthStore
from app.providers.base import ProviderResult, ProviderTimeout
from app.router import FallbackExhausted, Router, RoutingError


class FakeProvider:
    def __init__(self, name, fail_times=0, error=ProviderTimeout):
        self.name = name
        self.default_model = f"{name}-model"
        self.fail_times = fail_times
        self.error = error
        self.calls = 0

    async def generate(self, message, model=None):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise self.error("synthetic", self.name)
        return ProviderResult(text=f"ok:{self.name}", provider=self.name, model=self.default_model,
                               input_tokens=1, output_tokens=1)

    async def aclose(self):
        pass


def make_router(providers: dict, chains: dict, health=None) -> Router:
    r = Router.__new__(Router)  # skip __init__'s env-driven registration
    r._providers = providers
    r._chains = chains
    r.health = health or InMemoryHealthStore(failure_threshold=99, window_seconds=60, cooldown_seconds=60)
    return r


@pytest.mark.asyncio
async def test_uses_primary_when_healthy():
    router = make_router({"groq": FakeProvider("groq")}, {"cheap": ["groq"]})
    result, meta = await router.generate("hi", tier="cheap")
    assert result.provider == "groq"
    assert meta["attempted"] == ["groq"]


@pytest.mark.asyncio
async def test_falls_back_when_primary_exhausts_retries():
    router = make_router(
        {"groq": FakeProvider("groq", fail_times=99), "gemini": FakeProvider("gemini")},
        {"cheap": ["groq", "gemini"]},
    )
    result, meta = await router.generate("hi", tier="cheap")
    assert result.provider == "gemini"
    assert meta["attempted"] == ["groq", "gemini"]


@pytest.mark.asyncio
async def test_all_providers_fail_raises_fallback_exhausted():
    router = make_router(
        {"groq": FakeProvider("groq", fail_times=99), "gemini": FakeProvider("gemini", fail_times=99)},
        {"cheap": ["groq", "gemini"]},
    )
    with pytest.raises(FallbackExhausted):
        await router.generate("hi", tier="cheap")


@pytest.mark.asyncio
async def test_open_circuit_is_skipped():
    health = InMemoryHealthStore(failure_threshold=1, window_seconds=60, cooldown_seconds=60)
    await health.record_failure("groq")  # trips it open
    router = make_router(
        {"groq": FakeProvider("groq"), "gemini": FakeProvider("gemini")},
        {"cheap": ["groq", "gemini"]},
        health=health,
    )
    result, meta = await router.generate("hi", tier="cheap")
    assert result.provider == "gemini"
    assert meta["skipped_open_circuit"] == ["groq"]
    assert meta["attempted"] == ["gemini"]


@pytest.mark.asyncio
async def test_explicit_provider_bypasses_chain_and_fallback():
    router = make_router(
        {"groq": FakeProvider("groq", fail_times=99), "gemini": FakeProvider("gemini")},
        {"cheap": ["groq", "gemini"]},
    )
    with pytest.raises(FallbackExhausted):
        # explicit provider = no fallback list, so this fails outright
        await router.generate("hi", provider="groq")


def test_unknown_provider_raises_routing_error():
    router = make_router({"groq": FakeProvider("groq")}, {"cheap": ["groq"]})
    with pytest.raises(RoutingError):
        router._candidates(provider="nonexistent", tier=None)


def test_unknown_tier_raises_routing_error():
    router = make_router({"groq": FakeProvider("groq")}, {"cheap": ["groq"]})
    with pytest.raises(RoutingError):
        router._candidates(provider=None, tier="ultra-premium")