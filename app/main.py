"""
Phase 2 — FastAPI service.

    Client -> FastAPI -> LLM -> Response

Run with:
    uvicorn app.main:app --reload

Then open http://127.0.0.1:8000/docs for the interactive API docs.
"""

from fastapi import Depends, FastAPI

from app.auth import require_api_key
from app.config import settings
from app.llm_client import generate_chat_response
from app.schemas import ChatRequest, ChatResponse, ErrorResponse

app = FastAPI(
    title="LLM Fallback Router",
    description="A minimal AI backend. Phase 2: single provider behind a REST API.",
    version="0.2.0",
)


@app.get("/health", tags=["system"])
async def health():
    """
    Unauthenticated liveness check.

    Every real backend needs one of these — load balancers and deploy
    platforms hit it to decide whether your service is alive.
    """
    return {"status": "ok", "model": settings.LLM_MODEL}


@app.post(
    "/v1/chat",
    response_model=ChatResponse,        # <- output is validated/filtered to this shape
    dependencies=[Depends(require_api_key)],  # <- auth runs before the body below
    tags=["chat"],
    responses={                          # <- documents the error shapes in /docs
        401: {"model": ErrorResponse, "description": "Missing or invalid API key"},
        422: {"description": "Validation error (e.g. empty message)"},
        429: {"model": ErrorResponse, "description": "Upstream rate limit"},
        502: {"model": ErrorResponse, "description": "Upstream provider error"},
        503: {"model": ErrorResponse, "description": "Upstream unreachable"},
        504: {"model": ErrorResponse, "description": "Upstream timeout"},
    },
)
async def chat(payload: ChatRequest) -> ChatResponse:
    """
    Send a message to the LLM and get its reply.

    Note how little happens here. That's intentional:
      - validation      -> handled by ChatRequest
      - authentication  -> handled by the dependency
      - provider errors -> handled inside generate_chat_response
    The route only wires things together. This is what keeps a backend
    maintainable as it grows.
    """
    return await generate_chat_response(
        message=payload.message,
        model=payload.model,
    )