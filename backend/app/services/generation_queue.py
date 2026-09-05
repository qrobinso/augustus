"""Durable FIFO generation queue for the single-worker application."""

import asyncio
import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.briefing import Briefing
from app.services.briefing import BriefingService, BriefingCancelledException
from app.services.briefing_queue import briefing_queue

logger = logging.getLogger(__name__)


async def recover_interrupted_briefings(db: AsyncSession) -> None:
    """At startup, recover unstarted claims and unblock work behind interrupted runs."""
    rows = (await db.scalars(select(Briefing).where(
        Briefing.status.in_(["pending", "generating"])
    ))).all()
    for briefing in rows:
        if briefing.status == "pending":
            briefing.status = "queued"
        else:
            briefing.status = "failed"
            briefing.error_message = "Generation interrupted by a server restart. Please generate again."
        briefing.extra_data = {**(briefing.extra_data or {}), "progress": None}
    await db.commit()


async def _fail_unfinished(maker, briefing_id: str, message: str) -> None:
    """Use a fresh transaction even if the generation session failed or rolled back."""
    async with maker() as db:
        briefing = await db.get(Briefing, briefing_id)
        if briefing and briefing.status in ("pending", "generating"):
            await db.execute(update(Briefing).where(
                Briefing.id == briefing_id,
                Briefing.status.in_(["pending", "generating"]),
            ).values(
                status="failed", error_message=message,
                extra_data={**(briefing.extra_data or {}), "progress": None},
            ))
            await db.commit()


async def process_generation_queue(db_url: str | None = None) -> None:
    """Drain accepted requests in order; concurrent wakeups cannot duplicate work."""
    if briefing_queue.worker_lock.locked() or briefing_queue.generation_lock.locked():
        return
    async with briefing_queue.worker_lock:
        settings = get_settings()
        engine = create_async_engine(db_url or settings.database_url)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            while not briefing_queue.generation_lock.locked():
                async with maker() as db:
                    # Read only; provider initialization must not block claiming a job.
                    briefing = await db.scalar(select(Briefing).where(
                        Briefing.status == "queued",
                    ).order_by(Briefing.created_at.asc(), Briefing.id.asc()).limit(1))
                    if briefing is None:
                        return
                    briefing_id = briefing.id
                    extra = briefing.extra_data or {}
                    # Cancel/delete can race with selection. Claim only a still-queued row.
                    claimed = await db.execute(update(Briefing).where(
                        Briefing.id == briefing_id, Briefing.status == "queued",
                    ).values(status="pending"))
                    await db.commit()
                    if not claimed.rowcount:
                        continue
                failure = "Generation ended without producing a completed episode."
                try:
                    async with maker() as db:
                        await BriefingService(db).generate_briefing(
                            briefing_id=briefing_id,
                            topic_ids=extra.get("topic_ids") or None,
                            max_duration_minutes=extra.get("max_duration", extra.get("target_duration"))
                                or settings.briefing_duration_minutes,
                            profile_name=extra.get("profile_name"),
                        )
                except BriefingCancelledException:
                    failure = "Generation cancelled."
                except asyncio.CancelledError:
                    failure = "Generation interrupted by server shutdown. Please generate again."
                    raise
                except Exception as error:
                    failure = str(error) or "Generation failed."
                    logger.exception("Generation failed for %s; continuing queue", briefing_id)
                finally:
                    await _fail_unfinished(maker, briefing_id, failure)
        finally:
            await engine.dispose()
