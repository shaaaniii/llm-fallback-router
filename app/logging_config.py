"""
PHASE 5 — Structured logging.

Plain `print()` or default logging gives you unstructured text — great to
read in a terminal, painful to query later ("show me every request that
took >2s and used gemini last Tuesday"). Structured logging emits JSON:
one object per event, with consistent fields, so tools like Datadog,
Grafana Loki, or even `jq` on a log file can filter and aggregate it.

We use structlog for this. Each log call is a structured EVENT with
key=value context attached, not a formatted sentence.
"""

import logging
import sys

import structlog

from app.config import settings


def configure_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.LOG_LEVEL,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,  # picks up request_id, etc.
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(settings.LOG_LEVEL)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "app"):
    return structlog.get_logger(name)