"""Casts API router."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.cast import (
    CastCreate,
    CastUpdate,
    CastResponse,
    CastListResponse,
)
from app.services.cast import CastService

router = APIRouter()


@router.post("", response_model=CastResponse, status_code=status.HTTP_201_CREATED)
async def create_cast(
    cast_data: CastCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new cast."""
    service = CastService(db)
    try:
        cast = await service.create_cast(user.id, cast_data)
        return CastResponse.model_validate(cast)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=CastListResponse)
async def list_casts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all casts for the current user."""
    service = CastService(db)
    casts = await service.get_user_casts(user.id)
    return CastListResponse(casts=[CastResponse.model_validate(c) for c in casts])


@router.get("/{cast_id}", response_model=CastResponse)
async def get_cast(
    cast_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a cast by ID."""
    service = CastService(db)
    cast = await service.get_cast(cast_id, user.id)
    if not cast:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cast not found")
    return CastResponse.model_validate(cast)


@router.put("/{cast_id}", response_model=CastResponse)
async def update_cast(
    cast_id: str,
    cast_data: CastUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a cast."""
    service = CastService(db)
    try:
        cast = await service.update_cast(cast_id, user.id, cast_data)
        if not cast:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cast not found")
        return CastResponse.model_validate(cast)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{cast_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cast(
    cast_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a cast."""
    service = CastService(db)
    try:
        deleted = await service.delete_cast(cast_id, user.id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cast not found")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{cast_id}/set-default", response_model=CastResponse)
async def set_default_cast(
    cast_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set a cast as the default for the user."""
    service = CastService(db)
    cast = await service.set_default_cast(cast_id, user.id)
    if not cast:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cast not found")
    return CastResponse.model_validate(cast)


@router.post("/default/restore", response_model=CastResponse)
async def restore_default_cast(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Restore the default cast to its original values (Alex and Sam with Kore/Puck voices)."""
    service = CastService(db)
    cast = await service.restore_default_cast(user.id)
    return CastResponse.model_validate(cast)





