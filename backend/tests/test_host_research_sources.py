import pytest
from app.services.search import SearchResult
from tests.conftest import FakeLLM, FakeSearch
from app.services.llm.agents.host_research import HostResearchAgent

STORIES = [{"title": "AI chip launch", "summary": "x", "url": "http://news/1"}]


@pytest.mark.asyncio
async def test_gather_sources_tags_found_by_and_returns_content():
    search = FakeSearch(results=[SearchResult("Deep Dive", "http://deep.example", "s")])
    agent = HostResearchAgent(FakeLLM(), search_service=search)
    queries_by_idx = {0: ["benchmark data"]}
    content_by_idx, sources = await agent._gather_sources(STORIES, queries_by_idx, "Alex")
    # Content fetched for the story.
    assert 0 in content_by_idx and len(content_by_idx[0]) > 0
    # Sources tagged with the host.
    assert sources
    assert all(src["found_by"] == ["Alex"] for src in sources)
    assert any(src["url"] == "http://deep.example" for src in sources)
    # The persona query was actually issued.
    assert "benchmark data" in search.queries
