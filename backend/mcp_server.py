"""Augustus MCP server (stdio transport).

Tools mirror the Augustus REST API. Each call:
  1. checks the per-key enabled_tools list
  2. proxies the request to the backend with X-API-Key
  3. POSTs an audit entry back to the backend

The server discovers its identity by calling /api/mcp/me on startup.
"""

import asyncio
import json
import os
import platform
import sys
import time
from typing import Any, Optional

import httpx
from pydantic import AnyUrl
from mcp.server import Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool

API_URL = os.environ.get("AUGUSTUS_API_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.environ.get("AUGUSTUS_API_KEY", "")
CLIENT_LABEL = f"augustus-mcp/{platform.python_implementation()}-{platform.system()}"

GUIDE_URI = "augustus://guide"

# Surfaced to the client at initialize time (most clients show this to the agent).
# Keep it short — the full reference lives in the augustus://guide resource.
SERVER_INSTRUCTIONS = """\
Augustus is a self-hosted news-briefing app; this server exposes its REST API as \
tools, scoped to the single profile your API key is bound to (no profile/user id \
needed anywhere).

Important behaviours:
- Briefing generation is ASYNCHRONOUS. `generate_briefing` returns immediately with a \
briefing whose status is "queued" or "pending" — the audio and transcript are NOT \
ready yet. Producing them usually takes ~2-8 minutes. Poll `get_briefing(briefing_id)` \
until status is "completed" (or "failed"/"cancelled"); don't claim it's done or read \
the transcript before then.
- Only one briefing per profile generates at a time. `generate_briefing` errors (HTTP \
409) if one is already in progress or queued — wait for it to finish, or \
`cancel_briefing` it first.
- For a briefing about a NEW subject: `create_topic(name=...)` → take the `id` from \
the response → `generate_briefing(topic_ids=[that id])`. With no `topic_ids`, \
generation uses the profile's currently-active topics.
- When a briefing is ready, give the user the links the briefing object carries: \
`listen_url` (a directly playable audio file) and `detail_url` (the in-app page). These \
are exact, absolute URLs the briefing tools fill in for you — pass them through, don't \
construct or guess your own.

Read the `augustus://guide` resource for the full tool reference and workflows.
"""


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=API_URL,
        headers={"X-API-Key": API_KEY, "User-Agent": CLIENT_LABEL},
        timeout=60.0,
    )


