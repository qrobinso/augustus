from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from app.database import get_db
from app.models.cast import Cast
from app.routers import casts as routes
from app.routers.auth import get_current_user
from app.routers.profiles import get_current_profile


@pytest.fixture
def api(db_session):
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/casts")
    async def db():
        yield db_session
    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u")
    app.dependency_overrides[get_current_profile] = lambda: SimpleNamespace(id="p")
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def seeded(db_session):
    db_session.add_all([
        Cast(id="g", user_id="u", profile_id="p", name="G", tts_provider="gemini", is_default=True),
        Cast(id="e", user_id="u", profile_id="p", name="E", tts_provider="elevenlabs", is_default=True),
    ])
    await db_session.commit()


@pytest.mark.asyncio
async def test_list_defaults_to_active_provider_and_reports_providers(api, seeded):
    async with api as client:
        body = (await client.get("/api/casts")).json()
    assert [c["id"] for c in body["casts"]] == ["g"]
    assert body["casts"][0]["tts_provider"] == "gemini"
    assert body["active_provider"] == "gemini"
    assert {"id": "piper", "label": "Piper", "allows_custom_voice": True} in body["providers"]


@pytest.mark.asyncio
async def test_list_all_includes_every_provider(api, seeded):
    async with api as client:
        body = (await client.get("/api/casts", params={"provider": "all"})).json()
    assert {c["id"] for c in body["casts"]} == {"g", "e"}


@pytest.mark.asyncio
async def test_voices_for_active_and_named_provider(api):
    async with api as client:
        gemini = (await client.get("/api/casts/voices")).json()
        piper = (await client.get("/api/casts/voices", params={"provider": "piper"})).json()
        bad = await client.get("/api/casts/voices", params={"provider": "nope"})
    assert gemini["provider"] == "gemini" and gemini["allows_custom"] is False
    assert {"id": "Kore", "name": "Kore", "description": "Firm"} in gemini["voices"]
    assert piper["allows_custom"] is True and piper["provider_label"] == "Piper"
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_summary_counts(api, seeded):
    async with api as client:
        body = (await client.get("/api/casts/summary")).json()
    assert body == {"active_provider": "gemini", "counts": {"gemini": 1, "elevenlabs": 1}}
