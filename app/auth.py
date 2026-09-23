"""
API authentication.

Pattern: a FastAPI "dependency". Any endpoint that declares
`dependencies=[Depends(require_api_key)]` will run this FIRST.
If it raises, the endpoint body never executes.

This is how you protect an endpoint without copy-pasting auth
checks into every route.
"""

import secrets
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import settings

# auto_error=False -> we handle the "missing header" case ourselves
# so we can return our own message instead of FastAPI's default.
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(provided_key: str | None = Security(api_key_header)) -> str:
    if not provided_key:
        raise HTTPException(
            status_code=401,
            detail="Missing X-API-Key header.",
        )

    # compare_digest instead of == : constant-time comparison,
    # so an attacker can't guess the key character-by-character by timing responses.
    if not secrets.compare_digest(provided_key, settings.SERVICE_API_KEY):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key.",
        )

    return provided_key