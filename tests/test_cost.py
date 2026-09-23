"""Tests for app/cost.py."""

from app.cost import calculate_cost


def test_calculates_cost_for_known_provider():
    result = calculate_cost("groq", "llama-3.1-8b-instant", 1_000_000, 1_000_000)
    assert result is not None
    assert result.input_cost_usd == 0.05
    assert result.output_cost_usd == 0.08
    assert round(result.total_cost_usd, 2) == 0.13


def test_falls_back_to_default_rate_for_unknown_model():
    result = calculate_cost("groq", "some-new-model-not-in-table", 1_000_000, 0)
    assert result is not None
    assert result.input_cost_usd == 0.05  # uses "default" entry


def test_returns_none_for_unknown_provider():
    result = calculate_cost("unknown-provider", "x", 100, 100)
    assert result is None


def test_returns_none_when_tokens_missing():
    assert calculate_cost("groq", "m", None, 100) is None
    assert calculate_cost("groq", "m", 100, None) is None


def test_zero_tokens_is_zero_cost():
    result = calculate_cost("groq", "llama-3.1-8b-instant", 0, 0)
    assert result.total_cost_usd == 0.0