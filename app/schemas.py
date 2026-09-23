"""
Pydantic models = the contract of your API.

Phase 3 additions: `tier` and `provider` on the request, `provider` on the
response. Note that BOTH request fields are optional — a Phase 2 client
sending only {"message": "..."} still works unchanged. Backwards
compatibility matters once anything is calling your API.
"""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Prompt = Annotated[
    str,
    Field(
        min_length=1,
        max_length=8_000,
        description="The user's prompt to send to the LLM.",
    ),
]

TokenCount = Annotated[int, Field(ge=0, description="Token count (never negative).")]

# Literal gives you validation AND a dropdown in /docs for free.
# An invalid tier is rejected at the schema layer, before routing runs.
Tier = Literal["cheap", "powerful"]


class ChatRequest(BaseModel):
    """What the client must POST to /v1/chat."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"message": "Explain RAG"},
                {"message": "Explain RAG", "tier": "powerful"},
            ]
        },
    )

    message: Prompt

    tier: Tier | None = Field(
        default=None,
        description="Routing hint: 'cheap' or 'powerful'. Defaults to the server's DEFAULT_TIER.",
    )

    provider: str | None = Field(
        default=None,
        max_length=50,
        description="Force a specific provider (e.g. 'groq'). Overrides tier. Usually leave unset.",
    )

    model: str | None = Field(
        default=None,
        max_length=100,
        description="Override the chosen provider's default model.",
    )

    @model_validator(mode="after")
    def _warn_on_conflict(self) -> Self:
        """
        `provider` overrides `tier`, so sending both is contradictory.
        Rejecting it is kinder than silently ignoring one — the caller
        finds out now instead of wondering why `tier` had no effect.
        """
        if self.provider and self.tier:
            raise ValueError("Send either 'tier' or 'provider', not both.")
        return self


class Usage(BaseModel):
    """Token accounting."""

    model_config = ConfigDict(frozen=True)

    input_tokens: TokenCount
    output_tokens: TokenCount
    total_tokens: TokenCount

    @model_validator(mode="after")
    def _check_total(self) -> Self:
        expected = self.input_tokens + self.output_tokens
        if self.total_tokens != expected:
            raise ValueError(
                f"total_tokens ({self.total_tokens}) != input + output ({expected})"
            )
        return self

    @classmethod
    def from_counts(cls, input_tokens: int | None, output_tokens: int | None) -> "Usage | None":
        """Returns None if the provider didn't report usage."""
        if input_tokens is None or output_tokens is None:
            return None
        return cls(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        )


class ChatResponse(BaseModel):
    """
    What we send back.

    `provider` is reported for transparency and debugging — but the client
    is never REQUIRED to look at it. Same request shape, same response
    shape, whichever backend answered, however many providers were tried
    internally before one succeeded.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "response": "RAG stands for Retrieval-Augmented Generation...",
                    "provider": "groq",
                    "model": "llama-3.1-8b-instant",
                    "usage": {"input_tokens": 12, "output_tokens": 74, "total_tokens": 86},
                    "cost_usd": 0.00000682,
                }
            ]
        }
    )

    response: str = Field(description="The model's generated text.")
    provider: str = Field(description="Which provider actually served this request.")
    model: str = Field(description="The model that served this request.")
    usage: Usage | None = Field(default=None, description="Token usage, when reported.")
    cost_usd: float | None = Field(default=None, description="Estimated cost in USD for this request.")


class ErrorResponse(BaseModel):
    """Consistent error envelope for API errors."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"detail": "Invalid API key."}]}
    )

    detail: str = Field(description="Human-readable description of what failed.")