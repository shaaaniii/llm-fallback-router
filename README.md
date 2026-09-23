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

# llm-fallback-router — Phase 3: Multiple Providers + Routing

## What it does

```
                       ┌──► Groq   (llama-3.1-8b-instant)
                       │
    Client → FastAPI → Router
                       │
                       └──► Gemini (gemini-2.5-flash)
```

One API, two backends. The client sends the same request shape and gets the
same response shape no matter who answered.

## Project structure

```
llm-fallback-router/
│
├── app/
│   ├── main.py                     # routes + error→HTTP translation
│   ├── config.py                   # .env, incl. the routing table
│   ├── schemas.py                  # request/response contract
│   ├── auth.py                     # X-API-Key dependency
│   ├── router.py                   # registry + tier→provider selection
│   └── providers/
│       ├── base.py                 # LLMProvider interface + normalized errors
│       ├── groq_provider.py        # adapter (uses groq SDK)
│       └── gemini_provider.py      # adapter (uses raw httpx)
│
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

## The three ideas in this phase

**1. Common interface.** `LLMProvider.generate()` returns a `ProviderResult`.
Every provider implements it. Nothing outside `providers/` knows Groq or
Gemini exist.

**2. Adapter pattern.** The two providers are genuinely incompatible:

```
Groq:    {"messages": [{"role":"user","content":"hi"}]}
         → response.choices[0].message.content

Gemini:  {"contents": [{"parts":[{"text":"hi"}]}]}
         → response.candidates[0].content.parts[0].text
```

The adapters absorb that difference. Groq uses its SDK; Gemini uses raw
`httpx` — on purpose, to show a provider is just an HTTP endpoint.

**3. Normalized errors.** `groq.RateLimitError` and Gemini's HTTP 429 both
become `ProviderRateLimited`. Routing logic never writes provider-specific
`except` blocks. Errors marked `RETRYABLE_ERRORS` in `base.py` are the ones
Phase 4 will use to trigger fallback.

## Install

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Configure

Both keys are free and need no card:

| Provider | Get key at |
|---|---|
| Groq | https://console.groq.com/keys |
| Gemini | https://aistudio.google.com/apikey |

```
SERVICE_API_KEY=pick-any-long-random-string

LLM_TIMEOUT=30
LLM_MAX_TOKENS=1024

GROQ_API_KEY=gsk_your_groq_key
GROQ_MODEL=llama-3.1-8b-instant

GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.5-flash

ROUTE_CHEAP=groq
ROUTE_POWERFUL=gemini
DEFAULT_TIER=cheap
```

**The routing table lives in `.env`, not in code.** Swapping which provider
serves `powerful` is a config edit and a restart.

**Only have one key?** The app still runs. Providers are registered only if
their key is present, and the unconfigured tier returns a clear 400.

## Run

```bash
uvicorn app.main:app --reload
```

Docs: http://127.0.0.1:8000/docs

## Endpoints

### `GET /health`
```json
{
  "status": "ok",
  "providers": ["gemini", "groq"],
  "routes": {"cheap": "groq", "powerful": "gemini"}
}
```

### `POST /v1/chat`
Header: `X-API-Key: <SERVICE_API_KEY>`

| Field | Required | Meaning |
|---|---|---|
| `message` | yes | The prompt |
| `tier` | no | `"cheap"` or `"powerful"` |
| `provider` | no | Force one, e.g. `"groq"`. Overrides tier |
| `model` | no | Override that provider's default model |

Sending both `tier` and `provider` is a 422 — they contradict each other.

**Request**
```json
{"message": "Explain RAG", "tier": "powerful"}
```

**Response**
```json
{
  "response": "RAG stands for Retrieval-Augmented Generation...",
  "provider": "gemini",
  "model": "gemini-2.5-flash",
  "usage": {"input_tokens": 12, "output_tokens": 74, "total_tokens": 86}
}
```

A Phase 2 client sending only `{"message": "..."}` still works — both new
fields are optional.

## Selection precedence

```
1. explicit `provider`   → use it
2. `tier`                → look up the routing table
3. neither               → DEFAULT_TIER
```

## Examples

```bash
KEY="dev-local-secret-change-me"
URL="http://127.0.0.1:8000/v1/chat"

# default tier
curl -X POST $URL -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"message":"Explain RAG"}'

