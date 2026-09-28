"""HTTP client for a self-hosted Voicebox server (tested against API 0.5.0)."""

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

import httpx

# Voicebox model name -> (engine, model_size) for POST /generate. The only
# Voicebox-version-specific table in Augustus: unknown models are skipped.
VOICEBOX_MODELS: dict[str, tuple[str, Optional[str]]] = {
    "qwen-tts-1.7B": ("qwen", "1.7B"),
    "qwen-tts-0.6B": ("qwen", "0.6B"),
    "qwen-custom-voice-1.7B": ("qwen_custom_voice", "1.7B"),
    "qwen-custom-voice-0.6B": ("qwen_custom_voice", "0.6B"),
    "luxtts": ("luxtts", None),
    "chatterbox-tts": ("chatterbox", None),
    "chatterbox-turbo": ("chatterbox_turbo", None),
    "tada-1b": ("tada", "1B"),
    "tada-3b-ml": ("tada", "3B"),
    "kokoro": ("kokoro", None),
    "breeze-tts-2": ("breeze", None),
}
MIN_TESTED_VERSION = (0, 5, 0)
PROFILE_CACHE_SECONDS = 30.0

# base_url -> (fetched_at, profiles); shared by the voices API and synthesis.
_profile_cache: dict[str, tuple[float, list["VoiceboxProfile"]]] = {}

T = TypeVar("T")


class VoiceboxError(RuntimeError):
    """A Voicebox failure with a message fit to show on a failed briefing."""


@dataclass(frozen=True)
class VoiceboxProfile:
    id: str
    name: str
    language: str
    voice_type: str
    preset_engine: Optional[str]


@dataclass(frozen=True)
class VoiceboxModel:
    name: str
    display_name: str
    engine: str
    model_size: Optional[str]


def parse_version(version: str) -> tuple[int, ...]:
    parts = []
    for piece in version.split("."):
        digits = ""
        for ch in piece:
            if not ch.isdigit():
                break
            digits += ch
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


class VoiceboxClient:
    def __init__(self, base_url: str, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0, connect=5.0),
            transport=transport,
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = await self._http.request(method, path, **kwargs)
        except httpx.TransportError as error:
            raise VoiceboxError(f"Can't reach Voicebox at {self.base_url}.") from error
        if response.status_code >= 400:
            raise VoiceboxError(f"Voicebox {method} {path} failed with HTTP {response.status_code}.")
        return response

    def _parse(self, payload: Callable[[], Any], read: Callable[[Any], T]) -> T:
        """Read a response body, treating any unexpected shape as "not Voicebox"."""
        try:
            return read(payload())
        except (ValueError, KeyError, TypeError, AttributeError) as error:  # incl. JSON decode
            raise VoiceboxError(f"{self.base_url} doesn't look like a Voicebox server.") from error

    async def _json(self, method: str, path: str, read: Callable[[Any], T], **kwargs) -> T:
        response = await self._request(method, path, **kwargs)
        return self._parse(response.json, read)

    async def version(self) -> str:
        """The server's API version, or "" when it doesn't say."""
        return await self._json("GET", "/openapi.json",
                                lambda body: str(body.get("info", {}).get("version") or ""))

    async def list_profiles(self, max_age: float = PROFILE_CACHE_SECONDS) -> list[VoiceboxProfile]:
        cached = _profile_cache.get(self.base_url)
        if cached and time.monotonic() - cached[0] < max_age:
            return cached[1]
        profiles = await self._json("GET", "/profiles", lambda raw: [
            VoiceboxProfile(
                id=p["id"], name=p.get("name") or p["id"], language=p.get("language") or "en",
                voice_type=p.get("voice_type") or "cloned", preset_engine=p.get("preset_engine"),
            )
            for p in raw
        ])
        _profile_cache[self.base_url] = (time.monotonic(), profiles)
        return profiles

    async def list_tts_models(self) -> list[VoiceboxModel]:
        statuses = await self._json("GET", "/models/status", lambda body: [
            (m.get("model_name", ""), m.get("display_name"), bool(m.get("downloaded")))
            for m in body.get("models", [])
        ])
        models = []
        for name, display_name, downloaded in statuses:
            if not downloaded:
                continue
            if name not in VOICEBOX_MODELS:
                print(f"[Voicebox] Skipping model {name!r}: not a TTS model Augustus knows")
                continue
            engine, size = VOICEBOX_MODELS[name]
            models.append(VoiceboxModel(name, display_name or name, engine, size))
        return models

    async def generate(self, profile_id: str, text: str, language: str, engine: str,
                       model_size: Optional[str]) -> str:
        body = {"profile_id": profile_id, "text": text, "language": language, "engine": engine}
        if model_size:
            body["model_size"] = model_size
        return await self._json("POST", "/generate", lambda raw: str(raw["id"]), json=body)

    async def wait_until_done(self, generation_id: str, timeout: float) -> None:
        """Follow the status event stream until the generation completes or fails."""
        async def follow() -> Optional[dict]:
            last = None
            try:
                async with self._http.stream(
                    "GET", f"/generate/{generation_id}/status",
                    timeout=httpx.Timeout(timeout, connect=5.0),
                ) as response:
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        last = self._parse(lambda: json.loads(line[5:].strip()), dict)
                        if last.get("status") in ("completed", "failed"):
                            return last
            except httpx.TransportError as error:
                raise VoiceboxError(f"Can't reach Voicebox at {self.base_url}.") from error
            return last

        try:
            event = await asyncio.wait_for(follow(), timeout=timeout)
        except asyncio.TimeoutError:
            raise VoiceboxError(f"Voicebox generation {generation_id} timed out after {int(timeout)}s.")
        if not event or event.get("status") not in ("completed", "failed"):
            # The stream ended early; ask once for the stored result.
            event = await self._json("GET", f"/history/{generation_id}", dict)
        if event.get("status") == "failed":
            raise VoiceboxError(f"Voicebox generation {generation_id} failed: {event.get('error') or 'unknown error'}")
        if event.get("status") != "completed":
            raise VoiceboxError(f"Voicebox generation {generation_id} ended as {event.get('status')!r}.")

    async def download_audio(self, generation_id: str, dest: Path) -> None:
        try:
            async with self._http.stream("GET", f"/audio/{generation_id}") as response:
                if response.status_code >= 400:
                    raise VoiceboxError(f"Voicebox audio for {generation_id} failed with HTTP {response.status_code}.")
                with open(dest, "wb") as out:
                    async for chunk in response.aiter_bytes():
                        out.write(chunk)
        except httpx.TransportError as error:
            raise VoiceboxError(f"Can't reach Voicebox at {self.base_url}.") from error

    async def delete_generation(self, generation_id: str) -> None:
        """Best effort: history cleanup must never fail a briefing."""
        try:
            await self._http.delete(f"/history/{generation_id}")
        except httpx.HTTPError as error:
            print(f"[Voicebox] Could not delete generation {generation_id}: {error}")

    async def cancel_generation(self, generation_id: str) -> None:
        try:
            await self._http.post(f"/generate/{generation_id}/cancel")
        except httpx.HTTPError as error:
            print(f"[Voicebox] Could not cancel generation {generation_id}: {error}")
