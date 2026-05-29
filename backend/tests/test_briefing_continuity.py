from app.services.llm.agents.briefing_writer import build_continuity_section, NON_SPEECH_SOUNDS_GUIDE


def test_continuity_lists_prior_titles():
    section = build_continuity_section(["Story A", "Story B"])
    assert "Story A" in section
    assert "Story B" in section
    assert "do not repeat" in section.lower()


def test_continuity_empty_when_no_titles():
    assert build_continuity_section([]) == ""


def test_disfluency_guide_is_not_aggressive():
    # The over-stuffing language was removed.
    assert "OFTEN (2-4 times per segment)" not in NON_SPEECH_SOUNDS_GUIDE
    assert "FREQUENTLY (3-5 times per segment)" not in NON_SPEECH_SOUNDS_GUIDE
