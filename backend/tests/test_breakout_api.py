from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import httpx
from fastapi import FastAPI
from app.database import get_db
from app.models.briefing import Briefing
from app.models.topic import Topic
from app.models.cast import Cast
from app.routers import briefings as routes
from app.routers.auth import get_current_user
from app.routers.profiles import get_current_profile


@pytest.fixture
def api_app(db_session, monkeypatch):
    app = FastAPI()
    app.include_router(routes.router, prefix='/api/briefings')
    async def db():
        yield db_session
    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id='u')
    app.dependency_overrides[get_current_profile] = lambda: SimpleNamespace(id='p', name='Listener')
    monkeypatch.setattr(routes, 'process_generation_queue', AsyncMock())
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize('body', [
    {}, {'topic':'  '}, {'topic':'X','topic_id':'t'}, {'source_briefing_id':'b'},
    {'chapter_index':0}, {'source_briefing_id':'b','chapter_index':-1},
    {'topic':'X','max_duration_minutes':31}, {'topic':'X','max_duration_minutes':True},
])
async def test_breakout_request_validation(api_app, body):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url='http://test') as client:
        assert (await client.post('/api/briefings/breakout', json=body)).status_code == 422


@pytest.mark.asyncio
async def test_breakout_persists_target_before_scheduling(api_app, db_session):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url='http://test') as client:
        response = await client.post('/api/briefings/breakout', json={'topic':' Ocean currents ', 'focus':'Why circulation changes'})
        assert response.status_code == 202
        data = response.json()
        assert data['status'] == 'queued'
        assert data['extra_data']['kind'] == 'breakout'
        assert data['extra_data']['breakout']['topic'] == 'Ocean currents'
        assert data['extra_data']['target_duration'] == 10
        stored = await db_session.get(Briefing, data['id'])
        assert stored.extra_data['breakout']['focus'] == 'Why circulation changes'
        assert stored.profile_id == 'p'
        second = await client.post('/api/briefings/breakout', json={'topic':'Another', 'max_duration_minutes':20})
        assert second.status_code == 202
        assert second.json()['id'] != data['id']
        assert second.json()['extra_data']['target_duration'] == 20
        assert stored.extra_data['target_duration'] == 10


@pytest.mark.asyncio
async def test_chapter_target_scoped_snapshot_cast_and_queue(api_app, db_session):
    db_session.add(Cast(id='cast',user_id='u',profile_id='p',name='Hosts'))
    parent = Briefing(id='source',user_id='u',profile_id='p',title='Source episode',status='completed',cast_id='cast',extra_data={
        'chapters':[{'title':'Ocean circulation','start_time':0,'end_time':30},{'title':'Unrelated','start_time':30,'end_time':60}],
        'chapter_stories':{'0':{'title':'Ocean circulation','development':'New ocean measurement','claims':[]}},
        'segment_timings':[{'text':'Focused context','start_seconds':0,'end_seconds':25},{'text':'Unrelated private context','start_seconds':35,'end_seconds':60}],
    })
    db_session.add(parent)
    await db_session.commit()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url='http://test') as client:
        response = await client.post('/api/briefings/breakout', json={'source_briefing_id':'source','chapter_index':0,'max_duration_minutes':20})
        assert response.status_code == 202
        data = response.json()
        assert data['status'] == 'queued'
        assert data['cast_id'] == 'cast'
        metadata = data['extra_data']['breakout']
        assert metadata['source_briefing_id'] == 'source'
        assert metadata['topic'] == 'Ocean circulation'
        assert 'New ocean measurement' in metadata['source_context']
        assert 'Unrelated private context' not in metadata['source_context']
        second = await client.post('/api/briefings/breakout', json={
            'topic':'Fusion', 'max_duration_minutes':5})
        assert second.status_code == 202
        assert second.json()['id'] != data['id']
        assert second.json()['cast_id'] is None
        assert second.json()['extra_data']['breakout']['source_briefing_id'] is None
        stored = await db_session.get(Briefing, data['id'])
        assert stored.cast_id == 'cast'
        assert stored.extra_data['max_duration'] == 20
        assert stored.extra_data['breakout']['source_briefing_id'] == 'source'
        assert not parent.listened


