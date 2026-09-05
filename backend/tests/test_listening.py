"""Listening coverage records real playback independently of resume/listened flags."""

import asyncio
import math

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models.briefing import Briefing
from app.models.listening import ListeningRecord
from app.models.profile import Profile
from app.models.user import User
from app.routers.briefings import record_listening
from app.schemas.briefing import ListeningRangesRequest
from app.services.listening import ListeningService


async def _briefing(
    db,
    *,
    briefing_id="briefing-1",
    user_id="user-1",
    profile_id="profile-1",
    listened=False,
    playback_position=None,
):
    user = await db.get(User, user_id)
    if user is None:
        db.add(User(id=user_id, name=user_id, preferences={}))
    profile = await db.get(Profile, profile_id)
    if profile is None:
        db.add(
            Profile(
                id=profile_id,
                user_id=user_id,
                name=profile_id,
                color="#123456",
                is_admin=False,
            )
        )
    briefing = Briefing(
        id=briefing_id,
        user_id=user_id,
        profile_id=profile_id,
        title="Coverage fixture",
        status="completed",
        duration_seconds=100,
        listened=listened,
        playback_position=playback_position,
        extra_data={
            "chapters": [
                {"title": "First", "start_time": 0, "end_time": 50},
                {"title": "Second", "start_time": 50, "end_time": 100},
            ]
        },
        sources=[],
    )
    db.add(briefing)
    await db.commit()
    return briefing


@pytest.mark.asyncio
async def test_overlaps_merge_and_only_covered_chapter_time_counts(db_session):
    briefing = await _briefing(db_session)

    coverage = await ListeningService(db_session).record(
        briefing, [[0, 40], [20, 60]]
    )

    assert coverage == {
        "ranges": [[0.0, 60.0]],
        "chapter_coverage": {"0": 1.0, "1": 0.2},
        "episode_coverage": 0.6,
    }
    await db_session.refresh(briefing)
    assert briefing.listened is False


@pytest.mark.asyncio
async def test_repeated_ranges_are_idempotent_and_eighty_percent_marks_listened(db_session):
    briefing = await _briefing(db_session)
    service = ListeningService(db_session)

    await service.record(briefing, [[0, 40], [0, 40]])
    coverage = await service.record(briefing, [[0, 40], [40, 80]])

    assert coverage["ranges"] == [[0.0, 80.0]]
    assert coverage["episode_coverage"] == 0.8
    rows = (await db_session.execute(select(ListeningRecord))).scalars().all()
    assert len(rows) == 1
    await db_session.refresh(briefing)
    assert briefing.listened is True
    assert briefing.listened_at is not None


@pytest.mark.asyncio
async def test_legacy_flags_and_resume_position_do_not_create_coverage(db_session):
    briefing = await _briefing(
        db_session, listened=True, playback_position=99
    )

    assert await ListeningService(db_session).coverage(briefing) == {
        "ranges": [],
        "chapter_coverage": {},
        "episode_coverage": 0.0,
    }


@pytest.mark.parametrize(
    "ranges",
    [
        [[5, 5]],
        [[6, 5]],
        [[-1, 5]],
        [[0, math.inf]],
        [[0, math.nan]],
        [[0]],
    ],
)
def test_request_rejects_malformed_ranges(ranges):
    with pytest.raises(ValidationError):
        ListeningRangesRequest(ranges=ranges)


@pytest.mark.asyncio
async def test_service_rejects_ranges_past_episode_duration(db_session):
    briefing = await _briefing(db_session)

    with pytest.raises(ValueError, match="duration"):
        await ListeningService(db_session).record(briefing, [[99, 101]])


@pytest.mark.asyncio
async def test_endpoint_blocks_a_different_profile(db_session):
    briefing = await _briefing(db_session)
    other_profile = Profile(
        id="profile-2",
        user_id=briefing.user_id,
        name="Other",
        color="#654321",
        is_admin=False,
    )
    db_session.add(other_profile)
    await db_session.commit()
    user = await db_session.get(User, briefing.user_id)

    with pytest.raises(HTTPException) as exc:
        await record_listening(
            briefing.id,
            ListeningRangesRequest(ranges=[[0, 10]]),
            user=user,
            profile=other_profile,
            db=db_session,
        )

    assert exc.value.status_code == 403
    assert await db_session.get(ListeningRecord, briefing.id) is None


@pytest.mark.asyncio
async def test_concurrent_sqlite_writers_do_not_drop_ranges(tmp_path):
    database_path = tmp_path / "listening.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path}",
        connect_args={"timeout": 5},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as setup:
        briefing = await _briefing(setup)
        briefing_id = briefing.id

    async with maker() as first, maker() as second:
        first_briefing = await first.get(Briefing, briefing_id)
        second_briefing = await second.get(Briefing, briefing_id)
        await asyncio.gather(
            ListeningService(first).record(first_briefing, [[0, 20]]),
            ListeningService(second).record(second_briefing, [[40, 60]]),
        )

    async with maker() as check:
        stored = await check.get(Briefing, briefing_id)
        coverage = await ListeningService(check).coverage(stored)
        assert coverage["ranges"] == [[0.0, 20.0], [40.0, 60.0]]

    await engine.dispose()
