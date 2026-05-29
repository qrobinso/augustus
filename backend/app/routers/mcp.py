"""MCP management API: API keys, audit log, tool catalog."""

import os
import socket
import sys
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.api_key import ApiKey, McpAuditLog
from app.models.profile import Profile
from app.models.user import User
from app.routers.auth import get_current_user
from app.services.api_key import generate_raw_key, hash_key, key_prefix_display

router = APIRouter()

# Path to the bundled stdio MCP server script (backend/mcp_server.py).
# __file__ here is backend/app/routers/mcp.py, so ../.. is the backend dir.
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_MCP_SCRIPT_PATH = os.path.join(_BACKEND_DIR, "mcp_server.py")


# Static catalog of tools the stdio MCP server exposes.
# Keep in sync with backend/mcp_server.py.
MCP_TOOL_CATALOG = [
    {"name": "list_briefings", "description": "List briefings for the connected profile.", "category": "read"},
    {"name": "get_briefing", "description": "Fetch a briefing by id, including transcript.", "category": "read"},
    {"name": "generate_briefing", "description": "Generate a new briefing (queues it).", "category": "write"},
    {"name": "cancel_briefing", "description": "Cancel a queued/in-progress briefing.", "category": "write"},
    {"name": "regenerate_audio", "description": "Regenerate audio for a completed briefing using a different cast.", "category": "write"},
    {"name": "set_briefing_favorite", "description": "Mark a briefing favorite/unfavorite.", "category": "write"},
    {"name": "set_briefing_listened", "description": "Mark a briefing listened/unlistened.", "category": "write"},
    {"name": "list_topics", "description": "List topics for the connected profile.", "category": "read"},
    {"name": "create_topic", "description": "Create a new topic; returns its id for use with generate_briefing.", "category": "write"},
    {"name": "list_casts", "description": "List casts (host personalities) for the connected profile.", "category": "read"},
    {"name": "list_scheduled_briefings", "description": "List scheduled briefings.", "category": "read"},
    {"name": "list_profiles", "description": "List all profiles on this Augustus instance.", "category": "read"},
]
ALL_TOOL_NAMES = [t["name"] for t in MCP_TOOL_CATALOG]


# ---------- Schemas ----------

class ApiKeyResponse(BaseModel):
    id: str
    name: str
    profile_id: str
    profile_name: Optional[str] = None
    key_prefix: str
    enabled_tools: Optional[list[str]] = None
    last_used_at: Optional[datetime] = None
    last_client: Optional[str] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    profile_id: str
    enabled_tools: Optional[list[str]] = None


class ApiKeyCreateResponse(ApiKeyResponse):
    key: str = Field(..., description="Raw API key. Shown ONCE on creation.")


class ApiKeyUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    enabled_tools: Optional[list[str]] = None


class ToolCatalogItem(BaseModel):
    name: str
    description: str
    category: str


class AuditLogEntry(BaseModel):
    id: str
    api_key_id: Optional[str]
    api_key_name: Optional[str]
    tool_name: str
    status: str
    error: Optional[str]
    duration_ms: Optional[int]
    client: Optional[str]
    args_summary: Optional[str]
    created_at: datetime


class ConnectedClient(BaseModel):
    api_key_id: str
    api_key_name: str
    client: Optional[str]
    last_seen: datetime
    request_count_24h: int


# ---------- Helpers ----------

def _to_response(api_key: ApiKey, profile_name: Optional[str] = None) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        profile_id=api_key.profile_id,
        profile_name=profile_name,
        key_prefix=api_key.key_prefix,
        enabled_tools=api_key.enabled_tools,
        last_used_at=api_key.last_used_at,
        last_client=api_key.last_client,
        revoked_at=api_key.revoked_at,
        created_at=api_key.created_at,
    )


# ---------- Routes ----------

