"""Single source of truth for TTS providers: ids, labels, capabilities and voices.

Adding a provider = a registry entry, a TTSProvider class in the factory, a
voice-listing branch below and a Settings card. Nothing else hard-codes the list.
"""

import re
from dataclasses import dataclass
from typing import Iterable

from app.config import get_settings
from app.services.tts.base import Voice


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    label: str
    # The built-in catalogs for these providers are partial, so casts may use raw IDs.
    allows_custom_voice: bool


TTS_PROVIDERS: dict[str, ProviderSpec] = {
    "piper": ProviderSpec("piper", "Piper", allows_custom_voice=True),
    "elevenlabs": ProviderSpec("elevenlabs", "ElevenLabs", allows_custom_voice=True),
    "gemini": ProviderSpec("gemini", "Google Gemini", allows_custom_voice=False),
}


def provider_label(provider: str) -> str:
    spec = TTS_PROVIDERS.get(provider)
    return spec.label if spec else provider


def active_tts_provider() -> str:
    return get_settings().tts_provider


_ELEVENLABS_ID = re.compile(r"^[A-Za-z0-9]{20}$")
_KOKORO_VOICE = re.compile(r"^[a-z]{2}_[a-z]+$")  # af_heart, am_eric
_PIPER_MODEL = re.compile(r"^[a-z]{2}_[A-Z]{2}-")  # en_US-lessac-medium


def _looks_like_piper(voice_id: str) -> bool:
    return (
        ":" in voice_id
        or "," in voice_id  # Kokoro blends such as "af_heart:0.6,af_bella:0.4"
        or bool(_KOKORO_VOICE.match(voice_id))
        or bool(_PIPER_MODEL.match(voice_id))
    )


def infer_cast_provider(voice_ids: Iterable[str], fallback: str) -> str:
    """Best-effort provider for a legacy cast, judged from its member voice IDs."""
    from app.services.tts.gemini import GeminiProvider

    ids = [v.strip() for v in voice_ids if v and v.strip()]
    if not ids:
        return fallback
    if all(v in GeminiProvider.VOICES for v in ids):
        return "gemini"
    if any(_ELEVENLABS_ID.match(v) for v in ids):
        return "elevenlabs"
    if any(_looks_like_piper(v) for v in ids):
        return "piper"
    return fallback


async def list_provider_voices(provider: str) -> list[Voice]:
    """Voices a cast can use with this provider, de-duplicated by id."""
    if provider == "gemini":
        from app.services.tts.gemini import GeminiProvider
        voices = list(GeminiProvider.VOICES.values())
    elif provider == "elevenlabs":
        from app.services.tts.elevenlabs import ElevenLabsProvider
        voices = list(ElevenLabsProvider.VOICES.values())
    elif provider == "piper":
        from app.services.tts.piper import PiperProvider
        voices = list(PiperProvider.VOICES.values())
    else:
        raise ValueError(f"Unknown TTS provider: {provider}")
    unique: dict[str, Voice] = {}
    for voice in voices:
        unique.setdefault(voice.id, voice)
    return list(unique.values())
