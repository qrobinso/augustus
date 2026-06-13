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


def test_prompts_have_no_weather_priority():
    # Weather stories must compete on topic relevance like everything else;
    # the old forced-priority rule leaked off-topic stories into briefings.
    agent = StoryAnalyzerAgent(FakeLLM())
    sp = agent._build_system_prompt(["AI"])
    assert "weather" not in sp.lower()
    up = agent._build_user_prompt(ARTICLES, ["AI"], max_stories=3)
    assert "weather" not in up.lower()


def test_prompts_use_max_stories_with_quality_gate():
    agent = StoryAnalyzerAgent(FakeLLM())
    sp = agent._build_system_prompt(["AI"], max_stories=2)
    up = agent._build_user_prompt(ARTICLES, ["AI"], max_stories=2)
    assert "up to 2 stories" in sp
    assert "up to 2" in up
    assert "3-5" not in sp and "3-5" not in up
    # Quality gate: explicitly permits selecting fewer, forbids slot-filling.
    assert "fill a slot" in sp
    assert "never pad" in up.lower()


def test_empty_topics_renders_general_news():
    agent = StoryAnalyzerAgent(FakeLLM())
    sp = agent._build_system_prompt([])
    assert "general news" in sp
