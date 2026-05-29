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


@pytest.mark.asyncio
async def test_gather_host_research_survives_one_host_failure():
    orch = BriefingOrchestrator(FakeLLM())

    class BoomAgent:
        async def research(self, **kwargs):
            raise RuntimeError("search backend down")

    good_q = json.dumps({"articles": [{"article_num": 1, "queries": ["q"]}]})
    good_f = json.dumps({"articles": [{"article_num": 1, "title": "S1",
                        "questions_and_answers": [{"question": "Q", "answer": "A"}]}]})
    from app.services.llm.agents.host_research import HostResearchAgent
    agents = iter([
        BoomAgent(),
        HostResearchAgent(FakeLLM(response_content=[good_q, good_f]),
                          search_service=FakeSearch(results=[SearchResult("R", "http://r.example", "s")])),
    ])
    orch._make_host_agent = lambda: next(agents)

    research_list, sources = await orch.gather_host_research(STORIES, CAST)
    # Both hosts present; the failed one has empty findings, the good one has facts.
    assert len(research_list) == 2
    by_name = {r.host_name: r for r in research_list}
    assert by_name["Alex"].facts_by_story_index == {}   # Alex (order 0) used BoomAgent
    assert by_name["Sam"].facts_by_story_index           # Sam (order 1) succeeded
