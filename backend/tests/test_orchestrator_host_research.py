import json
import pytest
from app.services.search import SearchResult
from tests.conftest import FakeLLM, FakeSearch
from app.services.llm.agents.orchestrator import BriefingOrchestrator

STORIES = [{"title": "S1", "summary": "x", "url": "http://news/1"}]
CAST = [{"name": "Alex", "personality": "Analytical", "order": 0},
        {"name": "Sam", "personality": "The Skeptic", "order": 1}]


@pytest.mark.asyncio
async def test_gather_host_research_runs_one_pass_per_host():
    q = json.dumps({"articles": [{"article_num": 1, "queries": ["q"]}]})
    f = json.dumps({"articles": [{"article_num": 1, "title": "S1",
                   "questions_and_answers": [{"question": "Q", "answer": "A"}]}]})
    orch = BriefingOrchestrator(FakeLLM())
    # Inject deterministic per-host agents.
    from app.services.llm.agents.host_research import HostResearchAgent
    orch._make_host_agent = lambda: HostResearchAgent(
        FakeLLM(response_content=[q, f]),
        search_service=FakeSearch(results=[SearchResult("R", "http://r.example", "s")]),
    )
    research_list, sources = await orch.gather_host_research(STORIES, CAST)
    assert [r.host_name for r in research_list] == ["Alex", "Sam"]
    assert all(s.get("found_by") for s in sources)
