"""Voicebox TTS provider: one Voicebox generation per script line, stitched locally.

Lines render with bounded concurrency so the server always has the next line
queued; output order follows the script. Audio is streamed to disk and
stitched one line at a time, so memory stays flat for long episodes.
"""

import asyncio
import shutil
import tempfile
import time
import wave
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.services.tts.base import SegmentTiming, TTSProvider, TTSResult, Voice
from app.services.tts.voicebox_client import (
    VOICEBOX_MODELS, VoiceboxClient, VoiceboxError, VoiceboxProfile,
)
from app.utils.audio import convert_to_mp3

GAP_SECONDS = 0.25
LINE_TIMEOUT_SECONDS = 300.0  # the first line may wait for a model to load


def stitch_wavs(paths: list[Path], output: Path, gap_seconds: float) -> list[float]:
    """Append WAVs into one mono WAV at the first file's rate; returns each line's duration."""
    from pydub import AudioSegment

    def load(path: Path) -> "AudioSegment":
        with open(path, "rb") as f:
            return AudioSegment.from_wav(f)

    first = load(paths[0])
    rate, width = first.frame_rate, first.sample_width
    gap = b"\x00" * (int(gap_seconds * rate) * width)
    durations: list[float] = []
    with wave.open(str(output), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(width)
        out.setframerate(rate)
        for index, path in enumerate(paths):
            segment = first if index == 0 else load(path)
            segment = segment.set_channels(1).set_frame_rate(rate).set_sample_width(width)
            out.writeframes(segment.raw_data)
            durations.append(len(segment.raw_data) / (rate * width))
            if index < len(paths) - 1:
                out.writeframes(gap)
    return durations


def _normalize(name: str) -> str:
    return " ".join(name.split()).casefold()


_cleanup_tasks: set[asyncio.Future] = set()


def _track(task: asyncio.Future) -> asyncio.Future:
    """Keep a strong reference so best-effort cleanup survives a repeated cancel."""
    _cleanup_tasks.add(task)
    task.add_done_callback(_cleanup_tasks.discard)
    return task


def _first_error(error: BaseException) -> BaseException:
    """The first real failure inside (possibly nested) exception groups."""
    while isinstance(error, BaseExceptionGroup):
        real = [e for e in error.exceptions if not isinstance(e, asyncio.CancelledError)]
        error = (real or list(error.exceptions))[0]
    return error


class VoiceboxProvider(TTSProvider):
    def __init__(
        self,
        client: Optional[VoiceboxClient] = None,
        model: Optional[str] = None,
        concurrency: Optional[int] = None,
    ):
        settings = get_settings()
        if client is None:
            if not settings.voicebox_url:
                raise ValueError("Voicebox server URL required")
            client = VoiceboxClient(settings.voicebox_url)
        self.client = client
        self.model = settings.voicebox_model if model is None else model
        self.concurrency = max(1, concurrency or settings.voicebox_concurrency)

    async def close(self):
        await self.client.close()

    def list_voices(self) -> list[Voice]:
        # Voices are live on the server; the cast API uses registry.list_provider_voices.
        return []

    async def _resolve_voices(self, voice_ids: set[str]) -> dict[str, VoiceboxProfile]:
        profiles = await self.client.list_profiles()
        by_id = {p.id: p for p in profiles}
        by_name = {_normalize(p.name): p for p in profiles}
        resolved = {}
        for voice_id in voice_ids:
            profile = by_id.get(voice_id) or by_name.get(_normalize(voice_id))
            if profile is None:
                raise VoiceboxError(f"'{voice_id}' isn't a Voicebox voice. Edit the cast.")
            resolved[voice_id] = profile
        return resolved

    async def _default_engine(self) -> tuple[str, Optional[str]]:
        downloaded = await self.client.list_tts_models()
        if not self.model:
            if not downloaded:
                raise VoiceboxError(f"No supported TTS model is downloaded on {self.client.base_url}.")
            return downloaded[0].engine, downloaded[0].model_size
        if self.model not in VOICEBOX_MODELS:
            raise VoiceboxError(f"Voicebox model '{self.model}' isn't supported by Augustus.")
        if self.model not in {m.name for m in downloaded}:
            raise VoiceboxError(f"Voicebox model '{self.model}' isn't downloaded on {self.client.base_url}.")
        return VOICEBOX_MODELS[self.model]

    async def _discard_submitted(self, submit: "asyncio.Future[str]") -> None:
        """Wait for an interrupted POST /generate; cancel and delete what it created."""
        try:
            generation_id = await submit
        except BaseException:
            return  # the request itself failed, so nothing was created
        try:
            await self.client.cancel_generation(generation_id)
        finally:
            await self.client.delete_generation(generation_id)

    async def _render_line(
        self, text: str, profile: VoiceboxProfile, engine: tuple[str, Optional[str]],
        dest: Path, briefing_id: Optional[str],
    ) -> None:
        from app.services.cancellation import (
            BriefingCancelledException, cancellable_await, is_cancelled,
        )

        # Don't submit new work for a briefing that has already been cancelled.
        if briefing_id and is_cancelled(briefing_id):
            raise BriefingCancelledException("Briefing was cancelled by user")
        engine_name, size = (profile.preset_engine, None) if profile.voice_type == "preset" else engine
        started = time.monotonic()
        # The server may queue the generation before our POST returns, so a cancel
        # mid-POST still lets the request finish and removes what it created.
        submit = asyncio.ensure_future(
            self.client.generate(profile.id, text, profile.language, engine_name, size))
        try:
            generation_id = await asyncio.shield(submit)
        except BaseException:
            await asyncio.shield(_track(asyncio.ensure_future(self._discard_submitted(submit))))
            raise
        try:
            wait = self.client.wait_until_done(generation_id, LINE_TIMEOUT_SECONDS)
            try:
                await (cancellable_await(wait, briefing_id) if briefing_id else wait)
            finally:
                wait.close()  # no-op once awaited; avoids "never awaited" if cancelled first
            await self.client.download_audio(generation_id, dest)
        except BaseException:
            await asyncio.shield(self.client.cancel_generation(generation_id))
            raise
        finally:
            await asyncio.shield(self.client.delete_generation(generation_id))
        print(f"[Voicebox] {generation_id} ({profile.name.strip()}, {engine_name}) {time.monotonic() - started:.1f}s")

    async def synthesize_conversation(
        self,
        script: list[dict],
        output_path: Path,
        voice_map: Optional[dict[str, str]] = None,
        briefing_id: Optional[str] = None,
        style_prompt: Optional[str] = None,  # not supported by Voicebox engines yet
    ) -> TTSResult:
        voice_map = voice_map or {}
        lines = [
            (segment.get("speaker", "HOST1"), segment["text"].strip())
            for segment in script if segment.get("text", "").strip()
        ]
        if not lines:
            raise VoiceboxError("The script has no lines to speak.")
        voice_for = {speaker: voice_map.get(speaker, speaker) for speaker, _ in lines}
        profiles = await self._resolve_voices(set(voice_for.values()))
        engine = await self._default_engine()

        started = time.monotonic()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        workdir = Path(tempfile.mkdtemp(prefix=".voicebox-", dir=output_path.parent))
        try:
            paths = [workdir / f"{i:05d}.wav" for i in range(len(lines))]
            semaphore = asyncio.Semaphore(self.concurrency)
            failed = False

            async def render(i: int) -> None:
                nonlocal failed
                async with semaphore:
                    # A waiter woken by a failing line's release can run before the
                    # TaskGroup cancels it; don't start a new generation then.
                    if failed:
                        return
                    speaker, text = lines[i]
                    try:
                        await self._render_line(text, profiles[voice_for[speaker]], engine, paths[i], briefing_id)
                    except BaseException:
                        failed = True
                        raise

            try:
                async with asyncio.TaskGroup() as group:  # the first failure cancels the rest
                    for i in range(len(lines)):
                        group.create_task(render(i))
            except BaseExceptionGroup as group_error:
                # Callers expect VoiceboxError / BriefingCancelledException, not a group.
                raise _first_error(group_error) from None

            wav_path = workdir / "episode.wav"
            durations = await asyncio.to_thread(stitch_wavs, paths, wav_path, GAP_SECONDS)
            fmt = await self._finalize(wav_path, output_path)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        timings, cursor = [], 0.0
        for index, ((speaker, text), duration) in enumerate(zip(lines, durations)):
            timings.append(SegmentTiming(index, speaker, text, cursor, cursor + duration, duration))
            cursor += duration + (GAP_SECONDS if index < len(lines) - 1 else 0.0)
        elapsed = time.monotonic() - started
        print(f"[Voicebox] {len(lines)} lines, {cursor:.1f}s audio in {elapsed:.1f}s "
              f"(real-time factor {elapsed / max(cursor, 0.01):.2f})")
        return TTSResult(output_path, cursor, "conversation", fmt, timings)

    async def _finalize(self, wav_path: Path, output_path: Path) -> str:
        if output_path.suffix.lower() == ".mp3":
            if await convert_to_mp3(wav_path, output_path):
                return "mp3"
            print("[Voicebox] MP3 conversion unavailable (ffmpeg missing); keeping WAV audio")
        shutil.move(str(wav_path), output_path)
        return "wav"

    async def synthesize(
        self, text: str, voice_id: str, output_path: Path, briefing_id: Optional[str] = None,
    ) -> TTSResult:
        return await self.synthesize_conversation(
            [{"speaker": "HOST1", "text": text}], output_path, {"HOST1": voice_id}, briefing_id=briefing_id,
        )
