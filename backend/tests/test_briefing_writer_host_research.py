import pytest
from tests.conftest import FakeLLM
from app.services.llm.agents.briefing_writer import BriefingWriterAgent, build_host_research_section
from app.services.llm.agents.host_research import HostResearch

CAST = [{"name": "Alex", "personality": "Analytical"}, {"name": "Sam", "personality": "The Skeptic"}]


def test_build_host_research_section_attributes_facts_to_each_host():
    research = [
        HostResearch("Alex", "Analytical", "Analytical — data", {0: ["Question: Q1\nAnswer: data point"]}, []),
        HostResearch("Sam", "The Skeptic", "The Skeptic — doubt", {0: ["Question: Q2\nAnswer: a caveat"]}, []),
    ]
    stories = [{"title": "AI chip launch"}]
    section = build_host_research_section(research, stories)
    assert "Alex" in section and "Sam" in section
    assert "data point" in section and "a caveat" in section
    assert "AI chip launch" in section


def test_build_host_research_section_empty_when_none():
    assert build_host_research_section(None, []) == ""


@pytest.mark.asyncio
async def test_write_briefing_includes_host_research_in_prompt():
    fake = FakeLLM(response_content="TITLE: x\nAlex: hi")
    agent = BriefingWriterAgent(fake)
    research = [HostResearch("Alex", "Analytical", "Analytical — data", {0: ["Question: Q\nAnswer: deep data"]}, [])]
    await agent.write_briefing(content="news", topics=["AI"], cast_members=CAST, duration=10,
                               ranked_items=[type("I", (), {"title": "AI chip launch"})()],
                               host_research=research)
    assert "deep data" in fake.calls[0]["prompt"]