class McpMeResponse(BaseModel):
    api_key_id: str
    name: str
    profile_id: str
    profile_name: str
    enabled_tools: Optional[list[str]] = None
    # Base URL of the Augustus web UI (for building /briefing/<id> links).
    web_url: str


class AuditLogCreate(BaseModel):
    tool_name: str
    status: str = Field(..., pattern="^(success|error|denied)$")
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    args_summary: Optional[str] = None
    client: Optional[str] = None


@router.get("/me", response_model=McpMeResponse)
async def mcp_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Identify the calling MCP client via its X-API-Key. Used by the stdio server on startup."""
    # get_current_user attaches current_api_key_id when X-API-Key was provided.
    api_key_id = getattr(user, "current_api_key_id", None)
    if not api_key_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")
    result = await db.execute(
        select(ApiKey, Profile.name)
        .join(Profile, Profile.id == ApiKey.profile_id)
        .where(ApiKey.id == api_key_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")
    api_key, profile_name = row
    from app.config import get_settings
    web_url = (get_settings().frontend_url or "http://localhost:3000").rstrip("/")
    return McpMeResponse(
        api_key_id=api_key.id,
        name=api_key.name,
        profile_id=api_key.profile_id,
        profile_name=profile_name,
        enabled_tools=api_key.enabled_tools,
        web_url=web_url,
    )


@router.post("/audit", status_code=status.HTTP_204_NO_CONTENT)
async def write_audit(
    entry: AuditLogCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Write an audit log entry. Called by the stdio MCP server after each tool invocation."""
    api_key_id = getattr(user, "current_api_key_id", None)
    if not api_key_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")

    log = McpAuditLog(
        api_key_id=api_key_id,
        tool_name=entry.tool_name[:100],
        status=entry.status,
        error=(entry.error or None) and entry.error[:500],
        duration_ms=entry.duration_ms,
        client=(entry.client or None) and entry.client[:255],
        args_summary=(entry.args_summary or None) and entry.args_summary[:500],
    )
    db.add(log)
    await db.commit()


class ServerInfoResponse(BaseModel):
    api_url: str
    python_path: str
    mcp_script_path: str


