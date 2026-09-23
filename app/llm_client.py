"""
Compatibility layer between FastAPI and the Phase 3 router.

The route in main.py continues calling generate_chat_response(),
but the actual provider selection is now handled by Router.
"""

from fastapi import HTTPException

from app.providers.base import (
    ProviderAuthError,
    ProviderBadRequest,
    ProviderBadResponse,
    ProviderError,
    ProviderRateLimited,
    ProviderTimeout,
    LLMProvider,
    ProviderResult,
    ProviderUnavailable,
)
from app.router import RoutingError, router
from app.schemas import ChatResponse, Usage

# Each ProviderError subtype -> the HTTP status it should surface as.
# Checked most-specific-first isinstance() would also work, but a dict
# keyed by exact type is O(1) and just as correct here since providers
# only ever raise these concrete subtypes, never the base class directly.
_STATUS_MAP: dict[type[ProviderError], int] = {
    ProviderRateLimited: 429,
    ProviderTimeout: 504,
    ProviderUnavailable: 503,
    ProviderAuthError: 502,   # our upstream credential — not the caller's fault
    ProviderBadRequest: 502,  # we sent the provider something invalid
    ProviderBadResponse: 502,  # provider replied with something unparseable
}


async def generate_chat_response(
    message: str,
    provider: str | None = None,
    tier: str | None = None,
    model: str | None = None,
) -> ChatResponse:
    """
    Route the request through the Phase 3 provider router.
    """
    try:
        result = await router.generate(
            message=message,
            provider=provider,
            tier=tier,
            model=model,
        )

    except RoutingError as e:
        # Caller/configuration error: unknown tier, unknown provider,
        # or a tier with no API key configured for it.
        raise HTTPException(status_code=400, detail=str(e))

    except ProviderError as e:
        # Normalized provider failure -> its mapped status code.
        # type(e) is exact because RoutingError above already intercepted
        # the non-provider case; anything reaching here IS one of the
        # concrete subtypes in _STATUS_MAP.
        status = _STATUS_MAP.get(type(e), 502)
        raise HTTPException(status_code=status, detail=f"Provider '{e.provider}' failed: {e.message}")

    # Anything else is a genuine bug, not a modeled failure — let it
    # propagate as a real 500 with a traceback instead of masking it here.

    usage = Usage.from_counts(result.input_tokens, result.output_tokens)

    return ChatResponse(
        response=result.text,
        provider=result.provider,
        model=result.model,
        usage=usage,
    )