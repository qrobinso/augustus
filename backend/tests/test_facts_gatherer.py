import pytest
from tests.conftest import FakeLLM
from app.services.llm.agents.facts_gatherer import FactsGathererAgent

STORIES = [{"title": "T", "summary": "s", "source": "Reuters", "category": "tech", "url": "", "full_content": "c"}]
RESP = '{"articles": [{"article_num": 1, "title": "T", "questions_and_answers": [{"question": "q", "answer": "a"}]}]}'


@pytest.mark.asyncio
async def test_passes_response_format_when_enabled(monkeypatch):
    monkeypatch.setenv("LLM_STRUCTURED_OUTPUTS", "true")
    fake = FakeLLM(response_content=RESP)
    agent = FactsGathererAgent(fake)
    # Avoid network in _fetch_article_content
    async def _no_fetch(story):
        return None
    agent._fetch_article_content = _no_fetch
    facts, raw, usage = await agent.gather_facts(STORIES)
    assert fake.calls[0]["response_format"]["type"] == "json_schema"
    assert 0 in facts
