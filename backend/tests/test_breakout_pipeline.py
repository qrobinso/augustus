"""Focused breakout research and generation pipeline tests with fake I/O."""

from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.briefing import Briefing
from app.models.cast import Cast, CastMember
from app.models.story import StoryDevelopment
from app.services.breakout import BreakoutResearchError, research_breakout
from app.services.briefing import BriefingService
from app.services.llm.agents.briefing_writer import BriefingWriterAgent
from app.services.llm.agents.orchestrator import BriefingOrchestrator
from app.services.news import NewsService
from app.services.search import SearchResult
from app.services.story_memory import StoryMemoryService
from app.services.tts.base import SegmentTiming, TTSResult
from app.services.tts.factory import TTSFactory
from tests.conftest import FakeLLM, make_silent_mp3


class FocusedSearch:
    """Return a distinct retrieved page for each requested research angle."""

    def __init__(self, empty=False):
        self.queries = []
        self.urls = []
        self.empty = empty

    async def search(self, query, num_results=5):
        self.queries.append(query)
        index = len(self.queries)
        return [
            SearchResult(
                f"Evidence source {index}",
                f"https://research.example/{index}",
                f"Search snippet {index}",
            )
        ]

    async def fetch_page_content(self, url):
        self.urls.append(url)
        if self.empty:
            return None
        return (
            f"Retrieved reporting from {url} with concrete evidence, qualifications, "
            "and enough detail to support a careful podcast discussion. " * 8
        )


@pytest.mark.asyncio
async def test_research_breakout_fetches_multiple_angles_and_keeps_page_provenance():
    search = FocusedSearch()

    result = await research_breakout(
        search=search,
        topic="Fusion energy",
        focus="commercial timelines",
        source_context="The source episode asked when fusion could reach the grid.",
    )

    assert len(search.queries) == 4
    assert all("Fusion energy" in query for query in search.queries)
    assert all("commercial timelines" in query for query in search.queries)
    assert any("background" in query.lower() for query in search.queries)
    assert any("mechanism" in query.lower() for query in search.queries)
    assert any("evidence" in query.lower() for query in search.queries)
    assert any("competing" in query.lower() for query in search.queries)
    assert len(result.sources) == 4
    assert {source["url"] for source in result.sources} == set(search.urls)
    assert all(source["retrieval"] == "fetched_page" for source in result.sources)
    assert "Search snippet" not in result.content
    assert "source episode asked" in result.content


async def setup_breakout_pipeline(db, monkeypatch, tmp_path, *, empty_research=False):
    import app.services.briefing as briefing_module

    monkeypatch.setattr(briefing_module.settings, "audio_storage_path", str(tmp_path))
    monkeypatch.setattr(briefing_module.settings, "host_research_enabled", True)

    cast = Cast(
        id="cast",
        user_id="u",
        profile_id="p",
        name="Deep Dive",
        is_default=True,
        members=[
            CastMember(
                name="Alex",
                personality="Analytical",
                voice_id="fake",
                order=0,
            )
        ],
    )
    briefing = Briefing(
        id="breakout",
        user_id="u",
        profile_id="p",
        cast_id="cast",
        title="Breakout: Fusion energy",
        status="pending",
        extra_data={
            "kind": "breakout",
            "topic_ids": ["fusion-topic"],
            "target_duration": 10,
            "profile_name": "Listener",
            "breakout": {
                "topic": "Fusion energy",
                "focus": "commercial timelines",
                "source_briefing_id": "daily-source",
                "chapter_index": 2,
                "source_title": "Energy roundup",
                "source_context": "The original chapter compared three pilot plants.",
            },
        },
    )
    db.add_all([cast, briefing])
    await db.commit()

    llm = FakeLLM(
        "TITLE: Fusion's Long Road\n"
        "[CHAPTER: 1 | Foundations]\nAlex: The premise begins here.\n"
        "[CHAPTER: 2 | How It Works]\nAlex: The mechanism matters.\n"
        "[CHAPTER: 3 | Evidence]\nAlex: The evidence is mixed.\n"
        "[CHAPTER: 4 | Debate]\nAlex: Critics disagree.\n"
        "[CHAPTER: 5 | Implications]\nAlex: The grid impact follows."
    )
    service = BriefingService.__new__(BriefingService)
    service.db = db
    service.llm = llm
    service.news = NewsService()
    service.search = FocusedSearch(empty=empty_research)
    service.orchestrator = BriefingOrchestrator(llm)
    service.orchestrator.briefing_writer = BriefingWriterAgent(llm)

    async def forbidden_daily_call(*args, **kwargs):
        raise AssertionError("breakouts must not fetch or select the daily feed")

    service.news.fetch_all_feeds = forbidden_daily_call
    service.news.fetch_newsapi = forbidden_daily_call
    service._fetch_custom_site_articles = forbidden_daily_call
    service._analyze_and_rank_stories = forbidden_daily_call

    async def forbidden_memory(*args, **kwargs):
        raise AssertionError("breakouts must not read or write story memory")

    monkeypatch.setattr(StoryMemoryService, "context", forbidden_memory)
    monkeypatch.setattr(StoryMemoryService, "save", forbidden_memory)

    audio_calls = []

    async def synthesize(script, output_path, **kwargs):
        audio_calls.append(script)
        make_silent_mp3(str(output_path))
        timings = [
            SegmentTiming(i, part["speaker"], part["text"], i * 10, (i + 1) * 10, 10)
            for i, part in enumerate(script)
        ]
        return TTSResult(
            Path(output_path),
            len(script) * 10,
            "fake",
            segment_timings=timings,
        )

    monkeypatch.setattr(TTSFactory, "synthesize_conversation", synthesize)
    return service, briefing, llm, audio_calls


