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
from mcp.types import Resource, TextContent, Tool, ToolAnnotations

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
briefing whose status is "queued" — the audio and transcript are NOT \
ready yet. Producing them usually takes ~2-8 minutes. Poll `get_briefing(briefing_id)` \
until status is "completed" (or "failed"/"cancelled"); don't claim it's done or read \
the transcript before then.
- `generate_breakout_podcast` is also asynchronous and follows the same polling and result \
link workflow. Give it exactly one target: a typed `topic`, a saved `topic_id`, or a \
`source_briefing_id` together with `chapter_index`.
- Briefing results are trimmed for you: `list_briefings` returns summaries, and \
`get_briefing` adds the transcript, sources, and a `stories` list whose `story_id` values \
feed `set_story_preference` (follow / less / normal) to steer future coverage.
- `delete_briefing` and `delete_topic` are permanent. Confirm with the user before calling them.
- You can queue multiple daily briefings and breakout podcasts for the same profile. \
Each request returns a separate id. Jobs run one at a time, oldest first, across profiles. \
Waiting jobs survive backend restarts; interrupted generation is marked failed. \
Poll each id independently, or cancel any job you no longer want.
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


def _id(desc: str) -> dict:
    return {"type": "string", "minLength": 1, "maxLength": 100, "description": desc}


