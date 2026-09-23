"""
Configuration management.

Phase 2 had one provider, so config was flat. Now that routing rules and
per-provider credentials exist, config is where they're declared — NOT
hardcoded in the router.

Changing which provider serves "powerful" should be a .env edit and a
restart, not a code change.
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- Our own API's auth ---
    SERVICE_API_KEY: str = os.getenv("SERVICE_API_KEY", "")

    # --- Shared request limits ---
    LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "30"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "1024"))

    # --- Provider A: Groq ---
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    # --- Provider B: Gemini ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # --- Routing rules: tier -> provider name ---
    # This is the "rule-based routing" table. Rules live in config so the
    # mapping is visible and changeable without touching Python.
    ROUTE_CHEAP: str = os.getenv("ROUTE_CHEAP", "groq")
    ROUTE_POWERFUL: str = os.getenv("ROUTE_POWERFUL", "gemini")
    DEFAULT_TIER: str = os.getenv("DEFAULT_TIER", "cheap")


settings = Settings()

# Fail fast: at least one provider must be usable, and our own key must exist.
if not settings.SERVICE_API_KEY:
    print("ERROR: SERVICE_API_KEY missing. Add it to .env — see README.md")
    sys.exit(1)

if not (settings.GROQ_API_KEY or settings.GEMINI_API_KEY):
    print("ERROR: no provider keys found. Set GROQ_API_KEY and/or GEMINI_API_KEY in .env")
    sys.exit(1)