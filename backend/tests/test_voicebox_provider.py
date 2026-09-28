"""VoiceboxProvider: voice resolution, engine choice, ordering, stitching, cleanup."""
import asyncio
import wave
from pathlib import Path

import pytest

from app.services.tts.voicebox import VoiceboxProvider, stitch_wavs
from app.services.tts.voicebox_client import VoiceboxError, VoiceboxModel, VoiceboxProfile


def write_wav(path: Path, seconds: float, rate: int) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))


class FakeClient:
    """Stands in for VoiceboxClient; each line's WAV length is taken from its text."""

    base_url = "http://vb.local:17493"

    def __init__(self, fail_on: str | None = None, delays: dict[str, float] | None = None):
        self.profiles = [
            VoiceboxProfile("p-halie", "Halie ", "en", "cloned", None),
            VoiceboxProfile("p-dad", "Dad", "en", "cloned", None),
            VoiceboxProfile("p-heart", "Heart (kokoro)", "en", "preset", "kokoro"),
        ]
        self.models = [VoiceboxModel("qwen-tts-1.7B", "Qwen", "qwen", "1.7B"),
                       VoiceboxModel("chatterbox-turbo", "Turbo", "chatterbox_turbo", None)]
        self.generated: list[dict] = []
        self.deleted: list[str] = []
        self.cancelled: list[str] = []
        self.fail_on, self.delays = fail_on, delays or {}
        self._texts: dict[str, str] = {}

    async def list_profiles(self, max_age=30.0):
        return self.profiles

    async def list_tts_models(self):
        return self.models

    async def generate(self, profile_id, text, language, engine, model_size):
        gen_id = f"g{len(self.generated)}"
        self.generated.append({"id": gen_id, "profile_id": profile_id, "text": text, "engine": engine, "model_size": model_size})
        self._texts[gen_id] = text
        return gen_id

    async def wait_until_done(self, generation_id, timeout):
        await asyncio.sleep(self.delays.get(self._texts[generation_id], 0))
        if self._texts[generation_id] == self.fail_on:
            raise VoiceboxError(f"Voicebox generation {generation_id} failed: boom")

    async def download_audio(self, generation_id, dest):
        seconds = float(self._texts[generation_id].split("s:")[0]) if "s:" in self._texts[generation_id] else 0.5
        write_wav(dest, seconds, 24000)

    async def delete_generation(self, generation_id):
        self.deleted.append(generation_id)

    async def cancel_generation(self, generation_id):
        self.cancelled.append(generation_id)

    async def close(self):
        pass


def script(*lines):
    return [{"speaker": speaker, "text": text} for speaker, text in lines]


@pytest.mark.asyncio
async def test_resolves_by_id_or_trimmed_case_insensitive_name_and_picks_engine(tmp_path):
    client = FakeClient()
    provider = VoiceboxProvider(client=client, model="qwen-tts-1.7B")
    result = await provider.synthesize_conversation(
        script(("HOST1", "1s: hello"), ("HOST2", "1s: hi"), ("HOST3", "1s: hey")),
        tmp_path / "out.wav",
        voice_map={"HOST1": "halie", "HOST2": "p-dad", "HOST3": "Heart (kokoro)"},
    )
    assert [g["profile_id"] for g in client.generated] == ["p-halie", "p-dad", "p-heart"]
    assert [(g["engine"], g["model_size"]) for g in client.generated] == [
        ("qwen", "1.7B"), ("qwen", "1.7B"), ("kokoro", None)]  # the preset keeps its own engine
    assert sorted(client.deleted) == ["g0", "g1", "g2"]  # history cleaned up
    assert result.format == "wav" and result.audio_path.exists()


@pytest.mark.asyncio
async def test_unknown_voice_fails_with_edit_the_cast_message(tmp_path):
    provider = VoiceboxProvider(client=FakeClient(), model="qwen-tts-1.7B")
    with pytest.raises(VoiceboxError, match=r"^'Zephyr' isn't a Voicebox voice\. Edit the cast\.$"):
        await provider.synthesize_conversation(script(("HOST1", "x")), tmp_path / "o.wav", voice_map={"HOST1": "Zephyr"})


