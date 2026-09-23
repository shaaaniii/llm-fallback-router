"""
The router — decides WHICH provider handles a request.

Two responsibilities:

1. REGISTRY: build the set of available providers at startup, based on
   which API keys are actually present. A missing GEMINI_API_KEY just means
   Gemini isn't registered; the app still runs on Groq alone.

2. ROUTING: map a request to a provider.

Routing precedence (first match wins):
    a) explicit `provider` in the request   -> caller knows exactly what it wants
    b) `tier` in the request                -> "cheap" / "powerful"
    c) the configured DEFAULT_TIER          -> caller expressed no preference

Rule-based means exactly that: no ML, no heuristics on prompt content —
just a lookup table. Phase 4+ can make this smarter (latency, cost,
health checks); the interface won't change.
"""
import groq 
from app.config import settings
from app.providers.base import LLMProvider, ProviderResult
from app.providers.gemini_provider import GeminiProvider
from app.providers.groq_providers import GroqProvider


class RoutingError(Exception):
    """Raised when no provider can serve the request. Caller's fault -> 400."""


class Router:
    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self._register_all()
        self._tiers: dict[str, str] = {
            "cheap": settings.ROUTE_CHEAP,
            "powerful": settings.ROUTE_POWERFUL,
        }

    # -- registry ----------------------------------------------------------

    def _register_all(self) -> None:
        """Only register providers we actually have credentials for."""
        if settings.GROQ_API_KEY:
            self._register(
                GroqProvider(
                    api_key=settings.GROQ_API_KEY,
                    default_model=settings.GROQ_MODEL,
                    timeout=settings.LLM_TIMEOUT,
                    max_tokens=settings.LLM_MAX_TOKENS,
                )
            )
        if settings.GEMINI_API_KEY:
            self._register(
                GeminiProvider(
                    api_key=settings.GEMINI_API_KEY,
                    default_model=settings.GEMINI_MODEL,
                    timeout=settings.LLM_TIMEOUT,
                    max_tokens=settings.LLM_MAX_TOKENS,
                )
            )

    def _register(self, provider: LLMProvider) -> None:
        self._providers[provider.name] = provider

    @property
    def available(self) -> list[str]:
        return sorted(self._providers)

    def describe_routes(self) -> dict[str, str | None]:
        """What each tier currently resolves to — handy on /health."""
        return {
            tier: (name if name in self._providers else None)
            for tier, name in self._tiers.items()
        }

    # -- selection ---------------------------------------------------------

    def select(self, provider: str | None = None, tier: str | None = None) -> LLMProvider:
        """Resolve a request to a concrete provider, or raise RoutingError."""

        # (a) Explicit provider wins.
        if provider:
            chosen = self._providers.get(provider)
            if not chosen:
                raise RoutingError(
                    f"Unknown or unconfigured provider '{provider}'. "
                    f"Available: {', '.join(self.available) or 'none'}"
                )
            return chosen

        # (b)/(c) Tier lookup, falling back to the configured default tier.
        tier_name = tier or settings.DEFAULT_TIER
        mapped = self._tiers.get(tier_name)
        if mapped is None:
            raise RoutingError(
                f"Unknown tier '{tier_name}'. Valid tiers: {', '.join(self._tiers)}"
            )

        chosen = self._providers.get(mapped)
        if not chosen:
            raise RoutingError(
                f"Tier '{tier_name}' routes to '{mapped}', which has no API key configured."
            )
        return chosen

    # -- execution ---------------------------------------------------------

    async def generate(
        self,
        message: str,
        provider: str | None = None,
        tier: str | None = None,
        model: str | None = None,
    ) -> ProviderResult:
        """
        Pick a provider and run the request.

        Phase 4 turns this into a loop over candidates, catching
        RETRYABLE_ERRORS and moving to the next one. Everything calling
        this method stays unchanged when that happens — which is the
        payoff for building the abstraction now.
        """
        chosen = self.select(provider=provider, tier=tier)
        return await chosen.generate(message=message, model=model)

    async def aclose(self) -> None:
        for p in self._providers.values():
            await p.aclose()


# One shared router for the app.
router = Router()