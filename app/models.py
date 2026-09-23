"""
PHASE 5 — Database schema.

One table: every request that hit /v1/chat, success or failure. This is
the raw material for usage tracking, cost dashboards, and debugging
"why did provider X fail at 3am" after the fact.
"""

import datetime
import uuid

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RequestLog(Base):
    __tablename__ = "request_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    # What was requested
    tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    requested_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # What actually happened
    status: Mapped[str] = mapped_column(String(20))  # "success" | "error"
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attempted_providers: Mapped[str | None] = mapped_column(String(200), nullable=True)  # "groq,gemini"

    # Usage + cost
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Performance + errors
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<RequestLog {self.id} {self.status} provider={self.provider}>"