"""The writer prompt should set up a cast with real stances and get out of the way."""
import pytest

from tests.conftest import FakeLLM
from app.services.llm.agents.briefing_writer import BriefingWriterAgent
from app.services.llm.agents.host_research import HostResearch
from app.services.llm.personalities import PERSONALITY_REGISTRY, get_personality
from app.services.news import NewsItem

CAST = [{"name": "Alex", "personality": "Casual"}, {"name": "Sam", "personality": "The Skeptic"}]


def _sp(**kw):
    return BriefingWriterAgent(FakeLLM())._build_system_prompt(CAST, cast_name="Show", topics=["AI"], **kw)


def test_system_prompt_is_lean():
    sp = _sp(briefing_title="Morning AI")
    assert len(sp) < 4500, len(sp)


def test_system_prompt_drops_the_formula():
    sp = _sp()
    for banned in [
        "Alright, let's shift gears here",   # canned transition list
        "[medium pause]",                    # inert pause mandate
        "PLAYFUL BANTER",                    # scripted banter recipe
        "AVOID:",                            # affect-flattening ban list
        "Rise and shine",                    # time-of-day greeting list
        "SPARINGLY",                         # throttled dynamics
        "The lead anchor",                   # role bound to slot order
        "what happened, why it matters",     # per-story template
    ]:
        assert banned not in sp, banned


def test_system_prompt_keeps_format_rules_and_names():
    sp = _sp()
    assert "TITLE:" in sp
    assert "[CHAPTER:" in sp
    assert "Alex" in sp and "Sam" in sp


def test_hosts_get_stances_not_slots():
    sp = _sp()
    assert get_personality("Casual").stance in sp
    assert get_personality("The Skeptic").stance in sp


def test_two_hosts_are_told_not_to_ping_pong():
    sp = _sp()
    assert "twice in a row" in sp or "two or three times in a row" in sp


def test_every_personality_has_a_stance():
    for name in PERSONALITY_REGISTRY:
        stance = get_personality(name).stance
        assert stance and len(stance) > 40, name


def test_user_prompt_weights_lead_story_and_uses_editor_priority():
    items = [
        NewsItem(title="Lead", summary="", url="u1", source="s", priority=9, editor_note="big"),
        NewsItem(title="Tail", summary="", url="u2", source="s", priority=5, editor_note="small"),
    ]
    up = BriefingWriterAgent(FakeLLM())._build_user_prompt(
        content="ARTICLE 1: Lead\nARTICLE 2: Tail", topics=["AI"], duration=7, ranked_items=items)
    assert "half" in up.lower()          # lead story gets about half the runtime
    assert "recap" not in up.lower()     # no mandatory recap outro
    assert "1500" not in up and "1050" in up  # 7 min * 150 wpm


def test_user_prompt_tells_hosts_to_react_to_each_others_research():
    research = [HostResearch("Alex", "Casual", "Casual - vibes", {0: ["Question: Q\nAnswer: fact A"]}, []),
                HostResearch("Sam", "The Skeptic", "The Skeptic - doubt", {0: ["Question: Q\nAnswer: fact B"]}, [])]
    up = BriefingWriterAgent(FakeLLM())._build_user_prompt(
        content="news", topics=["AI"], duration=7,
        ranked_items=[NewsItem(title="T", summary="", url="u", source="s")], host_research=research)
    assert "fact A" in up and "fact B" in up
    assert "surprised" in up.lower() or "corrected" in up.lower()


def test_last_script_fallback_is_not_the_outro():
    a = BriefingWriterAgent(FakeLLM())
    script = "Alex: opening line\n" + ("Alex: middle\n" * 300) + "Sam: thanks for listening, see you tomorrow"
    up = a._build_user_prompt(content="news", topics=["AI"], duration=7, last_script=script)
    assert "see you tomorrow" not in up