READ = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
WRITE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}
IDEMPOTENT_WRITE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
DESTRUCTIVE = {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": False}

# Each entry: name, description, JSON schema, MCP annotations, and how to proxy it.
# `kind` is how arguments map onto the REST call: query string, JSON body,
# path-only, or path plus a JSON body built from `json_keys`.
# Keep names and categories in sync with MCP_TOOL_CATALOG in app/routers/mcp.py
# (a test enforces it).
TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "list_briefings",
        "description": (
            "List briefings for the connected profile as compact summaries (no transcript). "
            "Optional filters. Use get_briefing for the transcript and sources."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
                "listened": {"type": "boolean"},
                "favorite": {"type": "boolean"},
                "cast_id": {"type": "string"},
                "topic_ids": {"type": "array", "items": {"type": "string"}},
            },
        },
        "annotations": READ,
        "method": "GET",
        "path": "/api/briefings",
        "kind": "query",
    },
    {
        "name": "get_briefing",
        "description": (
            "Fetch one briefing by id: status, chapters, transcript, sources, and the "
            "story ids behind each chapter (for set_story_preference)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "briefing_id": _id("Briefing id"),
                "include_transcript": {
                    "type": "boolean",
                    "default": True,
                    "description": "Set false to poll status without the full transcript.",
                },
            },
            "required": ["briefing_id"],
        },
        "annotations": READ,
        "method": "GET",
        "path": "/api/briefings/{briefing_id}",
        "kind": "path",
        "local_keys": ["include_transcript"],
    },
    {
        "name": "list_generation_queue",
        "description": "List briefings still queued, pending, or generating for this profile, oldest first.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": READ,
        "method": "GET",
        "path": "/api/briefings/queue",
        "kind": "query",
    },
    {
        "name": "generate_briefing",
        "description": (
            "Queue generation of a new daily-style briefing (asynchronous; poll get_briefing). "
            "topic_ids and cast_id optional."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic_ids": {"type": "array", "items": {"type": "string"}},
                "cast_id": {"type": "string"},
                "max_duration_minutes": {"type": "integer", "minimum": 1, "maximum": 60},
            },
        },
        "annotations": WRITE,
        "method": "POST",
        "path": "/api/briefings/generate",
        "kind": "json",
    },
    {
        "name": "generate_breakout_podcast",
        "description": (
            "Queue a focused standalone podcast (asynchronous; poll get_briefing). Give it "
            "EXACTLY ONE subject: `topic` (typed subject), `topic_id` (saved topic), or "
            "`source_briefing_id` together with `chapter_index` (a chapter of an existing "
            "briefing). The backend rejects requests with zero or multiple subjects."
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "topic": {"type": "string", "minLength": 1, "maxLength": 300,
                          "description": "Typed subject to research"},
                "topic_id": _id("Saved topic id (from list_topics)"),
                "source_briefing_id": _id("Briefing id; requires chapter_index"),
                "chapter_index": {"type": "integer", "minimum": 0,
                                  "description": "Zero-based chapter index in the source briefing"},
                "focus": {"type": "string", "maxLength": 1000, "default": "",
                          "description": "Optional narrower angle within the subject"},
                "max_duration_minutes": {"type": "integer", "minimum": 3, "maximum": 30, "default": 10},
                "cast_id": _id("Cast id (from list_casts)"),
            },
        },
        "annotations": WRITE,
        "method": "POST",
        "path": "/api/briefings/breakout",
        "kind": "json",
    },
    {
        "name": "cancel_briefing",
        "description": "Cancel a queued, pending, or generating briefing.",
        "inputSchema": {
            "type": "object",
            "properties": {"briefing_id": _id("Briefing id")},
            "required": ["briefing_id"],
        },
        "annotations": IDEMPOTENT_WRITE,
        "method": "POST",
        "path": "/api/briefings/{briefing_id}/cancel",
        "kind": "path",
    },
    {
        "name": "delete_briefing",
        "description": "Permanently delete a briefing and its audio. Confirm with the user first.",
        "inputSchema": {
            "type": "object",
            "properties": {"briefing_id": _id("Briefing id")},
            "required": ["briefing_id"],
        },
        "annotations": DESTRUCTIVE,
        "method": "DELETE",
        "path": "/api/briefings/{briefing_id}",
        "kind": "path",
    },
    {
        "name": "regenerate_audio",
        "description": "Regenerate audio for a completed briefing using a different cast (asynchronous).",
        "inputSchema": {
            "type": "object",
            "properties": {"briefing_id": _id("Briefing id"), "cast_id": _id("Cast id")},
            "required": ["briefing_id", "cast_id"],
        },
        "annotations": WRITE,
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
            "properties": {"briefing_id": _id("Briefing id"), "favorite": {"type": "boolean"}},
            "required": ["briefing_id", "favorite"],
        },
        "annotations": IDEMPOTENT_WRITE,
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
            "properties": {"briefing_id": _id("Briefing id"), "listened": {"type": "boolean"}},
            "required": ["briefing_id", "listened"],
        },
        "annotations": IDEMPOTENT_WRITE,
        "method": "PATCH",
        "path": "/api/briefings/{briefing_id}/listened",
        "kind": "path_json",
        "json_keys": ["listened"],
    },
    {
        "name": "set_story_preference",
        "description": (
            "Tell the profile's story memory to follow a story more closely, cover it less, "
            "or return to normal. Story ids come from get_briefing's `stories` list."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "story_id": _id("Story id from get_briefing"),
                "preference": {"type": "string", "enum": ["normal", "follow", "less"]},
            },
            "required": ["story_id", "preference"],
        },
        "annotations": IDEMPOTENT_WRITE,
        "method": "PATCH",
        "path": "/api/stories/{story_id}/preference",
        "kind": "path_json",
        "json_keys": ["preference"],
    },
    {
        "name": "list_topics",
        "description": "List topics for the connected profile, including whether each is active.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": READ,
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
                "name": {"type": "string", "maxLength": 100, "description": "Display name for the topic"},
                "description": {"type": "string", "maxLength": 500, "description": "Optional short description"},
                "color": {"type": "string", "description": "Optional hex color, e.g. #3B82F6"},
                "use_newsapi": {"type": "boolean", "default": True, "description": "Include NewsAPI results for this topic"},
                "enable_site_generation": {"type": "boolean", "default": True, "description": "Allow AI site discovery for this topic"},
            },
            "required": ["name"],
        },
        "annotations": WRITE,
        "method": "POST",
        "path": "/api/topics",
        "kind": "json",
    },
    {
        "name": "update_topic",
        "description": "Update a topic: rename, describe, recolor, or activate/deactivate it (is_active).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic_id": _id("Topic id"),
                "name": {"type": "string", "maxLength": 100},
                "description": {"type": "string", "maxLength": 500},
                "color": {"type": "string"},
                "is_active": {"type": "boolean"},
                "use_newsapi": {"type": "boolean"},
                "enable_site_generation": {"type": "boolean"},
            },
            "required": ["topic_id"],
        },
        "annotations": IDEMPOTENT_WRITE,
        "method": "PUT",
        "path": "/api/topics/{topic_id}",
        "kind": "path_json",
        "json_keys": ["name", "description", "color", "is_active", "use_newsapi", "enable_site_generation"],
    },
    {
        "name": "delete_topic",
        "description": "Permanently delete a topic. Confirm with the user first.",
        "inputSchema": {
            "type": "object",
            "properties": {"topic_id": _id("Topic id")},
            "required": ["topic_id"],
        },
        "annotations": DESTRUCTIVE,
        "method": "DELETE",
        "path": "/api/topics/{topic_id}",
        "kind": "path",
    },
    {
        "name": "list_casts",
        "description": "List casts (host personalities) for the connected profile.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": READ,
        "method": "GET",
        "path": "/api/casts",
        "kind": "query",
    },
    {
        "name": "list_scheduled_briefings",
        "description": "List scheduled (recurring) briefings for the connected profile.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": READ,
        "method": "GET",
        "path": "/api/scheduled-briefings",
        "kind": "query",
    },
    {
        "name": "create_scheduled_briefing",
        "description": (
            "Create a recurring briefing schedule. Times are HH:MM in the profile's timezone; "
            "days are 0=Monday .. 6=Sunday. Empty topic_ids means the profile's active topics."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "minLength": 1, "maxLength": 500},
                "schedule_time": {"type": "string", "pattern": "^([0-1][0-9]|2[0-3]):[0-5][0-9]$"},
                "schedule_days": {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 6},
                                  "minItems": 1},
                "topic_ids": {"type": "array", "items": {"type": "string"}},
                "cast_id": {"type": "string"},
                "max_duration_minutes": {"type": "integer", "minimum": 1, "maximum": 60},
                "is_active": {"type": "boolean", "default": True},
            },
            "required": ["name", "schedule_time", "schedule_days"],
        },
        "annotations": WRITE,
        "method": "POST",
        "path": "/api/scheduled-briefings",
        "kind": "json",
    },
    {
        "name": "toggle_scheduled_briefing",
        "description": "Enable or disable a schedule (flips its is_active flag).",
        "inputSchema": {
            "type": "object",
            "properties": {"schedule_id": _id("Schedule id")},
            "required": ["schedule_id"],
        },
        "annotations": WRITE,
        "method": "PATCH",
        "path": "/api/scheduled-briefings/{schedule_id}/toggle",
        "kind": "path",
    },
    {
        "name": "trigger_scheduled_briefing",
        "description": "Run a schedule now, queuing a briefing with that schedule's settings (asynchronous).",
        "inputSchema": {
            "type": "object",
            "properties": {"schedule_id": _id("Schedule id")},
            "required": ["schedule_id"],
        },
        "annotations": WRITE,
        "method": "POST",
        "path": "/api/scheduled-briefings/{schedule_id}/trigger",
        "kind": "path",
    },
    {
        "name": "list_profiles",
        "description": "List all profiles on this Augustus instance (informational; you still act as your key's profile).",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": READ,
        "method": "GET",
        "path": "/api/profiles",
        "kind": "query",
    },
]


