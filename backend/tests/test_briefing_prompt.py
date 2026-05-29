import pytest
from tests.conftest import FakeLLM
from app.services.llm.agents.briefing_writer import BriefingWriterAgent

CAST = [{"name": "Alex", "personality": "Casual"}, {"name": "Sam", "personality": "Skeptic"}]


def _agent():
    return BriefingWriterAgent(FakeLLM())


def test_filler_blacklist_appears_once_across_both_prompts():
    a = _agent()
    sp = a._build_system_prompt(CAST, topics=["AI"])
    up = a._build_user_prompt(content="news", topics=["AI"], duration=10)
    # The filler-phrase rule lives in the system prompt only.
    assert "there's a lot to unpack here" in sp
    assert "there's a lot to unpack here" not in up


def test_output_format_example_only_in_system_prompt():
    a = _agent()
    up = a._build_user_prompt(content="news", topics=["AI"], duration=10)
    assert "TITLE: Tech & Business Update" not in up  # example lives in system prompt