@pytest.mark.asyncio
async def test_breakout_chapter_keeps_parent_subject_when_chapter_title_is_conceptual(
    api_app, db_session
):
    parent = Briefing(
        id='source-breakout', user_id='u', profile_id='p', title='Fusion deep dive',
        status='completed', extra_data={
            'kind': 'breakout',
            'breakout': {'topic': 'Fusion energy', 'focus': 'commercial timelines'},
            'chapters': [{'title': 'Mechanism', 'start_time': 0, 'end_time': 20}],
            'segment_timings': [
                {'text': 'Magnetic confinement requires stable plasma.',
                 'start_seconds': 0, 'end_seconds': 20}
            ],
        },
    )
    db_session.add(parent)
    await db_session.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api_app), base_url='http://test'
    ) as client:
        response = await client.post('/api/briefings/breakout', json={
            'source_briefing_id': parent.id, 'chapter_index': 0,
        })

    assert response.status_code == 202
    metadata = response.json()['extra_data']['breakout']
    assert metadata['topic'] == 'Fusion energy: Mechanism'
    assert 'Magnetic confinement' in metadata['source_context']


@pytest.mark.asyncio
async def test_daily_chapter_prefers_story_title_to_generic_chapter_label(
    api_app, db_session
):
    parent = Briefing(
        id='source-daily', user_id='u', profile_id='p', title='Daily briefing',
        status='completed', extra_data={
            'chapters': [{'title': 'Mechanism', 'start_time': 0, 'end_time': 20}],
            'chapter_stories': {
                '0': {
                    'title': 'Atlantic overturning circulation',
                    'development': 'A new observation changed the estimate.',
                    'claims': [],
                }
            },
        },
    )
    db_session.add(parent)
    await db_session.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api_app), base_url='http://test'
    ) as client:
        response = await client.post('/api/briefings/breakout', json={
            'source_briefing_id': parent.id, 'chapter_index': 0,
        })

    assert response.status_code == 202
    assert (
        response.json()['extra_data']['breakout']['topic']
        == 'Atlantic overturning circulation'
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('target', ['topic', 'source', 'cast'])
async def test_breakout_rejects_foreign_profile_resources(api_app, db_session, target):
    db_session.add(Topic(id='foreign-topic',user_id='u',profile_id='other',name='Secret',slug='secret'))
    db_session.add(Briefing(id='foreign-source',user_id='u',profile_id='other',title='Secret',status='completed',extra_data={'chapters':[{'title':'Secret','start_time':0}]}))
    db_session.add(Cast(id='foreign-cast',user_id='u',profile_id='other',name='Secret'))
    await db_session.commit()
    body = {'topic_id':'foreign-topic'} if target == 'topic' else {'source_briefing_id':'foreign-source','chapter_index':0} if target == 'source' else {'topic':'Ocean','cast_id':'foreign-cast'}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url='http://test') as client:
        assert (await client.post('/api/briefings/breakout',json=body)).status_code == 404


@pytest.mark.asyncio
async def test_breakout_rejects_disabled_api_tool(api_app):
    api_app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id='u',current_api_key_id='key',current_api_key_tools=['get_briefing'])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url='http://test') as client:
        assert (await client.post('/api/briefings/breakout',json={'topic':'Ocean'})).status_code == 403

@pytest.mark.asyncio
async def test_saved_topic_target_and_invalid_chapter(api_app, db_session):
    db_session.add(Topic(id='local-topic',user_id='u',profile_id='p',name='Ocean currents',slug='ocean',description='Explain the physical mechanisms'))
    db_session.add(Briefing(id='local-source',user_id='u',profile_id='p',title='Source',status='completed',extra_data={'chapters':[]}))
    await db_session.commit()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url='http://test') as client:
        bad = await client.post('/api/briefings/breakout',json={'source_briefing_id':'local-source','chapter_index':4})
        assert bad.status_code == 422
        response = await client.post('/api/briefings/breakout',json={'topic_id':'local-topic'})
        assert response.status_code == 202
        extra = response.json()['extra_data']
        assert extra['topic_ids'] == ['local-topic']
        assert extra['breakout']['topic'] == 'Ocean currents'
        assert extra['breakout']['source_context'] == 'Explain the physical mechanisms'


