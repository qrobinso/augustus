"""Durable queue integration tests using separate sessions and a real SQLite file."""

import asyncio
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models.briefing import Briefing
from app.services.briefing import BriefingService, BriefingCancelledException
from app.services.briefing_queue import briefing_queue
from app.services.generation_queue import process_generation_queue, recover_interrupted_briefings


@pytest_asyncio.fixture
async def queue_db(tmp_path, monkeypatch):
    url = f"sqlite+aiosqlite:///{tmp_path / 'queue.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(briefing_queue, 'generation_lock', asyncio.Lock())
    monkeypatch.setattr(briefing_queue, 'worker_lock', asyncio.Lock())
    yield url, maker
    await engine.dispose()


async def seed(maker, *statuses):
    async with maker() as db:
        for index, status in enumerate(statuses):
            db.add(Briefing(
                id=f'job-{index}', user_id='user', profile_id=f'profile-{index % 2}',
                title=f'Job {index}', status=status,
                created_at=datetime(2026, 9, 4) + timedelta(seconds=index),
                extra_data={'kind': 'breakout' if index % 2 else 'daily',
                            'topic_ids': [f'topic-{index}'], 'profile_name': f'Listener {index}',
                            'max_duration': 5 + index, 'progress': {'percent': 40}},
            ))
        await db.commit()


async def states(maker):
    async with maker() as db:
        rows = (await db.scalars(select(Briefing).order_by(Briefing.id))).all()
        return {row.id: row.status for row in rows}


@pytest.mark.asyncio
async def test_concurrent_workers_generate_mixed_jobs_once_in_fifo_order(queue_db, monkeypatch):
    url, maker = queue_db
    await seed(maker, 'queued', 'queued', 'queued')
    calls = []
    entered, release = asyncio.Event(), asyncio.Event()

    async def generate(service, briefing_id, briefing, topic_ids, max_duration_minutes, profile_name):
        calls.append((briefing_id, topic_ids, max_duration_minutes, profile_name))
        if briefing_id == 'job-0':
            entered.set()
            await release.wait()
        briefing.status = 'completed'
        await service.db.commit()
        return briefing

    monkeypatch.setattr(BriefingService, '_generate_briefing_internal', generate)
    first = asyncio.create_task(process_generation_queue(url))
    await asyncio.wait_for(entered.wait(), 2)
    await process_generation_queue(url)
    assert [call[0] for call in calls] == ['job-0']
    release.set()
    await asyncio.wait_for(first, 3)
    assert calls == [
        ('job-0', ['topic-0'], 5, 'Listener 0'),
        ('job-1', ['topic-1'], 6, 'Listener 1'),
        ('job-2', ['topic-2'], 7, 'Listener 2'),
    ]
    assert set((await states(maker)).values()) == {'completed'}


@pytest.mark.asyncio
async def test_failure_and_cancelled_job_do_not_block_later_jobs(queue_db, monkeypatch):
    url, maker = queue_db
    await seed(maker, 'queued', 'cancelled', 'queued')
    calls = []

    async def generate(service, briefing_id, briefing, **kwargs):
        calls.append(briefing_id)
        if briefing_id == 'job-0':
            raise RuntimeError('Provider unavailable')
        briefing.status = 'completed'
        await service.db.commit()
        return briefing

    monkeypatch.setattr(BriefingService, '_generate_briefing_internal', generate)
    await process_generation_queue(url)
    assert calls == ['job-0', 'job-2']
    assert await states(maker) == {'job-0': 'failed', 'job-1': 'cancelled', 'job-2': 'completed'}


@pytest.mark.asyncio
async def test_restart_keeps_waiting_jobs_and_clears_interrupted_active_blockers(queue_db):
    _, maker = queue_db
    await seed(maker, 'queued', 'pending', 'generating', 'completed', 'cancelled')
    async with maker() as db:
        await recover_interrupted_briefings(db)
    assert await states(maker) == {
        'job-0': 'queued', 'job-1': 'queued', 'job-2': 'failed',
        'job-3': 'completed', 'job-4': 'cancelled',
    }
    async with maker() as db:
        interrupted = await db.get(Briefing, 'job-2')
        assert 'restart' in interrupted.error_message.lower()
        assert interrupted.extra_data['progress'] is None
        waiting = await db.get(Briefing, 'job-1')
        assert waiting.extra_data['max_duration'] == 6
        assert waiting.extra_data['topic_ids'] == ['topic-1']


