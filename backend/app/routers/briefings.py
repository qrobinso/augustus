"""Briefings API router."""

import asyncio
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.profile import Profile
from app.models.cast import Cast
from app.routers.auth import get_current_user
from app.routers.profiles import get_current_profile
from app.schemas.briefing import (
    BriefingGenerateRequest,
    BreakoutGenerateRequest,
    BriefingResponse,
    BriefingListResponse,
    BriefingListenedUpdate,
    BriefingPlaybackPositionUpdate,
    BriefingFavoriteUpdate,
    ListeningRangesRequest,
    ListeningCoverageResponse,
)
from app.services.briefing import BriefingService
from app.services.listening import ListeningService
from app.services.generation_queue import process_generation_queue

router = APIRouter()

# Keep validation and row creation together for concurrent on-demand requests.
_generation_request_lock = asyncio.Lock()


@router.get("", response_model=BriefingListResponse)
async def list_briefings(
    limit: int = 10,
    offset: int = 0,
    listened: Optional[bool] = None,
    cast_id: Optional[str] = None,
    topic_ids: Optional[list[str]] = Query(None),
    favorite: Optional[bool] = None,
    q: Optional[str] = None,
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
        q=q,
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
    """Persist a daily briefing in the shared generation queue."""
    async with _generation_request_lock:
        from app.config import get_settings

        service = BriefingService(db)
        if request.cast_id:
            cast = await db.scalar(select(Cast).where(
                Cast.id == request.cast_id,
                Cast.user_id == user.id,
                Cast.profile_id == profile.id,
            ))
            if cast is None:
                raise HTTPException(404, "Cast not found in this profile")

        duration = request.max_duration_minutes or get_settings().briefing_duration_minutes
        briefing = await service.create_briefing(
            user_id=user.id,
            profile_id=profile.id,
            topic_ids=request.topic_ids,
            max_duration_minutes=duration,
            initial_status="queued",
            cast_id=request.cast_id,
            profile_name=profile.name,
        )
        background_tasks.add_task(process_generation_queue)
        return BriefingResponse.model_validate(briefing)


@router.post("/breakout", response_model=BriefingResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_breakout_podcast(
    request: BreakoutGenerateRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """Queue one focused episode; the source episode and playback are unchanged."""
    from app.models.briefing import Briefing
    from app.services.breakout_request import resolve_breakout_request

    if getattr(user, "current_api_key_id", None):
        allowed = getattr(user, "current_api_key_tools", None)
        if allowed is not None and "generate_breakout_podcast" not in allowed:
            raise HTTPException(403, "generate_breakout_podcast is disabled for this API key")

    async with _generation_request_lock:
        metadata, topic_ids, cast_id = await resolve_breakout_request(db, request, user.id, profile.id)
        # All routing metadata is committed with the row. A queue worker must
        # never see a breakout record before its generation mode is durable.
        briefing = Briefing(
            id=str(uuid.uuid4()), user_id=user.id, profile_id=profile.id,
            title=f"Breakout: {metadata['topic']}", cast_id=cast_id,
            status="queued",
            extra_data={"kind": "breakout", "breakout": metadata,
                        "topic_ids": topic_ids, "profile_name": profile.name,
                        "target_duration": request.max_duration_minutes,
                        "max_duration": request.max_duration_minutes},
        )
        db.add(briefing)
        await db.commit()
        await db.refresh(briefing)
        background_tasks.add_task(process_generation_queue)
        return BriefingResponse.model_validate(briefing)


@router.get("/queue", response_model=BriefingListResponse)
async def list_generation_queue(
    user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """List every active generation job for this profile, oldest first."""
    briefings = await BriefingService(db).list_active_briefings(user.id, profile.id)
    return BriefingListResponse(
        briefings=[BriefingResponse.model_validate(briefing) for briefing in briefings],
        total=len(briefings),
    )


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


@router.post("/{briefing_id}/listening", response_model=ListeningCoverageResponse)
async def record_listening(
    briefing_id: str,
    request: ListeningRangesRequest,
    user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """Merge verified playback intervals for a briefing owned by this profile."""
    briefing = await BriefingService(db).get_briefing(briefing_id)
    if not briefing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Briefing not found")
    if briefing.user_id != user.id or briefing.profile_id != profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    try:
        return await ListeningService(db).record(briefing, [list(item) for item in request.ranges])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


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
    
    if briefing.status not in ["pending", "generating", "queued"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Briefing cannot be cancelled (not in progress)",
        )

    cancelled = await service.cancel_briefing(briefing_id)

    # Signal immediate cancellation of any in-flight LLM/TTS requests
    from app.services.cancellation import signal as cancel_signal
    cancel_signal(briefing_id)

    return BriefingResponse.model_validate(cancelled)
