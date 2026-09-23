"""
Groq adapter — uses the official SDK.

Notice what this file does: takes Groq's SDK-specific behaviour and
exceptions, and converts them into our normalized `ProviderResult` /
`ProviderError`. Nothing outside this file knows the `groq` package exists.
"""

import groq

from app.providers.base import (
    LLMProvider,
    ProviderAuthError,
    ProviderBadRequest,
    ProviderBadResponse,
    ProviderError,
    ProviderRateLimited,
    ProviderResult,
    ProviderTimeout,
    ProviderUnavailable,
)


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, api_key: str, default_model: str, timeout: float, max_tokens: int):
        self.default_model = default_model
        self.timeout = timeout
        self.max_tokens = max_tokens
        # One client reused for the app's lifetime.
        self._client = groq.AsyncGroq(api_key=api_key)

    async def generate(self, message: str, model: str | None = None) -> ProviderResult:
        model_name = model or self.default_model

        try:
            completion = await self._client.chat.completions.create(
                model=model_name,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": message}],
                timeout=self.timeout,
            )

        # --- Translate Groq's exceptions -> our normalized ones -----------
        except groq.AuthenticationError as e:
            raise ProviderAuthError(str(e), self.name) from e
        except groq.APITimeoutError as e:
            raise ProviderTimeout("request timed out", self.name) from e
        except groq.APIConnectionError as e:
            raise ProviderUnavailable("could not connect", self.name) from e
        except groq.RateLimitError as e:
            raise ProviderRateLimited("rate limit reached", self.name) from e
        except groq.APIStatusError as e:
            # 4xx = we sent something wrong; 5xx = their problem.
            if 400 <= e.status_code < 500:
                raise ProviderBadRequest(f"{e.status_code}: {e.message}", self.name) from e
            raise ProviderUnavailable(f"{e.status_code}: {e.message}", self.name) from e
        except Exception as e:
            raise ProviderError(f"unexpected: {e}", self.name) from e

        # --- Normalize the response shape ---------------------------------
        try:
            text = completion.choices[0].message.content
        except (IndexError, AttributeError) as e:
            raise ProviderBadResponse("malformed response", self.name) from e

        if text is None:
            raise ProviderBadResponse("empty content", self.name)

        usage = completion.usage
        return ProviderResult(
            text=text,
            provider=self.name,
            model=model_name,
            input_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
            output_tokens=getattr(usage, "completion_tokens", None) if usage else None,
        )

    async def aclose(self) -> None:
        await self._client.close()