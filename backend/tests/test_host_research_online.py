"""Host research via the OpenRouter web plugin: one call per host per story."""
import json
import pytest

from tests.conftest import FakeLLM
from app.services.llm.base import LLMResponse
from app.services.llm.agents.host_research import HostResearchAgent
from app.services.llm.openrouter import OpenRouterProvider

STORIES = [
    {"title": "AI chip launch", "summary": "new accelerator", "url": "http://news/1"},
    {"title": "Rate cut", "summary": "central bank", "url": "http://news/2"},
]


def _online_response(answer: str, url: str, title: str) -> LLMResponse:
    content = json.dumps({"questions_and_answers": [{"question": "Q?", "answer": answer}]})
    return LLMResponse(
        content=content, model="google/gemini-3.8-flash", usage={},
        annotations=[{"type": "url_citation", "url_citation": {
            "url": url, "title": title, "content": "excerpt " * 50, "start_index": 0, "end_index": 5}}],
    )


def test_build_payload_includes_plugins():
    p = OpenRouterProvider(api_key="t", model="google/gemini-3.8-flash")
    payload = p._build_payload([{"role": "user", "content": "hi"}], 100, 0.3,
                               plugins=[{"id": "web", "max_results": 3}])
    assert payload["plugins"] == [{"id": "web", "max_results": 3}]
    assert "plugins" not in p._build_payload([{"role": "user", "content": "hi"}], 100, 0.3)


@pytest.mark.asyncio
async def test_generate_returns_annotations():
    p = OpenRouterProvider(api_key="t", model="google/gemini-3.8-flash")

    class R:
        def raise_for_status(self): pass
        def json(self):
            return {"model": "m", "choices": [{"message": {"content": "x", "annotations": [
                {"type": "url_citation", "url_citation": {"url": "http://c", "title": "C", "content": "e"}}]},
                "finish_reason": "stop"}], "usage": {}}

    class C:
        async def post(self, *a, **k): return R()

    p._client = C(); p._cached_api_key = "t"
    resp = await p.generate(prompt="hi", plugins=[{"id": "web"}])
    assert resp.annotations[0]["url_citation"]["url"] == "http://c"


@pytest.mark.asyncio
async def test_online_research_one_call_per_story_with_web_plugin():
    fake = FakeLLM(response_content=[
        _online_response("2x faster on MLPerf", "http://mlperf.example", "MLPerf results"),
        _online_response("25 basis points", "http://fed.example", "Fed statement"),
    ])
    agent = HostResearchAgent(fake, use_web_plugin=True)
    research = await agent.research(STORIES, "Sam", "The Skeptic")

    assert len(fake.calls) == 2
    assert all(c["plugins"][0]["id"] == "web" for c in fake.calls)
    assert all(c["plugins"][0]["engine"] for c in fake.calls)   # engine is explicit, not provider default
    assert all(c["max_tokens"] >= 4096 for c in fake.calls)     # room for reasoning + search excerpts
    assert "Skeptic" in fake.calls[0]["system_prompt"]
    assert "AI chip launch" in fake.calls[0]["prompt"]
    assert "Rate cut" in fake.calls[1]["prompt"]

    assert "2x faster on MLPerf" in research.facts_by_story_index[0][0]
    assert "25 basis points" in research.facts_by_story_index[1][0]
    urls = {s["url"]: s for s in research.sources}
    assert urls["http://mlperf.example"]["found_by"] == ["Sam"]
    assert urls["http://mlperf.example"]["story_index"] == 0
    assert urls["http://fed.example"]["story_index"] == 1


@pytest.mark.asyncio
async def test_online_research_tolerates_prose_around_json_and_bad_story():
    good = LLMResponse(content='Here you go:\n```json\n{"questions_and_answers":[{"question":"Q","answer":"A1"}]}\n```',
                       model="m", usage={}, annotations=[])
    bad = LLMResponse(content="I could not find anything.", model="m", usage={}, annotations=[])
    agent = HostResearchAgent(FakeLLM(response_content=[good, bad]), use_web_plugin=True)
    research = await agent.research(STORIES, "Alex", "Casual")
    assert research.facts_by_story_index == {0: ["Question: Q\nAnswer: A1"]}


@pytest.mark.asyncio
async def test_legacy_path_still_used_when_plugin_disabled():
    from tests.conftest import FakeSearch
    q = json.dumps({"articles": [{"article_num": 1, "queries": ["x"]}]})
    f = json.dumps({"articles": [{"article_num": 1, "title": "t", "questions_and_answers": [{"question": "Q", "answer": "A"}]}]})
    fake = FakeLLM(response_content=[q, f])
    agent = HostResearchAgent(fake, search_service=FakeSearch(), use_web_plugin=False)
    research = await agent.research(STORIES[:1], "Alex", "Casual")
    assert research.facts_by_story_index[0]
    assert all(not c.get("plugins") for c in fake.calls)


def test_markdown_links_in_answers_become_plain_text():
    out = HostResearchAgent._plain_text("According to [cnbc.com](https://www.cnbc.com/2026/x) the price was $13B.")
    assert out == "According to cnbc.com the price was $13B."
