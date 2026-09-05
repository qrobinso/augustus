"""Provider selection must never switch billing providers implicitly."""
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError
from app.routers import settings as routes
from app.services.llm import openrouter
from app.services.llm.agents.orchestrator import BriefingOrchestrator
from app.services.llm.agents.host_research import HostResearchAgent

@pytest.fixture
def isolated_settings(monkeypatch, tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('OPENROUTER_MODEL=existing/model\n')
    monkeypatch.setattr(routes, 'find_env_file', lambda: env_file)
    for key in ('LLM_PROVIDER', 'CODEX_MODEL', 'OPENROUTER_MODEL', 'OPENROUTER_WRITER_MODEL'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(openrouter, '_provider', None)
    from app.config import get_settings
    get_settings.cache_clear()
    yield env_file
    get_settings.cache_clear()

@pytest.mark.asyncio
async def test_provider_settings_round_trip_preserves_openrouter(isolated_settings, monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'openrouter')
    monkeypatch.setenv('CODEX_MODEL', '')
    result = await routes.update_settings(routes.SettingsUpdate(llm_provider='codex', codex_model='gpt-test'))
    assert result.llm_provider == 'codex'
    assert result.codex_model == 'gpt-test'
    assert result.openrouter_model == 'existing/model'
    assert 'LLM_PROVIDER=codex' in isolated_settings.read_text()
    result = await routes.update_settings(routes.SettingsUpdate(llm_provider='openrouter'))
    assert result.codex_model == 'gpt-test'

def test_invalid_provider_or_multiline_model_rejected():
    with pytest.raises(ValidationError):
        routes.SettingsUpdate(llm_provider='unknown')
    with pytest.raises(ValidationError):
        routes.SettingsUpdate(codex_model='gpt\nOPENROUTER_API_KEY=oops')

def test_factory_selects_codex_without_openrouter(monkeypatch):
    fake = object()
    monkeypatch.setitem(sys.modules, 'app.services.llm.codex', SimpleNamespace(CodexProvider=lambda: fake))
    monkeypatch.setattr(openrouter, '_provider', None)
    monkeypatch.setenv('LLM_PROVIDER', 'codex')
    from app.config import get_settings
    get_settings.cache_clear()
    try:
        assert openrouter.get_llm_provider() is fake
    finally:
        get_settings.cache_clear()

def test_codex_writer_ignores_saved_openrouter_writer(monkeypatch):
    monkeypatch.setenv('OPENROUTER_WRITER_MODEL', 'paid/writer')
    llm = SimpleNamespace(supports_web_search_plugin=False)
    orchestrator = BriefingOrchestrator(llm)
    assert orchestrator.briefing_writer.llm is llm
    assert HostResearchAgent(llm).use_web_plugin is False

@pytest.mark.asyncio
async def test_codex_account_routes_reject_cross_origin(monkeypatch):
    fake = SimpleNamespace(start_login=AsyncMock(return_value={'login_id':'one', 'verification_url':'https://auth.openai.com/codex/device','user_code':'ABCD'}))
    monkeypatch.setitem(sys.modules, 'app.services.llm.codex', SimpleNamespace(get_codex_service=lambda: fake))
    app = FastAPI()
    app.include_router(routes.router, prefix='/api/settings')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://testserver') as client:
        bad = await client.post('/api/settings/codex/login', headers={'Origin':'https://evil.example'})
        assert bad.status_code == 403
        fake.start_login.assert_not_awaited()
        ok = await client.post('/api/settings/codex/login', headers={'Origin':'http://testserver'})
        assert ok.status_code == 200
        assert ok.json()['user_code'] == 'ABCD'
        assert ok.headers['cache-control'] == 'no-store'

@pytest.mark.asyncio
async def test_account_route_errors_do_not_leak_protocol_payloads(monkeypatch):
    class SafeError(Exception):
        pass
    fake = SimpleNamespace(models=AsyncMock(side_effect=RuntimeError('access_token=secret')))
    monkeypatch.setitem(sys.modules, 'app.services.llm.codex', SimpleNamespace(
        get_codex_service=lambda: fake, CodexError=SafeError))
    app = FastAPI()
    app.include_router(routes.router, prefix='/api/settings')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://testserver') as client:
        result = await client.get('/api/settings/codex/models')
        assert result.status_code == 503
        assert 'secret' not in result.text

@pytest.mark.asyncio
@pytest.mark.parametrize('headers', [{'Origin':'null'}, {'Sec-Fetch-Site':'cross-site'}])
async def test_browser_account_control_requires_trusted_site(headers):
    app = FastAPI()
    app.include_router(routes.router, prefix='/api/settings')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://testserver') as client:
        result = await client.post('/api/settings/codex/logout', headers=headers)
        assert result.status_code == 403

def test_app_does_not_inherit_desktop_codex_home(monkeypatch, tmp_path):
    from app.config import Settings
    monkeypatch.setenv('CODEX_HOME', str(tmp_path / 'desktop-credentials'))
    monkeypatch.delenv('AUGUSTUS_CODEX_HOME', raising=False)
    settings = Settings(_env_file=None, debug=False)
    assert settings.codex_home != str(tmp_path / 'desktop-credentials')
    assert settings.codex_home.endswith('/backend/data/codex')


@pytest.mark.asyncio
async def test_configured_frontend_can_control_codex_with_cross_site_header(monkeypatch):
    from app import config

    monkeypatch.setattr(config, 'get_settings', lambda: SimpleNamespace(frontend_url='http://localhost:5173'))
    fake = SimpleNamespace(start_login=AsyncMock(return_value={
        'login_id': 'one',
        'verification_url': 'https://auth.openai.com/codex/device',
        'user_code': 'ABCD',
    }))
    monkeypatch.setitem(sys.modules, 'app.services.llm.codex', SimpleNamespace(get_codex_service=lambda: fake))
    app = FastAPI()
    app.include_router(routes.router, prefix='/api/settings')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://127.0.0.1:8000') as client:
        response = await client.post('/api/settings/codex/login', headers={
            'Origin': 'http://localhost:5173',
            'Sec-Fetch-Site': 'cross-site',
        })
        assert response.status_code == 200
        assert response.json()['user_code'] == 'ABCD'
        assert response.headers['cache-control'] == 'no-store'


@pytest.mark.asyncio
async def test_untrusted_cross_site_origin_cannot_control_codex(monkeypatch):
    from app import config

    monkeypatch.setattr(config, 'get_settings', lambda: SimpleNamespace(frontend_url='http://localhost:5173'))
    fake = SimpleNamespace(start_login=AsyncMock())
    monkeypatch.setitem(sys.modules, 'app.services.llm.codex', SimpleNamespace(get_codex_service=lambda: fake))
    app = FastAPI()
    app.include_router(routes.router, prefix='/api/settings')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://127.0.0.1:8000') as client:
        response = await client.post('/api/settings/codex/login', headers={
            'Origin': 'https://evil.example',
            'Sec-Fetch-Site': 'cross-site',
        })
        assert response.status_code == 403
        fake.start_login.assert_not_awaited()
