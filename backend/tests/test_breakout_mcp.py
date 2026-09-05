"""MCP identity and breakout-tool integration tests."""

import asyncio
import json
from contextlib import asynccontextmanager
from contextlib import suppress
from datetime import datetime
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from mcp import ClientSession
from mcp.shared.memory import create_client_server_memory_streams
from mcp.types import TextContent

import mcp_server as installed_mcp_server

from app.database import get_db
from app.models.api_key import ApiKey
from app.models.briefing import Briefing
from app.models.profile import Profile
from app.models.user import User
from app.routers import briefings as briefing_routes
from app.routers import mcp
from app.routers.auth import get_current_user
from app.routers.profiles import get_current_profile
from app.services.api_key import hash_key


RAW_KEY = "aug_test-active-key"


async def _seed_identity(db_session, *, revoked: bool = False, enabled_tools=None):
    user = User(id="user-1", name="Owner", preferences={})
    admin = Profile(
        id="profile-admin",
        user_id=user.id,
        name="Admin",
        color="#e85d04",
        is_admin=True,
    )
    bound = Profile(
        id="profile-bound",
        user_id=user.id,
        name="Bound",
        color="#123456",
        is_admin=False,
    )
    api_key = ApiKey(
        id="key-1",
        user_id=user.id,
        profile_id=bound.id,
        name="Test key",
        key_prefix=RAW_KEY[:8],
        key_hash=hash_key(RAW_KEY),
        enabled_tools=enabled_tools,
        revoked_at=datetime.utcnow() if revoked else None,
    )
    db_session.add_all([user, admin, bound, api_key])
    await db_session.commit()
    return user, admin, bound, api_key


def _identity_app(db_session):
    app = FastAPI()

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.include_router(mcp.router, prefix="/api/mcp")

    @app.get("/identity")
    async def identity(
        user=Depends(get_current_user),
        profile=Depends(get_current_profile),
    ):
        return {
            "user_id": user.id,
            "profile_id": profile.id,
            "current_profile_id": getattr(user, "current_profile_id", None),
            "api_key_id": getattr(user, "current_api_key_id", None),
            "tools": getattr(user, "current_api_key_tools", None),
        }

    return app


