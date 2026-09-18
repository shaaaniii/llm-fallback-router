# llm-fallback-router — Phase 1: Your First LLM Application

## What it does

A minimal command-line program that sends whatever you type to an LLM
(via the Groq API, free tier — no card required) and prints back the
generated answer, along with token usage (input / output / total).

This is the "hello world" of LLM applications: one function that sends a
request and reads a response. Everything later (fallback routing, multiple
providers, retries) gets built on top of this.

```
User input -> Python -> LLM (Groq API) -> Print response
```

## Project structure

```
llm-fallback-router/
│
├── app/
│   └── main.py        # the entire program
│
├── .env                # your API key (never committed)
├── .gitignore
├── requirements.txt
└── README.md
```

## How to install it

1. Clone/download this folder, then move into it:
   ```bash
   cd llm-fallback-router
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv

   # Windows
   .venv\Scripts\activate

   # macOS / Linux
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## How to configure the API key

1. Get a free API key from [Groq Console](https://console.groq.com/keys)
   (sign in, no card required).
2. Open `.env` in this folder and set:
   ```
   LLM_API_KEY=gsk_your-real-key-here
   LLM_MODEL=llama-3.3-70b-versatile
   ```
3. Make sure `.env` is listed in `.gitignore` (it already is) so your key
   never gets pushed to GitHub.

**Never hardcode the key in Python.**

Bad:
```python
api_key = "sk-ant-abc123..."
```

Good — key lives in `.env`, Python just reads it:
```python
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("LLM_API_KEY")
```

## How to run it

```bash
python app/main.py
```

## Example input/output

```
==================================================
Tiny LLM CLI — type 'exit' or 'quit' to stop
==================================================

> Ask something: What is an API?

Answer: An API (Application Programming Interface) is a set of rules
that lets one piece of software talk to another...

Usage:
  Input tokens:  8
  Output tokens: 41
  Total tokens:  49

> Ask something: exit
Goodbye.
```

## Error handling covered

The program will not crash ugly on:
- Invalid / missing API key
- Empty input
- Request timeout
- Provider/network failure
- Rate limiting
- Malformed response

## Manual test checklist

- [ ] Normal question ("What is RAG?")
- [ ] Empty input (just press Enter)
- [ ] Very long input (paste a big paragraph)
- [ ] Invalid API key (temporarily break `.env`, confirm clean error message)
- [ ] No internet / provider down (disconnect Wi-Fi, confirm clean error message)

## What's next (Phase 2+)

This program hardcodes one provider (Anthropic). Later phases will add:
- Multiple providers with automatic fallback
- Retry logic with backoff
- A FastAPI wrapper around this same core function

# llm-fallback-router — Phase 2: FastAPI Service

## What it does

Phase 1 was `Terminal → Python → LLM`.
Phase 2 is:

```
Client → FastAPI → LLM → Response
```

You now have an **AI backend** — any client (curl, a React app, Postman,
another service) can POST a message and get an LLM answer as JSON.

## Project structure

```
llm-fallback-router/
│
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app + routes (thin — just wiring)
│   ├── config.py        # reads .env once, fails fast if keys missing
│   ├── schemas.py       # Pydantic request/response models
│   ├── llm_client.py    # async LLM call + provider error → HTTP status mapping
│   └── auth.py          # X-API-Key dependency
│
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

**Why split into files?** Phase 3 replaces `llm_client.py` with a multi-provider
router. Because routes, schemas, auth, and the LLM call are separate, that swap
won't touch `main.py`.

## Install

```bash
cd llm-fallback-router
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Configure

Edit `.env`:

```
LLM_API_KEY=gsk_your_real_groq_key      # from console.groq.com/keys
LLM_MODEL=llama-3.3-70b-versatile
LLM_TIMEOUT=30
LLM_MAX_TOKENS=1024

SERVICE_API_KEY=pick-any-long-random-string
```

**Two different keys — don't confuse them:**

| Key | Who uses it | Purpose |
|---|---|---|
| `LLM_API_KEY` | Your server → Groq | Authenticates *you* to the provider |
| `SERVICE_API_KEY` | Client → your server | Authenticates *callers* to your API |

## Run

```bash
uvicorn app.main:app --reload
```

- API: http://127.0.0.1:8000
- Interactive docs: http://127.0.0.1:8000/docs ← try requests straight from the browser

`--reload` restarts the server on every file save. Development only.

## Endpoints

### `GET /health`
No auth. Returns `{"status": "ok", "model": "..."}`.

### `POST /v1/chat`
Requires header `X-API-Key: <your SERVICE_API_KEY>`.

**Request**
```json
{
  "message": "Explain RAG"
}
```

**Response**
```json
{
  "response": "RAG stands for Retrieval-Augmented Generation...",
  "model": "llama-3.3-70b-versatile",
  "usage": {
    "input_tokens": 12,
    "output_tokens": 74,
    "total_tokens": 86
  }
}
```

## Example calls

**curl (macOS/Linux)**
```bash
curl -X POST http://127.0.0.1:8000/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-local-secret-change-me" \
  -d '{"message": "Explain RAG"}'
```

**PowerShell (Windows)**
```powershell
curl.exe -X POST http://127.0.0.1:8000/v1/chat `
  -H "Content-Type: application/json" `
  -H "X-API-Key: dev-local-secret-change-me" `
  -d '{\"message\": \"Explain RAG\"}'
```

**Python client**
```python
import httpx

r = httpx.post(
    "http://127.0.0.1:8000/v1/chat",
    headers={"X-API-Key": "dev-local-secret-change-me"},
    json={"message": "Explain RAG"},
    timeout=60,
)
print(r.json()["response"])
```

## Status codes

| Code | Meaning |
|---|---|
| 200 | Success |
| 401 | Missing or wrong `X-API-Key` |
| 422 | Validation failed (empty message, missing field, too long) |
| 429 | Groq rate limit hit |
| 502 | Groq returned an error (bad model name, bad upstream key) |
| 503 | Couldn't reach Groq |
| 504 | Groq timed out |

Note the split: **4xx = the caller's fault, 5xx = our/upstream fault.**
A broken `LLM_API_KEY` is a 502, not a 401 — the *client* did nothing wrong.

## Test checklist

- [ ] `GET /health` returns 200
- [ ] Valid request with correct key → 200 + answer
- [ ] No `X-API-Key` header → 401
- [ ] Wrong `X-API-Key` → 401
- [ ] `{"message": ""}` → 422
- [ ] `{}` (missing field) → 422
- [ ] 9000-character message → 422
- [ ] Break `LLM_API_KEY` in `.env`, restart → 502
- [ ] Disconnect internet → 503

## What you learned

| Concept | Where it lives |
|---|---|
| REST API / POST endpoint | `main.py` `@app.post("/v1/chat")` |
| Request model + validation | `schemas.py` `ChatRequest` |
| Response model | `schemas.py` `ChatResponse` |
| async / await | `llm_client.py` `await client.chat...` |
| HTTP exceptions | `llm_client.py` `raise HTTPException(...)` |
| API authentication | `auth.py` + `Depends(require_api_key)` |
| Project structure | the `app/` split above |

## Next (Phase 3)

Add a second provider and fall back automatically when the first fails —
the 429/502/503/504 cases above become *triggers to retry elsewhere*
instead of errors returned to the client.