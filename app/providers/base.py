"""
The provider abstraction — the heart of Phase 3.

Two things live here:

1. `LLMProvider` — the COMMON INTERFACE every provider must implement.
   Groq and Gemini have completely different HTTP shapes, SDKs, and error
   types. This class is the promise that, from the rest of the app's point
   of view, they behave identically.

2. `ProviderError` and friends — NORMALIZED errors.
   Groq raises `groq.RateLimitError`; Gemini returns HTTP 429 JSON. Each
   adapter translates its own failures into these shared types, so routing
   logic (and Phase 4's fallback) can reason about failures without
   knowing which provider produced them.

This is the Adapter pattern: one interface, many incompatible backends.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Normalized result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProviderResult:
    """
    What every provider returns, regardless of its native response shape.

    Note `provider` and `model`: the client doesn't *need* to care who
    answered, but we still report it — useful for debugging and for
    Phase 4, where the answer may come from a fallback.
    """
    text: str
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


# ---------------------------------------------------------------------------
# Normalized errors
# ---------------------------------------------------------------------------

class ProviderError(Exception):
    """Base class. Everything a provider can fail with inherits from this."""

    def __init__(self, message: str, provider: str = "unknown"):
        self.message = message
        self.provider = provider
        super().__init__(f"[{provider}] {message}")


class ProviderAuthError(ProviderError):
    """Our upstream credential was rejected. Our fault, not the client's."""


class ProviderTimeout(ProviderError):
    """Provider took too long."""


class ProviderUnavailable(ProviderError):
    """Network failure, or provider returned 5xx."""


class ProviderRateLimited(ProviderError):
    """We hit the provider's rate limit."""


class ProviderBadRequest(ProviderError):
    """Provider rejected the request — bad model name, prompt too long, etc."""


class ProviderBadResponse(ProviderError):
    """Provider replied with something we couldn't parse."""


# `retryable` matters in Phase 4: these are the failures where trying a
# DIFFERENT provider is likely to succeed. An auth error or a malformed
# prompt would fail everywhere, so retrying is pointless.
RETRYABLE_ERRORS = (
    ProviderTimeout,
    ProviderUnavailable,
    ProviderRateLimited,
)


# ---------------------------------------------------------------------------
# The common interface
# ---------------------------------------------------------------------------

class LLMProvider(ABC):
    """
    Every provider adapter subclasses this.

    Adding a third provider later means writing one new file that implements
    `generate()` — nothing else in the app changes. That is the whole point.
    """

    name: str          # short id used in config and logs, e.g. "groq"
    default_model: str

    @abstractmethod
    async def generate(self, message: str, model: str | None = None) -> ProviderResult:
        """
        Send one prompt, return a normalized result.

        MUST raise a ProviderError subclass on failure — never a
        provider-specific exception, and never HTTPException. Translating
        errors is the adapter's job, so callers stay provider-agnostic.
        """
        raise NotImplementedError

    async def aclose(self) -> None:
        """Release connections on shutdown. Override if the adapter needs it."""
        return None