@pytest.mark.asyncio
async def test_active_api_key_authenticates_its_owner_and_bound_profile(db_session):
    """Catches falling back to the first user/admin profile when a valid key is supplied."""
    _, _, bound, api_key = await _seed_identity(
        db_session,
        enabled_tools=["generate_breakout_podcast"],
    )
    app = _identity_app(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/identity",
            headers={"X-API-Key": RAW_KEY, "User-Agent": "mcp-test-client"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "user-1",
        "profile_id": bound.id,
        "current_profile_id": bound.id,
        "api_key_id": api_key.id,
        "tools": ["generate_breakout_podcast"],
    }
    await db_session.refresh(api_key)
    assert api_key.last_used_at is not None
    assert api_key.last_client == "mcp-test-client"


@pytest.mark.asyncio
async def test_api_key_with_null_tool_scope_remains_unrestricted(db_session):
    """Catches turning the persisted None allowlist into an empty, deny-all list."""
    await _seed_identity(db_session, enabled_tools=None)
    app = _identity_app(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/identity", headers={"X-API-Key": RAW_KEY})

    assert response.status_code == 200
    assert response.json()["api_key_id"] == "key-1"
    assert response.json()["tools"] is None


@pytest.mark.asyncio
async def test_api_key_cannot_switch_away_from_its_bound_profile(db_session):
    """Catches honoring X-Profile-ID over the profile permanently bound to the key."""
    await _seed_identity(db_session)
    app = _identity_app(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/identity",
            headers={"X-API-Key": RAW_KEY, "X-Profile-ID": "profile-admin"},
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "API key is bound to a different profile"}


@pytest.mark.asyncio
@pytest.mark.parametrize("raw_key,revoked", [("aug_invalid-key", False), (RAW_KEY, True)])
async def test_invalid_or_revoked_api_key_is_rejected(db_session, raw_key, revoked):
    """Catches silently treating a rejected credential as an unauthenticated local request."""
    await _seed_identity(db_session, revoked=revoked)
    app = _identity_app(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/identity", headers={"X-API-Key": raw_key})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or revoked API key"}


@pytest.mark.asyncio
async def test_no_key_preserves_local_ui_admin_profile_resolution(db_session):
    """Catches making the API-key credential mandatory for the self-hosted UI."""
    await _seed_identity(db_session)
    app = _identity_app(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/identity")

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "user-1",
        "profile_id": "profile-admin",
        "current_profile_id": "profile-admin",
        "api_key_id": None,
        "tools": None,
    }


@pytest.mark.asyncio
async def test_mcp_me_reports_authenticated_key_scope(db_session):
    """Catches /api/mcp/me losing the key id, profile binding, or tool allowlist."""
    await _seed_identity(
        db_session,
        enabled_tools=["list_topics", "generate_breakout_podcast"],
    )
    app = _identity_app(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/mcp/me", headers={"X-API-Key": RAW_KEY})

    assert response.status_code == 200
    payload = response.json()
    assert payload["api_key_id"] == "key-1"
    assert payload["profile_id"] == "profile-bound"
    assert payload["profile_name"] == "Bound"
    assert payload["enabled_tools"] == ["list_topics", "generate_breakout_podcast"]


@pytest.mark.asyncio
async def test_breakout_mcp_tool_proxies_request_and_enriches_result(monkeypatch):
    """Catches a wrong REST path/body or omission from standard briefing URL enrichment."""
    server = installed_mcp_server
    requests = []

    def handler(request: httpx.Request):
        requests.append(request)
        return httpx.Response(
            202,
            json={"id": "breakout-1", "status": "queued", "audio_url": None},
        )

    monkeypatch.setattr(
        server,
        "_client",
        lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://backend.test",
        ),
    )
    tool = next(t for t in server.TOOL_DEFS if t["name"] == "generate_breakout_podcast")
    args = {
        "source_briefing_id": "source-1",
        "chapter_index": 0,
        "focus": "Explain the mechanism",
        "max_duration_minutes": 10,
        "cast_id": "cast-1",
    }

    result = await server._proxy(tool, args)
    result = server._add_briefing_urls(result, "http://ui.test")

    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/briefings/breakout"
    assert json.loads(requests[0].content) == args
    assert result["detail_url"] == "http://ui.test/briefing/breakout-1"
    assert "generate_breakout_podcast" in server._BRIEFING_RESULT_TOOLS


@pytest.mark.asyncio
async def test_breakout_mcp_proxy_queues_multiple_jobs_with_key_bound_identity(db_session, monkeypatch):
    """Catches losing key scope between the stdio proxy and the real breakout route."""
    _, _, bound, _ = await _seed_identity(
        db_session,
        enabled_tools=["generate_breakout_podcast"],
    )
    app = FastAPI()

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.include_router(briefing_routes.router, prefix="/api/briefings")
    monkeypatch.setattr(briefing_routes, "process_generation_queue", AsyncMock())
    server = installed_mcp_server
    monkeypatch.setattr(
        server,
        "_client",
        lambda: httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://backend.test",
            headers={"X-API-Key": RAW_KEY},
        ),
    )
    tool = next(t for t in server.TOOL_DEFS if t["name"] == "generate_breakout_podcast")

    result = await server._proxy(
        tool,
        {"topic": "Fusion power", "focus": "Recent confinement evidence", "max_duration_minutes": 5},
    )

    assert result["status"] == "queued"
    assert result["extra_data"]["kind"] == "breakout"
    assert result["extra_data"]["breakout"]["topic"] == "Fusion power"
    stored = await db_session.get(Briefing, result["id"])
    assert stored.profile_id == bound.id
    second = await server._proxy(
        tool,
        {"topic": "Ocean currents", "max_duration_minutes": 20},
    )
    assert second["status"] == "queued"
    assert second["id"] != result["id"]
    assert second["extra_data"]["breakout"]["topic"] == "Ocean currents"
    assert second["extra_data"]["target_duration"] == 20
    assert stored.extra_data["target_duration"] == 5
    assert (await db_session.get(Briefing, second["id"])).profile_id == bound.id
    assert briefing_routes.process_generation_queue.await_count == 2


def test_breakout_tool_catalog_and_schema_match_api_contract():
    """Catches catalog drift or relaxing the exactly-one-target request contract."""
    server = installed_mcp_server
    tool = next(t for t in server.TOOL_DEFS if t["name"] == "generate_breakout_podcast")
    schema = tool["inputSchema"]

    assert any(item["name"] == "generate_breakout_podcast" for item in mcp.MCP_TOOL_CATALOG)
    assert schema["properties"]["focus"]["maxLength"] == 1000
    assert schema["properties"]["max_duration_minutes"] == {
        "type": "integer",
        "minimum": 3,
        "maximum": 30,
        "default": 10,
    }
    assert schema["properties"]["chapter_index"] == {"type": "integer", "minimum": 0}
    assert [branch["required"] for branch in schema["oneOf"]] == [
        ["topic"],
        ["topic_id"],
        ["source_briefing_id", "chapter_index"],
    ]
    assert all("not" in branch for branch in schema["oneOf"])


@pytest.mark.asyncio
async def test_real_mcp_sdk_lists_and_calls_breakout_tool(monkeypatch):
    """Catches tool schema or response shapes rejected by the installed MCP SDK."""
    requests = []

    def backend_handler(request: httpx.Request):
        requests.append(request)
        if request.method == "GET" and request.url.path == "/api/mcp/me":
            return httpx.Response(
                200,
                json={
                    "enabled_tools": ["generate_breakout_podcast"],
                    "web_url": "http://ui.test",
                },
            )
        if request.method == "POST" and request.url.path == "/api/briefings/breakout":
            return httpx.Response(
                202,
                json={"id": "sdk-breakout", "status": "queued", "audio_url": None},
            )
        if request.method == "POST" and request.url.path == "/api/mcp/audit":
            return httpx.Response(204)
        return httpx.Response(404, text="unexpected backend request")

    streams = {}
    streams_ready = asyncio.Event()

    @asynccontextmanager
    async def memory_stdio():
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            streams["client"] = client_streams
            streams_ready.set()
            yield server_streams

    monkeypatch.setattr(installed_mcp_server, "API_KEY", RAW_KEY)
    monkeypatch.setattr(installed_mcp_server, "stdio_server", memory_stdio)
    monkeypatch.setattr(
        installed_mcp_server,
        "_client",
        lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(backend_handler),
            base_url="http://backend.test",
        ),
    )

    server_task = asyncio.create_task(installed_mcp_server.main_async())
    await asyncio.wait_for(streams_ready.wait(), timeout=2)
    try:
        client_read, client_write = streams["client"]
        async with ClientSession(client_read, client_write) as session:
            initialized = await session.initialize()
            listed = await session.list_tools()
            result = await session.call_tool(
                "generate_breakout_podcast",
                {"topic": "Fusion power", "max_duration_minutes": 10},
            )
    finally:
        server_task.cancel()
        with suppress(asyncio.CancelledError):
            await server_task

    assert "generate_breakout_podcast" in (initialized.instructions or "")
    assert [tool.name for tool in listed.tools] == ["generate_breakout_podcast"]
    assert listed.tools[0].inputSchema["oneOf"][2]["required"] == [
        "source_briefing_id",
        "chapter_index",
    ]
    assert result.isError is False
    assert len(result.content) == 1
    assert isinstance(result.content[0], TextContent)
    assert json.loads(result.content[0].text) == {
        "id": "sdk-breakout",
        "status": "queued",
        "audio_url": None,
        "detail_url": "http://ui.test/briefing/sdk-breakout",
    }
    breakout_request = next(
        request for request in requests if request.url.path == "/api/briefings/breakout"
    )
    assert json.loads(breakout_request.content) == {
        "topic": "Fusion power",
        "max_duration_minutes": 10,
    }
    audit_request = next(request for request in requests if request.url.path == "/api/mcp/audit")
    assert json.loads(audit_request.content)["tool_name"] == "generate_breakout_podcast"
    assert json.loads(audit_request.content)["status"] == "success"
