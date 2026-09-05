"""Resolve a breakout target from the active profile and snapshot its context."""
import math

from fastapi import HTTPException
from sqlalchemy import select

from app.models.briefing import Briefing
from app.models.cast import Cast
from app.models.topic import Topic
from app.schemas.briefing import BreakoutGenerateRequest


def _clean_topic(value) -> str:
    return " ".join(str(value or "").split())


def _chapter_topic(extra: dict, index: int, chapter: dict) -> str:
    """Keep the underlying story subject when chapter labels are conceptual."""
    chapter_title = _clean_topic(chapter.get("title"))
    stories = extra.get("chapter_stories") or {}
    story = stories.get(str(index)) if isinstance(stories, dict) else None
    story_title = _clean_topic(story.get("title")) if isinstance(story, dict) else ""

    if extra.get("kind") != "breakout":
        return (story_title or chapter_title)[:300]

    breakout = extra.get("breakout") or {}
    parent_topic = (
        _clean_topic(breakout.get("topic"))
        if isinstance(breakout, dict)
        else ""
    )
    if not parent_topic:
        return (story_title or chapter_title)[:300]
    if not chapter_title or chapter_title.casefold() in parent_topic.casefold():
        return parent_topic[:300]

    # Keep both the durable subject and the selected conceptual facet in the
    # bounded search topic. Prefer retaining the start of the subject if the
    # combined label must be shortened.
    suffix = f": {chapter_title[:80]}"
    return f"{parent_topic[:max(1, 300 - len(suffix))]}{suffix}"[:300]


def _chapter_context(extra: dict, index: int, chapter: dict) -> str:
    """Only include the selected chapter, never the entire parent transcript."""
    parts = []
    stories = extra.get("chapter_stories") or {}
    story = stories.get(str(index)) if isinstance(stories, dict) else None
    if isinstance(story, dict):
        parts.extend(str(story.get(key) or "")[:2000] for key in ("title", "development"))
        for claim in (story.get("claims") or [])[:8]:
            if isinstance(claim, dict):
                parts.append(str(claim.get("text") or "")[:500])
    start, end = chapter.get("start_time"), chapter.get("end_time")
    if end is None:
        chapters = extra.get("chapters") or []
        if index + 1 < len(chapters):
            end = chapters[index + 1].get("start_time")
    def number(value):
        return type(value) in (int, float) and math.isfinite(value)
    if number(start) and number(end) and end > start:
        for segment in extra.get("segment_timings") or []:
            if not isinstance(segment, dict):
                continue
            a, b = segment.get("start_seconds"), segment.get("end_seconds")
            # Only fully contained segments; a boundary-spanning segment could
            # discuss the adjacent chapter and is not reliable source context.
            if number(a) and number(b) and start <= a < b <= end:
                parts.append(str(segment.get("text") or "")[:1000])
    return "\n".join(part for part in parts if part)[:6000]


async def resolve_breakout_request(db, request: BreakoutGenerateRequest, user_id: str, profile_id: str):
    topic_ids = []
    parent = None
    metadata = {"topic": request.topic, "focus": request.focus,
                "source_briefing_id": request.source_briefing_id,
                "chapter_index": request.chapter_index, "source_title": None,
                "source_context": ""}
    if request.topic_id:
        topic = await db.scalar(select(Topic).where(
            Topic.id == request.topic_id, Topic.user_id == user_id, Topic.profile_id == profile_id))
        if topic is None:
            raise HTTPException(404, "Topic not found in this profile")
        metadata["topic"] = topic.name[:300]
        metadata["source_context"] = (topic.description or "")[:6000]
        topic_ids = [topic.id]
    elif request.source_briefing_id:
        parent = await db.scalar(select(Briefing).where(
            Briefing.id == request.source_briefing_id, Briefing.user_id == user_id,
            Briefing.profile_id == profile_id))
        if parent is None:
            raise HTTPException(404, "Source briefing not found in this profile")
        if parent.status != "completed":
            raise HTTPException(422, "Choose a chapter from a completed briefing")
        extra = parent.extra_data or {}
        chapters = extra.get("chapters") or []
        index = request.chapter_index
        if index >= len(chapters) or not isinstance(chapters[index], dict):
            raise HTTPException(422, "Source chapter not found")
        chapter = chapters[index]
        title = _chapter_topic(extra, index, chapter)
        if not title:
            raise HTTPException(422, "Source chapter has no topic")
        metadata.update(topic=title[:300], source_title=parent.title,
                        source_context=_chapter_context(extra, index, chapter))
        # Retain only active-profile IDs, including for legacy parent records.
        ids = extra.get("topic_ids") or []
        if isinstance(ids, list) and ids:
            topic_ids = list((await db.scalars(select(Topic.id).where(
                Topic.id.in_(ids), Topic.user_id == user_id, Topic.profile_id == profile_id))).all())
    cast_id = request.cast_id or (parent.cast_id if parent else None)
    if cast_id:
        cast = await db.scalar(select(Cast).where(
            Cast.id == cast_id, Cast.user_id == user_id, Cast.profile_id == profile_id))
        if cast is None:
            if request.cast_id:
                raise HTTPException(404, "Cast not found in this profile")
            cast_id = None  # A removed parent cast falls back to the current default.
    return metadata, topic_ids, cast_id
