"""ScheduledBriefing service for managing scheduled daily briefings."""

import uuid
from datetime import datetime, date, time
from typing import Optional, List
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scheduled_briefing import ScheduledBriefing
from app.models.briefing import Briefing
from app.utils.timezone import get_user_timezone, to_local, utc_now
from app.services.briefing import BriefingService
from app.services.email import send_briefing_email
import httpx


class ScheduledBriefingService:
    """Service for managing scheduled daily briefings."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_scheduled_briefing(
        self,
        user_id: str,
        name: str,
        topic_ids: List[str],
        schedule_time: str,
        schedule_days: List[int],
        notification_methods: List[str],
        email_recipients: List[str] = None,
        webhook_url: Optional[str] = None,
        is_active: bool = True,
        max_duration_minutes: int = 5,
        resend_api_key: Optional[str] = None,
    ) -> ScheduledBriefing:
        """Create a new scheduled briefing."""
        scheduled_briefing = ScheduledBriefing(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            topic_ids=topic_ids or [],
            schedule_time=schedule_time,
            schedule_days=schedule_days,
            notification_methods=notification_methods,
            email_recipients=email_recipients or [],
            webhook_url=webhook_url,
            is_active=is_active,
            max_duration_minutes=max_duration_minutes,
            resend_api_key=resend_api_key,
        )
        
        self.db.add(scheduled_briefing)
        await self.db.commit()
        await self.db.refresh(scheduled_briefing)
        
        return scheduled_briefing
    
    async def get_scheduled_briefing(self, schedule_id: str) -> Optional[ScheduledBriefing]:
        """Get a scheduled briefing by ID."""
        result = await self.db.execute(
            select(ScheduledBriefing).where(ScheduledBriefing.id == schedule_id)
        )
        return result.scalar_one_or_none()
    
    async def list_scheduled_briefings(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[ScheduledBriefing], int]:
        """List scheduled briefings for a user."""
        # Get total count
        count_result = await self.db.execute(
            select(ScheduledBriefing).where(ScheduledBriefing.user_id == user_id)
        )
        total = len(count_result.scalars().all())
        
        # Get paginated results
        result = await self.db.execute(
            select(ScheduledBriefing)
            .where(ScheduledBriefing.user_id == user_id)
            .order_by(ScheduledBriefing.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        scheduled_briefings = result.scalars().all()
        
        return list(scheduled_briefings), total
    
    async def update_scheduled_briefing(
        self,
        schedule_id: str,
        **updates,
    ) -> Optional[ScheduledBriefing]:
        """Update a scheduled briefing."""
        scheduled_briefing = await self.get_scheduled_briefing(schedule_id)
        if not scheduled_briefing:
            return None
        
        # Update fields
        for key, value in updates.items():
            if value is not None and hasattr(scheduled_briefing, key):
                setattr(scheduled_briefing, key, value)
        
        scheduled_briefing.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(scheduled_briefing)
        
        return scheduled_briefing
    
    async def delete_scheduled_briefing(self, schedule_id: str) -> bool:
        """Delete a scheduled briefing."""
        scheduled_briefing = await self.get_scheduled_briefing(schedule_id)
        if not scheduled_briefing:
            return False
        
        await self.db.delete(scheduled_briefing)
        await self.db.commit()
        
        return True
    
    async def toggle_active(self, schedule_id: str) -> Optional[ScheduledBriefing]:
        """Toggle the active status of a scheduled briefing."""
        scheduled_briefing = await self.get_scheduled_briefing(schedule_id)
        if not scheduled_briefing:
            return None
        
        scheduled_briefing.is_active = not scheduled_briefing.is_active
        scheduled_briefing.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(scheduled_briefing)
        
        return scheduled_briefing
    
    async def get_active_schedules_for_user(self, user_id: str) -> List[ScheduledBriefing]:
        """Get all active scheduled briefings for a user."""
        result = await self.db.execute(
            select(ScheduledBriefing)
            .where(ScheduledBriefing.user_id == user_id)
            .where(ScheduledBriefing.is_active == True)
        )
        return list(result.scalars().all())
    
    async def get_schedules_due_now(self, user_timezone: str) -> List[ScheduledBriefing]:
        """Get all active schedules that should run now (timezone-aware).
        
        Args:
            user_timezone: IANA timezone name (e.g., 'America/New_York')
        
        Returns:
            List of scheduled briefings that should run now
        """
        try:
            tz = ZoneInfo(user_timezone)
        except Exception:
            tz = ZoneInfo("UTC")
        
        now = datetime.now(tz)
        current_time = now.time()
        current_weekday = now.weekday()  # 0=Monday, 6=Sunday
        
        # Get all active schedules
        result = await self.db.execute(
            select(ScheduledBriefing).where(ScheduledBriefing.is_active == True)
        )
        all_schedules = result.scalars().all()
        
        due_schedules = []
        
        for schedule in all_schedules:
            # Check if today is in schedule_days
            if current_weekday not in schedule.schedule_days:
                continue
            
            # Parse schedule_time (HH:MM format)
            try:
                hour, minute = map(int, schedule.schedule_time.split(':'))
                schedule_time_obj = time(hour, minute)
            except Exception:
                continue
            
            # Check if current time matches schedule time (within 1-minute window)
            time_diff = abs(
                (current_time.hour * 60 + current_time.minute) -
                (schedule_time_obj.hour * 60 + schedule_time_obj.minute)
            )
            
            if time_diff <= 1:  # Within 1 minute
                # Check if we already generated today (prevent duplicates)
                if schedule.last_generated_at:
                    last_generated = schedule.last_generated_at
                    if isinstance(last_generated, datetime):
                        # Convert to user's timezone for comparison
                        last_generated_local = to_local(last_generated, tz)
                        if last_generated_local.date() == now.date():
                            # Already generated today, skip
                            continue
                
                due_schedules.append(schedule)
        
        return due_schedules
    
    async def trigger_scheduled_briefing(
        self,
        schedule_id: str,
        db_url: str,
    ) -> Optional[Briefing]:
        """Trigger briefing generation from a scheduled briefing.
        
        Args:
            schedule_id: The scheduled briefing ID
            db_url: Database URL for creating a new session
        
        Returns:
            The generated briefing if successful, None otherwise
        """
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        
        # Get the schedule
        schedule = await self.get_scheduled_briefing(schedule_id)
        if not schedule:
            print(f"[ScheduledBriefing] Schedule {schedule_id} not found")
            return None
        
        if not schedule.is_active:
            print(f"[ScheduledBriefing] Schedule {schedule_id} is not active")
            return None
        
        # Create a new database session for the briefing generation
        engine = create_async_engine(db_url)
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        
        try:
            async with async_session() as db:
                briefing_service = BriefingService(db)
                
                # Check if there's already a briefing in progress for this user
                in_progress = await briefing_service.has_briefing_in_progress(schedule.user_id)
                if in_progress:
                    print(f"[ScheduledBriefing] Briefing already in progress for user {schedule.user_id}, skipping")
                    # Re-queue this schedule to be processed later
                    from app.services.briefing_queue import briefing_queue
                    await briefing_queue.enqueue(
                        schedule_id=schedule.id,
                        user_id=schedule.user_id,
                        db_url=db_url,
                    )
                    return None
                
                # Create briefing record
                briefing = await briefing_service.create_briefing(
                    user_id=schedule.user_id,
                    topic_ids=schedule.topic_ids if schedule.topic_ids else None,
                    max_duration_minutes=schedule.max_duration_minutes,
                )
                
                # Set cast_id from scheduled briefing if specified
                if schedule.cast_id:
                    briefing.cast_id = schedule.cast_id
                    await db.commit()
                    await db.refresh(briefing)
                
                # Update schedule's last_generated_at
                schedule.last_generated_at = utc_now()
                await self.db.commit()
                
                # Generate briefing synchronously (queue ensures only one at a time)
                try:
                    await briefing_service.generate_briefing(
                        briefing_id=briefing.id,
                        topic_ids=schedule.topic_ids if schedule.topic_ids else None,
                        max_duration_minutes=schedule.max_duration_minutes,
                    )
                    
                    # Refresh briefing to get updated status
                    await db.refresh(briefing)
                    
                    # Send notifications if briefing completed successfully
                    if briefing.status == 'completed':
                        # Use batched email notifications if email is enabled
                        if 'email' in schedule.notification_methods:
                            # Schedule batched email notification after a delay
                            # This allows other briefings to complete and be batched together
                            import asyncio
                            asyncio.create_task(
                                self._send_batched_email_after_delay(
                                    db=db,
                                    db_url=db_url,
                                    user_id=schedule.user_id,
                                    current_briefing_id=briefing.id,
                                    window_minutes=15,
                                )
                            )
                        else:
                            # For non-email notifications, send immediately
                            await self._send_notifications(schedule, briefing)
                    
                    return briefing
                except Exception as e:
                    print(f"[ScheduledBriefing] Failed to generate briefing: {e}")
                    return None
        finally:
            await engine.dispose()
    
    async def _send_batched_email_after_delay(
        self,
        db: AsyncSession,
        db_url: str,
        user_id: str,
        current_briefing_id: str,
        window_minutes: int = 15,
    ):
        """Send batched email notification after a delay to allow other briefings to complete.
        
        Args:
            db: Current database session (will create new one after delay)
            db_url: Database URL
            user_id: User ID
            current_briefing_id: The briefing that just completed
            window_minutes: Time window for batching
        """
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        
        # Wait 90 seconds to allow other briefings to complete
        import asyncio
        await asyncio.sleep(90)
        
        engine = create_async_engine(db_url)
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        
        try:
            async with async_session() as new_db:
                from app.services.email_batch import find_briefings_for_batching
                from app.services.email import send_batched_briefings_email
                from app.services.email_tracker import email_tracker
                from app.utils.timezone import utc_now
                
                # Check if we've already sent an email for briefings in this time window
                # (prevent duplicate emails if multiple briefings complete)
                if await email_tracker.has_been_emailed(current_briefing_id):
                    print(f"[ScheduledBriefing] Briefing {current_briefing_id} already emailed, skipping")
                    return
                
                # Find all briefings that should be batched together
                batched_items = await find_briefings_for_batching(
                    db=new_db,
                    user_id=user_id,
                    reference_time=utc_now(),
                    window_minutes=window_minutes,
                )
                
                if not batched_items:
                    print(f"[ScheduledBriefing] No briefings found for batching")
                    return
                
                # Filter out briefings that have already been emailed
                briefings_to_email = []
                schedules_to_email = []
                for briefing, schedule in batched_items:
                    if not await email_tracker.has_been_emailed(briefing.id):
                        briefings_to_email.append(briefing)
                        schedules_to_email.append(schedule)
                
                if not briefings_to_email:
                    print(f"[ScheduledBriefing] All briefings already emailed, skipping")
                    return
                
                # Group by email recipients (schedules might have different recipients)
                recipient_groups = {}
                for briefing, schedule in zip(briefings_to_email, schedules_to_email):
                    if not schedule.email_recipients:
                        continue
                    recipients_key = tuple(sorted(schedule.email_recipients))
                    if recipients_key not in recipient_groups:
                        recipient_groups[recipients_key] = []
                    recipient_groups[recipients_key].append((briefing, schedule))
                
                # Send one email per recipient group
                for recipients, items in recipient_groups.items():
                    if not recipients:
                        continue
                    
                    briefings = [item[0] for item in items]
                    briefing_ids = {b.id for b in briefings}
                    # Use the first schedule's resend key (or global)
                    first_schedule = items[0][1]
                    
                    # Send batched email
                    success = await send_batched_briefings_email(
                        briefings=briefings,
                        recipients=list(recipients),
                        api_key=first_schedule.resend_api_key,
                    )
                    
                    if success:
                        # Mark briefings as emailed
                        await email_tracker.mark_emailed(briefing_ids, user_id)
                        print(f"[ScheduledBriefing] Sent batched email with {len(briefings)} briefings to {len(recipients)} recipients")
        except Exception as e:
            print(f"[ScheduledBriefing] Error sending batched email: {e}")
        finally:
            await engine.dispose()
    
    async def _send_notifications(
        self,
        schedule: ScheduledBriefing,
        briefing: Briefing,
    ):
        """Send notifications for a completed briefing (non-email notifications only).
        
        Note: Email notifications are handled by the batched email service.
        
        Args:
            schedule: The scheduled briefing configuration
            briefing: The completed briefing
        """
        # Webhook notifications
        if 'webhook' in schedule.notification_methods and schedule.webhook_url:
            try:
                payload = {
                    "briefing_id": briefing.id,
                    "title": briefing.title,
                    "status": briefing.status,
                    "audio_url": briefing.audio_url,
                    "duration_seconds": briefing.duration_seconds,
                    "created_at": briefing.created_at.isoformat() if briefing.created_at else None,
                    "transcript_preview": briefing.transcript[:500] if briefing.transcript else None,
                }
                
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        schedule.webhook_url,
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    )
                    response.raise_for_status()
                    print(f"[ScheduledBriefing] Successfully sent webhook notification")
            except Exception as e:
                print(f"[ScheduledBriefing] Failed to send webhook notification: {e}")
