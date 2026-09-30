"""Standalone Gemini TTS smoke test.

Bypasses the briefing pipeline so we can tell whether the API call itself
works for this account/key/model. Run from repo root:

    python backend/scripts/smoke_gemini_tts.py

Reads GEMINI_API_KEY from env or backend/.env. Set GEMINI_MODEL to override
the default model.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Load backend/.env if present
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except Exception:
    pass

from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-preview-tts")

if not API_KEY:
    sys.exit("GEMINI_API_KEY not set")

print(f"[smoke] google-genai version: {getattr(genai, '__version__', '?')}")
print(f"[smoke] model: {MODEL}")

client = genai.Client(
    api_key=API_KEY,
    http_options=types.HttpOptions(timeout=60_000),
)

# --- 1) Single-speaker ---
print("\n[smoke] === single-speaker ===")
config = types.GenerateContentConfig(
    response_modalities=["AUDIO"],
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore"),
        )
    ),
)
t0 = time.time()
try:
    resp = client.models.generate_content(
        model=MODEL,
        contents="Say cheerfully: have a wonderful day!",
        config=config,
    )
    dur = time.time() - t0
    parts = resp.candidates[0].content.parts if resp.candidates else []
    audio = b"".join(p.inline_data.data for p in parts if p.inline_data and p.inline_data.data)
    print(f"[smoke] single-speaker OK in {dur:.1f}s, {len(audio)} bytes audio")
except Exception as e:
    print(f"[smoke] single-speaker FAILED after {time.time()-t0:.1f}s: {type(e).__name__}: {e}")

# --- 2) Multi-speaker ---
print("\n[smoke] === multi-speaker ===")
config = types.GenerateContentConfig(
    response_modalities=["AUDIO"],
    speech_config=types.SpeechConfig(
        multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
            speaker_voice_configs=[
                types.SpeakerVoiceConfig(
                    speaker="HOST1",
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore"),
                    ),
                ),
                types.SpeakerVoiceConfig(
                    speaker="HOST2",
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Sadachbia"),
                    ),
                ),
            ]
        ),
    ),
)
script = (
    "HOST1: Welcome to the show.\n"
    "HOST2: Glad to be here.\n"
    "HOST1: Let's get started.\n"
)
t0 = time.time()
try:
    resp = client.models.generate_content(
        model=MODEL,
        contents=script,
        config=config,
    )
    dur = time.time() - t0
    parts = resp.candidates[0].content.parts if resp.candidates else []
    audio = b"".join(p.inline_data.data for p in parts if p.inline_data and p.inline_data.data)
    print(f"[smoke] multi-speaker OK in {dur:.1f}s, {len(audio)} bytes audio")
except Exception as e:
    print(f"[smoke] multi-speaker FAILED after {time.time()-t0:.1f}s: {type(e).__name__}: {e}")
