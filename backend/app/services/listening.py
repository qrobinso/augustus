"""Store and calculate unique listening coverage."""

import asyncio
import math
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.briefing import Briefing
from app.models.listening import ListeningRecord


Range = list[float]


def merge_ranges(ranges: Iterable[Iterable[float]]) -> list[Range]:
    """Return sorted, non-overlapping intervals; touching intervals are joined."""
    ordered = sorted(([float(start), float(end)] for start, end in ranges), key=lambda r: r[0])
    merged: list[Range] = []
    for start, end in ordered:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


class ListeningService:
    """Owns atomic interval merging and coverage calculations."""

    _MAX_WRITE_ATTEMPTS = 12

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record(self, briefing: Briefing, ranges: list[list[float]]) -> dict[str, Any]:
        """Atomically merge ranges and return the resulting coverage payload."""
        snapshot = self._snapshot(briefing)
        incoming = self._validate_ranges(ranges, snapshot["duration"])

        for attempt in range(self._MAX_WRITE_ATTEMPTS):
            try:
                result = await self.db.execute(
                    select(ListeningRecord.ranges, ListeningRecord.revision).where(
                        ListeningRecord.briefing_id == snapshot["id"]
                    )
                )
                current = result.one_or_none()

                if current is None:
                    merged = merge_ranges(incoming)
                    await self.db.execute(
                        insert(ListeningRecord).values(
                            briefing_id=snapshot["id"],
                            ranges=merged,
                            revision=0,
                            updated_at=datetime.utcnow(),
                        )
                    )
                else:
                    stored_ranges, revision = current
                    safe_stored = self._valid_stored_ranges(stored_ranges, snapshot["duration"])
                    merged = merge_ranges([*safe_stored, *incoming])
                    updated = await self.db.execute(
                        update(ListeningRecord)
                        .where(
                            ListeningRecord.briefing_id == snapshot["id"],
                            ListeningRecord.revision == revision,
                        )
                        .values(
                            ranges=merged,
                            revision=revision + 1,
                            updated_at=datetime.utcnow(),
                        )
                    )
                    if updated.rowcount != 1:
                        await self.db.rollback()
                        await asyncio.sleep(0)
                        continue

                payload = self._coverage_payload(snapshot, merged)
                if payload["episode_coverage"] >= 0.8:
                    await self.db.execute(
                        update(Briefing)
                        .where(Briefing.id == snapshot["id"])
                        .values(
                            listened=True,
                            listened_at=func.coalesce(Briefing.listened_at, datetime.utcnow()),
                        )
                    )
                await self.db.commit()
                return payload
            except (IntegrityError, OperationalError):
                await self.db.rollback()
                if attempt + 1 == self._MAX_WRITE_ATTEMPTS:
                    raise
                await asyncio.sleep(0.01 * (attempt + 1))

        raise RuntimeError("Could not persist listening coverage")

    async def coverage(self, briefing: Briefing) -> dict[str, Any]:
        """Return persisted coverage without consulting legacy listened/resume fields."""
        snapshot = self._snapshot(briefing)
        ranges = await self.db.scalar(
            select(ListeningRecord.ranges).where(
                ListeningRecord.briefing_id == snapshot["id"]
            )
        )
        valid = self._valid_stored_ranges(ranges, snapshot["duration"])
        if not valid:
            return {"ranges": [], "chapter_coverage": {}, "episode_coverage": 0.0}
        return self._coverage_payload(snapshot, merge_ranges(valid))

    @staticmethod
    def _snapshot(briefing: Briefing) -> dict[str, Any]:
        duration = briefing.duration_seconds
        return {
            "id": briefing.id,
            "duration": float(duration) if duration is not None else None,
            "chapters": (briefing.extra_data or {}).get("chapters", []),
        }

    @staticmethod
    def _validate_ranges(ranges: list[list[float]], duration: float | None) -> list[Range]:
        if duration is None or not math.isfinite(duration) or duration <= 0:
            raise ValueError("Briefing duration must be a positive finite number")
        validated: list[Range] = []
        for interval in ranges:
            if not isinstance(interval, (list, tuple)) or len(interval) != 2:
                raise ValueError("Each listening range must contain a start and end")
            start, end = float(interval[0]), float(interval[1])
            if not math.isfinite(start) or not math.isfinite(end):
                raise ValueError("Listening ranges must be finite")
            if start < 0 or end <= start:
                raise ValueError("Listening range end must be greater than its non-negative start")
            if end > duration:
                raise ValueError("Listening range exceeds briefing duration")
            validated.append([start, end])
        return validated

    @staticmethod
    def _valid_stored_ranges(ranges: Any, duration: float | None) -> list[Range]:
        if not isinstance(ranges, list) or duration is None or not math.isfinite(duration) or duration <= 0:
            return []
        valid: list[Range] = []
        for interval in ranges:
            try:
                if not isinstance(interval, (list, tuple)) or len(interval) != 2:
                    continue
                start, end = float(interval[0]), float(interval[1])
                if math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= duration:
                    valid.append([start, end])
            except (TypeError, ValueError):
                continue
        return valid

    @classmethod
    def _coverage_payload(cls, snapshot: dict[str, Any], ranges: list[Range]) -> dict[str, Any]:
        duration = snapshot["duration"]
        if duration is None or duration <= 0:
            return {"ranges": [], "chapter_coverage": {}, "episode_coverage": 0.0}

        episode_seconds = sum(end - start for start, end in ranges)
        chapter_coverage: dict[str, float] = {}
        chapters = snapshot["chapters"] if isinstance(snapshot["chapters"], list) else []

        for index, chapter in enumerate(chapters):
            if not isinstance(chapter, dict):
                continue
            try:
                start = float(chapter["start_time"])
                raw_end = chapter.get("end_time")
                if raw_end is None and index + 1 < len(chapters):
                    next_chapter = chapters[index + 1]
                    raw_end = next_chapter.get("start_time") if isinstance(next_chapter, dict) else None
                end = float(raw_end) if raw_end is not None else duration
            except (KeyError, TypeError, ValueError):
                continue
            if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start or end > duration:
                continue
            heard = sum(max(0.0, min(range_end, end) - max(range_start, start)) for range_start, range_end in ranges)
            chapter_coverage[str(index)] = round(min(1.0, heard / (end - start)), 6)

        return {
            "ranges": ranges,
            "chapter_coverage": chapter_coverage,
            "episode_coverage": round(min(1.0, episode_seconds / duration), 6),
        }