@pytest.mark.asyncio
async def test_serialized_generation_keeps_profile_context_through_cancellation_checks(
    db_session, monkeypatch, tmp_path
):
    from app.models.profile import Profile
    from app.services.briefing_queue import briefing_queue

    service, briefing, llm, audio_calls = await setup_breakout_pipeline(
        db_session, monkeypatch, tmp_path
    )
    db_session.add(Profile(id='p', user_id='u', name='Profile Listener'))
    await db_session.commit()

    # Exercise the real wrapper, atomic start, cancellation checks and pipeline.
    # No profile_name override: the eagerly loaded relationship must remain usable.
    result = await service.generate_briefing(briefing.id)
    assert result.status == 'completed'
    assert len(audio_calls) == 1
    assert len(llm.calls) == 1
    assert not briefing_queue.generation_lock.locked()


@pytest.mark.asyncio
async def test_breakout_pipeline_bypasses_daily_selection_and_keeps_requested_duration(
    db_session, monkeypatch, tmp_path
):
    service, briefing, llm, audio_calls = await setup_breakout_pipeline(
        db_session, monkeypatch, tmp_path
    )
    progress_names = []
    original_commit = db_session.commit

    async def recording_commit():
        progress = (briefing.extra_data or {}).get("progress") or {}
        if progress.get("step_name"):
            progress_names.append(progress["step_name"])
        await original_commit()

    monkeypatch.setattr(db_session, "commit", recording_commit)

    result = await service._generate_briefing_internal(
        briefing.id, briefing, ["fusion-topic"], 10, "Listener"
    )

    assert result.status == "completed"
    assert len(audio_calls) == 1
    assert len(llm.calls) == 1
    prompt = llm.calls[0].get("prompt") or llm.calls[0]["messages"][-1]["content"]
    system = llm.calls[0].get("system_prompt") or llm.calls[0]["messages"][0]["content"]
    assert "10-minute" in prompt
    assert "foundations" in prompt.lower()
    assert "mechanisms" in prompt.lower()
    assert "competing viewpoints" in prompt.lower()
    assert "original chapter compared three pilot plants" in prompt.lower()
    assert "one subject" in system.lower()
    assert result.extra_data["editorial_duration_minutes"] == 10
    assert result.extra_data["kind"] == "breakout"
    assert result.extra_data["breakout"]["source_briefing_id"] == "daily-source"
    assert len(result.sources) == 4
    assert all(source["retrieval"] == "fetched_page" for source in result.sources)
    assert result.extra_data["chapter_sources"]["0"] == result.sources
    assert result.extra_data["chapter_stories"] == {}
    assert (await db_session.execute(select(StoryDevelopment))).scalars().all() == []
    assert "Preparing breakout topic" in progress_names
    assert "Planning the deep dive" in progress_names
    assert not any("RSS" in name or "NewsAPI" in name or "custom sites" in name for name in progress_names)


@pytest.mark.asyncio
async def test_breakout_fails_before_writing_or_tts_when_pages_cannot_be_retrieved(
    db_session, monkeypatch, tmp_path
):
    service, briefing, llm, audio_calls = await setup_breakout_pipeline(
        db_session, monkeypatch, tmp_path, empty_research=True
    )

    with pytest.raises(BreakoutResearchError, match="usable pages"):
        await service._generate_briefing_internal(
            briefing.id, briefing, ["fusion-topic"], 10, "Listener"
        )

    assert briefing.status == "failed"
    assert "usable pages" in briefing.error_message
    assert llm.calls == []
    assert audio_calls == []


@pytest.mark.asyncio
async def test_breakout_with_missing_metadata_fails_without_entering_daily_pipeline(
    db_session, monkeypatch, tmp_path
):
    service, briefing, llm, audio_calls = await setup_breakout_pipeline(
        db_session, monkeypatch, tmp_path
    )
    briefing.extra_data = {"kind": "breakout", "target_duration": 10}
    await db_session.commit()

    with pytest.raises(ValueError, match="missing breakout metadata"):
        await service._generate_briefing_internal(
            briefing.id, briefing, [], 10, "Listener"
        )

    assert briefing.status == "failed"
    assert llm.calls == []
    assert audio_calls == []
