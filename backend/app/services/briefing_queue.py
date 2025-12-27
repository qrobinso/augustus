"""Queue service for managing scheduled briefing generation queue."""

import asyncio
from typing import Optional
from datetime import datetime
from dataclasses import dataclass


@dataclass
class QueuedBriefing:
    """Represents a scheduled briefing waiting to be generated."""
    schedule_id: str
    user_id: str
    queued_at: datetime
    db_url: str


class BriefingQueue:
    """In-memory queue for scheduled briefings."""
    
    def __init__(self):
        self._queue: list[QueuedBriefing] = []
        self._processing = False
        self._lock = asyncio.Lock()
    
    async def enqueue(
        self,
        schedule_id: str,
        user_id: str,
        db_url: str,
    ):
        """Add a scheduled briefing to the queue.
        
        Args:
            schedule_id: The scheduled briefing ID
            user_id: The user ID
            db_url: Database URL for creating sessions
        """
        async with self._lock:
            # Check if already in queue
            if any(q.schedule_id == schedule_id for q in self._queue):
                print(f"[BriefingQueue] Schedule {schedule_id} already in queue, skipping")
                return
            
            queued = QueuedBriefing(
                schedule_id=schedule_id,
                user_id=user_id,
                queued_at=datetime.utcnow(),
                db_url=db_url,
            )
            self._queue.append(queued)
            print(f"[BriefingQueue] Enqueued schedule {schedule_id} (queue size: {len(self._queue)})")
    
    async def dequeue(self) -> Optional[QueuedBriefing]:
        """Get the next briefing from the queue.
        
        Returns:
            The next queued briefing, or None if queue is empty
        """
        async with self._lock:
            if self._queue:
                return self._queue.pop(0)
            return None
    
    async def peek(self) -> Optional[QueuedBriefing]:
        """Peek at the next briefing without removing it.
        
        Returns:
            The next queued briefing, or None if queue is empty
        """
        async with self._lock:
            if self._queue:
                return self._queue[0]
            return None
    
    async def remove(self, schedule_id: str) -> bool:
        """Remove a specific schedule from the queue.
        
        Args:
            schedule_id: The schedule ID to remove
            
        Returns:
            True if removed, False if not found
        """
        async with self._lock:
            initial_size = len(self._queue)
            self._queue = [q for q in self._queue if q.schedule_id != schedule_id]
            removed = len(self._queue) < initial_size
            if removed:
                print(f"[BriefingQueue] Removed schedule {schedule_id} from queue")
            return removed
    
    async def size(self) -> int:
        """Get the current queue size."""
        async with self._lock:
            return len(self._queue)
    
    async def is_processing(self) -> bool:
        """Check if queue is currently processing."""
        return self._processing
    
    async def set_processing(self, value: bool):
        """Set the processing flag."""
        async with self._lock:
            self._processing = value
    
    async def clear(self):
        """Clear the entire queue."""
        async with self._lock:
            self._queue.clear()
            print("[BriefingQueue] Queue cleared")


# Global queue instance
briefing_queue = BriefingQueue()













