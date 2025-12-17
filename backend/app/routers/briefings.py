"""Briefings API router."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.briefing import (
    BriefingGenerateRequest,
    BriefingResponse,
    BriefingListResponse,
    BriefingListenedUpdate,
)
from app.services.briefing import BriefingService

router = APIRouter()


async def generate_briefing_task(
    briefing_id: str,
    topic_ids: Optional[list[str]],
    max_duration: int,
    db_url: str,
):
    """Background task to generate briefing."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    
    engine = create_async_engine(db_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as db:
        service = BriefingService(db)
        try:
            await service.generate_briefing(
                briefing_id=briefing_id,
                topic_ids=topic_ids,
                max_duration_minutes=max_duration,
            )
        except Exception as e:
            print(f"Briefing generation failed: {e}")
        finally:
            await engine.dispose()


@router.get("", response_model=BriefingListResponse)
async def list_briefings(
    limit: int = 10,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all briefings for the current user."""
    service = BriefingService(db)
    briefings, total = await service.list_briefings(user.id, limit, offset)
    
    return BriefingListResponse(
        briefings=[BriefingResponse.model_validate(b) for b in briefings],
        total=total,
    )


@router.post("/generate", response_model=BriefingResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_briefing(
    request: BriefingGenerateRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger generation of a new daily briefing."""
    from app.config import get_settings
    settings = get_settings()
    
    service = BriefingService(db)
    
    # Check if there's already a briefing in progress
    in_progress = await service.has_briefing_in_progress(user.id)
    if in_progress:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A briefing is already being generated. Please wait for it to complete.",
        )
    
    # Use configured duration if not specified in request
    duration = request.max_duration_minutes or settings.briefing_duration_minutes
    
    # Create briefing record with topic_ids
    briefing = await service.create_briefing(
        user_id=user.id,
        topic_ids=request.topic_ids,
        max_duration_minutes=duration,
    )
    
    # Start background generation
    background_tasks.add_task(
        generate_briefing_task,
        briefing.id,
        request.topic_ids,
        duration,
        settings.database_url,
    )
    
    return BriefingResponse.model_validate(briefing)


@router.get("/{briefing_id}", response_model=BriefingResponse)
async def get_briefing(
    briefing_id: str,
    user: User = Depends(get_current_user),
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
    
    if briefing.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    return BriefingResponse.model_validate(briefing)


@router.delete("/{briefing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_briefing(
    briefing_id: str,
    user: User = Depends(get_current_user),
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
    
    if briefing.user_id != user.id:
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
    
    if briefing.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    updated = await service.update_listened_status(briefing_id, update.listened)
    return BriefingResponse.model_validate(updated)


@router.post("/{briefing_id}/cancel", response_model=BriefingResponse)
async def cancel_briefing(
    briefing_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a briefing that is pending or generating."""
    service = BriefingService(db)
    briefing = await service.get_briefing(briefing_id)
    
    if not briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Briefing not found",
        )
    
    if briefing.user_id != user.id:
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

