import json
import pytest
from tests.conftest import FakeLLM, FakeSearch
from app.services.llm.agents.host_research import HostResearchAgent, persona_angle

STORIES = [{"title": "AI chip launch", "summary": "new accelerator", "url": "http://news/1"}]


def test_persona_angle_is_persona_specific():
    analytical = persona_angle("Analytical")
    skeptic = persona_angle("The Skeptic")
    assert analytical != skeptic
    assert "Analytical" in analytical


@pytest.mark.asyncio
async def test_generate_queries_returns_persona_queries_per_story():
    resp = json.dumps({"articles": [{"article_num": 1, "queries": ["benchmark data", "methodology"]}]})
    fake = FakeLLM(response_content=resp)
    agent = HostResearchAgent(fake, search_service=FakeSearch())
    queries = await agent._generate_queries(STORIES, "Alex", "Analytical")
    assert queries[0] == ["benchmark data", "methodology"]
    # Persona name reached the model.
    assert "Analytical" in fake.calls[0]["system_prompt"]
