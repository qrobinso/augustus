"""Profiles API router."""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.user import User
from app.models.profile import Profile
from app.models.topic import Topic, DEFAULT_TOPICS
from app.models.cast import Cast, CastMember
from app.routers.auth import get_current_user
from app.schemas.profile import (
    ProfileCreate,
    ProfileUpdate,
    ProfileResponse,
    ProfileListResponse,
)

router = APIRouter()


async def get_current_profile(
    x_profile_id: Optional[str] = Header(None, alias="X-Profile-ID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Profile:
    """Get the current profile from X-Profile-ID header.
    
    If no header is provided, returns the admin profile.
    """
    if x_profile_id:
        result = await db.execute(
            select(Profile).where(
                Profile.id == x_profile_id,
                Profile.user_id == user.id,
            )
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found",
            )
        return profile
    
    # Return admin profile by default
    result = await db.execute(
        select(Profile).where(
            Profile.user_id == user.id,
            Profile.is_admin == True,
        )
    )
    profile = result.scalar_one_or_none()
    
    if not profile:
        # Create admin profile if it doesn't exist
        profile = await _create_admin_profile(user.id, user.name, db)
    
    return profile


async def _create_admin_profile(user_id: str, user_name: str, db: AsyncSession) -> Profile:
    """Create the admin profile for a user."""
    profile_name = user_name if user_name and user_name != "Default User" else "Admin"
    
    profile = Profile(
        id=str(uuid.uuid4()),
        user_id=user_id,
        name=profile_name,
        color="#e85d04",  # App accent color
        is_admin=True,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    
    # Seed default topics for the admin profile
    await _seed_default_topics(user_id, profile.id, db)
    
    # Seed default cast for the admin profile
    await _seed_default_cast(user_id, profile.id, db)
    
    return profile


async def _seed_default_topics(user_id: str, profile_id: str, db: AsyncSession) -> None:
    """Create default topics for a new profile."""
    for topic_data in DEFAULT_TOPICS:
        topic = Topic(
            id=str(uuid.uuid4()),
            user_id=user_id,
            profile_id=profile_id,
            name=topic_data["name"],
            slug=topic_data["slug"],
            color=topic_data["color"],
            is_active=True,
        )
        db.add(topic)
    await db.commit()


async def _seed_default_cast(user_id: str, profile_id: str, db: AsyncSession) -> None:
    """Create default cast for a new profile."""
    cast_id = str(uuid.uuid4())
    now = datetime.utcnow()
    
    cast = Cast(
        id=cast_id,
        user_id=user_id,
        profile_id=profile_id,
        name="Augustus Daily",
        is_default=True,
        created_at=now,
        updated_at=now,
    )
    db.add(cast)
    
    # Add default cast members
    members = [
        CastMember(
            id=str(uuid.uuid4()),
            cast_id=cast_id,
            name="Alex",
            voice_id="Kore",
            personality="Casual",
            order=0,
            created_at=now,
        ),
        CastMember(
            id=str(uuid.uuid4()),
            cast_id=cast_id,
            name="Sebastian",
            voice_id="Sadachbia",
            personality="Analytical",
            order=1,
            created_at=now,
        ),
    ]
    for member in members:
        db.add(member)
    
    await db.commit()


def _profile_to_response(profile: Profile) -> ProfileResponse:
    """Convert Profile model to response."""
    return ProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        name=profile.name,
        color=profile.color,
        is_admin=profile.is_admin,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.get("", response_model=ProfileListResponse)
async def list_profiles(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all profiles for the current user."""
    # Ensure admin profile exists
    result = await db.execute(
        select(Profile).where(
            Profile.user_id == user.id,
            Profile.is_admin == True,
        )
    )
    admin_profile = result.scalar_one_or_none()
    
    if not admin_profile:
        await _create_admin_profile(user.id, user.name, db)
    
    # Get all profiles
    result = await db.execute(
        select(Profile)
        .where(Profile.user_id == user.id)
        .order_by(Profile.is_admin.desc(), Profile.created_at.asc())
    )
    profiles = result.scalars().all()
    
    return ProfileListResponse(
        profiles=[_profile_to_response(p) for p in profiles],
        total=len(profiles),
    )


@router.post("", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    request: ProfileCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new profile (non-admin)."""
    profile = Profile(
        id=str(uuid.uuid4()),
        user_id=user.id,
        name=request.name,
        color=request.color,
        is_admin=False,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    
    # Seed default topics for the new profile
    await _seed_default_topics(user.id, profile.id, db)
    
    # Seed default cast for the new profile
    await _seed_default_cast(user.id, profile.id, db)
    
    return _profile_to_response(profile)


@router.get("/{profile_id}", response_model=ProfileResponse)
async def get_profile(
    profile_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific profile by ID."""
    result = await db.execute(
        select(Profile).where(Profile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )
    
    if profile.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    return _profile_to_response(profile)


@router.put("/{profile_id}", response_model=ProfileResponse)
async def update_profile(
    profile_id: str,
    request: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a profile (name and color)."""
    result = await db.execute(
        select(Profile).where(Profile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )
    
    if profile.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    if request.name is not None:
        profile.name = request.name
    if request.color is not None:
        profile.color = request.color
    
    await db.commit()
    await db.refresh(profile)
    
    return _profile_to_response(profile)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    profile_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a profile. Cannot delete admin profile."""
    result = await db.execute(
        select(Profile).where(Profile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )
    
    if profile.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    if profile.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the admin profile",
        )
    
    await db.delete(profile)
    await db.commit()

