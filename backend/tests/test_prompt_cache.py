import pytest

from app.config import get_settings
from app.services.llm.agents.briefing_writer import BriefingWriterAgent
from app.services.llm.openrouter import cached_system_message
from tests.conftest import FakeLLM

CAST = [{"name": "Alex", "personality": "Casual"}]


def test_cached_system_message_structure():
    msg = cached_system_message("big stable prompt")
    assert msg["role"] == "system"
    assert msg["content"][0]["type"] == "text"
    assert msg["content"][0]["text"] == "big stable prompt"
    assert msg["content"][0]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_write_briefing_uses_cached_conversation_when_enabled(monkeypatch):
    monkeypatch.setenv("LLM_PROMPT_CACHE", "true")
    get_settings.cache_clear()
    try:
        fake = FakeLLM(response_content="TITLE: x\nAlex: hi")
        agent = BriefingWriterAgent(fake)
        await agent.write_briefing(content="news", topics=["AI"], cast_members=CAST, duration=10)
        call = fake.calls[0]
        # Cache path uses generate_conversation (records "messages", not "prompt").
        assert "messages" in call
        system_msg = call["messages"][0]
        assert system_msg["role"] == "system"
        assert system_msg["content"][0]["cache_control"] == {"type": "ephemeral"}
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_write_briefing_uses_plain_generate_when_disabled(monkeypatch):
    monkeypatch.setenv("LLM_PROMPT_CACHE", "false")
    get_settings.cache_clear()
    try:
        fake = FakeLLM(response_content="TITLE: x\nAlex: hi")
        agent = BriefingWriterAgent(fake)
        await agent.write_briefing(content="news", topics=["AI"], cast_members=CAST, duration=10)
        call = fake.calls[0]
        # Default path uses generate (records "prompt", not "messages").
        assert "prompt" in call
        assert "messages" not in call
    finally:
        get_settings.cache_clear()