def _annotations(tool: dict[str, Any]) -> ToolAnnotations:
    return ToolAnnotations(**tool["annotations"])


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
`status` `"queued"`; `transcript`, `audio_filename`/`audio_url`, and
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

**Multiple queued episodes:** submit as many daily briefings and breakout podcasts as
needed, retaining each returned id. The shared worker generates one episode at a time in
first-in, first-out order across profiles. Waiting jobs are stored in the database and
resume after a backend restart. A generation interrupted by a restart is marked `failed`;
legacy `pending` jobs are returned to the queue. Poll each id independently or cancel it.
`GET /api/briefings/queue` lists all active jobs for the authenticated profile, oldest first.

`generate_breakout_podcast` queues the same kind of briefing result and uses the same polling
loop. Pass exactly one subject selector: `topic="<typed subject>"`, `topic_id="<saved id>"`,
or both `source_briefing_id="<briefing id>"` and `chapter_index=<zero-based index>`. You may
also pass `focus` (up to 1000 characters), `max_duration_minutes` (3-30, default 10), and
`cast_id`. A chapter breakout snapshots its source context when queued.

## When a briefing is ready — what to give the user

Every briefing returned by these tools — `get_briefing`, `list_briefings`,
`generate_briefing`, `generate_breakout_podcast`, `cancel_briefing`, `regenerate_audio`,
`set_briefing_*` — is enriched with two exact, absolute URLs. Hand these to the user
verbatim; do **not** build or guess your own.

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

