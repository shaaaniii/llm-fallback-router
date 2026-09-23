"""
PHASE 5 — Rate limit dependency.

Runs AFTER auth (it needs the validated API key to know whose bucket to
count against) and BEFORE the route body. Same `Depends()` pattern as
auth.py — this is why splitting auth into its own dependency in Phase 2
paid off: the pipeline order (auth -> rate limit -> validation -> routing)
is just the order dependencies are listed on the route.
"""

from fastapi import Depends, HTTPException, Request

from app.auth import require_api_key
from app.config import settings


async def enforce_rate_limit(request: Request, api_key: str = Depends(require_api_key)) -> None:
    limiter = request.app.state.rate_limiter
    allowed, remaining = await limiter.check(api_key, settings.RATE_LIMIT_PER_MINUTE)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit of {settings.RATE_LIMIT_PER_MINUTE} requests/minute exceeded.",
            headers={"Retry-After": "60"},
        )