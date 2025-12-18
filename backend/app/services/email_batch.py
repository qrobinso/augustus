"""Email batching service for combining multiple briefing notifications."""

from datetime import datetime, timedelta
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.briefing import Briefing
from app.models.scheduled_briefing import ScheduledBriefing
from app.services.email import send_batched_briefings_email
from app.utils.timezone import utc_now


async def find_briefings_for_batching(
    db: AsyncSession,
    user_id: str,
    reference_time: datetime,
    window_minutes: int = 15,
) -> List[tuple[Briefing, ScheduledBriefing]]:
    """Find briefings that should be batched together for email notification.
    
    Args:
        db: Database session
        user_id: User ID to find briefings for
        reference_time: Reference time to check window from
        window_minutes: Time window in minutes (default 15)
    
    Returns:
        List of tuples (briefing, schedule) for briefings that should be batched
    """
    # Calculate time window
    window_start = reference_time - timedelta(minutes=window_minutes)
    
    # Find all completed briefings for this user within the window
    result = await db.execute(
        select(Briefing)
        .where(Briefing.user_id == user_id)
        .where(Briefing.status == 'completed')
        .where(Briefing.generated_at.isnot(None))
        .where(Briefing.generated_at >= window_start)
        .where(Briefing.generated_at <= reference_time)
        .order_by(Briefing.generated_at.asc())
    )
    recent_briefings = result.scalars().all()
    
    if not recent_briefings:
        return []
    
    # Get all scheduled briefings for this user that have email notifications
    schedules_result = await db.execute(
        select(ScheduledBriefing)
        .where(ScheduledBriefing.user_id == user_id)
        .where(ScheduledBriefing.is_active == True)
    )
    all_schedules = schedules_result.scalars().all()
    
    # Filter to only schedules with email notifications (SQLite doesn't support JSON contains)
    email_schedules = [s for s in all_schedules if 'email' in (s.notification_methods or [])]
    
    if not email_schedules:
        return []
    
    # Match briefings to schedules based on timing and topic_ids
    batched_items = []
    for briefing in recent_briefings:
        if not briefing.generated_at:
            continue
            
        briefing_topic_ids = set(briefing.extra_data.get('topic_ids', []))
        
        # Find matching schedule by checking if briefing was generated around schedule's last_generated_at
        for schedule in email_schedules:
            if not schedule.last_generated_at:
                continue
                
            # Check if briefing was generated within 5 minutes of schedule's last_generated_at
            time_diff = abs((briefing.generated_at - schedule.last_generated_at).total_seconds())
            if time_diff < 300:  # Within 5 minutes
                schedule_topic_ids = set(schedule.topic_ids or [])
                
                # Match if topic_ids match (or if both are empty for "all topics")
                topic_match = (
                    briefing_topic_ids == schedule_topic_ids or
                    (not briefing_topic_ids and not schedule_topic_ids)
                )
                
                if topic_match:
                    batched_items.append((briefing, schedule))
                    break
    
    return batched_items



