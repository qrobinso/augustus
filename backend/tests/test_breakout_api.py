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
    monkeypatch.setattr(routes, 'generate_briefing_task', AsyncMock())
    from app.services.briefing_queue import briefing_queue
    monkeypatch.setattr(briefing_queue, 'is_global_generating', AsyncMock(return_value=False))
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
        assert data['status'] == 'pending'
        assert data['extra_data']['kind'] == 'breakout'
        assert data['extra_data']['breakout']['topic'] == 'Ocean currents'
        assert data['extra_data']['target_duration'] == 10
        stored = await db_session.get(Briefing, data['id'])
        assert stored.extra_data['breakout']['focus'] == 'Why circulation changes'
        assert stored.profile_id == 'p'
        assert (await client.post('/api/briefings/breakout', json={'topic':'Another'})).status_code == 409


@pytest.mark.asyncio
async def test_chapter_target_scoped_snapshot_cast_and_queue(api_app, db_session, monkeypatch):
    db_session.add(Cast(id='cast',user_id='u',profile_id='p',name='Hosts'))
    parent = Briefing(id='source',user_id='u',profile_id='p',title='Source episode',status='completed',cast_id='cast',extra_data={
        'chapters':[{'title':'Ocean circulation','start_time':0,'end_time':30},{'title':'Unrelated','start_time':30,'end_time':60}],
        'chapter_stories':{'0':{'title':'Ocean circulation','development':'New ocean measurement','claims':[]}},
        'segment_timings':[{'text':'Focused context','start_seconds':0,'end_seconds':25},{'text':'Unrelated private context','start_seconds':35,'end_seconds':60}],
    })
    db_session.add(parent)
    await db_session.commit()
    from app.services.briefing_queue import briefing_queue
    monkeypatch.setattr(briefing_queue,'is_global_generating',AsyncMock(return_value=True))
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
        assert not parent.listened
        routes.generate_briefing_task.assert_not_awaited()


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
async def test_simultaneous_breakout_clicks_admit_one_job(api_app, monkeypatch):
    import asyncio
    monkeypatch.setattr(routes, '_generation_request_lock', asyncio.Lock())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url='http://test') as client:
        responses = await asyncio.gather(*[
            client.post('/api/briefings/breakout',json={'topic':'Ocean'}) for _ in range(2)
        ])
    assert sorted(response.status_code for response in responses) == [202,409]

@pytest.mark.asyncio
async def test_daily_and_breakout_share_admission_limit(api_app, monkeypatch):
    import asyncio
    monkeypatch.setattr(routes, '_generation_request_lock', asyncio.Lock())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url='http://test') as client:
        responses = await asyncio.gather(
            client.post('/api/briefings/generate',json={}),
            client.post('/api/briefings/breakout',json={'topic':'Ocean'}),
        )
    assert sorted(response.status_code for response in responses) == [202,409]
