"""Tests for global briefing search (q param)."""
import pytest

from app.models.user import User
from app.models.briefing import Briefing
from app.services.briefing import BriefingService


async def _seed(db):
    user = User(id="u1", email="u@test.com")
    db.add(user)
    db.add_all([
        Briefing(id="b1", user_id="u1", title="Tech Roundup",
                 transcript="Apple announced a new chip today.", status="completed"),
        Briefing(id="b2", user_id="u1", title="World News",
                 transcript="Elections were held in several countries.", status="completed"),
        Briefing(id="b3", user_id="u1", title="Market Update",
                 transcript="The apple harvest affected commodity prices.", status="completed"),
    ])
    await db.commit()
    return user


@pytest.mark.asyncio
async def test_search_matches_title(db_session):
    await _seed(db_session)
    service = BriefingService(db_session)
    results, total = await service.list_briefings("u1", q="world")
    assert total == 1
    assert results[0].id == "b2"


@pytest.mark.asyncio
async def test_search_matches_transcript_case_insensitive(db_session):
    await _seed(db_session)
    service = BriefingService(db_session)
    results, total = await service.list_briefings("u1", q="APPLE")
    ids = {b.id for b in results}
    assert ids == {"b1", "b3"}
    assert total == 2


@pytest.mark.asyncio
async def test_empty_q_returns_all(db_session):
    await _seed(db_session)
    service = BriefingService(db_session)
    _, total = await service.list_briefings("u1", q="")
    assert total == 3


@pytest.mark.asyncio
async def test_search_escapes_like_wildcards(db_session):
    await _seed(db_session)
    service = BriefingService(db_session)
    _, total = await service.list_briefings("u1", q="%")
    assert total == 0
