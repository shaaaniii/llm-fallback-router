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