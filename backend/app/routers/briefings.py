"""Briefings API router."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.profile import Profile
from app.routers.auth import get_current_user
from app.routers.profiles import get_current_profile
from app.schemas.briefing import (
    BriefingGenerateRequest,
    BriefingResponse,
    BriefingListResponse,
    BriefingListenedUpdate,
    BriefingPlaybackPositionUpdate,
    BriefingFavoriteUpdate,
)
from app.services.briefing import BriefingService

router = APIRouter()


async def generate_briefing_task(
    briefing_id: str,
    topic_ids: Optional[list[str]],
    max_duration: int,
    db_url: str,
    profile_name: Optional[str] = None,
):
    """Background task to generate briefing."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.services.briefing import BriefingService, BriefingCancelledException, BriefingTimeoutException
    from app.services.briefing_queue import briefing_queue
    
    engine = create_async_engine(db_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    # Set global generating flag
    await briefing_queue.set_global_generating(True)
    
    async with async_session() as db:
        service = BriefingService(db)
        try:
            await service.generate_briefing(
                briefing_id=briefing_id,
                topic_ids=topic_ids,
                max_duration_minutes=max_duration,
                profile_name=profile_name,
            )
        except BriefingCancelledException:
            # Briefing was cancelled - this is expected, just log it
            print(f"[Briefing] Briefing {briefing_id} was cancelled by user")
        except BriefingTimeoutException:
            # Briefing timed out - already handled in generate_briefing
            print(f"[Briefing] Briefing {briefing_id} exceeded timeout")
        except Exception as e:
            print(f"[Briefing] Briefing generation failed: {e}")
        finally:
            await engine.dispose()
            # Clear global generating flag
            await briefing_queue.set_global_generating(False)


@router.get("", response_model=BriefingListResponse)
async def list_briefings(
    limit: int = 10,
    offset: int = 0,
    listened: Optional[bool] = None,
    cast_id: Optional[str] = None,
    topic_ids: Optional[list[str]] = Query(None),
    favorite: Optional[bool] = None,
    user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """List all briefings for the current profile."""
    service = BriefingService(db)
    briefings, total = await service.list_briefings(
        user.id,
        profile_id=profile.id,
        limit=limit, 
        offset=offset, 
        listened=listened,
        cast_id=cast_id,
        topic_ids=topic_ids,
        favorite=favorite,
    )
    
    return BriefingListResponse(
        briefings=[BriefingResponse.model_validate(b) for b in briefings],
        total=total,
    )


@router.post("/generate", response_model=BriefingResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_briefing(
    request: BriefingGenerateRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """Trigger generation of a new daily briefing.
    
    If another briefing is currently being generated globally, this briefing will be
    queued and processed when the current generation completes.
    """
    from app.config import get_settings
    from app.services.briefing_queue import briefing_queue
    
    settings = get_settings()
    service = BriefingService(db)
    
    # Check if this specific profile already has a briefing in progress or queued
    in_progress = await service.has_briefing_in_progress(user.id, profile.id)
    if in_progress:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You already have a briefing being generated or queued. Please wait for it to complete.",
        )
    
    # Use configured duration if not specified in request
    duration = request.max_duration_minutes or settings.briefing_duration_minutes
    
    # Check if any briefing is currently being generated globally
    is_global_generating = await briefing_queue.is_global_generating()
    
    # Also check database for any briefings with "pending" or "generating" status
    any_active = await service.has_any_active_briefing()
    
    should_queue = is_global_generating or any_active
    
    # Create briefing record - queued if another is generating, pending otherwise
    initial_status = "queued" if should_queue else "pending"
    briefing = await service.create_briefing(
        user_id=user.id,
        profile_id=profile.id,
        topic_ids=request.topic_ids,
        max_duration_minutes=duration,
        initial_status=initial_status,
    )
    
    # Set cast_id if provided
    if request.cast_id:
        briefing.cast_id = request.cast_id
        await db.commit()
        await db.refresh(briefing)
    
    # Store profile name in extra_data for later use by queue processor
    if not briefing.extra_data:
        briefing.extra_data = {}
    briefing.extra_data["profile_name"] = profile.name
    briefing.extra_data["max_duration"] = duration
    await db.commit()
    await db.refresh(briefing)
    
    # If not queued, start generation immediately
    if initial_status == "pending":
        background_tasks.add_task(
            generate_briefing_task,
            briefing.id,
            request.topic_ids,
            duration,
            settings.database_url,
            profile.name,
        )
        print(f"[Briefing] Started immediate generation for {briefing.id}")
    else:
        print(f"[Briefing] Queued briefing {briefing.id} (another generation in progress)")
    
    return BriefingResponse.model_validate(briefing)


@router.get("/{briefing_id}", response_model=BriefingResponse)
async def get_briefing(
    briefing_id: str,
    user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific briefing by ID."""
    service = BriefingService(db)
    briefing = await service.get_briefing(briefing_id)
    
    if not briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Briefing not found",
        )
    
    if briefing.user_id != user.id or briefing.profile_id != profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    return BriefingResponse.model_validate(briefing)


@router.delete("/{briefing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_briefing(
    briefing_id: str,
    user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """Delete a briefing."""
    service = BriefingService(db)
    briefing = await service.get_briefing(briefing_id)
    
    if not briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Briefing not found",
        )
    
    if briefing.user_id != user.id or briefing.profile_id != profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    await service.delete_briefing(briefing_id)


@router.patch("/{briefing_id}/listened", response_model=BriefingResponse)
async def update_listened_status(
    briefing_id: str,
    update: BriefingListenedUpdate,
    user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """Update the listened status of a briefing."""
    service = BriefingService(db)
    briefing = await service.get_briefing(briefing_id)
    
    if not briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Briefing not found",
        )
    
    if briefing.user_id != user.id or briefing.profile_id != profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    updated = await service.update_listened_status(briefing_id, update.listened)
    return BriefingResponse.model_validate(updated)


@router.patch("/{briefing_id}/playback-position", response_model=BriefingResponse)
async def update_playback_position(
    briefing_id: str,
    update: BriefingPlaybackPositionUpdate,
    user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """Update the playback position of a briefing (for resume functionality)."""
    service = BriefingService(db)
    briefing = await service.get_briefing(briefing_id)
    
    if not briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Briefing not found",
        )
    
    if briefing.user_id != user.id or briefing.profile_id != profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    updated = await service.update_playback_position(briefing_id, update.position)
    return BriefingResponse.model_validate(updated)


@router.patch("/{briefing_id}/favorite", response_model=BriefingResponse)
async def update_favorite_status(
    briefing_id: str,
    update: BriefingFavoriteUpdate,
    user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """Update the favorite status of a briefing."""
    service = BriefingService(db)
    briefing = await service.get_briefing(briefing_id)
    
    if not briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Briefing not found",
        )
    
    if briefing.user_id != user.id or briefing.profile_id != profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    updated = await service.update_favorite_status(briefing_id, update.favorite)
    return BriefingResponse.model_validate(updated)


@router.post("/{briefing_id}/cancel", response_model=BriefingResponse)
async def cancel_briefing(
    briefing_id: str,
    user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a briefing that is pending, generating, or queued."""
    service = BriefingService(db)
    briefing = await service.get_briefing(briefing_id)
    
    if not briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Briefing not found",
        )
    
    if briefing.user_id != user.id or briefing.profile_id != profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    if briefing.status not in ["pending", "generating"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Briefing cannot be cancelled (not in progress)",
        )
    
    cancelled = await service.cancel_briefing(briefing_id)
    return BriefingResponse.model_validate(cancelled)

