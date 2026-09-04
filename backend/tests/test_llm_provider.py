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


@pytest.mark.asyncio
async def test_generate_warns_and_records_finish_reason_on_truncation(capsys):
    p = OpenRouterProvider(api_key="test", model="google/gemini-3.8-flash")

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "model": "google/gemini-3.8-flash",
                "choices": [{"message": {"content": "cut off mid"}, "finish_reason": "length"}],
                "usage": {"completion_tokens": 2083,
                          "completion_tokens_details": {"reasoning_tokens": 1355}},
            }

    class FakeClient:
        async def post(self, *_args, **_kwargs):
            return FakeResponse()

    p._client = FakeClient()
    p._cached_api_key = "test"
    resp = await p.generate(prompt="hi", max_tokens=2087)
    assert resp.finish_reason == "length"
    out = capsys.readouterr().out
    assert "truncated" in out and "reasoning_tokens=1355" in out