@pytest.mark.asyncio
async def test_cancel_before_generation_start_cannot_revive_job(queue_db, monkeypatch):
    _, maker = queue_db
    await seed(maker, 'cancelled')

    async def unexpected(*args, **kwargs):
        pytest.fail('Cancelled job entered generation')

    monkeypatch.setattr(BriefingService, '_generate_briefing_internal', unexpected)
    async with maker() as db:
        with pytest.raises(BriefingCancelledException):
            await BriefingService(db).generate_briefing('job-0')
    assert await states(maker) == {'job-0': 'cancelled'}


@pytest.mark.asyncio
async def test_cancellation_between_loading_and_claiming_cannot_revive_job(queue_db, monkeypatch):
    _, maker = queue_db
    await seed(maker, 'pending')
    original = BriefingService._generate_briefing_internal

    async def cancel_then_generate(service, **kwargs):
        async with maker() as other:
            await BriefingService(other).cancel_briefing('job-0')
        return await original(service, **kwargs)

    monkeypatch.setattr(BriefingService, '_generate_briefing_internal', cancel_then_generate)
    async with maker() as db:
        with pytest.raises(BriefingCancelledException):
            await BriefingService(db).generate_briefing('job-0')
    assert await states(maker) == {'job-0': 'cancelled'}


@pytest.mark.asyncio
async def test_jobs_added_or_cancelled_while_running_are_seen_by_worker(queue_db, monkeypatch):
    url, maker = queue_db
    await seed(maker, 'queued', 'queued')
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def generate(service, briefing_id, briefing, **kwargs):
        calls.append(briefing_id)
        if briefing_id == 'job-0':
            entered.set()
            await release.wait()
        briefing.status = 'completed'
        await service.db.commit()
        return briefing

    monkeypatch.setattr(BriefingService, '_generate_briefing_internal', generate)
    worker = asyncio.create_task(process_generation_queue(url))
    await asyncio.wait_for(entered.wait(), 2)
    async with maker() as db:
        await BriefingService(db).cancel_briefing('job-1')
        new = await BriefingService(db).create_briefing(
            user_id='user', profile_id='profile-0', initial_status='queued',
            topic_ids=[], max_duration_minutes=12, profile_name='New listener',
        )
    release.set()
    await asyncio.wait_for(worker, 3)
    assert calls == ['job-0', new.id]
    assert (await states(maker))['job-1'] == 'cancelled'


@pytest.mark.asyncio
async def test_direct_generation_and_queue_share_execution_slot(queue_db, monkeypatch):
    url, maker = queue_db
    await seed(maker, 'pending', 'queued')
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def generate(service, briefing_id, briefing, **kwargs):
        calls.append(briefing_id)
        if briefing_id == 'job-0':
            entered.set()
            await release.wait()
        briefing.status = 'completed'
        await service.db.commit()
        return briefing

    monkeypatch.setattr(BriefingService, '_generate_briefing_internal', generate)
    async with maker() as db:
        direct = asyncio.create_task(BriefingService(db).generate_briefing('job-0'))
        await asyncio.wait_for(entered.wait(), 2)
        await process_generation_queue(url)
        assert calls == ['job-0']
        release.set()
        await direct
    await process_generation_queue(url)
    assert calls == ['job-0', 'job-1']


@pytest.mark.asyncio
async def test_shutdown_releases_worker_and_leaves_remaining_jobs_queued(queue_db, monkeypatch):
    url, maker = queue_db
    await seed(maker, 'queued', 'queued')
    entered = asyncio.Event()

    async def generate(*args, **kwargs):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(BriefingService, '_generate_briefing_internal', generate)
    worker = asyncio.create_task(process_generation_queue(url))
    await asyncio.wait_for(entered.wait(), 2)
    worker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker
    assert not briefing_queue.worker_lock.locked()
    assert not briefing_queue.generation_lock.locked()
    assert (await states(maker))['job-1'] == 'queued'