@pytest.mark.asyncio
async def test_simultaneous_breakout_clicks_admit_independent_jobs(api_app, monkeypatch):
    import asyncio
    monkeypatch.setattr(routes, '_generation_request_lock', asyncio.Lock())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url='http://test') as client:
        responses = await asyncio.gather(*[
            client.post('/api/briefings/breakout',json={'topic':topic,'max_duration_minutes':duration})
            for topic, duration in [('Ocean', 5), ('Fusion', 20)]
        ])
    assert [response.status_code for response in responses] == [202, 202]
    assert len({response.json()['id'] for response in responses}) == 2
    assert all(response.json()['status'] == 'queued' for response in responses)
    assert [response.json()['extra_data']['max_duration'] for response in responses] == [5, 20]

@pytest.mark.asyncio
async def test_daily_and_breakout_can_queue_together(api_app, monkeypatch):
    import asyncio
    monkeypatch.setattr(routes, '_generation_request_lock', asyncio.Lock())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url='http://test') as client:
        responses = await asyncio.gather(
            client.post('/api/briefings/generate',json={'max_duration_minutes':15}),
            client.post('/api/briefings/breakout',json={'topic':'Ocean'}),
        )
    assert [response.status_code for response in responses] == [202, 202]
    assert len({response.json()['id'] for response in responses}) == 2
    assert all(response.json()['status'] == 'queued' for response in responses)
    assert [response.json()['extra_data']['max_duration'] for response in responses] == [15, 10]


@pytest.mark.asyncio
async def test_queue_lists_all_active_jobs_in_order_for_current_profile(api_app, db_session):
    from datetime import datetime, timedelta
    start = datetime(2026, 1, 1)
    rows = [
        ('third', 'u', 'p', 'queued', 3),
        ('finished', 'u', 'p', 'completed', 0),
        ('foreign-profile', 'u', 'other', 'queued', 0),
        ('second', 'u', 'p', 'pending', 2),
        ('first', 'u', 'p', 'generating', 1),
        ('foreign-user', 'other', 'p', 'queued', 0),
    ]
    for id_, user_id, profile_id, status, minute in rows:
        db_session.add(Briefing(id=id_, user_id=user_id, profile_id=profile_id,
                               title=id_, status=status, created_at=start+timedelta(minutes=minute)))
    await db_session.commit()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url='http://test') as client:
        response = await client.get('/api/briefings/queue')
    assert response.status_code == 200
    assert response.json()['total'] == 3
    assert [item['id'] for item in response.json()['briefings']] == ['first', 'second', 'third']


@pytest.mark.asyncio
async def test_daily_job_persists_requested_cast_and_duration(api_app, db_session):
    db_session.add(Cast(id='daily-cast',user_id='u',profile_id='p',name='Daily hosts'))
    await db_session.commit()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url='http://test') as client:
        response = await client.post('/api/briefings/generate', json={
            'cast_id':'daily-cast', 'max_duration_minutes':25, 'topic_ids':['topic-1']})
    assert response.status_code == 202
    stored = await db_session.get(Briefing, response.json()['id'])
    assert stored.status == 'queued'
    assert stored.cast_id == 'daily-cast'
    assert stored.extra_data['topic_ids'] == ['topic-1']
    assert stored.extra_data['max_duration'] == 25
    assert stored.extra_data['profile_name'] == 'Listener'


@pytest.mark.asyncio
async def test_daily_rejects_foreign_profile_cast(api_app, db_session):
    db_session.add(Cast(id='foreign-daily-cast',user_id='u',profile_id='other',name='Private hosts'))
    await db_session.commit()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url='http://test') as client:
        response = await client.post('/api/briefings/generate', json={'cast_id':'foreign-daily-cast'})
    assert response.status_code == 404