@pytest.mark.asyncio
async def test_model_not_downloaded_or_unknown(tmp_path):
    with pytest.raises(VoiceboxError, match="isn't downloaded"):
        await VoiceboxProvider(client=FakeClient(), model="tada-1b").synthesize_conversation(
            script(("HOST1", "x")), tmp_path / "o.wav", voice_map={"HOST1": "Dad"})
    with pytest.raises(VoiceboxError, match="isn't supported"):
        await VoiceboxProvider(client=FakeClient(), model="mystery").synthesize_conversation(
            script(("HOST1", "x")), tmp_path / "o.wav", voice_map={"HOST1": "Dad"})


@pytest.mark.asyncio
async def test_empty_model_setting_uses_first_downloaded(tmp_path):
    client = FakeClient()
    await VoiceboxProvider(client=client, model="").synthesize_conversation(
        script(("HOST1", "x")), tmp_path / "o.wav", voice_map={"HOST1": "Dad"})
    assert client.generated[0]["engine"] == "qwen"


@pytest.mark.asyncio
async def test_concurrent_lines_keep_script_order_and_timings(tmp_path):
    # The first line finishes last; the output must still be in script order.
    client = FakeClient(delays={"1s: first": 0.05})
    provider = VoiceboxProvider(client=client, model="qwen-tts-1.7B", concurrency=3)
    result = await provider.synthesize_conversation(
        script(("HOST1", "1s: first"), ("HOST2", "2s: second"), ("HOST1", "0.5s: third")),
        tmp_path / "out.wav", voice_map={"HOST1": "Dad", "HOST2": "Halie"},
    )
    timings = result.segment_timings
    assert [t.text for t in timings] == ["1s: first", "2s: second", "0.5s: third"]
    assert [round(t.start_seconds, 2) for t in timings] == [0.0, 1.25, 3.5]  # 250 ms gaps
    assert round(result.duration_seconds, 2) == 4.0


@pytest.mark.asyncio
async def test_failed_line_cleans_up_every_generation(tmp_path):
    client = FakeClient(fail_on="bad")
    provider = VoiceboxProvider(client=client, model="qwen-tts-1.7B", concurrency=1)
    with pytest.raises(VoiceboxError, match="failed: boom"):
        await provider.synthesize_conversation(
            script(("HOST1", "ok"), ("HOST1", "bad"), ("HOST1", "never")),
            tmp_path / "o.wav", voice_map={"HOST1": "Dad"})
    assert set(client.deleted) == {g["id"] for g in client.generated}
    assert "never" not in [g["text"] for g in client.generated]
    assert not any(p.name.startswith(".voicebox-") for p in tmp_path.iterdir())  # temp dir removed


@pytest.mark.asyncio
async def test_cancellation_cancels_in_flight_generation(tmp_path):
    from app.services import cancellation
    from app.services.cancellation import BriefingCancelledException
    client = FakeClient(delays={"slow": 5})
    provider = VoiceboxProvider(client=client, model="qwen-tts-1.7B", concurrency=1)
    cancellation.register("b1")
    try:
        task = asyncio.create_task(provider.synthesize_conversation(
            script(("HOST1", "slow")), tmp_path / "o.wav", voice_map={"HOST1": "Dad"}, briefing_id="b1"))
        await asyncio.sleep(0.05)
        cancellation.signal("b1")
        with pytest.raises(BriefingCancelledException):
            await task
    finally:
        cancellation.unregister("b1")
    assert client.cancelled == ["g0"] and client.deleted == ["g0"]


def test_stitch_mixed_sample_rates_preserves_durations(tmp_path):
    a, b = tmp_path / "a.wav", tmp_path / "b.wav"
    write_wav(a, 1.0, 24000)
    write_wav(b, 2.0, 44100)
    out = tmp_path / "out.wav"
    durations = stitch_wavs([a, b], out, gap_seconds=0.25)
    assert [round(d, 2) for d in durations] == [1.0, 2.0]
    with wave.open(str(out)) as w:
        assert w.getframerate() == 24000 and w.getnchannels() == 1
        assert round(w.getnframes() / w.getframerate(), 2) == 3.25


