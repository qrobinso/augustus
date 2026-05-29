"""Tests for web research gap-fill helpers."""
import pytest

from app.services.web_research import (
    story_needs_research,
    select_stories_for_research,
    merge_sources,
)


class FakeItem:
    def __init__(self, title, content="", url=""):
        self.title = title
        self.content = content
        self.url = url


def test_story_needs_research_thin_content():
    assert story_needs_research(FakeItem("A", content="short"), facts=[], min_chars=600, min_facts=2) is True


def test_story_needs_research_sufficient_content():
    assert story_needs_research(FakeItem("A", content="x" * 700), facts=["f1", "f2"], min_chars=600, min_facts=2) is False


def test_story_needs_research_few_facts():
    assert story_needs_research(FakeItem("A", content="x" * 700), facts=["only one"], min_chars=600, min_facts=2) is True


def test_select_stories_caps_at_max():
    items = [FakeItem(f"s{i}", content="short") for i in range(10)]
    facts_by_index = {i: [] for i in range(10)}
    selected = select_stories_for_research(items, facts_by_index, min_chars=600, min_facts=2, max_stories=3)
    assert len(selected) == 3
    assert selected == [0, 1, 2]


def test_merge_sources_dedupes_by_url():
    existing = [{"title": "A", "url": "http://a.com"}]
    new = [{"title": "A dup", "url": "http://a.com"}, {"title": "B", "url": "http://b.com"}]
    merged = merge_sources(existing, new)
    urls = [s["url"] for s in merged]
    assert urls == ["http://a.com", "http://b.com"]
