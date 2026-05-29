import pytest
from tests.conftest import FakeLLM
from app.services.llm.agents.story_analyzer import StoryAnalyzerAgent

ARTICLES = [{"title": "AI breakthrough", "summary": "x", "source": "Reuters", "category": "tech"}]


@pytest.mark.asyncio
async def test_passes_response_format_when_enabled(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setenv("LLM_STRUCTURED_OUTPUTS", "true")
    fake = FakeLLM(response_content='{"ranked_stories": [{"article_num": 1, "priority": 9, "reason": "r"}], "summary": "s"}')
    agent = StoryAnalyzerAgent(fake)
    ranked, summary, raw, usage = await agent.analyze_and_rank(ARTICLES, ["AI"], max_stories=5)
    assert ranked[0]["article_num"] == 1
    assert fake.calls[0]["response_format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_parses_plain_json_without_fences():
    fake = FakeLLM(response_content='{"ranked_stories": [], "summary": null}')
    agent = StoryAnalyzerAgent(fake)
    ranked, summary, raw, usage = await agent.analyze_and_rank(ARTICLES, ["AI"])
    assert ranked == []
    assert summary is None


def test_system_prompt_weather_is_weighted_not_absolute():
    agent = StoryAnalyzerAgent(FakeLLM())
    sp = agent._build_system_prompt(["AI"])
    assert "regardless of other factors" not in sp
    assert "weather" in sp.lower()
