"""Selection quality: the editor must see dates/URLs/descriptions/prior titles,
and the pipeline must not pad its choices with rejected articles."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import FakeLLM
from app.services.llm.agents.story_analyzer import StoryAnalyzerAgent
from app.services.news import NewsItem, filter_stale_items


NOW = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)


def _articles():
    return [
        {"title": "Fresh", "summary": "s", "source": "NYT", "category": "ai",
         "url": "https://nyt.com/2026/09/03/fresh", "published": "2026-09-03T10:00:00+00:00"},
        {"title": "Undated", "summary": "s", "source": "Wired", "category": "ai",
         "url": "https://wired.com/tag/ai/", "published": None},
    ]


def test_analyzer_prompt_shows_date_url_and_flags_undated():
    agent = StoryAnalyzerAgent(FakeLLM())
    up = agent._build_user_prompt(_articles(), ["AI"], max_stories=3, today=NOW)
    assert "https://nyt.com/2026/09/03/fresh" in up
    assert "2026-09-03" in up
    assert "Published: unknown" in up
    assert "September 03, 2026" in up  # today's date so it can judge staleness


def test_analyzer_prompt_uses_max_stories_and_topic_descriptions():
    agent = StoryAnalyzerAgent(FakeLLM())
    sp = agent._build_system_prompt(
        ["AI"], topic_descriptions={"AI": "Frontier model releases and AI policy, not consumer gadgets"},
        max_stories=3,
    )
    assert "at most 3" in sp
    assert "not consumer gadgets" in sp
    assert "3-5" not in sp


def test_analyzer_prompt_has_no_weather_bypass():
    agent = StoryAnalyzerAgent(FakeLLM())
    sp = agent._build_system_prompt(["AI"], max_stories=3)
    up = agent._build_user_prompt(_articles(), ["AI"], max_stories=3, today=NOW)
    assert "weather" not in (sp + up).lower()


def test_analyzer_prompt_lists_prior_titles():
    agent = StoryAnalyzerAgent(FakeLLM())
    up = agent._build_user_prompt(_articles(), ["AI"], max_stories=3, today=NOW,
                                  prior_titles=["Nvidia buys Hugging Face"])
    assert "Nvidia buys Hugging Face" in up
    assert "already covered" in up.lower()


@pytest.mark.asyncio
async def test_analyze_and_rank_passes_context_through():
    fake = FakeLLM(response_content='{"ranked_stories": [{"article_num": 1, "priority": 9, "reason": "r"}], "summary": "s"}')
    agent = StoryAnalyzerAgent(fake)
    await agent.analyze_and_rank(_articles(), ["AI"], max_stories=3,
                                 topic_descriptions={"AI": "frontier models"},
                                 prior_titles=["Old story"])
    call = fake.calls[0]
    assert "frontier models" in call["system_prompt"]
    assert "Old story" in call["prompt"]


def test_filter_stale_items_drops_old_keeps_fresh_and_undated():
    items = [
        NewsItem(title="fresh", summary="", url="u1", source="s", published=NOW - timedelta(hours=5)),
        NewsItem(title="old", summary="", url="u2", source="s", published=NOW - timedelta(days=20)),
        NewsItem(title="undated", summary="", url="u3", source="s", published=None),
    ]
    kept = filter_stale_items(items, max_age_days=3, now=NOW)
    assert [i.title for i in kept] == ["fresh", "undated"]


class _FakeOrchestrator:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    async def analyze_and_rank_stories(self, **kwargs):
        self.calls.append(kwargs)
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def _service(orchestrator):
    from app.services.briefing import BriefingService
    svc = BriefingService.__new__(BriefingService)
    svc.orchestrator = orchestrator

    async def _noop(_id):
        return None
    svc._check_cancelled = _noop
    return svc


def _items(n):
    return [NewsItem(title=f"story {i}", summary="s", url=f"http://x/{i}", source="src") for i in range(n)]


@pytest.mark.asyncio
async def test_rank_does_not_pad_when_editor_selects_fewer():
    orch = _FakeOrchestrator([([{"article_num": 2, "priority": 8, "reason": "on topic"}], "sum", "raw", {})])
    svc = _service(orch)
    ranked, summary, raw, usage = await svc._analyze_and_rank_stories(
        briefing_id="b", news_items=_items(6), topics=["AI"], max_stories=3)
    assert [i.title for i in ranked] == ["story 1"]
    assert ranked[0].priority == 8
    assert ranked[0].editor_note == "on topic"


@pytest.mark.asyncio
async def test_rank_retries_once_then_raises_on_bad_json():
    orch = _FakeOrchestrator([ValueError("bad json"), ValueError("bad json again")])
    svc = _service(orch)
    with pytest.raises(ValueError):
        await svc._analyze_and_rank_stories(briefing_id="b", news_items=_items(4), topics=["AI"], max_stories=3)
    assert len(orch.calls) == 2


@pytest.mark.asyncio
async def test_rank_forwards_descriptions_and_prior_titles():
    orch = _FakeOrchestrator([([{"article_num": 1, "priority": 9, "reason": "r"}], None, "", {})])
    svc = _service(orch)
    await svc._analyze_and_rank_stories(
        briefing_id="b", news_items=_items(2), topics=["AI"], max_stories=3,
        topic_descriptions={"AI": "d"}, prior_titles=["p"])
    kw = orch.calls[0]
    assert kw["topic_descriptions"] == {"AI": "d"}
    assert kw["prior_titles"] == ["p"]
    assert kw["articles"][0]["url"] == "http://x/0"
    assert "published" in kw["articles"][0]


@pytest.mark.asyncio
async def test_existing_urls_are_scoped_to_window(db_session):
    from app.models.article import Article
    from app.services.briefing import BriefingService
    old = Article(title="old", url="http://old", source="s", fetched_at=NOW - timedelta(days=30))
    new = Article(title="new", url="http://new", source="s", fetched_at=NOW - timedelta(days=1))
    db_session.add_all([old, new])
    await db_session.commit()
    svc = BriefingService.__new__(BriefingService)
    svc.db = db_session
    found = await svc._get_existing_article_urls(["http://old", "http://new"], since=NOW - timedelta(days=7))
    assert found == {"http://new"}
