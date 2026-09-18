"""
Pydantic models = the contract of your API.

Request models  -> validate what comes IN
Response models -> define what goes OUT

FastAPI reads these to auto-generate the interactive docs at /docs.
"""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Reusable constrained types.
# Defining the constraint once means /v1/chat, a future /v1/complete, and any
# batch endpoint all enforce identical rules -- they can't drift apart.
# ---------------------------------------------------------------------------

Prompt = Annotated[
    str,
    Field(
        min_length=1,
        max_length=8_000,
        description="The user's prompt to send to the LLM.",
    ),
]

TokenCount = Annotated[int, Field(ge=0, description="Token count (never negative).")]


class ChatRequest(BaseModel):
    """
    What the client must POST to /v1/chat.
    """

    model_config = ConfigDict(
        # Trim surrounding whitespace BEFORE min_length runs, so a body of
        # {"message": "   "} is rejected instead of sending a blank prompt
        # to the provider and paying tokens for nothing.
        str_strip_whitespace=True,
        # Reject unknown fields. {"mesage": "..."} now returns a clear 422
        # naming the typo, instead of silently dropping it.
        extra="forbid",
        json_schema_extra={"examples": [{"message": "Explain RAG"}]},
    )

    message: Prompt

    model: str | None = Field(
        default=None,
        max_length=100,  # bound it -- this string is forwarded upstream
        description="Optional model override. Defaults to the server's configured model.",
    )


class Usage(BaseModel):
    """Token accounting."""

    model_config = ConfigDict(frozen=True)  # usage is a fact, not mutable state

    input_tokens: TokenCount
    output_tokens: TokenCount
    total_tokens: TokenCount

    @model_validator(mode="after")
    def _check_total(self) -> Self:
        """
        Guard against a provider reporting inconsistent numbers.
        Catches the bug at the boundary rather than after it has been
        logged, billed against, or shown to a user.
        """
        expected = self.input_tokens + self.output_tokens
        if self.total_tokens != expected:
            raise ValueError(
                f"total_tokens ({self.total_tokens}) != "
                f"input + output ({expected})"
            )
        return self

    @classmethod
    def from_counts(cls, input_tokens: int, output_tokens: int) -> Self:
        """Build a Usage without the caller having to compute the total."""
        return cls(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        )


class ChatResponse(BaseModel):
    """
    What we send back.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "response": "RAG stands for Retrieval-Augmented Generation...",
                    "model": "llama-3.3-70b-versatile",
                    "usage": {
                        "input_tokens": 12,
                        "output_tokens": 74,
                        "total_tokens": 86,
                    },
                }
            ]
        }
    )

    response: str = Field(description="The model's generated text.")
    model: str = Field(description="The model that actually served this request.")
    usage: Usage | None = Field(
        default=None,
        description="Token usage, when the provider reports it.",
    )


class ErrorResponse(BaseModel):
    """Consistent error envelope for API errors."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"detail": "Invalid API key."}]}
    )

    detail: str = Field(description="Human-readable description of what failed.")