"""
PHASE 5 — The full gateway.

    Client
     v
    Authentication      (auth.py            - Depends(require_api_key))
     v
    Rate limiting        (rate_limit_dep.py  - Depends(enforce_rate_limit))
     v
    Request validation   (schemas.py         - ChatRequest, automatic)
     v
    Routing               (router.py         - tier/provider -> candidate chain)
     v
    Provider A -> retry -> Fallback -> Provider B   (router.py, Phase 4)
     v
    Response
     v
    Usage tracking + Cost tracking + Logging   (this file, after the call)

Run:
    uvicorn app.main:app --reload
Docs:
    http://127.0.0.1:8000/docs
"""

import time
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from app.cost import calculate_cost
from app.db import get_session, init_db
from app.logging_config import configure_logging, get_logger
from app.models import RequestLog
from app.providers.base import (
    ProviderAuthError,
    ProviderBadRequest,
    ProviderBadResponse,
    ProviderError,
    ProviderRateLimited,
    ProviderTimeout,
    ProviderUnavailable,
)
from app.rate_limit import build_rate_limiter
from app.rate_limit_depen import enforce_rate_limit
from app.router import FallbackExhausted, RoutingError, router
from app.schemas import ChatRequest, ChatResponse, ErrorResponse, Usage
from app.tracing import configure_tracing

configure_logging()
log = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()  # dev convenience; a real deploy uses Alembic instead
    app.state.rate_limiter = build_rate_limiter(_redis_url())
    log.info("startup", providers=router.available, routes=router.describe_routes())
    yield
    await router.aclose()


def _redis_url() -> str | None:
    from app.config import settings
    return settings.REDIS_URL


app = FastAPI(
    title="LLM Fallback Router",
    description="Phase 5: production-style gateway — auth, rate limiting, retry, "
    "fallback, circuit breaking, usage/cost tracking, structured logging, tracing.",
    version="0.5.0",
    lifespan=lifespan,
)

configure_tracing(app)  # no-op if OTEL_ENABLED=false


# ---------------------------------------------------------------------------
# Request ID middleware — every log line for one request shares this ID,
# so you can grep/query one request's full story across auth, routing,
# provider calls, and the final DB write.
# ---------------------------------------------------------------------------

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    import uuid
    request_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    structlog.contextvars.clear_contextvars()
    return response


# ---------------------------------------------------------------------------
# Exception handlers — normalized errors -> HTTP status codes, in one place.
# ---------------------------------------------------------------------------

_STATUS_MAP: list[tuple[type[ProviderError], int]] = [
    (ProviderRateLimited, 429),
    (ProviderTimeout, 504),
    (ProviderUnavailable, 503),
    (ProviderAuthError, 502),
    (ProviderBadRequest, 502),
    (ProviderBadResponse, 502),
]


@app.exception_handler(FallbackExhausted)
async def fallback_exhausted_handler(request: Request, exc: FallbackExhausted):
    log.warning("fallback_exhausted", attempted=exc.attempts)
    return JSONResponse(
        status_code=502,
        content={"detail": f"All providers failed: {', '.join(exc.attempts)}"},
    )


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
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["system"])
async def health():
    return {
        "status": "ok",
        "providers": router.available,
        "routes": router.describe_routes(),
    }


@app.post(
    "/v1/chat",
    response_model=ChatResponse,
    dependencies=[Depends(enforce_rate_limit)],  # auth runs first inside this dependency
    tags=["chat"],
    responses={
        400: {"model": ErrorResponse, "description": "Unknown tier or provider"},
        401: {"model": ErrorResponse, "description": "Missing or invalid API key"},
        422: {"description": "Validation error"},
        429: {"model": ErrorResponse, "description": "Rate limit or upstream rate limit"},
        502: {"model": ErrorResponse, "description": "All providers failed"},
        503: {"model": ErrorResponse, "description": "Upstream unreachable"},
        504: {"model": ErrorResponse, "description": "Upstream timeout"},
    },
)
async def chat(payload: ChatRequest) -> ChatResponse:
    """
    The whole pipeline in one function:
    routing+retry+fallback happen inside router.generate(); everything
    below that line is Phase 5's observability layer wrapped around it.
    """
    started = time.monotonic()
    log_row = RequestLog(tier=payload.tier, requested_provider=payload.provider)

    try:
        result, meta = await router.generate(
            message=payload.message,
            provider=payload.provider,
            tier=payload.tier,
            model=payload.model,
        )
    except (ProviderError, FallbackExhausted, RoutingError) as exc:
        # Log the failure, then re-raise so the exception handlers above
        # still produce the HTTP response. Observability must never
        # swallow an error the caller needs to see.
        log_row.status = "error"
        log_row.error_detail = str(exc)
        log_row.latency_ms = round((time.monotonic() - started) * 1000, 1)
        await _persist_log(log_row)
        log.warning("chat_failed", error=str(exc), tier=payload.tier)
        raise

    usage = Usage.from_counts(result.input_tokens, result.output_tokens)
    cost = calculate_cost(result.provider, result.model, result.input_tokens, result.output_tokens)

    log_row.status = "success"
    log_row.provider = result.provider
    log_row.model = result.model
    log_row.attempted_providers = ",".join(meta["attempted"])
    log_row.input_tokens = result.input_tokens
    log_row.output_tokens = result.output_tokens
    log_row.cost_usd = cost.total_cost_usd if cost else None
    log_row.latency_ms = meta["latency_ms"]
    await _persist_log(log_row)

    log.info(
        "chat_completed",
        provider=result.provider,
        model=result.model,
        attempted=meta["attempted"],
        latency_ms=meta["latency_ms"],
        cost_usd=log_row.cost_usd,
    )

    return ChatResponse(
        response=result.text,
        provider=result.provider,
        model=result.model,
        usage=usage,
        cost_usd=cost.total_cost_usd if cost else None,
    )


async def _persist_log(row: RequestLog) -> None:
    """
    Best-effort persistence: a DB hiccup must never break the API response
    the caller is waiting on. Log the failure and move on.
    """
    try:
        async with get_session() as session:
            session.add(row)
            await session.commit()
    except Exception as e:  # pragma: no cover - defensive path
        log.error("log_persist_failed", error=str(e))