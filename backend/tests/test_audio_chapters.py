"""Tests for ID3 chapter embedding."""
from mutagen.id3 import ID3

from app.utils.audio import embed_chapters_in_mp3


def test_embed_writes_chap_and_ctoc(silent_mp3):
    chapters = [
        {"title": "Intro", "start_time": 0.0, "end_time": 2.0},
        {"title": "Story One", "start_time": 2.0, "end_time": 5.0},
        {"title": "Wrap Up", "start_time": 5.0, "end_time": 7.5},
    ]
    ok = embed_chapters_in_mp3(silent_mp3, chapters, title="My Briefing")
    assert ok is True

    tags = ID3(silent_mp3)
    chaps = tags.getall("CHAP")
    ctocs = tags.getall("CTOC")
    assert len(chaps) == 3
    assert len(ctocs) == 1
    by_id = {c.element_id: c for c in chaps}
    assert by_id["chp0"].sub_frames.getall("TIT2")[0].text[0] == "Intro"
    assert by_id["chp0"].start_time == 0
    assert by_id["chp1"].start_time == 2000
    assert by_id["chp2"].end_time == 7500
    assert tags.getall("TIT2")[0].text[0] == "My Briefing"


def test_embed_is_idempotent(silent_mp3):
    chapters = [{"title": "A", "start_time": 0.0, "end_time": 1.0}]
    embed_chapters_in_mp3(silent_mp3, chapters)
    embed_chapters_in_mp3(silent_mp3, chapters)
    tags = ID3(silent_mp3)
    assert len(tags.getall("CHAP")) == 1
    assert len(tags.getall("CTOC")) == 1


def test_embed_empty_chapters_returns_false(silent_mp3):
    assert embed_chapters_in_mp3(silent_mp3, []) is False


def test_embed_bad_path_returns_false_no_raise():
    assert embed_chapters_in_mp3("/nonexistent/path/x.mp3", [{"title": "A", "start_time": 0.0, "end_time": 1.0}]) is False
