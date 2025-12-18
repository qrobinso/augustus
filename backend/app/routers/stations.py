"""Stations API router."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.station import (
    StationCreate,
    StationUpdate,
    StationResponse,
    StationListResponse,
    EpisodeResponse,
)
from app.services.station import StationService

router = APIRouter()


async def generate_episode_task(
    station_id: str,
    db_url: str,
    force: bool = False,
):
    """Background task to generate station episode."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    
    engine = create_async_engine(db_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as db:
        service = StationService(db)
        try:
            await service.generate_episode(station_id, force=force)
        except Exception as e:
            print(f"Episode generation failed: {e}")
        finally:
            await engine.dispose()


@router.get("", response_model=StationListResponse)
async def list_stations(
    limit: int = 10,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all stations for the current user."""
    service = StationService(db)
    stations, total = await service.list_stations(user.id, limit, offset)
    
    # Get episode counts
    station_responses = []
    for station in stations:
        episodes, episode_count = await service.get_episodes(station.id, limit=0)
        station_responses.append(
            StationResponse.from_orm_with_count(station, episode_count)
        )
    
    return StationListResponse(
        stations=station_responses,
        total=total,
    )


@router.post("", response_model=StationResponse, status_code=status.HTTP_201_CREATED)
async def create_station(
    request: StationCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new station subscription."""
    from app.config import get_settings
    settings = get_settings()
    
    service = StationService(db)
    
    station = await service.create_station(
        user_id=user.id,
        topic=request.topic,
        description=request.description,
        update_frequency_hours=request.update_frequency_hours,
        settings=request.settings,
    )
    
    # Set cast_id if provided
    if request.cast_id:
        station.cast_id = request.cast_id
        await db.commit()
        await db.refresh(station)
    
    # Generate first episode in background
    background_tasks.add_task(
        generate_episode_task,
        station.id,
        settings.database_url,
        True,  # Force first episode
    )
    
    return StationResponse.from_orm_with_count(station, 0)


@router.get("/{station_id}", response_model=StationResponse)
async def get_station(
    station_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific station by ID."""
    service = StationService(db)
    station = await service.get_station(station_id)
    
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found",
        )
    
    if station.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    # Get episodes
    episodes, episode_count = await service.get_episodes(station_id, limit=10)
    
    response = StationResponse.model_validate(station)
    response.episodes = [EpisodeResponse.model_validate(e) for e in episodes]
    response.episode_count = episode_count
    
    return response


@router.put("/{station_id}", response_model=StationResponse)
async def update_station(
    station_id: str,
    request: StationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a station."""
    service = StationService(db)
    station = await service.get_station(station_id)
    
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found",
        )
    
    if station.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    updated = await service.update_station(
        station_id=station_id,
        topic=request.topic,
        description=request.description,
        update_frequency_hours=request.update_frequency_hours,
        settings=request.settings,
        is_active=request.is_active,
    )
    
    return StationResponse.from_orm_with_count(updated, 0)


@router.delete("/{station_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_station(
    station_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a station and all its episodes."""
    service = StationService(db)
    station = await service.get_station(station_id)
    
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found",
        )
    
    if station.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    await service.delete_station(station_id)


@router.post("/{station_id}/episodes", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def generate_episode(
    station_id: str,
    background_tasks: BackgroundTasks,
    force: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger episode generation for a station."""
    from app.config import get_settings
    settings = get_settings()
    
    service = StationService(db)
    station = await service.get_station(station_id)
    
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found",
        )
    
    if station.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    background_tasks.add_task(
        generate_episode_task,
        station_id,
        settings.database_url,
        force,
    )
    
    return {"status": "generating", "message": "Episode generation started"}


@router.get("/{station_id}/episodes", response_model=list[EpisodeResponse])
async def list_episodes(
    station_id: str,
    limit: int = 10,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List episodes for a station."""
    service = StationService(db)
    station = await service.get_station(station_id)
    
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found",
        )
    
    if station.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    episodes, _ = await service.get_episodes(station_id, limit, offset)
    
    return [EpisodeResponse.model_validate(e) for e in episodes]