# (name, description, JSON schema, handler) - handler returns dict/list to JSON-encode
TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "list_briefings",
        "description": "List briefings for the connected profile. Optional filters.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10},
                "offset": {"type": "integer", "default": 0},
                "listened": {"type": "boolean"},
                "favorite": {"type": "boolean"},
                "cast_id": {"type": "string"},
                "topic_ids": {"type": "array", "items": {"type": "string"}},
            },
        },
        "method": "GET",
        "path": "/api/briefings",
        "kind": "query",
    },
    {
        "name": "get_briefing",
        "description": "Fetch a single briefing by id, including full transcript and metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {"briefing_id": {"type": "string"}},
            "required": ["briefing_id"],
        },
        "method": "GET",
        "path": "/api/briefings/{briefing_id}",
        "kind": "path",
    },
    {
        "name": "generate_briefing",
        "description": "Queue generation of a new briefing. topic_ids and cast_id optional.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic_ids": {"type": "array", "items": {"type": "string"}},
                "cast_id": {"type": "string"},
                "max_duration_minutes": {"type": "integer"},
            },
        },
        "method": "POST",
        "path": "/api/briefings/generate",
        "kind": "json",
    },
    {
        "name": "cancel_briefing",
        "description": "Cancel a queued, pending, or generating briefing.",
        "inputSchema": {
            "type": "object",
            "properties": {"briefing_id": {"type": "string"}},
            "required": ["briefing_id"],
        },
        "method": "POST",
        "path": "/api/briefings/{briefing_id}/cancel",
        "kind": "path",
    },
    {
        "name": "regenerate_audio",
        "description": "Regenerate audio for a completed briefing using a different cast.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "briefing_id": {"type": "string"},
                "cast_id": {"type": "string"},
            },
            "required": ["briefing_id", "cast_id"],
        },
        "method": "POST",
        "path": "/api/briefings/{briefing_id}/regenerate-audio",
        "kind": "path_json",
        "json_keys": ["cast_id"],
    },
    {
        "name": "set_briefing_favorite",
        "description": "Mark a briefing as favorite or unfavorite.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "briefing_id": {"type": "string"},
                "favorite": {"type": "boolean"},
            },
            "required": ["briefing_id", "favorite"],
        },
        "method": "PATCH",
        "path": "/api/briefings/{briefing_id}/favorite",
        "kind": "path_json",
        "json_keys": ["favorite"],
    },
    {
        "name": "set_briefing_listened",
        "description": "Mark a briefing as listened or unlistened.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "briefing_id": {"type": "string"},
                "listened": {"type": "boolean"},
            },
            "required": ["briefing_id", "listened"],
        },
        "method": "PATCH",
        "path": "/api/briefings/{briefing_id}/listened",
        "kind": "path_json",
        "json_keys": ["listened"],
    },
    {
        "name": "list_topics",
        "description": "List topics for the connected profile.",
        "inputSchema": {"type": "object", "properties": {}},
        "method": "GET",
        "path": "/api/topics",
        "kind": "query",
    },
    {
        "name": "create_topic",
        "description": (
            "Create a new topic for the connected profile. Returns the topic, "
            "including its id — pass that id in generate_briefing's topic_ids to "
            "produce a briefing about this topic."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Display name for the topic"},
                "description": {"type": "string", "description": "Optional short description"},
                "color": {"type": "string", "description": "Optional hex color, e.g. #3B82F6"},
                "use_newsapi": {"type": "boolean", "default": True, "description": "Include NewsAPI results for this topic"},
                "enable_site_generation": {"type": "boolean", "default": True, "description": "Allow AI site discovery for this topic"},
            },
            "required": ["name"],
        },
        "method": "POST",
        "path": "/api/topics",
        "kind": "json",
    },
    {
        "name": "list_casts",
        "description": "List casts (host personalities) for the connected profile.",
        "inputSchema": {"type": "object", "properties": {}},
        "method": "GET",
        "path": "/api/casts",
        "kind": "query",
    },
    {
        "name": "list_scheduled_briefings",
        "description": "List scheduled briefings.",
        "inputSchema": {"type": "object", "properties": {}},
        "method": "GET",
        "path": "/api/scheduled-briefings",
        "kind": "query",
    },
    {
        "name": "list_profiles",
        "description": "List all profiles on this Augustus instance.",
        "inputSchema": {"type": "object", "properties": {}},
        "method": "GET",
        "path": "/api/profiles",
        "kind": "query",
    },
]


