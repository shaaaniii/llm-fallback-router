"""
Phase 3 — Multiple providers + routing.

                       ┌──► Groq
                       │
    Client → FastAPI → Router
                       │
                       └──► Gemini

Run:
    uvicorn app.main:app --reload
Docs:
    http://127.0.0.1:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from app.auth import require_api_key
from app.providers.base import (
    ProviderAuthError,
    ProviderBadRequest,
    ProviderBadResponse,
    ProviderError,
    ProviderRateLimited,
    ProviderTimeout,
    ProviderUnavailable,
)
from app.router import RoutingError, router
from app.schemas import ChatRequest, ChatResponse, ErrorResponse, Usage


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown. Closing HTTP clients avoids leaked connections."""
    yield
    await router.aclose()


app = FastAPI(
    title="LLM Fallback Router",
    description="Phase 3: multiple providers behind one stable API.",
    version="0.3.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Exception handlers: normalized provider errors -> HTTP status codes.
#
# Phase 2 raised HTTPException inside the client. That was fine for one
# provider, but it coupled the LLM layer to FastAPI. Now providers raise
# plain ProviderErrors, and the HTTP translation happens HERE — in exactly
# one place, at the edge of the app.
# ---------------------------------------------------------------------------

_STATUS_MAP: list[tuple[type[ProviderError], int]] = [
    (ProviderRateLimited, 429),   # too many requests upstream
    (ProviderTimeout, 504),       # gateway timeout
    (ProviderUnavailable, 503),   # upstream down / unreachable
    (ProviderAuthError, 502),     # OUR key is bad — not the client's fault
    (ProviderBadRequest, 502),    # we sent the provider something invalid
    (ProviderBadResponse, 502),   # provider replied with nonsense
]


@app.exception_handler(ProviderError)
async def provider_error_handler(request: Request, exc: ProviderError):
    status = 500
    for err_type, code in _STATUS_MAP:
        if isinstance(exc, err_type):
            status = code
            break
    return JSONResponse(
        status_code=status,
        content={"detail": f"Provider '{exc.provider}' failed: {exc.message}"},
    )


@app.exception_handler(RoutingError)
async def routing_error_handler(request: Request, exc: RoutingError):
    # 400: the client asked for a route that doesn't exist.
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["system"])
async def health():
    """Unauthenticated liveness check — now also reports the routing table."""
    return {
        "status": "ok",
        "providers": router.available,
        "routes": router.describe_routes(),
    }


@app.post(
    "/v1/chat",
    response_model=ChatResponse,
    dependencies=[Depends(require_api_key)],
    tags=["chat"],
    responses={
        400: {"model": ErrorResponse, "description": "Unknown tier or provider"},
        401: {"model": ErrorResponse, "description": "Missing or invalid API key"},
        422: {"description": "Validation error"},
        429: {"model": ErrorResponse, "description": "Upstream rate limit"},
        502: {"model": ErrorResponse, "description": "Upstream provider error"},
        503: {"model": ErrorResponse, "description": "Upstream unreachable"},
        504: {"model": ErrorResponse, "description": "Upstream timeout"},
    },
)
async def chat(payload: ChatRequest) -> ChatResponse:
    """
    Send a message to an LLM. The router picks the provider.

    The route itself still knows nothing about Groq or Gemini — it hands
    the request to the router and shapes whatever comes back. Adding a
    third provider requires zero changes to this function.
    """
    result = await router.generate(
        message=payload.message,
        provider=payload.provider,
        tier=payload.tier,
        model=payload.model,
    )

    return ChatResponse(
        response=result.text,
        provider=result.provider,
        model=result.model,
        usage=Usage.from_counts(result.input_tokens, result.output_tokens),
    )