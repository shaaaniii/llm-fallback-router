"""
PHASE 4 — The router now does what the diagram shows:

    Request -> Provider A -> FAIL -> retry -> FAIL -> Provider B -> SUCCESS

Two distinct mechanisms, easy to conflate but genuinely different:

    RETRY     = try the SAME provider again (transient blip: one dropped
                connection, one slow response).
    FALLBACK  = move to a DIFFERENT provider (that provider is having a
                bad time; a sibling service probably isn't).

Order per attempt:
    1. Is provider A's circuit OPEN? If so, skip it immediately — don't
       even try, don't wait for a timeout we already know is coming.
    2. Otherwise call it with retry-with-backoff (Phase 4's retry.py).
    3. Any failure (retries exhausted, or a non-retryable error) -> record
       it against the circuit breaker, then move to the NEXT provider in
       the chain.
    4. All candidates exhausted -> raise FallbackExhausted (502 — every
       upstream failed, not the caller's fault).
"""

import time

from app.circuit_breaker import HealthStore, build_health_store
from app.config import settings
from app.providers.base import LLMProvider, ProviderError, ProviderResult
from app.providers.gemini_provider import GeminiProvider
from app.providers.groq_providers import GroqProvider
from app.retry import call_with_retry


class RoutingError(Exception):
    """Client asked for a route that can't be resolved. -> 400."""


class FallbackExhausted(Exception):
    """Every provider in the chain failed. -> 502."""

    def __init__(self, attempts: list[str]):
        self.attempts = attempts
        super().__init__(f"All providers failed: {', '.join(attempts)}")


class Router:
    def __init__(self, health_store: HealthStore | None = None) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self._register_all()
        self._chains: dict[str, list[str]] = {
            "cheap": settings.ROUTE_CHEAP,
            "powerful": settings.ROUTE_POWERFUL,
        }
        self.health = health_store or build_health_store(
            settings.REDIS_URL,
            settings.CB_FAILURE_THRESHOLD,
            settings.CB_WINDOW_SECONDS,
            settings.CB_COOLDOWN_SECONDS,
        )

    # -- registry ------------------------------------------------------

    def _register_all(self) -> None:
        if settings.GROQ_API_KEY:
            self._register(GroqProvider(
                api_key=settings.GROQ_API_KEY, default_model=settings.GROQ_MODEL,
                timeout=settings.LLM_TIMEOUT, max_tokens=settings.LLM_MAX_TOKENS,
            ))
        if settings.GEMINI_API_KEY:
            self._register(GeminiProvider(
                api_key=settings.GEMINI_API_KEY, default_model=settings.GEMINI_MODEL,
                timeout=settings.LLM_TIMEOUT, max_tokens=settings.LLM_MAX_TOKENS,
            ))

    def _register(self, provider: LLMProvider) -> None:
        self._providers[provider.name] = provider

    @property
    def available(self) -> list[str]:
        return sorted(self._providers)

    def describe_routes(self) -> dict[str, list[str]]:
        return {
            tier: [p for p in chain if p in self._providers]
            for tier, chain in self._chains.items()
        }

    # -- candidate resolution -------------------------------------------

    def _candidates(self, provider: str | None, tier: str | None) -> list[str]:
        """Returns an ORDERED list of provider names to try, in order."""
        if provider:
            if provider not in self._providers:
                raise RoutingError(
                    f"Unknown or unconfigured provider '{provider}'. "
                    f"Available: {', '.join(self.available) or 'none'}"
                )
            return [provider]  # explicit choice: no fallback chain

        tier_name = tier or settings.DEFAULT_TIER
        chain = self._chains.get(tier_name)
        if chain is None:
            raise RoutingError(f"Unknown tier '{tier_name}'. Valid tiers: {', '.join(self._chains)}")

        usable = [name for name in chain if name in self._providers]
        if not usable:
            raise RoutingError(
                f"Tier '{tier_name}' has no configured providers with API keys set "
                f"(chain was: {', '.join(chain)})."
            )
        return usable

    # -- execution --------------------------------------------------------

    async def generate(
        self,
        message: str,
        provider: str | None = None,
        tier: str | None = None,
        model: str | None = None,
    ) -> tuple[ProviderResult, dict]:
        """
        Returns (result, meta). `meta` carries observability data Phase 5
        needs for logging: which providers were tried, latency, etc.
        Kept separate from ProviderResult so that struct stays a pure
        provider-facing type.
        """
        candidates = self._candidates(provider, tier)
        attempted: list[str] = []
        skipped_open: list[str] = []
        start = time.monotonic()

        for name in candidates:
            if await self.health.is_open(name):
                skipped_open.append(name)
                continue

            attempted.append(name)
            chosen = self._providers[name]

            try:
                result = await call_with_retry(
                    lambda: chosen.generate(message=message, model=model),
                    max_attempts=settings.RETRY_MAX_ATTEMPTS,
                    base_delay=settings.RETRY_BASE_DELAY,
                    max_delay=settings.RETRY_MAX_DELAY,
                )
            except ProviderError:
                await self.health.record_failure(name)
                continue  # try the next provider in the chain

            await self.health.record_success(name)
            meta = {
                "attempted": attempted,
                "skipped_open_circuit": skipped_open,
                "latency_ms": round((time.monotonic() - start) * 1000, 1),
            }
            return result, meta

        # Every candidate either failed or had an open circuit.
        raise FallbackExhausted(attempted or skipped_open)

    async def aclose(self) -> None:
        for p in self._providers.values():
            await p.aclose()
        aclose = getattr(self.health, "aclose", None)
        if aclose:
            await aclose()


router = Router()