# Full agent-facing docs, served as the `augustus://guide` MCP resource.
USAGE_GUIDE = """\
# Augustus MCP — agent guide

Augustus is a self-hosted app that turns news topics into short, podcast-style audio
"briefings" (a narrated summary with a transcript and chapters). This MCP server proxies
the Augustus REST API. Every call is scoped to one **profile** — the one your API key is
bound to — so you never pass a profile or user id.

## Core objects

- **Topic** — a subject to follow (e.g. "AI policy"). A profile has several; some are active.
- **Cast** — the set of host "personalities"/voices a briefing is narrated with.
- **Briefing** — a generated episode: `title`, `transcript`, `chapters`, `duration_seconds`,
  and an audio file. Built from a set of topics (or the profile's active topics) and a cast.

## Briefing generation is asynchronous — wait for it

`generate_briefing` **queues** the work and returns immediately. The briefing it returns has
`status` `"queued"` or `"pending"`; `transcript`, `audio_filename`/`audio_url`, and
`duration_seconds` are empty until generation finishes. End-to-end (fetch news → rank → write
script → text-to-speech) usually takes **~2-8 minutes**, sometimes longer.

To detect completion, poll:

1. `generate_briefing(...)` → keep `id` (the `briefing_id`) and `status`.
2. Every ~20-30 seconds, call `get_briefing(briefing_id)`.
3. Stop when `status` is `"completed"` (success — transcript/audio now populated) or
   `"failed"` / `"cancelled"` (see `error_message`). `"queued"`, `"pending"`, and
   `"generating"` mean keep waiting.

Do not tell the user the briefing is ready, or read its transcript, before
`status == "completed"`.

**One at a time:** a profile can have only one briefing generating or queued. Calling
`generate_briefing` while one is in progress returns an HTTP 409 error. Either wait for the
current one (poll `list_briefings` / `get_briefing`) or `cancel_briefing(briefing_id)` first.

## When a briefing is ready — what to give the user

Every briefing returned by these tools — `get_briefing`, `list_briefings`,
`generate_briefing`, `cancel_briefing`, `regenerate_audio`, `set_briefing_*` — is enriched
with two exact, absolute URLs. Hand these to the user verbatim; do **not** build or guess
your own.

- **`listen_url`** — the audio file on the Augustus server, directly playable. Present once
  `status == "completed"` (absent before then, since the audio doesn't exist yet).
- **`detail_url`** — the in-app briefing page (`.../briefing/<id>`). Present as soon as the
  briefing exists, so you can give it to the user right after `generate_briefing` so they can
  watch it generate. Append `?autoplay=true` to start playback. Prefer this when the user
  wants the in-app player — transcript follow-along, chapters, favorite/listened controls.
- Also surface the `title`, `duration_seconds`, and the chapter titles so the user knows what
  they're getting.

For a generation that ends in `status == "failed"`, tell the user it failed and include
`error_message`; offer to retry (`generate_briefing` again) or try different topics.

## Workflow: briefing about a new subject

1. `create_topic(name="<subject>", description="<optional>")` → the response includes `id`.
2. `generate_briefing(topic_ids=["<that id>"])` — optionally also `cast_id`,
   `max_duration_minutes`.
3. Poll `get_briefing` until `status == "completed"` (see above).

For a briefing about subjects the profile already follows, skip step 1 and call
`generate_briefing()` with no `topic_ids`.

## Workflow: re-narrate an existing briefing with different voices

`regenerate_audio(briefing_id, cast_id)` — also asynchronous; poll `get_briefing` until
`status == "completed"`.

## Tool reference

Read:
- `list_briefings(limit, offset, listened, favorite, cast_id, topic_ids)` — recent briefings.
- `get_briefing(briefing_id)` — one briefing with full transcript, chapters, status, error.
- `list_topics()` / `list_casts()` / `list_scheduled_briefings()` — the profile's topics,
  casts, and schedules.
- `list_profiles()` — all profiles on this instance (informational; you still act as your
  key's profile).

Write:
- `create_topic(name, description?, color?, use_newsapi?, enable_site_generation?)` — new
  topic; returns its `id`.
- `generate_briefing(topic_ids?, cast_id?, max_duration_minutes?)` — queue a briefing (async).
- `cancel_briefing(briefing_id)` — cancel a queued/pending/generating briefing.
- `regenerate_audio(briefing_id, cast_id)` — re-narrate a completed briefing with another
  cast (async).
- `set_briefing_favorite(briefing_id, favorite)` / `set_briefing_listened(briefing_id, listened)`
  — toggle flags.

Write actions are recorded in the app's MCP activity log.
"""


async def _proxy(tool: dict[str, Any], args: dict[str, Any]) -> Any:
    method = tool["method"]
    path = tool["path"]
    kind = tool["kind"]
    args = dict(args or {})

    # Substitute path params
    if "{" in path:
        for key in list(args.keys()):
            placeholder = "{" + key + "}"
            if placeholder in path:
                path = path.replace(placeholder, str(args.pop(key)))

    json_body: Optional[dict] = None
    params: Optional[dict] = None
    if kind == "query":
        params = {k: v for k, v in args.items() if v is not None}
    elif kind == "json":
        json_body = {k: v for k, v in args.items() if v is not None}
    elif kind == "path_json":
        json_keys = tool.get("json_keys", [])
        json_body = {k: args[k] for k in json_keys if k in args}
    # 'path' kind = no body, no params

    async with _client() as http:
        resp = await http.request(method, path, params=params, json=json_body)
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        if resp.status_code == 204 or not resp.content:
            return {"ok": True}
        return resp.json()


