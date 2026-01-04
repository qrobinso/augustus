"""ScheduledBriefings API router."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.models.profile import Profile
from app.routers.auth import get_current_user
from app.routers.profiles import get_current_profile
from app.schemas.scheduled_briefing import (
    ScheduledBriefingCreate,
    ScheduledBriefingUpdate,
    ScheduledBriefingResponse,
    ScheduledBriefingListResponse,
)
from app.services.scheduled_briefing import ScheduledBriefingService

router = APIRouter()


@router.get("", response_model=ScheduledBriefingListResponse)
async def list_scheduled_briefings(
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """List all scheduled briefings for the current profile."""
    service = ScheduledBriefingService(db)
    scheduled_briefings, total = await service.list_scheduled_briefings(
        user.id, profile_id=profile.id, limit=limit, offset=offset
    )
    
    return ScheduledBriefingListResponse(
        scheduled_briefings=[
            ScheduledBriefingResponse.model_validate(sb) for sb in scheduled_briefings
        ],
        total=total,
    )


@router.post("", response_model=ScheduledBriefingResponse, status_code=status.HTTP_201_CREATED)
async def create_scheduled_briefing(
    request: ScheduledBriefingCreate,
    user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """Create a new scheduled briefing."""
    service = ScheduledBriefingService(db)
    
    scheduled_briefing = await service.create_scheduled_briefing(
        user_id=user.id,
        profile_id=profile.id,
        name=request.name,
        topic_ids=request.topic_ids,
        schedule_time=request.schedule_time,
        schedule_days=request.schedule_days,
        notification_methods=request.notification_methods,
        email_recipients=request.email_recipients,
        webhook_url=request.webhook_url,
        is_active=request.is_active,
        max_duration_minutes=request.max_duration_minutes,
        resend_api_key=request.resend_api_key,
    )
    
    return ScheduledBriefingResponse.model_validate(scheduled_briefing)


@router.get("/{schedule_id}", response_model=ScheduledBriefingResponse)
async def get_scheduled_briefing(
    schedule_id: str,
    user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific scheduled briefing by ID."""
    service = ScheduledBriefingService(db)
    scheduled_briefing = await service.get_scheduled_briefing(schedule_id)
    
    if not scheduled_briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled briefing not found",
        )
    
    if scheduled_briefing.user_id != user.id or scheduled_briefing.profile_id != profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    return ScheduledBriefingResponse.model_validate(scheduled_briefing)


@router.put("/{schedule_id}", response_model=ScheduledBriefingResponse)
async def update_scheduled_briefing(
    schedule_id: str,
    update: ScheduledBriefingUpdate,
    user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """Update a scheduled briefing."""
    service = ScheduledBriefingService(db)
    scheduled_briefing = await service.get_scheduled_briefing(schedule_id)
    
    if not scheduled_briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled briefing not found",
        )
    
    if scheduled_briefing.user_id != user.id or scheduled_briefing.profile_id != profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    # Build update dict from non-None fields
    updates = {}
    for field, value in update.model_dump(exclude_unset=True).items():
        if value is not None:
            updates[field] = value
    
    updated = await service.update_scheduled_briefing(schedule_id, **updates)
    
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update scheduled briefing",
        )
    
    return ScheduledBriefingResponse.model_validate(updated)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scheduled_briefing(
    schedule_id: str,
    user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """Delete a scheduled briefing."""
    service = ScheduledBriefingService(db)
    scheduled_briefing = await service.get_scheduled_briefing(schedule_id)
    
    if not scheduled_briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled briefing not found",
        )
    
    if scheduled_briefing.user_id != user.id or scheduled_briefing.profile_id != profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    await service.delete_scheduled_briefing(schedule_id)


@router.patch("/{schedule_id}/toggle", response_model=ScheduledBriefingResponse)
async def toggle_scheduled_briefing(
    schedule_id: str,
    user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """Toggle the active status of a scheduled briefing."""
    service = ScheduledBriefingService(db)
    scheduled_briefing = await service.get_scheduled_briefing(schedule_id)
    
    if not scheduled_briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled briefing not found",
        )
    
    if scheduled_briefing.user_id != user.id or scheduled_briefing.profile_id != profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    toggled = await service.toggle_active(schedule_id)
    
    if not toggled:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle scheduled briefing",
        )
    
    return ScheduledBriefingResponse.model_validate(toggled)


@router.post("/{schedule_id}/trigger")
async def trigger_scheduled_briefing(
    schedule_id: str,
    user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger a scheduled briefing generation and notifications.
    
    This will:
    - Generate a briefing using the schedule's configuration
    - Send email/webhook notifications if configured
    - Update the schedule's last_generated_at timestamp
    """
    settings = get_settings()
    service = ScheduledBriefingService(db)
    scheduled_briefing = await service.get_scheduled_briefing(schedule_id)
    
    if not scheduled_briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled briefing not found",
        )
    
    if scheduled_briefing.user_id != user.id or scheduled_briefing.profile_id != profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    # Trigger the briefing generation
    briefing = await service.trigger_scheduled_briefing(
        schedule_id=schedule_id,
        db_url=settings.database_url,
    )
    
    if not briefing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to trigger briefing. A briefing may already be in progress.",
        )
    
    # Return the briefing ID so the frontend can track it
    from app.schemas.briefing import BriefingResponse
    return BriefingResponse.model_validate(briefing)