# force the powerful tier
curl -X POST $URL -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"message":"Explain RAG","tier":"powerful"}'

# force a specific provider
curl -X POST $URL -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"message":"Explain RAG","provider":"gemini"}'
```

## Status codes

| Code | Meaning |
|---|---|
| 200 | Success |
| 400 | Unknown provider, or tier with no key configured |
| 401 | Missing/wrong `X-API-Key` |
| 422 | Validation failed (empty message, bad tier, tier+provider together) |
| 429 | Upstream rate limit |
| 502 | Upstream error (bad model, bad upstream key, malformed reply) |
| 503 | Upstream unreachable |
| 504 | Upstream timeout |

400 vs 422: 422 means the *shape* was wrong (caught by Pydantic); 400 means
the shape was valid but the requested route doesn't exist (caught by the router).

## Test checklist

- [ ] `GET /health` lists both providers
- [ ] `{"message":"hi"}` → 200, uses DEFAULT_TIER
- [ ] `tier: "cheap"` → 200, `provider: "groq"`
- [ ] `tier: "powerful"` → 200, `provider: "gemini"`
- [ ] `provider: "gemini"` → 200
- [ ] `provider: "nope"` → 400
- [ ] `tier: "turbo"` → 422
- [ ] `tier` + `provider` together → 422
- [ ] Break one key in `.env`, restart → that tier 502, the other still 200
- [ ] Remove one key entirely → app starts, that tier returns 400

## Adding a third provider

1. Write `app/providers/openai_provider.py` subclassing `LLMProvider`.
2. Register it in `Router._register_all()`.
3. Point a tier at it in `.env`.

`main.py` and `schemas.py` don't change. That's the payoff.

# llm-fallback-router — Phase 4 & 5: Fallback Routing → Production Gateway

## What changed

**Phase 4** made a single request resilient:

```
Request -> Provider A -> FAIL -> retry (backoff+jitter) -> FAIL -> Provider B -> SUCCESS
```

**Phase 5** wrapped that in everything a real gateway needs around it:

```
Client
 v
Authentication      (X-API-Key)
 v
Rate limiting        (per-key, per-minute)
 v
Request validation   (Pydantic)
 v
Routing               (tier/provider -> fallback chain)
 v
Provider A -> retry -> Fallback -> Provider B     <- Phase 4, unchanged
 v
Response
 v
