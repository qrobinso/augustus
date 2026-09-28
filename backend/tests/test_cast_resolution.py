"""Which cast a briefing uses, for explicit and implicit cast choices."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from app.database import get_db
from app.models.briefing import Briefing
from app.models.cast import Cast
from app.routers import briefings as routes
from app.routers.auth import get_current_user
from app.routers.profiles import get_current_profile
from app.services.cast import CastService, NoCastForProviderError


async def _seed(db, *casts):
    db.add_all(casts)
    await db.commit()


@pytest.mark.asyncio
async def test_resolve_uses_matching_cast(db_session):
    await _seed(db_session, Cast(id="g", user_id="u", profile_id="p", name="G", tts_provider="gemini", is_default=True))
    assert (await CastService(db_session).resolve_for_generation("u", "p", "g", "gemini")).id == "g"


@pytest.mark.asyncio
async def test_resolve_falls_back_for_other_provider_or_missing_cast(db_session):
    await _seed(db_session,
        Cast(id="g", user_id="u", profile_id="p", name="G", tts_provider="gemini", is_default=True),
        Cast(id="v", user_id="u", profile_id="p", name="V", tts_provider="piper", is_default=True))
    service = CastService(db_session)
    assert (await service.resolve_for_generation("u", "p", "v", "gemini")).id == "g"      # schedule's cast
    assert (await service.resolve_for_generation("u", "p", "gone", "gemini")).id == "g"   # deleted cast
    assert (await service.resolve_for_generation("u", "p", None, "gemini")).id == "g"


@pytest.mark.asyncio
async def test_resolve_raises_when_provider_has_no_cast(db_session):
    await _seed(db_session, Cast(id="g", user_id="u", profile_id="p", name="G", tts_provider="gemini", is_default=True))
    with pytest.raises(NoCastForProviderError):
        await CastService(db_session).resolve_for_generation("u", "p", "g", "piper")


@pytest.fixture
def api_app(db_session, monkeypatch):
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/briefings")
    async def db():
        yield db_session
    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u")
    app.dependency_overrides[get_current_profile] = lambda: SimpleNamespace(id="p", name="Listener")
    monkeypatch.setattr(routes, "process_generation_queue", AsyncMock())
    return app


async def _post(app, path, body):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(path, json=body)


@pytest.mark.asyncio
async def test_generate_rejects_explicit_cast_of_other_provider(api_app, db_session):
    await _seed(db_session,
        Cast(id="g", user_id="u", profile_id="p", name="G", tts_provider="gemini", is_default=True),
        Cast(id="v", user_id="u", profile_id="p", name="Vox", tts_provider="piper", is_default=True))
    response = await _post(api_app, "/api/briefings/generate", {"cast_id": "v"})
    assert response.status_code == 400
    assert response.json()["detail"] == "'Vox' is a Piper cast; your voice provider is Google Gemini."


@pytest.mark.asyncio
async def test_generate_fails_fast_without_any_cast_for_provider(api_app, db_session):
    response = await _post(api_app, "/api/briefings/generate", {})
    assert response.status_code == 400
    assert response.json()["detail"] == "No Google Gemini cast yet. Create one on the Casts page."


@pytest.mark.asyncio
async def test_breakout_explicit_mismatch_400_but_parent_mismatch_falls_back(api_app, db_session, capsys):
    await _seed(db_session,
        Cast(id="g", user_id="u", profile_id="p", name="G", tts_provider="gemini", is_default=True),
        Cast(id="v", user_id="u", profile_id="p", name="Vox", tts_provider="piper", is_default=True),
        Briefing(id="src", user_id="u", profile_id="p", title="Src", status="completed", cast_id="v",
                 extra_data={"chapters": [{"title": "Tides", "start_time": 0, "end_time": 10}]}))
    explicit = await _post(api_app, "/api/briefings/breakout", {"topic": "Tides", "cast_id": "v"})
    assert explicit.status_code == 400
    implicit = await _post(api_app, "/api/briefings/breakout", {"source_briefing_id": "src", "chapter_index": 0})
    assert implicit.status_code == 202
    assert implicit.json()["cast_id"] is None  # resolved to the Gemini default at generation time
    assert "[Breakout] Parent cast v belongs to piper; using the gemini default" in capsys.readouterr().out
