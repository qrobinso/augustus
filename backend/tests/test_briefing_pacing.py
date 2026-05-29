import pytest
from tests.conftest import FakeLLM
from app.services.llm.prompts import tokens_for_duration, target_words_for_duration
from app.services.llm.agents.briefing_writer import BriefingWriterAgent

CAST = [{"name": "Alex", "personality": "Casual"}]


def test_word_target_scales_with_duration():
    assert target_words_for_duration(10) == 1500
    assert target_words_for_duration(20) == 3000


def test_tokens_scale_and_clamp():
    assert tokens_for_duration(5) >= 1024          # floor
    assert tokens_for_duration(30) > tokens_for_duration(10)
    assert tokens_for_duration(120) <= 16384       # ceiling


@pytest.mark.asyncio
async def test_write_briefing_uses_scaled_tokens_and_word_target():
    fake = FakeLLM(response_content="TITLE: x\nAlex: hi")
    agent = BriefingWriterAgent(fake)
    await agent.write_briefing(content="news", topics=["AI"], cast_members=CAST, duration=20)
    call = fake.calls[0]
    assert call["max_tokens"] == tokens_for_duration(20)
    assert "3000" in call["prompt"]  # word target injected into user prompt