## Workflow: steer future coverage (story memory)

Daily briefings are built on a per-profile **story memory**: each chapter is tied to a
story that carries across episodes. `get_briefing` returns a `stories` list with
`story_id`, `title`, `chapter_index`, and the current `preference`. When the user says
"keep me updated on this" or "I'm tired of hearing about that", call
`set_story_preference(story_id, preference)` with `"follow"`, `"less"`, or `"normal"`.

## Workflow: manage what the profile follows

- `list_topics()` shows every topic and whether it is active (active topics feed
  `generate_briefing()` when no `topic_ids` are given).
- `update_topic(topic_id, is_active=false)` pauses a topic without deleting it;
  `delete_topic` is permanent — confirm first.
- `create_scheduled_briefing(name, schedule_time="07:30", schedule_days=[0,1,2,3,4])` sets up a
  recurring episode; `toggle_scheduled_briefing` pauses/resumes it and
  `trigger_scheduled_briefing` runs it immediately.

## Payload shapes

Raw briefings carry large pipeline internals. The tools trim them:

- `list_briefings` / `list_generation_queue` items: `id`, `title`, `status`, `kind`
  (`daily` or `breakout`), `duration_seconds`, chapter titles, flags, links.
- `get_briefing`: the summary plus `transcript` (omit with `include_transcript=false` when
  only polling), `sources` (title, url, source), and `stories`.

## Tool reference

Read:
- `list_briefings(limit, offset, listened, favorite, cast_id, topic_ids)` — recent briefings
  as summaries.
- `get_briefing(briefing_id, include_transcript?)` — one briefing with transcript, chapters,
  sources, stories, status, error.
- `list_generation_queue()` — briefings still queued/pending/generating, oldest first.
- `list_topics()` / `list_casts()` / `list_scheduled_briefings()` — the profile's topics,
  casts, and schedules.
