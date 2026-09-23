"""
Configuration. Every phase-4/5 knob lives here, with defaults that let the
whole app run with ZERO external services (no Redis, no Postgres) for local
development — Redis/Postgres upgrade it automatically when their URLs are set.
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- Our own API's auth ---
    SERVICE_API_KEY: str = os.getenv("SERVICE_API_KEY", "")

    # --- Shared LLM request limits ---
    LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "30"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "1024"))

    # --- Provider A: Groq ---
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    # --- Provider B: Gemini ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # --- Routing: tier -> ORDERED fallback chain (first = primary) ---
    ROUTE_CHEAP: list[str] = [p.strip() for p in os.getenv("ROUTE_CHEAP", "groq,gemini").split(",") if p.strip()]
    ROUTE_POWERFUL: list[str] = [p.strip() for p in os.getenv("ROUTE_POWERFUL", "gemini,groq").split(",") if p.strip()]
    DEFAULT_TIER: str = os.getenv("DEFAULT_TIER", "cheap")

    # --- Phase 4: retry ---
    RETRY_MAX_ATTEMPTS: int = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
    RETRY_BASE_DELAY: float = float(os.getenv("RETRY_BASE_DELAY", "0.5"))
    RETRY_MAX_DELAY: float = float(os.getenv("RETRY_MAX_DELAY", "8"))

    # --- Phase 4: circuit breaker ---
    CB_FAILURE_THRESHOLD: int = int(os.getenv("CB_FAILURE_THRESHOLD", "3"))
    CB_WINDOW_SECONDS: float = float(os.getenv("CB_WINDOW_SECONDS", "60"))
    CB_COOLDOWN_SECONDS: float = float(os.getenv("CB_COOLDOWN_SECONDS", "30"))

    # --- Phase 4/5: Redis (optional — falls back to in-memory if unset) ---
    REDIS_URL: str | None = os.getenv("REDIS_URL") or None

    # --- Phase 5: rate limiting ---
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

    # --- Phase 5: database (defaults to a local SQLite file — zero setup) ---
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./local.db")

    # --- Phase 5: observability ---
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or None
    OTEL_ENABLED: bool = os.getenv("OTEL_ENABLED", "true").lower() == "true"


settings = Settings()

if not settings.SERVICE_API_KEY:
    print("ERROR: SERVICE_API_KEY missing. Add it to .env — see README.md")
    sys.exit(1)

if not (settings.GROQ_API_KEY or settings.GEMINI_API_KEY):
    print("ERROR: no provider keys found. Set GROQ_API_KEY and/or GEMINI_API_KEY in .env")
    sys.exit(1)