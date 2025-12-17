"""DeepCasts API router."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.deepcast import (
    DeepCastCreate,
    DeepCastResponse,
    DeepCastListResponse,
)
from app.services.deepcast import DeepCastService

router = APIRouter()


async def generate_deepcast_task(
    deepcast_id: str,
    db_url: str,
):
    """Background task to generate DeepCast."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    
    engine = create_async_engine(db_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as db:
        service = DeepCastService(db)
        try:
            await service.generate_deepcast(deepcast_id)
        except Exception as e:
            print(f"DeepCast generation failed: {e}")
        finally:
            await engine.dispose()


@router.get("", response_model=DeepCastListResponse)
async def list_deepcasts(
    limit: int = 10,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all DeepCasts for the current user."""
    service = DeepCastService(db)
    deepcasts, total = await service.list_deepcasts(user.id, limit, offset)
    
    return DeepCastListResponse(
        deepcasts=[DeepCastResponse.model_validate(d) for d in deepcasts],
        total=total,
    )


@router.post("", response_model=DeepCastResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_deepcast(
    request: DeepCastCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new DeepCast from a query."""
    from app.config import get_settings
    settings = get_settings()
    
    # Use configured duration if not specified in request
    duration = request.target_duration_minutes or settings.deepcast_duration_minutes
    
    service = DeepCastService(db)
    
    # Create DeepCast record
    deepcast = await service.create_deepcast(
        user_id=user.id,
        query=request.query,
        target_duration_minutes=duration,
        num_sources=request.num_sources,
    )
    
    # Start background generation
    background_tasks.add_task(
        generate_deepcast_task,
        deepcast.id,
        settings.database_url,
    )
    
    return DeepCastResponse.model_validate(deepcast)


@router.get("/{deepcast_id}", response_model=DeepCastResponse)
async def get_deepcast(
    deepcast_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific DeepCast by ID."""
    service = DeepCastService(db)
    deepcast = await service.get_deepcast(deepcast_id)
    
    if not deepcast:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DeepCast not found",
        )
    
    if deepcast.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    return DeepCastResponse.model_validate(deepcast)


@router.delete("/{deepcast_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deepcast(
    deepcast_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a DeepCast."""
    service = DeepCastService(db)
    deepcast = await service.get_deepcast(deepcast_id)
    
    if not deepcast:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DeepCast not found",
        )
    
    if deepcast.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    await service.delete_deepcast(deepcast_id)

