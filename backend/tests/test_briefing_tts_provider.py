"""The briefing pipeline reads the TTS provider once and respects its capabilities."""

from pathlib import Path

import pytest

from app.services.tts.base import SegmentTiming, TTSResult
from app.services.tts.factory import TTSFactory
from tests.conftest import make_silent_mp3
from tests.test_breakout_pipeline import setup_breakout_pipeline

SCRIPT_WITH_TAGS = (
    "TITLE: Fusion's Long Road\n"
    "[CHAPTER: 1 | Foundations]\nAlex: [sigh] The premise begins here.\n"
    "[CHAPTER: 2 | Evidence]\nAlex: [uhm] The evidence is mixed."
)


async def _pipeline(db_session, monkeypatch, tmp_path, provider):
    import app.services.briefing as briefing_module

    service, briefing, llm, _ = await setup_breakout_pipeline(db_session, monkeypatch, tmp_path)
    llm._responses = [SCRIPT_WITH_TAGS]
    monkeypatch.setattr(briefing_module.settings, "enable_non_speech_sounds", True)
    from app.models.cast import Cast
    cast = await db_session.get(Cast, "cast")
    cast.tts_provider = provider
    await db_session.commit()

    writer_kwargs = []
    original_write = service.orchestrator.write_briefing_script

    async def spy_write(**kwargs):
        writer_kwargs.append(kwargs)
        return await original_write(**kwargs)

    service.orchestrator.write_briefing_script = spy_write

    tts_calls = []

    async def synthesize(script, output_path, **kwargs):
        tts_calls.append({"script": script, **kwargs})
        make_silent_mp3(str(output_path))
        timings = [
            SegmentTiming(i, part["speaker"], part["text"], i * 10, (i + 1) * 10, 10)
            for i, part in enumerate(script)
        ]
        return TTSResult(Path(output_path), len(script) * 10, "fake", segment_timings=timings)

    monkeypatch.setattr(TTSFactory, "synthesize_conversation", synthesize)
    return service, briefing, writer_kwargs, tts_calls


@pytest.mark.asyncio
async def test_voicebox_briefing_never_asks_for_or_voices_sound_tags(db_session, monkeypatch, tmp_path):
    service, briefing, writer_kwargs, tts_calls = await _pipeline(
        db_session, monkeypatch, tmp_path, "voicebox")

    result = await service._generate_briefing_internal(
        briefing.id, briefing, ["fusion-topic"], 10, "Listener", tts_provider="voicebox",
    )

    assert result.status == "completed"
    assert writer_kwargs[0]["enable_non_speech_sounds"] is False
    spoken = " ".join(part["text"] for part in tts_calls[0]["script"])
    assert "[sigh]" not in spoken and "[uhm]" not in spoken
    assert "[sigh]" not in result.transcript
    assert tts_calls[0]["provider_name"] == "voicebox"
    assert result.extra_data["costs"]["tts_generation"]["provider"] == "voicebox"


@pytest.mark.asyncio
async def test_gemini_briefing_keeps_sound_tags_when_enabled(db_session, monkeypatch, tmp_path):
    service, briefing, writer_kwargs, tts_calls = await _pipeline(
        db_session, monkeypatch, tmp_path, "gemini")

    await service._generate_briefing_internal(
        briefing.id, briefing, ["fusion-topic"], 10, "Listener", tts_provider="gemini",
    )

    assert writer_kwargs[0]["enable_non_speech_sounds"] is True
    spoken = " ".join(part["text"] for part in tts_calls[0]["script"])
    assert "[sigh]" in spoken


@pytest.mark.asyncio
async def test_generate_briefing_reads_the_provider_once(db_session, monkeypatch, tmp_path):
    import app.services.briefing as briefing_module

    service, briefing, _, tts_calls = await _pipeline(db_session, monkeypatch, tmp_path, "voicebox")
    # The module-level settings still say piper; a second read would say piper too.
    monkeypatch.setattr(briefing_module.settings, "tts_provider", "piper")
    reads = []

    def active():
        reads.append(1)
        return "voicebox" if len(reads) == 1 else "piper"

    monkeypatch.setattr(briefing_module, "active_tts_provider", active)
    timeouts = []
    original_timeout = briefing_module.briefing_timeout_minutes

    def timeout(provider):
        timeouts.append(provider)
        return original_timeout(provider)

    monkeypatch.setattr(briefing_module, "briefing_timeout_minutes", timeout)

    result = await service.generate_briefing(briefing.id)

    assert result.status == "completed"
    assert len(reads) == 1
    assert timeouts == ["voicebox"]
    assert tts_calls[0]["provider_name"] == "voicebox"
    assert result.extra_data["costs"]["tts_generation"]["provider"] == "voicebox"
