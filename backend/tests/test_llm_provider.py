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


def test_extract_content_returns_string():
    p = OpenRouterProvider(api_key="test", model="m")
    data = {"choices": [{"message": {"content": "hello"}}]}
    assert p._extract_content(data) == "hello"


def test_extract_content_null_raises_clear_error():
    # Some models/providers return content: null (e.g. reasoning models or
    # filtered completions). That must surface as an actionable error, not
    # a TypeError deep in the logging code.
    p = OpenRouterProvider(api_key="test", model="m")
    data = {"choices": [{"message": {"content": None}, "finish_reason": "length"}]}
    with pytest.raises(ValueError) as exc:
        p._extract_content(data)
    assert "length" in str(exc.value)
    assert "empty" in str(exc.value).lower() or "no content" in str(exc.value).lower()


def test_extract_content_empty_string_raises():
    p = OpenRouterProvider(api_key="test", model="m")
    data = {"choices": [{"message": {"content": "  "}, "finish_reason": "stop"}]}
    with pytest.raises(ValueError):
        p._extract_content(data)


def test_extract_content_missing_choices_raises():
    p = OpenRouterProvider(api_key="test", model="m")
    with pytest.raises(ValueError):
        p._extract_content({"error": {"message": "rate limited"}})
