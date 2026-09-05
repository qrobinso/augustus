import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from types import SimpleNamespace
from app.database import get_db
from app.routers.auth import get_current_user
from app.routers.profiles import get_current_profile
from app.routers.stories import router
from app.models.story import Story


@pytest.mark.asyncio
async def test_story_route_reads_and_updates_only_active_profiles_memory(db_session):
    db_session.add(Story(id='story', user_id='u', profile_id='p', title='Launch'))
    await db_session.commit()
    app = FastAPI()
    app.include_router(router, prefix='/api/stories')
    async def db():
        yield db_session
    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id='u')
    app.dependency_overrides[get_current_profile] = lambda: SimpleNamespace(id='p')
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.patch('/api/stories/story/preference', json={'preference': 'follow'})
        assert response.status_code == 200
        assert (await client.get('/api/stories/story')).json()['preference'] == 'follow'
        assert (await client.patch('/api/stories/story/preference', json={'preference': 'invented'})).status_code == 422
        app.dependency_overrides[get_current_profile] = lambda: SimpleNamespace(id='other')
        assert (await client.get('/api/stories/story')).status_code == 404
        assert (await client.patch('/api/stories/story/preference', json={'preference': 'less'})).status_code == 404