async def _audit(tool_name: str, status: str, error: Optional[str], duration_ms: int, args: dict) -> None:
    try:
        async with _client() as http:
            await http.post(
                "/api/mcp/audit",
                json={
                    "tool_name": tool_name,
                    "status": status,
                    "error": error,
                    "duration_ms": duration_ms,
                    "args_summary": json.dumps(args)[:500] if args else None,
                    "client": CLIENT_LABEL,
                },
            )
    except Exception:
        # Audit failures must not break the tool call
        pass


# Tools whose result is a briefing object (or {"briefings": [...]}). We add an
# absolute `listen_url` (playable audio) and `detail_url` (in-app page) to each
# briefing so the agent can hand the user exact links without guessing.
_BRIEFING_RESULT_TOOLS = {
    "list_briefings",
    "get_briefing",
    "generate_briefing",
    "cancel_briefing",
    "regenerate_audio",
    "set_briefing_favorite",
    "set_briefing_listened",
}


def _add_briefing_urls(result: Any, web_url: Optional[str]) -> Any:
    """Return `result` with listen_url/detail_url added to each briefing dict in it."""
    def enrich(b: Any) -> Any:
        if not isinstance(b, dict) or "id" not in b:
            return b
        out = dict(b)
        if web_url:
            out["detail_url"] = f"{web_url}/briefing/{out['id']}"
        audio = out.get("audio_url")
        if isinstance(audio, str) and audio:
            out["listen_url"] = API_URL + (audio if audio.startswith("/") else "/" + audio)
        return out

    if isinstance(result, dict):
        if isinstance(result.get("briefings"), list):
            return {**result, "briefings": [enrich(b) for b in result["briefings"]]}
        return enrich(result)
    return result


async def main_async() -> None:
    if not API_KEY:
        print("AUGUSTUS_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(2)

    enabled_tools: Optional[list[str]] = None
    web_url: Optional[str] = None
    try:
        async with _client() as http:
            me = await http.get("/api/mcp/me")
            me.raise_for_status()
            me_data = me.json()
            enabled_tools = me_data.get("enabled_tools")
            web_url = (me_data.get("web_url") or "").rstrip("/") or None
    except Exception as e:
        print(f"Failed to authenticate to {API_URL}: {e}", file=sys.stderr)
        sys.exit(1)

    server: Server = Server("augustus", instructions=SERVER_INSTRUCTIONS)

    tools_by_name = {t["name"]: t for t in TOOL_DEFS}

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return [
            Resource(
                uri=AnyUrl(GUIDE_URI),
                name="augustus-usage-guide",
                title="Augustus usage guide",
                description=(
                    "How to use the Augustus tools: asynchronous briefing generation, "
                    "polling for completion, the create-topic → generate-briefing "
                    "workflow, how to report results to the user, and a tool reference."
                ),
                mimeType="text/markdown",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: AnyUrl) -> list[ReadResourceContents]:
        if str(uri).rstrip("/") != GUIDE_URI:
            raise ValueError(f"Unknown resource: {uri}")
        return [ReadResourceContents(content=USAGE_GUIDE, mime_type="text/markdown")]

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(name=t["name"], description=t["description"], inputSchema=t["inputSchema"])
            for t in TOOL_DEFS
            if enabled_tools is None or t["name"] in enabled_tools
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        tool = tools_by_name.get(name)
        if not tool:
            await _audit(name, "denied", "unknown tool", 0, arguments)
            raise ValueError(f"Unknown tool: {name}")
        if enabled_tools is not None and name not in enabled_tools:
            await _audit(name, "denied", "tool disabled for this key", 0, arguments)
            raise PermissionError(f"Tool '{name}' is disabled for this API key")

        started = time.perf_counter()
        try:
            result = await _proxy(tool, arguments or {})
            if name in _BRIEFING_RESULT_TOOLS:
                result = _add_briefing_urls(result, web_url)
            dur = int((time.perf_counter() - started) * 1000)
            await _audit(name, "success", None, dur, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
        except Exception as e:
            dur = int((time.perf_counter() - started) * 1000)
            await _audit(name, "error", str(e)[:500], dur, arguments)
            raise

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