Usage tracking + Cost tracking + Structured logging + Tracing
```

## Project structure

```
llm-fallback-router/
│
├── app/
│   ├── main.py              # the full pipeline above, wired together
│   ├── config.py            # every setting, all phases, in one place
│   ├── schemas.py           # request/response contract
│   ├── auth.py              # X-API-Key dependency          (Phase 2/3)
│   ├── rate_limit.py        # Redis + in-memory rate limiters (Phase 5)
│   ├── rate_limit_depen.py    # the FastAPI dependency for it   (Phase 5)
│   ├── retry.py             # exponential backoff + jitter    (Phase 4)
│   ├── circuit_breaker.py   # Redis + in-memory health stores (Phase 4)
│   ├── router.py            # fallback chains + retry + breaker (Phase 4)
│   ├── cost.py               # token -> USD calculation        (Phase 5)
│   ├── models.py             # SQLAlchemy RequestLog table     (Phase 5)
│   ├── db.py                  # async session management       (Phase 5)
│   ├── logging_config.py      # structlog JSON logging         (Phase 5)
│   ├── tracing.py             # OpenTelemetry setup            (Phase 5)
│   └── providers/
│       ├── base.py            # LLMProvider interface, normalized errors
│       ├── groq_provider.py
│       └── gemini_provider.py
│
├── alembic/                   # schema migrations (Phase 5)
│   ├── env.py
│   ├── script.py.mako
│   └── versions/0001_create_request_logs.py
├── alembic.ini
│
├── tests/                      # pytest suite (Phase 5)
│   ├── test_retry.py
│   ├── test_circuit_breaker.py
│   ├── test_cost.py
│   └── test_router.py
│
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml     # app + redis + postgres
│
├── .env
├── .gitignore
├── requirements.txt
├── pytest.ini
└── README.md
```

## Runs with ZERO external services by default

This matters for actually being able to develop it: `REDIS_URL` empty →
circuit breaker and rate limiter use in-memory stores. `DATABASE_URL`
defaults to a local SQLite file. You can run the whole gateway, retries,
fallback, and all, with nothing but `pip install` and your two free LLM
API keys. Redis and Postgres upgrade it to multi-process/production
without any code changes — just set the URLs.

## Install & run (no Docker needed)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Edit `.env` — same two free keys as before:

```
SERVICE_API_KEY=pick-any-long-random-string
GROQ_API_KEY=gsk_...        # console.groq.com/keys
GEMINI_API_KEY=...          # aistudio.google.com/apikey
```

Everything else in `.env` has a sane default. Then:

```bash
uvicorn app.main:app --reload
```

Docs: http://127.0.0.1:8000/docs

You'll see OpenTelemetry spans print to your console — that's the
zero-setup console exporter (see Observability below). Set
`OTEL_ENABLED=false` if it's too noisy for local dev.

## Run with Docker Compose (Redis + Postgres included)

```bash
cd docker
docker compose up --build
```

This starts the app, a Redis container, and a Postgres container, wired
together automatically. Then run migrations against the real database:

```bash
docker compose exec app alembic upgrade head
```

## PHASE 4 — Retry + Fallback + Circuit Breaker

### Retry vs. Fallback — two different mechanisms

- **Retry** = try the SAME provider again. For a transient blip (one
  dropped connection, one slow response).
- **Fallback** = move to a DIFFERENT provider. For when that provider is
  having a genuinely bad time and a sibling probably isn't.

`router.py`'s `generate()` does both: retry within a provider via
`retry.py`, fallback across providers via the chain in `.env`.

### Retryable vs. non-retryable errors

Defined in `providers/base.py`:

```python
RETRYABLE_ERRORS = (ProviderTimeout, ProviderUnavailable, ProviderRateLimited)
```

An auth error or a malformed-request error will fail identically on
attempt 2 — retrying wastes time. Those still trigger **fallback** to
the next provider (a different provider is a different failure mode),
just not a **retry** on the same one.

### Exponential backoff + jitter

```python
ceiling = min(max_delay, base_delay * (2 ** (attempt - 1)))
delay = random.uniform(0, ceiling)
```

Backoff alone still lets every failed request retry in lockstep — all
hitting the provider again at exactly 2s, 4s, 8s. **Jitter** (the random
`uniform`) spreads them out, preventing that "thundering herd."

### Circuit breaker

Three states via two Redis keys with TTLs:

| State | Meaning | Implementation |
|---|---|---|
| CLOSED | normal | absence of the `open` key |
| OPEN | skip this provider entirely | `open` key set, TTL = cooldown |
| HALF-OPEN | one trial request allowed | the moment the `open` key's TTL expires |

Configure via `.env`:
```
CB_FAILURE_THRESHOLD=3     # failures within the window before tripping
CB_WINDOW_SECONDS=60       # rolling window for counting failures
CB_COOLDOWN_SECONDS=30     # how long the circuit stays open
```

Retries handle a blip; the circuit breaker handles an **outage** — once
a provider is clearly down, every incoming request skips it instantly
instead of each one waiting through a full retry cycle before falling
back.

### Fallback chains

```
ROUTE_CHEAP=groq,gemini      # try groq first, gemini if groq fails
ROUTE_POWERFUL=gemini,groq
```

An explicit `provider` in the request bypasses the chain entirely (no
fallback) — the caller asked for that provider specifically.

## PHASE 5 — Production Gateway

### Rate limiting

Fixed-window counter per API key, in `rate_limit.py`. Redis: `INCR` a
key named for the current minute; first increment sets a 60s TTL — the
TTL rolling over IS the window reset. `RATE_LIMIT_PER_MINUTE` in `.env`.

### Cost tracking

`cost.py` has a price table (USD per 1M tokens) per provider/model.
**These numbers are illustrative** — provider pricing changes; check
each provider's current pricing page before relying on this for real
billing. What matters here is that the pipeline (tokens → cost →
logged) is correct, not that today's numbers stay accurate forever.

### Database persistence

Every request — success or failure — is logged to `request_logs`
(`models.py`). Writes are **best-effort**: a DB hiccup is logged and
swallowed, never breaks the response the caller is waiting on
(`_persist_log` in `main.py`).

`init_db()` auto-creates tables for local SQLite dev convenience. For
Postgres, use **Alembic migrations** instead — `init_db()` is skipped
in that path so migrations remain the single source of truth:

```bash
alembic upgrade head              # apply migrations
alembic revision -m "add X"       # create a new one after changing models.py
```

### Structured logging

`logging_config.py` configures `structlog` to emit one JSON object per
event instead of formatted sentences — the difference between "readable
in a terminal" and "queryable in Datadog/Loki months later." Every
request gets a `request_id` (middleware in `main.py`) that ties together
every log line for that one request, returned to the client as an
`X-Request-ID` header too.

### Distributed tracing (OpenTelemetry)

`tracing.py`. With no `OTEL_EXPORTER_OTLP_ENDPOINT` set, spans print to
console — you can see tracing working with zero infrastructure. Point
it at a real collector (Jaeger, Honeycomb, Grafana Tempo) by setting
that env var to ship spans there instead.

## Endpoints

### `GET /health`
```json
{"status": "ok", "providers": ["gemini", "groq"], "routes": {"cheap": ["groq", "gemini"], "powerful": ["gemini", "groq"]}}
```

### `POST /v1/chat`
Header: `X-API-Key: <SERVICE_API_KEY>`

Same request/response shape as Phase 3, plus `cost_usd` in the response:

```json
{
  "response": "RAG stands for...",
  "provider": "groq",
  "model": "llama-3.1-8b-instant",
  "usage": {"input_tokens": 12, "output_tokens": 74, "total_tokens": 86},
  "cost_usd": 0.0000068
}
```

## Status codes

| Code | Meaning |
|---|---|
| 200 | Success |
| 400 | Unknown provider, or tier with no key configured |
| 401 | Missing/wrong `X-API-Key` |
| 422 | Validation failed |
| 429 | Rate limit — either your own limit, or every provider tried hit its upstream limit |
| 502 | Every provider in the chain failed (`FallbackExhausted`), or a single explicit provider errored |
| 503 | Provider unreachable |
| 504 | Provider timed out |

## Testing

```bash
pytest -m pytest -v
```

21 tests, all running against fakes/in-memory stores — no network, no
real API keys, no Redis, no Postgres required. Covers: retry succeeds
after N failures, retry gives up after max attempts, non-retryable
errors skip retry, circuit breaker trips/resets/half-opens, cost
calculation including unknown-model fallback, and router fallback
chains including circuit-open-skip and total-exhaustion.

## Manual test checklist

- [ ] `GET /health` lists providers and the routing table
- [ ] Normal request succeeds, returns `cost_usd`
- [ ] Break `GROQ_API_KEY`, keep `GEMINI_API_KEY` valid, restart → `tier: cheap` request still succeeds (falls back to gemini), response `provider` says `"gemini"`
- [ ] Break BOTH keys → 502 `FallbackExhausted`
- [ ] Send >`RATE_LIMIT_PER_MINUTE` requests in one minute → 429 with `Retry-After` header
- [ ] Check `local.db` (or Postgres) has a row per request, including failed ones
- [ ] Response includes `X-Request-ID` header; same ID appears in the structured log lines for that request

## What you learned, and where

| Concept | File |
|---|---|
| Retryable vs non-retryable errors | `providers/base.py` `RETRYABLE_ERRORS` |
| Exponential backoff + jitter | `retry.py` |
| Failover / fallback chains | `router.py` `_candidates`, `generate` |
| Circuit breaker + Redis TTL | `circuit_breaker.py` |
| Provider health | `circuit_breaker.py` `HealthStore` |
| Rate limiting | `rate_limit.py`, `rate_limit_dep.py` |
| Token/cost calculation | `cost.py` |
| Database persistence | `models.py`, `db.py` |
| Migrations | `alembic/` |
| Structured logging | `logging_config.py` |
| Observability (tracing) | `tracing.py` |
| Testing | `tests/` |
| Docker / Compose | `docker/` |

## This is now portfolio-ready

At this point the project demonstrates: a provider abstraction (adapter
pattern), resilience engineering (retry/backoff/jitter/circuit breaking),
a real gateway pipeline (auth → rate limit → validate → route → observe),
persistence with migrations, structured observability, and a test suite
that runs without any live infrastructure. That's the actual shape of
production LLM infra — not just "I called an API."