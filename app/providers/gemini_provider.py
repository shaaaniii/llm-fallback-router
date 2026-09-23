"""
Gemini adapter — uses raw `httpx`, no SDK.

Deliberate choice: this shows that a provider is just an HTTP endpoint.
Gemini's wire format is nothing like Groq's —

    Groq:    {"messages": [{"role": "user", "content": "hi"}]}
             -> response.choices[0].message.content

    Gemini:  {"contents": [{"parts": [{"text": "hi"}]}]}
             -> response.candidates[0].content.parts[0].text

...yet both come out of `generate()` as the same `ProviderResult`.
That difference being invisible to the rest of the app IS the adapter pattern.
"""

import httpx

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

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, default_model: str, timeout: float, max_tokens: int):
        self.default_model = default_model
        self.max_tokens = max_tokens
        self._api_key = api_key
        # Reusable connection pool — same reasoning as Groq's single client.
        self._client = httpx.AsyncClient(timeout=timeout)

    async def generate(self, message: str, model: str | None = None) -> ProviderResult:
        model_name = model or self.default_model
        url = f"{BASE_URL}/{model_name}:generateContent"

        payload = {
            "contents": [{"parts": [{"text": message}]}],
            "generationConfig": {"maxOutputTokens": self.max_tokens},
        }

        try:
            resp = await self._client.post(
                url,
                json=payload,
                headers={"x-goog-api-key": self._api_key},
            )
        except httpx.TimeoutException as e:
            raise ProviderTimeout("request timed out", self.name) from e
        except httpx.RequestError as e:
            raise ProviderUnavailable(f"connection failed: {e}", self.name) from e

        # --- Translate HTTP status codes -> normalized errors -------------
        if resp.status_code in (401, 403):
            raise ProviderAuthError("credentials rejected", self.name)
        if resp.status_code == 429:
            raise ProviderRateLimited("rate limit reached", self.name)
        if 400 <= resp.status_code < 500:
            raise ProviderBadRequest(f"{resp.status_code}: {resp.text[:200]}", self.name)
        if resp.status_code >= 500:
            raise ProviderUnavailable(f"{resp.status_code}", self.name)

        # --- Parse Gemini's nested response shape -------------------------
        try:
            data = resp.json()
        except ValueError as e:
            raise ProviderBadResponse("response was not valid JSON", self.name) from e

        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as e:
            # Commonly happens when the prompt was blocked by safety filters.
            reason = data.get("promptFeedback", {}).get("blockReason")
            if reason:
                raise ProviderBadRequest(f"blocked: {reason}", self.name) from e
            raise ProviderBadResponse("unexpected response shape", self.name) from e

        usage = data.get("usageMetadata", {})
        return ProviderResult(
            text=text,
            provider=self.name,
            model=model_name,
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
        )

    async def aclose(self) -> None:
        await self._client.aclose()