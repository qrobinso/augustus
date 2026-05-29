"""Tests for previous-briefing continuity lookups."""
from datetime import datetime

import pytest

from app.models.briefing import Briefing
from app.services.briefing import BriefingService


async def _add_briefing(db, user_id, topic_ids, titles, generated_at, transcript="t"):
    briefing = Briefing(
        user_id=user_id,
        title="x",
        transcript=transcript,
        status="completed",
        extra_data={"topic_ids": topic_ids},
        sources=[{"title": t} for t in titles],
        generated_at=generated_at,
    )
    db.add(briefing)
    await db.commit()
    return briefing


@pytest.mark.asyncio
async def test_returns_titles_from_most_recent_matching_briefing(db_session):
    svc = BriefingService(db_session)
    await _add_briefing(db_session, "u1", ["t1", "t2"], ["Old A", "Old B"], datetime(2026, 1, 1))
    await _add_briefing(db_session, "u1", ["t1", "t2"], ["New A", "New B"], datetime(2026, 2, 1))
    titles = await svc.get_last_story_titles_for_topics("u1", ["t1", "t2"])
    assert titles == ["New A", "New B"]


@pytest.mark.asyncio
async def test_returns_empty_when_topics_do_not_match(db_session):
    svc = BriefingService(db_session)
    await _add_briefing(db_session, "u1", ["t1"], ["A"], datetime(2026, 1, 1))
    assert await svc.get_last_story_titles_for_topics("u1", ["other"]) == []


@pytest.mark.asyncio
async def test_returns_empty_when_no_topics_requested(db_session):
    svc = BriefingService(db_session)
    assert await svc.get_last_story_titles_for_topics("u1", []) == []
