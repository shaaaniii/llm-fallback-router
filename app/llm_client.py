"""
The LLM layer.

This is Phase 1's ask_llm() function, with two changes:
  1. It is ASYNC (uses AsyncGroq) so FastAPI can serve other requests
     while this one waits on the network.
  2. Instead of print()-ing errors, it RAISES HTTPException so FastAPI
     turns them into proper HTTP status codes.

Keeping this in its own file matters: Phase 3 swaps this single module
for a multi-provider router without touching main.py at all.
"""
import groq
from openai import AsyncOpenAI
from fastapi import HTTPException

from app.config import settings
from app.schemas import ChatResponse, Usage

# One client for the whole app lifetime.
# Creating a client per request would waste connections.
client = groq.AsyncGroq(api_key=settings.LLM_API_KEY)


async def generate_chat_response(message: str, model: str | None = None) -> ChatResponse:
    """
    Send one message to the LLM and return a validated ChatResponse.

    Raises HTTPException on any failure — FastAPI converts that into
    a JSON error response with the right status code.
    """
    model_name = model or settings.LLM_MODEL

    try:
        # `await` = "pause this request here, let the server handle others,
        #            resume when the provider replies"
        completion = await client.chat.completions.create(
            model=model_name,
            max_tokens=settings.LLM_MAX_TOKENS,
            messages=[{"role": "user", "content": message}],
            timeout=settings.LLM_TIMEOUT,
        )

    # --- Map provider errors -> HTTP status codes ------------------------
    except groq.AuthenticationError:
        # 502: the client's request was fine; OUR upstream credential is broken.
        raise HTTPException(
            status_code=502,
            detail="Upstream provider rejected the server's credentials.",
        )

    except groq.APITimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Upstream provider timed out.",
        )

    except groq.APIConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Could not reach the upstream provider.",
        )

    except groq.RateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Rate limit reached at the upstream provider. Try again shortly.",
        )

    except groq.APIStatusError as e:
        # e.g. 404 for an unknown model name — surface the real reason.
        raise HTTPException(
            status_code=502,
            detail=f"Upstream provider error ({e.status_code}): {e.message}",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error while generating a response: {e}",
        )

    # --- Extract the useful parts ----------------------------------------
    try:
        text = completion.choices[0].message.content
    except (IndexError, AttributeError):
        raise HTTPException(
            status_code=502,
            detail="Upstream provider returned a malformed response.",
        )

    usage = None
    if completion.usage:
        usage = Usage(
            input_tokens=completion.usage.prompt_tokens,
            output_tokens=completion.usage.completion_tokens,
            total_tokens=completion.usage.total_tokens,
        )

    return ChatResponse(response=text, model=model_name, usage=usage)