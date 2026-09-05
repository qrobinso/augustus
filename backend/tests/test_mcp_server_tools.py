"""MCP server contract: catalog sync, client-safe schemas, compact payloads, feature coverage."""

import json

import httpx
import pytest
from mcp.types import Tool

import mcp_server as server
from app.routers import mcp as mcp_router


def _tool(name):
    return next(t for t in server.TOOL_DEFS if t["name"] == name)


def test_router_catalog_matches_server_tool_definitions():
    """The management UI and the key permission check use the router catalog."""
    assert [t["name"] for t in server.TOOL_DEFS] == mcp_router.ALL_TOOL_NAMES
    assert {t["category"] for t in mcp_router.MCP_TOOL_CATALOG} <= {"read", "write"}


def test_schemas_avoid_top_level_combinators_and_declare_annotations():
    """Claude's tool schema validation rejects top-level oneOf/anyOf/allOf."""
    for t in server.TOOL_DEFS:
        assert not ({"oneOf", "anyOf", "allOf"} & set(t["inputSchema"])), t["name"]
        assert t["inputSchema"]["type"] == "object"
        annotations = t["annotations"]
        assert "readOnlyHint" in annotations, t["name"]
        # Pydantic validation of the wire shape the SDK sends to clients.
        Tool(name=t["name"], description=t["description"], inputSchema=t["inputSchema"],
             annotations=server._annotations(t))
    breakout = _tool("generate_breakout_podcast")["inputSchema"]
    assert breakout["additionalProperties"] is False
    assert "exactly one" in _tool("generate_breakout_podcast")["description"].lower()


def test_catalog_covers_app_features():
    names = set(mcp_router.ALL_TOOL_NAMES)
    assert {"list_generation_queue", "delete_briefing", "set_story_preference",
            "update_topic", "delete_topic", "create_scheduled_briefing",
            "toggle_scheduled_briefing", "trigger_scheduled_briefing"} <= names
    for name in ("delete_briefing", "delete_topic"):
        assert _tool(name)["annotations"]["destructiveHint"] is True
    for name in ("list_briefings", "get_briefing", "list_generation_queue", "list_topics"):
        assert _tool(name)["annotations"]["readOnlyHint"] is True


def _full_briefing():
    return {
        "id": "b1", "title": "Daily", "status": "completed", "audio_url": "/audio/b1.mp3",
        "transcript": "HOST: hello " * 50, "duration_seconds": 400.0, "cast_id": "c1",
        "favorite": False, "listened": False, "error_message": None,
        "created_at": "2026-09-04T00:00:00Z", "generated_at": "2026-09-04T00:05:00Z",
        "chapters": [{"title": "Coal", "start_time": 0.0, "end_time": 200.0}],
        "sources": [{"title": "ABC", "url": "https://abc.example/a", "source": "abc.example",
                     "summary": "x" * 1200, "excerpt": "y" * 1200}],
        "extra_data": {
            "kind": "breakout", "breakout": {"topic": "Coal loopholes"},
            "chapter_sources": {"0": [{"url": "u", "content": "z" * 50000}]},
            "segment_timings": [{"text": "..."}] * 200, "costs": {"total_usd": 0.12},
            "cast_member_names": ["Ava"], "model": "google/gemini",
            "chapter_stories": {"0": {"story_id": "s1", "title": "Coal", "preference": "normal",
                                      "change_type": "new", "development": "d", "claims": ["big"]}},
        },
    }


def test_briefing_list_items_are_compact_summaries():
    out = server._shape_briefing_result("list_briefings", {"briefings": [_full_briefing()], "total": 1}, {})
    item = out["briefings"][0]
    assert "transcript" not in item and "extra_data" not in item and "sources" not in item
    assert item["chapters"] == [{"title": "Coal", "start_time": 0.0, "end_time": 200.0}]
    assert item["kind"] == "breakout" and item["breakout_topic"] == "Coal loopholes"
    assert item["id"] == "b1" and item["status"] == "completed"
    assert len(json.dumps(item)) < 1500


def test_get_briefing_keeps_transcript_and_story_ids_but_drops_internals():
    out = server._shape_briefing_result("get_briefing", _full_briefing(), {})
    assert out["transcript"].startswith("HOST: hello")
    assert out["sources"] == [{"title": "ABC", "url": "https://abc.example/a", "source": "abc.example",
                               "chapter_index": None}]
    assert out["stories"] == [{"chapter_index": 0, "story_id": "s1", "title": "Coal",
                               "preference": "normal", "change_type": "new"}]
    assert "extra_data" not in out
    assert "segment_timings" not in json.dumps(out) and "chapter_sources" not in json.dumps(out)
    without = server._shape_briefing_result("get_briefing", _full_briefing(), {"include_transcript": False})
    assert "transcript" not in without


@pytest.mark.asyncio
async def test_new_tools_proxy_to_the_right_endpoints(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(server, "_client", lambda: httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://backend.test"))

    await server._proxy(_tool("list_generation_queue"), {})
    await server._proxy(_tool("delete_briefing"), {"briefing_id": "b1"})
    await server._proxy(_tool("set_story_preference"), {"story_id": "s1", "preference": "follow"})
    await server._proxy(_tool("update_topic"), {"topic_id": "t1", "is_active": False})
    await server._proxy(_tool("delete_topic"), {"topic_id": "t1"})
    await server._proxy(_tool("create_scheduled_briefing"),
                        {"name": "Morning", "schedule_time": "07:30", "schedule_days": [0, 1]})
    await server._proxy(_tool("toggle_scheduled_briefing"), {"schedule_id": "sch1"})
    await server._proxy(_tool("trigger_scheduled_briefing"), {"schedule_id": "sch1"})

    seen = [(r.method, r.url.path, json.loads(r.content) if r.content else None) for r in requests]
    assert seen == [
        ("GET", "/api/briefings/queue", None),
        ("DELETE", "/api/briefings/b1", None),
        ("PATCH", "/api/stories/s1/preference", {"preference": "follow"}),
        ("PUT", "/api/topics/t1", {"is_active": False}),
        ("DELETE", "/api/topics/t1", None),
        ("POST", "/api/scheduled-briefings", {"name": "Morning", "schedule_time": "07:30",
                                              "schedule_days": [0, 1]}),
        ("PATCH", "/api/scheduled-briefings/sch1/toggle", None),
        ("POST", "/api/scheduled-briefings/sch1/trigger", None),
    ]