def _detect_lan_ip() -> Optional[str]:
    """Return the LAN-reachable IP of this server, or None if undetectable."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Doesn't actually send packets; just picks the outbound interface.
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except Exception:
        return None


@router.get("/server-info", response_model=ServerInfoResponse)
async def server_info(request: Request):
    """Connection details the MCP stdio server config needs.

    - api_url: how the MCP server should reach this backend (prefers the LAN IP
      over loopback so a client on another machine can connect).
    - python_path / mcp_script_path: absolute paths to run the bundled stdio
      server as `<python_path> <mcp_script_path>` (valid when the MCP client
      runs on this same machine).
    """
    port = request.url.port
    scheme = request.url.scheme
    host = request.url.hostname or "localhost"

    lan_ip = _detect_lan_ip()
    if lan_ip and host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        host = lan_ip

    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        api_url = f"{scheme}://{host}:{port}"
    else:
        api_url = f"{scheme}://{host}"

    script_path = _MCP_SCRIPT_PATH if os.path.isfile(_MCP_SCRIPT_PATH) else "mcp_server.py"
    return ServerInfoResponse(
        api_url=api_url,
        python_path=sys.executable or "python",
        mcp_script_path=script_path,
    )


@router.get("/tools", response_model=list[ToolCatalogItem])
async def list_tools():
    """List all MCP tools the server can expose."""
    return MCP_TOOL_CATALOG


@router.get("/keys", response_model=list[ApiKeyResponse])
async def list_keys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ApiKey, Profile.name)
        .join(Profile, Profile.id == ApiKey.profile_id)
        .where(ApiKey.user_id == user.id)
        .order_by(desc(ApiKey.created_at))
    )
    rows = result.all()
    return [_to_response(k, profile_name=name) for k, name in rows]


@router.post("/keys", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_key(
    request: ApiKeyCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate profile belongs to user
    result = await db.execute(
        select(Profile).where(Profile.id == request.profile_id, Profile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    # Validate enabled_tools subset of catalog
    if request.enabled_tools is not None:
        invalid = [t for t in request.enabled_tools if t not in ALL_TOOL_NAMES]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown tools: {', '.join(invalid)}",
            )

    raw = generate_raw_key()
    api_key = ApiKey(
        user_id=user.id,
        profile_id=profile.id,
        name=request.name,
        key_prefix=key_prefix_display(raw),
        key_hash=hash_key(raw),
        enabled_tools=request.enabled_tools,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    base = _to_response(api_key, profile_name=profile.name)
    return ApiKeyCreateResponse(**base.model_dump(), key=raw)


@router.patch("/keys/{key_id}", response_model=ApiKeyResponse)
async def update_key(
    key_id: str,
    request: ApiKeyUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    if request.name is not None:
        api_key.name = request.name
    if request.enabled_tools is not None:
        invalid = [t for t in request.enabled_tools if t not in ALL_TOOL_NAMES]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown tools: {', '.join(invalid)}",
            )
        api_key.enabled_tools = request.enabled_tools

    await db.commit()
    await db.refresh(api_key)

    profile_result = await db.execute(select(Profile.name).where(Profile.id == api_key.profile_id))
    profile_name = profile_result.scalar_one_or_none()
    return _to_response(api_key, profile_name=profile_name)


@router.post("/keys/{key_id}/revoke", response_model=ApiKeyResponse)
async def revoke_key(
    key_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    if api_key.revoked_at is None:
        api_key.revoked_at = datetime.utcnow()
        await db.commit()
        await db.refresh(api_key)

    profile_result = await db.execute(select(Profile.name).where(Profile.id == api_key.profile_id))
    profile_name = profile_result.scalar_one_or_none()
    return _to_response(api_key, profile_name=profile_name)


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(
    key_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    await db.delete(api_key)
    await db.commit()


@router.get("/audit", response_model=list[AuditLogEntry])
async def list_audit(
    limit: int = 100,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Recent MCP tool invocations across this user's keys."""
    result = await db.execute(
        select(McpAuditLog, ApiKey.name)
        .join(ApiKey, ApiKey.id == McpAuditLog.api_key_id, isouter=True)
        .where((ApiKey.user_id == user.id) | (McpAuditLog.api_key_id.is_(None)))
        .order_by(desc(McpAuditLog.created_at))
        .limit(limit)
        .offset(offset)
    )
    rows = result.all()
    return [
        AuditLogEntry(
            id=log.id,
            api_key_id=log.api_key_id,
            api_key_name=name,
            tool_name=log.tool_name,
            status=log.status,
            error=log.error,
            duration_ms=log.duration_ms,
            client=log.client,
            args_summary=log.args_summary,
            created_at=log.created_at,
        )
        for log, name in rows
    ]


@router.get("/clients", response_model=list[ConnectedClient])
async def list_connected_clients(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Distinct (api_key, client) pairs seen in the last 24h."""
    since = datetime.utcnow() - timedelta(hours=24)
    result = await db.execute(
        select(
            McpAuditLog.api_key_id,
            ApiKey.name,
            McpAuditLog.client,
            func.max(McpAuditLog.created_at).label("last_seen"),
            func.count(McpAuditLog.id).label("count"),
        )
        .join(ApiKey, ApiKey.id == McpAuditLog.api_key_id)
        .where(ApiKey.user_id == user.id, McpAuditLog.created_at >= since)
        .group_by(McpAuditLog.api_key_id, ApiKey.name, McpAuditLog.client)
        .order_by(desc("last_seen"))
    )
    return [
        ConnectedClient(
            api_key_id=row.api_key_id,
            api_key_name=row.name,
            client=row.client,
            last_seen=row.last_seen,
            request_count_24h=row.count,
        )
        for row in result.all()
    ]
