"""Delivery helpers shared by the briefing service and TTS providers."""

import re
from typing import Optional

from app.services.llm.personalities import get_personality

_PAUSE_TAG = re.compile(r"\[(?:short|medium|long) pause\]", re.IGNORECASE)
# Any bracketed tag that is not a chapter marker.
_NON_CHAPTER_TAG = re.compile(r"\[(?!CHAPTER:)[^\]\n]{1,40}\]", re.IGNORECASE)
_SPACE_BEFORE_PUNCT = re.compile(r" +([.,!?;:])")


def strip_inert_tags(script: str, keep_sounds: bool) -> str:
    """Remove markup no TTS provider implements.

    Pause tags are always removed: none of the providers turn them into
    silence, and some read them aloud. Other bracketed sound/style tags are
    removed unless keep_sounds is True (Gemini/ElevenLabs v3 with non-speech
    sounds enabled). [CHAPTER: ...] markers are always preserved.
    """
    out = _PAUSE_TAG.sub("", script)
    if not keep_sounds:
        out = _NON_CHAPTER_TAG.sub("", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = _SPACE_BEFORE_PUNCT.sub(r"\1", out)
    return "\n".join(line.strip() for line in out.split("\n"))


def build_delivery_style(cast_members: list[dict], cast_description: Optional[str]) -> str:
    """One natural-language instruction telling the TTS how the show should sound.

    Uses the cast description when the user wrote one; otherwise derives a
    line per host from their personality.
    """
    names = [m.get("name", f"HOST{i+1}") for i, m in enumerate(cast_members)]
    if cast_description and cast_description.strip():
        return (
            f"Read this as a real podcast conversation between {' and '.join(names)}. "
            f"{cast_description.strip()} Natural pacing, quick back-and-forth, react to each other."
        )
    host_lines = []
    for name, member in zip(names, cast_members):
        p = get_personality(member.get("personality", "Casual"))
        host_lines.append(f"{name} sounds {p.voice.lower()}")
    return (
        f"Read this as a real podcast conversation between {' and '.join(names)}, "
        "not a news read. " + ". ".join(host_lines) + ". "
        "Natural pacing, quick back-and-forth, react to each other, no announcer voice."
    )
