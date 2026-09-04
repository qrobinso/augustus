"""Delivery: real names reach the TTS, inert tags do not, and Gemini gets a style prompt."""
from app.services.briefing import BriefingService
from app.services.tts.style import build_delivery_style, strip_inert_tags
from app.services.tts.gemini import GeminiProvider

CAST = [{"name": "Alex", "personality": "Casual", "order": 0, "voice_id": "Kore"},
        {"name": "Sam", "personality": "The Skeptic", "order": 1, "voice_id": "Puck"}]


def test_parse_script_keeps_real_names_alongside_host_ids():
    svc = BriefingService.__new__(BriefingService)
    segs = svc._parse_script("Alex: hi there\nSam: hello\n[CHAPTER: X]\nAlex: next", CAST)
    assert [s["speaker"] for s in segs] == ["HOST1", "HOST2", "HOST1"]
    assert [s["name"] for s in segs] == ["Alex", "Sam", "Alex"]


def test_strip_inert_tags_removes_pauses_always():
    text = "So... [short pause] here's the thing. [medium pause]\n[CHAPTER: Keep]\nAlex: ok"
    out = strip_inert_tags(text, keep_sounds=True)
    assert "pause]" not in out
    assert "[CHAPTER: Keep]" in out
    assert "So... here's the thing." in out


def test_strip_inert_tags_removes_sound_tags_when_disabled():
    text = "Alex: [laughing] okay [sigh] fine [CHAPTER: Keep]"
    assert strip_inert_tags(text, keep_sounds=False) == "Alex: okay fine [CHAPTER: Keep]"
    assert "[laughing]" in strip_inert_tags(text, keep_sounds=True)


def test_delivery_style_uses_cast_description_or_personalities():
    custom = build_delivery_style(CAST, "Two old friends who argue over coffee.")
    assert "argue over coffee" in custom
    default = build_delivery_style(CAST, None)
    assert "Alex" in default and "Sam" in default
    assert "Skeptic" in default or "cautious" in default.lower()


def test_gemini_conversation_text_uses_names_and_style_prefix():
    script = [{"speaker": "HOST1", "name": "Alex", "text": "hi"},
              {"speaker": "HOST2", "name": "Sam", "text": "hey"}]
    text, segments, labels = GeminiProvider._build_conversation(script, style_prompt="Fast and playful.")
    assert text.startswith("Fast and playful.")
    assert "Alex: hi" in text and "Sam: hey" in text
    assert "HOST1:" not in text
    assert labels == {"HOST1": "Alex", "HOST2": "Sam"}
    assert segments[0]["speaker"] == "HOST1"  # timings still keyed by host id


def test_gemini_conversation_text_falls_back_to_host_ids():
    text, _, labels = GeminiProvider._build_conversation([{"speaker": "HOST1", "text": "hi"}], style_prompt=None)
    assert text == "HOST1: hi"
    assert labels == {"HOST1": "HOST1"}
