import pytest
from tests.conftest import FakeLLM
from app.services.llm.prompts import tokens_for_duration, target_words_for_duration
from app.services.llm.agents.briefing_writer import BriefingWriterAgent

CAST = [{"name": "Alex", "personality": "Casual"}]


def test_word_target_scales_with_duration():
    assert target_words_for_duration(10) == 1500
    assert target_words_for_duration(20) == 3000


def test_tokens_scale_and_clamp():
    assert tokens_for_duration(30) > tokens_for_duration(10)
    assert tokens_for_duration(120) <= 16384       # ceiling


def test_tokens_leave_headroom_for_reasoning_and_markup():
    # Reasoning models (Gemini 3.x, DeepSeek) spend "thinking" tokens out of
    # the same max_tokens budget. A real 7-minute run burned 1355 reasoning
    # tokens + ~1.4 tokens/word of output and was cut off mid-sentence at 2087.
    for minutes in (5, 7, 10):
        words = target_words_for_duration(minutes)
        assert tokens_for_duration(minutes) >= int(words * 2) + 4096


@pytest.mark.asyncio
async def test_write_briefing_uses_scaled_tokens_and_word_target():
    fake = FakeLLM(response_content="TITLE: x\nAlex: hi")
    agent = BriefingWriterAgent(fake)
    await agent.write_briefing(content="news", topics=["AI"], cast_members=CAST, duration=20)
    call = fake.calls[0]
    assert call["max_tokens"] == tokens_for_duration(20)
    assert "3000" in call["prompt"]  # word target injected into user prompt
