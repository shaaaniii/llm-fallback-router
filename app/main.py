"""
Phase 1 — Your First LLM Application
--------------------------------------
A tiny CLI that:
  1. Reads your Groq API key from a .env file (never hardcoded).
  2. Sends whatever you type to an LLM via Groq.
  3. Prints the generated text + token usage.
  4. Doesn't crash on bad input, bad keys, timeouts, or provider errors.

Flow:
    User input -> Python -> LLM (Groq API) -> Print response
"""

import os
import sys

from dotenv import load_dotenv
import groq


# ---------------------------------------------------------------------------
# Step 6: Load environment variables (.env -> environment -> Python)
# ---------------------------------------------------------------------------
load_dotenv()  # reads the .env file sitting next to this project and loads
               # its key=value pairs into os.environ

API_KEY = os.getenv("LLM_API_KEY")
MODEL_NAME = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")  # sane default
print("DEBUG MODEL:", MODEL_NAME)
print("DEBUG API KEY LOADED:", bool(API_KEY))

if not API_KEY:
    # Fail loudly and clearly at startup rather than deep inside a request.
    print("ERROR: LLM_API_KEY not found. Did you create a .env file?")
    print("See README.md for setup instructions.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Step 4/5: One function = one LLM request.
# This is the entire "how do I call an LLM" answer.
# ---------------------------------------------------------------------------
def ask_llm(client: groq.Groq, user_message: str):
    """
    Sends a single user message to the LLM and returns (text, usage_dict).
    Returns (None, None) if something went wrong (error already printed).
    """
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            max_tokens=1024,
            messages=[
                {"role": "user", "content": user_message}
            ],
            timeout=30.0,  # Step 7: don't hang forever
        )

    # --- Step 7: Handle the realistic failure modes -----------------------
    except groq.AuthenticationError:
        print("Error: your API key was rejected. Check LLM_API_KEY in .env.")
        return None, None

    except groq.APITimeoutError:
        print("Error: the request timed out. Try again in a moment.")
        return None, None

    except groq.APIConnectionError:
        print("Error: could not reach the provider. Check your internet connection.")
        return None, None

    except groq.RateLimitError:
        print("Error: rate limit hit. Wait a bit and try again.")
        return None, None

    except groq.APIStatusError as e:
        # Catch-all for other 4xx/5xx responses from the provider
        print(f"Error: provider returned an error (status {e.status_code}).")
        print(f"Details: {e.message}")
        return None, None

    except Exception as e:
        # Last-resort safety net so the program never crashes ugly
        print(f"Unexpected error: {e}")
        return None, None

    # --- Step 8: Extract the useful parts, don't dump the raw object ------
    try:
        generated_text = response.choices[0].message.content
    except (IndexError, AttributeError):
        print("Error: response came back in an unexpected/malformed shape.")
        return None, None

    usage = {
        "input_tokens": getattr(response.usage, "prompt_tokens", None),
        "output_tokens": getattr(response.usage, "completion_tokens", None),
    }
    if usage["input_tokens"] is not None and usage["output_tokens"] is not None:
        usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]
    else:
        usage["total_tokens"] = None

    return generated_text, usage


# ---------------------------------------------------------------------------
# Step 9: Turn it into a tiny interactive CLI
# ---------------------------------------------------------------------------
def main():
    client = groq.Groq(api_key=API_KEY)

    print("=" * 50)
    print("Tiny LLM CLI — type 'exit' or 'quit' to stop")
    print("=" * 50)

    while True:
        try:
            user_input = input("\n> Ask something: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break

        if user_input.lower() in ("exit", "quit"):
            print("Goodbye.")
            break

        # Step 10: handle the empty-input edge case explicitly
        if not user_input:
            print("(empty input — type a question first)")
            continue

        text, usage = ask_llm(client, user_input)

        if text is None:
            # Error already printed inside ask_llm; loop continues
            continue

        print(f"\nAnswer: {text}")

        if usage["total_tokens"] is not None:
            print("\nUsage:")
            print(f"  Input tokens:  {usage['input_tokens']}")
            print(f"  Output tokens: {usage['output_tokens']}")
            print(f"  Total tokens:  {usage['total_tokens']}")


if __name__ == "__main__":
    main()