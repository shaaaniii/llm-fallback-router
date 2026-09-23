"""
PHASE 5 — Cost tracking.

Prices are USD per 1 million tokens. THESE NUMBERS ARE ILLUSTRATIVE —
provider pricing changes and varies by model tier; before relying on this
for real billing, replace PRICING with numbers copied from each provider's
current pricing page. What matters for the portfolio piece is that the
pipeline (usage in -> cost out -> logged) exists and is correct arithmetic,
not that today's numbers are exactly right forever.
"""

from dataclasses import dataclass

# USD per 1,000,000 tokens. Fallback "default" entry used for any model
# name not explicitly listed under that provider.
PRICING: dict[str, dict[str, dict[str, float]]] = {
    "groq": {
        "default": {"input": 0.05, "output": 0.08},
    },
    "gemini": {
        "default": {"input": 0.075, "output": 0.30},
    },
}


@dataclass(frozen=True)
class CostBreakdown:
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float


def calculate_cost(
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> CostBreakdown | None:
    """Returns None when token counts aren't available — can't price what wasn't reported."""
    if input_tokens is None or output_tokens is None:
        return None

    provider_prices = PRICING.get(provider, {})
    rates = provider_prices.get(model, provider_prices.get("default"))
    if rates is None:
        return None

    input_cost = (input_tokens / 1_000_000) * rates["input"]
    output_cost = (output_tokens / 1_000_000) * rates["output"]
    return CostBreakdown(
        input_cost_usd=round(input_cost, 8),
        output_cost_usd=round(output_cost, 8),
        total_cost_usd=round(input_cost + output_cost, 8),
    )