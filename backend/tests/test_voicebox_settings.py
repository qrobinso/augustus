from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

from app.routers import settings as routes
from app.routers.auth import get_current_user
from app.services.tts import voicebox_client as vc
from tests.test_voicebox_client import FakeVoicebox


@pytest.fixture
def isolated_settings(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("TTS_PROVIDER=gemini\n")
    monkeypatch.setattr(routes, "find_env_file", lambda: env_file)
    for key in ("VOICEBOX_URL", "VOICEBOX_MODEL"):
        monkeypatch.setenv(key, "")  # setenv (not delenv) so writes by update_settings are undone
    from app.config import get_settings
    get_settings.cache_clear()
    yield env_file
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_voicebox_round_trip_and_selection_requires_url(isolated_settings):
    with pytest.raises(HTTPException) as err:
        await routes.update_settings(routes.SettingsUpdate(tts_provider="voicebox"))
    assert err.value.status_code == 400
    result = await routes.update_settings(routes.SettingsUpdate(
        voicebox_url="http://vb.local:17493", voicebox_model="chatterbox-turbo", tts_provider="voicebox"))
    assert (result.tts_provider, result.voicebox_url, result.voicebox_model, result.voicebox_configured) == (
        "voicebox", "http://vb.local:17493", "chatterbox-turbo", True)
    assert "VOICEBOX_URL=http://vb.local:17493" in isolated_settings.read_text()
    with pytest.raises(HTTPException):  # cannot clear the URL while Voicebox is the provider
        await routes.update_settings(routes.SettingsUpdate(voicebox_url=""))


def test_update_validates_provider_and_url():
    with pytest.raises(ValidationError):
        routes.SettingsUpdate(tts_provider="mystery")
    with pytest.raises(ValidationError):
        routes.SettingsUpdate(voicebox_url="ftp://vb.local")
    routes.SettingsUpdate(voicebox_url="")  # clearing is allowed by the schema


@pytest.fixture
def api(monkeypatch):
    vc._profile_cache.clear()
    fake = FakeVoicebox()
    monkeypatch.setattr(routes, "VoiceboxClient",
                        lambda url: vc.VoiceboxClient(url, transport=httpx.MockTransport(fake)))
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/settings")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u")
    return app


@pytest.mark.asyncio
async def test_validate_and_models(api):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://test") as client:
        ok = (await client.post("/api/settings/validate/voicebox", json={"url": "http://vb.local:17493"})).json()
        models = (await client.get("/api/settings/voicebox/models", params={"url": "http://vb.local:17493"})).json()
        bad = await client.post("/api/settings/validate/voicebox", json={"url": "file:///etc/passwd"})
    assert ok == {"valid": True, "message": "Connected to Voicebox 0.5.0 · 2 voices",
                  "version": "0.5.0", "voice_count": 2, "warning": None}
    assert models == {"models": [{"name": "chatterbox-turbo", "display_name": "Chatterbox Turbo"},
                                 {"name": "qwen-tts-1.7B", "display_name": "Qwen TTS 1.7B"}]}
    assert bad.status_code == 422


@pytest.mark.parametrize("path", ["/voicebox/models", "/validate/voicebox"])
def test_new_voicebox_endpoints_require_login(path):
    """These endpoints make the server call a caller-supplied URL, so they must not be public."""
    route = next(r for r in routes.router.routes if r.path == path)
    assert any(dep.call is get_current_user for dep in route.dependant.dependencies)


def _app_with_transport(monkeypatch, handler):
    vc._profile_cache.clear()
    monkeypatch.setattr(routes, "VoiceboxClient",
                        lambda url: vc.VoiceboxClient(url, transport=httpx.MockTransport(handler)))
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/settings")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u")
    return app


@pytest.mark.asyncio
async def test_a_non_voicebox_server_is_reported_not_crashed(monkeypatch):
    """E.g. a Vite dev server answering every path with index.html."""
    html = lambda request: httpx.Response(200, text="<!doctype html><html></html>",
                                          headers={"content-type": "text/html"})
    app = _app_with_transport(monkeypatch, html)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        check = await client.post("/api/settings/validate/voicebox", json={"url": "http://localhost:5173"})
        models = await client.get("/api/settings/voicebox/models", params={"url": "http://localhost:5173"})
    message = "http://localhost:5173 doesn't look like a Voicebox server."
    assert check.status_code == 200
    assert check.json() == {"valid": False, "message": message, "version": None,
                            "voice_count": 0, "warning": None}
    assert models.status_code == 502
    assert models.json() == {"detail": message}


@pytest.mark.asyncio
async def test_unknown_version_is_reported_without_an_old_version_warning(monkeypatch):
    fake = FakeVoicebox()

    def no_version(request):
        if request.url.path == "/openapi.json":
            return httpx.Response(200, json={"info": {}})
        return fake(request)

    app = _app_with_transport(monkeypatch, no_version)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        check = (await client.post("/api/settings/validate/voicebox", json={"url": "http://vb.local:17493"})).json()
    assert check == {"valid": True, "message": "Connected to Voicebox (version unknown) · 2 voices",
                     "version": None, "voice_count": 2, "warning": None}