class SlowGenerateClient(FakeClient):
    """generate() for the given texts is still in flight (POST sent, no id yet) for a while."""

    def __init__(self, slow_generate: dict[str, float], **kwargs):
        super().__init__(**kwargs)
        self.slow_generate = slow_generate

    async def generate(self, profile_id, text, language, engine, model_size):
        gen_id = await super().generate(profile_id, text, language, engine, model_size)
        await asyncio.sleep(self.slow_generate.get(text, 0))
        return gen_id


@pytest.mark.asyncio
async def test_failure_while_sibling_is_inside_generate_cleans_up_its_generation(tmp_path):
    client = SlowGenerateClient({"queued": 0.05}, fail_on="bad")
    provider = VoiceboxProvider(client=client, model="qwen-tts-1.7B", concurrency=2)
    with pytest.raises(VoiceboxError, match="failed: boom"):
        await provider.synthesize_conversation(
            script(("HOST1", "bad"), ("HOST1", "queued")),
            tmp_path / "o.wav", voice_map={"HOST1": "Dad"})
    queued = next(g["id"] for g in client.generated if g["text"] == "queued")
    assert queued in client.cancelled and queued in client.deleted
    assert set(client.deleted) == {g["id"] for g in client.generated}
    assert not any(p.name.startswith(".voicebox-") for p in tmp_path.iterdir())


def test_stitch_closes_every_file_and_decodes_each_once(tmp_path, monkeypatch):
    import gc
    import warnings
    from pydub import AudioSegment

    paths = [tmp_path / f"{i}.wav" for i in range(3)]
    for path in paths:
        write_wav(path, 0.2, 24000)
    decoded = []
    original = AudioSegment.from_wav.__func__

    def counting_from_wav(cls, file, *args, **kwargs):
        decoded.append(file)
        return original(cls, file, *args, **kwargs)

    monkeypatch.setattr(AudioSegment, "from_wav", classmethod(counting_from_wav))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        stitch_wavs(paths, tmp_path / "out.wav", gap_seconds=0.1)
        gc.collect()
    assert len(decoded) == len(paths)
    assert not [w for w in caught if issubclass(w.category, ResourceWarning)]


@pytest.mark.asyncio
async def test_cancelled_briefing_submits_no_new_lines(tmp_path):
    from app.services import cancellation
    from app.services.cancellation import BriefingCancelledException
    client = FakeClient()
    provider = VoiceboxProvider(client=client, model="qwen-tts-1.7B", concurrency=1)
    cancellation.register("b2")
    cancellation.signal("b2")
    try:
        with pytest.raises(BriefingCancelledException):
            await provider.synthesize_conversation(
                script(("HOST1", "one"), ("HOST1", "two")), tmp_path / "o.wav",
                voice_map={"HOST1": "Dad"}, briefing_id="b2")
    finally:
        cancellation.unregister("b2")
    assert client.generated == []


class TrackingWaitClient(SlowGenerateClient):
    """Keeps every wait_until_done coroutine so a test can see if one was left unawaited."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.waits = []

    def wait_until_done(self, generation_id, timeout):
        coro = super().wait_until_done(generation_id, timeout)
        self.waits.append(coro)
        return coro


@pytest.mark.asyncio
async def test_cancel_during_submit_leaves_no_unawaited_coroutine(tmp_path):
    from app.services import cancellation
    from app.services.cancellation import BriefingCancelledException
    client = TrackingWaitClient({"slow post": 0.05})
    provider = VoiceboxProvider(client=client, model="qwen-tts-1.7B", concurrency=1)
    cancellation.register("b3")
    try:
        task = asyncio.create_task(provider.synthesize_conversation(
            script(("HOST1", "slow post")), tmp_path / "o.wav",
            voice_map={"HOST1": "Dad"}, briefing_id="b3"))
        await asyncio.sleep(0.01)
        cancellation.signal("b3")  # while POST /generate is still in flight
        with pytest.raises(BriefingCancelledException):
            await task
    finally:
        cancellation.unregister("b3")
    # A coroutine that was never started and never closed still has its frame.
    assert all(coro.cr_frame is None for coro in client.waits)
    assert client.cancelled == ["g0"] and client.deleted == ["g0"]
