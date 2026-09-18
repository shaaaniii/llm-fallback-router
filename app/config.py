"""
Central place for configuration.

Everything secret or environment-specific lives in .env and is read ONCE here.
The rest of the app imports `settings` instead of calling os.getenv() everywhere.
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()  # .env -> environment variables -> Python


class Settings:
    # --- LLM provider ---
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", " gpt-4o-mini")
    LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "30"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "1024"))

    # --- Our own API's auth ---
    # Clients must send this in the X-API-Key header to use our service.
    # This is OUR key for OUR API — completely separate from the Groq key.
    SERVICE_API_KEY: str = os.getenv("SERVICE_API_KEY", "")


settings = Settings()

# Fail fast and loudly at import time rather than on the first request.
if not settings.LLM_API_KEY:
    print("ERROR: LLM_API_KEY missing. Add it to .env — see README.md")
    sys.exit(1)

if not settings.SERVICE_API_KEY:
    print("ERROR: SERVICE_API_KEY missing. Add it to .env — see README.md")
    sys.exit(1)