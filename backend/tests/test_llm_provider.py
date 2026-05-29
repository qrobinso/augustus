import pytest
from app.services.llm.openrouter import OpenRouterProvider


def test_build_payload_includes_response_format():
    p = OpenRouterProvider(api_key="test", model="anthropic/claude-3.5-sonnet")
    rf = {"type": "json_schema", "json_schema": {"name": "x", "schema": {}}}
    payload = p._build_payload(
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=100, temperature=0.3, response_format=rf,
    )
    assert payload["response_format"] == rf
    assert payload["max_tokens"] == 100
    assert payload["temperature"] == 0.3


def test_build_payload_omits_response_format_when_none():
    p = OpenRouterProvider(api_key="test", model="anthropic/claude-3.5-sonnet")
    payload = p._build_payload(
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=100, temperature=0.3, response_format=None,
    )
    assert "response_format" not in payload