- `list_profiles()` — all profiles on this instance (informational; you still act as your
  key's profile).

Write:
- `generate_briefing(topic_ids?, cast_id?, max_duration_minutes?)` — queue a briefing (async).
- `generate_breakout_podcast(topic? | topic_id? | source_briefing_id + chapter_index, focus?,`
  `max_duration_minutes?, cast_id?)` — queue one focused standalone podcast (async).
- `cancel_briefing(briefing_id)` — cancel a queued/pending/generating briefing.
- `delete_briefing(briefing_id)` — permanent; confirm first.
- `regenerate_audio(briefing_id, cast_id)` — re-narrate a completed briefing with another
  cast (async).
- `set_briefing_favorite(briefing_id, favorite)` / `set_briefing_listened(briefing_id, listened)`
  — toggle flags.
- `set_story_preference(story_id, preference)` — `follow`, `less`, or `normal`.
- `create_topic(name, description?, color?, use_newsapi?, enable_site_generation?)` — new
  topic; returns its `id`.
- `update_topic(topic_id, name?, description?, color?, is_active?, ...)` /
  `delete_topic(topic_id)` (permanent; confirm first).
- `create_scheduled_briefing(name, schedule_time, schedule_days, topic_ids?, cast_id?,`
  `max_duration_minutes?, is_active?)` / `toggle_scheduled_briefing(schedule_id)` /
  `trigger_scheduled_briefing(schedule_id)`.

Write actions are recorded in the app's MCP activity log.
"""


async def _proxy(tool: dict[str, Any], args: dict[str, Any]) -> Any:
    method = tool["method"]
    path = tool["path"]
    kind = tool["kind"]
    args = dict(args or {})
    for key in tool.get("local_keys", []):
        args.pop(key, None)

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


# Tools whose result is a briefing object (or {"briefings": [...]}). Raw
# briefings carry large pipeline internals (per-chapter fetched pages, TTS
# segment timings) that an agent never needs, so results are reshaped:
# list items become compact summaries, get_briefing keeps the transcript,
# chapters, trimmed sources, and story ids. Each briefing also gains an
# absolute `listen_url` and `detail_url` so the agent hands out exact links.
_BRIEFING_RESULT_TOOLS = {
    "list_briefings",
    "get_briefing",
    "list_generation_queue",
    "generate_briefing",
    "generate_breakout_podcast",
    "cancel_briefing",
    "regenerate_audio",
    "set_briefing_favorite",
    "set_briefing_listened",
}

_SUMMARY_KEYS = (
    "id", "title", "status", "error_message", "duration_seconds", "cast_id",
    "favorite", "listened", "listened_at", "playback_position", "created_at",
    "generated_at", "audio_url",
)


def _summarize_briefing(b: dict) -> dict:
    out = {k: b[k] for k in _SUMMARY_KEYS if k in b}
    out["chapters"] = [
        {k: c.get(k) for k in ("title", "start_time", "end_time") if k in c}
        for c in b.get("chapters") or [] if isinstance(c, dict)
    ]
    extra = b.get("extra_data") or {}
    if isinstance(extra, dict):
        out["kind"] = extra.get("kind") or "daily"
        breakout = extra.get("breakout")
        if isinstance(breakout, dict):
            out["breakout_topic"] = breakout.get("topic")
            out["breakout_focus"] = breakout.get("focus") or None
            out["source_briefing_id"] = breakout.get("source_briefing_id")
        if extra.get("cast_member_names"):
            out["hosts"] = extra["cast_member_names"]
    return out


def _detail_briefing(b: dict, include_transcript: bool) -> dict:
    out = _summarize_briefing(b)
    if include_transcript and b.get("transcript"):
        out["transcript"] = b["transcript"]
    out["sources"] = [
        {
            "title": src.get("title"),
            "url": src.get("url"),
            "source": src.get("source"),
            "chapter_index": src.get("chapter_index"),
        }
        for src in b.get("sources") or [] if isinstance(src, dict) and src.get("url")
    ]
    extra = b.get("extra_data") or {}
    stories = extra.get("chapter_stories") if isinstance(extra, dict) else None
    out["stories"] = []
    if isinstance(stories, dict):
        for index, story in sorted(stories.items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else 0):
            if isinstance(story, dict) and story.get("story_id"):
                out["stories"].append({
                    "chapter_index": int(index) if str(index).isdigit() else index,
                    "story_id": story["story_id"],
                    "title": story.get("title"),
                    "preference": story.get("preference"),
                    "change_type": story.get("change_type"),
                })
    return out


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


def _shape_briefing_result(tool_name: str, result: Any, args: dict[str, Any]) -> Any:
    """Reduce raw API briefings to what an agent needs before adding links."""
    if isinstance(result, dict) and isinstance(result.get("briefings"), list):
        return {**result, "briefings": [
            _summarize_briefing(b) if isinstance(b, dict) and "id" in b else b
            for b in result["briefings"]
        ]}
    if isinstance(result, dict) and "id" in result:
        if tool_name == "get_briefing":
            return _detail_briefing(result, args.get("include_transcript", True) is not False)
        return _summarize_briefing(result)
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
            Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
                annotations=_annotations(t),
            )
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
                result = _add_briefing_urls(_shape_briefing_result(name, result, arguments or {}), web_url)
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
