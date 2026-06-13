import json
import pytest
from app.services.search import SearchResult
from tests.conftest import FakeLLM, FakeSearch
from app.services.llm.agents.host_research import HostResearchAgent, HostResearch

STORIES = [{"title": "AI chip launch", "summary": "x", "url": "http://news/1"}]


@pytest.mark.asyncio
async def test_research_returns_populated_hostresearch():
    queries_resp = json.dumps({"articles": [{"article_num": 1, "queries": ["benchmark data"]}]})
    facts_resp = json.dumps({"articles": [{"article_num": 1, "title": "AI chip launch",
                             "questions_and_answers": [{"question": "How fast?", "answer": "2x faster per benchmarks."}]}]})
    fake = FakeLLM(response_content=[queries_resp, facts_resp])  # query call, then facts call
    search = FakeSearch(results=[SearchResult("Deep Dive", "http://deep.example", "s")])
    agent = HostResearchAgent(fake, search_service=search)

    research = await agent.research(STORIES, "Alex", "Analytical")
    assert isinstance(research, HostResearch)
    assert research.host_name == "Alex"
    assert "Analytical" in research.angle
    assert research.facts_by_story_index[0]  # has facts
    assert any(s["found_by"] == ["Alex"] for s in research.sources)


@pytest.mark.asyncio
async def test_research_survives_query_failure():
    # Non-JSON query response -> no queries; still returns HostResearch with baseline content/facts.
    facts_resp = json.dumps({"articles": [{"article_num": 1, "title": "AI chip launch",
                             "questions_and_answers": [{"question": "Q", "answer": "A grounded in the article."}]}]})
    fake = FakeLLM(response_content=["not json", facts_resp])
    agent = HostResearchAgent(fake, search_service=FakeSearch())
    research = await agent.research(STORIES, "Sam", "The Skeptic")
    assert research.host_name == "Sam"
    assert research.facts_by_story_index[0]
