"""Exercise the generation pipeline with real DB/editor/writer and fake I/O."""
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.briefing import Briefing
from app.models.cast import Cast, CastMember
from app.models.topic import Topic
from app.models.article import Article
from app.models.story import StoryDevelopment
from app.services.briefing import BriefingService
from app.services.news import NewsItem, NewsService
from app.services.llm.agents.orchestrator import BriefingOrchestrator
from app.services.llm.agents.briefing_writer import BriefingWriterAgent
from app.services.llm.agents.host_research import HostResearchAgent
from app.services.tts.base import TTSResult, SegmentTiming
from app.services.tts.factory import TTSFactory
from tests.conftest import FakeLLM, make_silent_mp3


async def setup_pipeline(db, monkeypatch, tmp_path, ranked=None, fail_audio=False):
    import app.services.briefing as module
    monkeypatch.setattr(module.settings, 'audio_storage_path', str(tmp_path))
    monkeypatch.setattr(module.settings, 'host_research_enabled', True)
    monkeypatch.setattr(module.settings, 'briefing_story_count', 3)
    topic = Topic(id='topic', user_id='u', profile_id='p', name='Launches', slug='launches', use_newsapi=False)
    cast = Cast(user_id='u', profile_id='p', name='Morning', is_default=True,
                members=[CastMember(name='Alex', personality='Analytical', voice_id='fake', order=0)])
    b = Briefing(user_id='u', profile_id='p', title='Daily', status='pending', extra_data={'topic_ids': ['topic']})
    db.add_all([topic, cast, b])
    await db.commit()
    entries = ranked if ranked is not None else [{'article_num': 1, 'priority': 9, 'reason': 'Consequential launch',
        'story_key': 'Acme launch', 'development': 'Acme launches in July.', 'change_type': 'new'}]
    llm = FakeLLM([json.dumps({'ranked_stories': entries, 'summary': 'Launch update'}),
                   'TITLE: Acme launch\nAlex: Hello.\n[CHAPTER: 1 | Launch timing]\nAlex: Acme launches in July.'])
    svc = BriefingService.__new__(BriefingService)
    svc.db, svc.llm, svc.news = db, llm, NewsService()
    svc.orchestrator = BriefingOrchestrator(llm)
    svc.orchestrator.briefing_writer = BriefingWriterAgent(llm)
    svc.orchestrator._make_host_agent = lambda: HostResearchAgent(FakeLLM('{"questions_and_answers": []}'), use_web_plugin=True)

    async def fetch(*args, **kwargs):
        return [NewsItem('Acme launch date', 'Acme launches in July.', 'https://example.com/acme', 'Example', datetime.utcnow())], {'https://example.com/acme': 'topic'}
    svc._fetch_custom_site_articles = fetch
    calls = []

    async def synthesize(script, output_path, **kwargs):
        calls.append(script)
        if fail_audio:
            raise RuntimeError('audio unavailable')
        make_silent_mp3(str(output_path))
        timings = [SegmentTiming(i, part['speaker'], part['text'], i * 10, (i + 1) * 10, 10)
                   for i, part in enumerate(script)]
        return TTSResult(Path(output_path), len(script) * 10, 'fake', segment_timings=timings)
    monkeypatch.setattr(TTSFactory, 'synthesize_conversation', synthesize)
    return svc, b, llm, calls


@pytest.mark.asyncio
async def test_single_cached_article_is_ranked_and_saved_with_stable_chapter(db_session, monkeypatch, tmp_path):
    svc, b, llm, audio_calls = await setup_pipeline(db_session, monkeypatch, tmp_path)
    db_session.add(Article(title='Cached elsewhere', url='https://example.com/acme', source='Example'))
    await db_session.commit()
    result = await svc._generate_briefing_internal(b.id, b, ['topic'], 6, 'Listener')
    assert result.status == 'completed'
    assert len(audio_calls) == 1
    assert result.extra_data['editorial_duration_minutes'] == 2
    assert result.extra_data['chapter_stories']['0']['development'] == 'Acme launches in July.'
    assert result.extra_data['chapters'][0]['start_time'] == 10
    assert result.extra_data['chapter_sources']['0'][0]['url'] == 'https://example.com/acme'
    assert len((await db_session.execute(select(StoryDevelopment))).scalars().all()) == 1
    assert 'LISTENER STORY MEMORY' in llm.calls[0]['prompt']
    assert 'ARTICLE 1' in llm.calls[-1]['prompt']


@pytest.mark.asyncio
async def test_quiet_day_finishes_without_filler_or_audio(db_session, monkeypatch, tmp_path):
    svc, b, llm, audio_calls = await setup_pipeline(db_session, monkeypatch, tmp_path, ranked=[])
    result = await svc._generate_briefing_internal(b.id, b, ['topic'], 6, 'Listener')
    assert result.status == 'completed'
    assert result.extra_data['empty_reason'] == 'no_qualifying_developments'
    assert result.audio_url is None
    assert len(llm.calls) == 1
    assert audio_calls == []
    assert (await db_session.execute(select(StoryDevelopment))).scalars().all() == []


@pytest.mark.asyncio
async def test_failed_audio_does_not_write_story_memory(db_session, monkeypatch, tmp_path):
    svc, b, llm, calls = await setup_pipeline(db_session, monkeypatch, tmp_path, fail_audio=True)
    with pytest.raises(RuntimeError, match='audio unavailable'):
        await svc._generate_briefing_internal(b.id, b, ['topic'], 6, 'Listener')
    assert b.status == 'failed'
    assert (await db_session.execute(select(StoryDevelopment))).scalars().all() == []
