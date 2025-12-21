"""Simple in-memory tracker for emailed briefings to prevent duplicates."""

import asyncio
from datetime import datetime, timedelta
from typing import Set


class EmailTracker:
    """Tracks which briefings have been emailed to prevent duplicates."""
    
    def __init__(self):
        self._emailed_briefings: Set[str] = set()
        self._emailed_windows: dict[str, datetime] = {}  # user_id -> last_email_time
        self._lock = asyncio.Lock()
    
    async def mark_emailed(self, briefing_ids: Set[str], user_id: str):
        """Mark briefings as having been emailed.
        
        Args:
            briefing_ids: Set of briefing IDs that were emailed
            user_id: User ID
        """
        async with self._lock:
            self._emailed_briefings.update(briefing_ids)
            self._emailed_windows[user_id] = datetime.utcnow()
    
    async def has_been_emailed(self, briefing_id: str) -> bool:
        """Check if a briefing has already been emailed.
        
        Args:
            briefing_id: Briefing ID to check
            
        Returns:
            True if already emailed, False otherwise
        """
        async with self._lock:
            return briefing_id in self._emailed_briefings
    
    async def get_emailed_briefings(self) -> Set[str]:
        """Get all briefing IDs that have been emailed."""
        async with self._lock:
            return self._emailed_briefings.copy()
    
    async def cleanup_old_entries(self, hours: int = 24):
        """Remove old entries to prevent memory growth.
        
        Args:
            hours: Remove entries older than this many hours
        """
        async with self._lock:
            # For simplicity, just clear entries older than the window
            # In practice, we'd track timestamps, but for now just clear periodically
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            # Clear old window entries
            self._emailed_windows = {
                k: v for k, v in self._emailed_windows.items()
                if v > cutoff
            }
            # Note: We don't track individual briefing timestamps, so we can't clean them up precisely
            # This is fine for short-term tracking


# Global tracker instance
email_tracker = EmailTracker()






