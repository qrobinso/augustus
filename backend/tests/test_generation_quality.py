"""Tests for the generation-quality changes: story-count helper, writer prompt v2
contract, and topic scoping of host research."""

import pytest

from tests.conftest import FakeLLM
from app.services.llm.prompts import target_story_count
from app.services.llm.agents.briefing_writer import BriefingWriterAgent
from app.services.llm.agents.host_research import HostResearchAgent

CAST = [{"name": "Alex", "personality": "Casual"}, {"name": "Sam", "personality": "Skeptic"}]


# ---------- target_story_count ----------

def test_story_count_scales_with_duration(monkeypatch):
    monkeypatch.delenv("STORIES_PER_BRIEFING", raising=False)
    from app.config import get_settings
    get_settings.cache_clear() if hasattr(get_settings, "cache_clear") else None
    assert target_story_count(5) == 2
    assert target_story_count(10) == 3
    assert target_story_count(15) == 5
    # Clamped to [1, 6]
    assert target_story_count(1) == 1
    assert target_story_count(60) == 6


def test_story_count_config_override(monkeypatch):
    monkeypatch.setenv("STORIES_PER_BRIEFING", "4")
    from app.config import get_settings
    if hasattr(get_settings, "cache_clear"):
        get_settings.cache_clear()
    try:
        assert target_story_count(5) == 4
        assert target_story_count(30) == 4
    finally:
        monkeypatch.delenv("STORIES_PER_BRIEFING", raising=False)
        if hasattr(get_settings, "cache_clear"):
            get_settings.cache_clear()


# ---------- writer prompt v2 contract ----------

def _v2_prompt(**kwargs):
    agent = BriefingWriterAgent(FakeLLM())
    return agent._build_system_prompt_v2(cast_members=CAST, topics=["AI"], **kwargs)


def test_v2_keeps_output_contract():
    sp = _v2_prompt()
    # Load-bearing format markers the pipeline parses.
    assert "TITLE:" in sp
    assert "[CHAPTER:" in sp
    assert "[medium pause]" in sp
    assert "Alex" in sp and "Sam" in sp
    assert "TITLE: Tech & Business Update" in sp  # format example


def test_v2_drops_style_quotas_and_filler_pressure():
    sp = _v2_prompt()
    assert "2-4 lines" not in sp
    assert "2-4 instances" not in sp
    assert "Cover stories across ALL" not in sp
    # Material discipline present.
    assert "Discuss ONLY the stories" in sp
    # Filler blacklist phrase retained (other tests rely on it).
    assert "there's a lot to unpack here" in sp


def test_v2_single_host_variant():
    agent = BriefingWriterAgent(FakeLLM())
    sp = agent._build_system_prompt_v2(cast_members=[CAST[0]], topics=["AI"])
    assert "THE NARRATION" in sp
    assert "TITLE:" in sp


def test_flag_dispatches_v1_vs_v2(monkeypatch):
    from app.config import get_settings
    agent = BriefingWriterAgent(FakeLLM())

    monkeypatch.setenv("WRITER_PROMPT_V2", "false")
    if hasattr(get_settings, "cache_clear"):
        get_settings.cache_clear()
    v1 = agent._build_system_prompt(cast_members=CAST, topics=["AI"])
    assert "PLAYFUL BANTER" in v1  # v1 marker

    monkeypatch.setenv("WRITER_PROMPT_V2", "true")
    if hasattr(get_settings, "cache_clear"):
        get_settings.cache_clear()
    v2 = agent._build_system_prompt(cast_members=CAST, topics=["AI"])
    assert "PLAYFUL BANTER" not in v2
    assert "MATERIAL DISCIPLINE" in v2

    monkeypatch.delenv("WRITER_PROMPT_V2", raising=False)
    if hasattr(get_settings, "cache_clear"):
        get_settings.cache_clear()


def test_user_prompt_constrains_to_provided_stories():
    agent = BriefingWriterAgent(FakeLLM())
    up = agent._build_user_prompt(content="news", topics=["AI"], duration=10)
    assert "Discuss ONLY the stories above" in up
    assert "end the episode early" in up
    assert "Cover stories across ALL" not in up


# ---------- host research topic scoping ----------

def test_query_prompts_are_topic_scoped():
    agent = HostResearchAgent(FakeLLM(), search_service=object())
    sp = agent._query_system_prompt("Sam", "Skeptic")
    assert "do not broaden into adjacent topics" in sp
    up = agent._query_user_prompt(
        [{"title": "Chip wars", "summary": "s", "category": "Technology"}],
        queries_per_story=2,
        topics=["Technology", "AI"],
    )
    assert "Briefing topics: Technology, AI" in up
    assert "Category: Technology" in up


def test_facts_prompt_ignores_off_topic_sources():
    agent = HostResearchAgent(FakeLLM(), search_service=object())
    sp = agent._facts_system_prompt("Sam", "Skeptic")
    assert "ignore it" in sp
