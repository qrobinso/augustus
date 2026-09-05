"""Authentication router - simplified for self-hosted use."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.profile import Profile
from app.models.topic import Topic, DEFAULT_TOPICS
from app.schemas.user import UserCreate, UserResponse
from app.services.api_key import find_api_key, touch_api_key

router = APIRouter()


async def seed_default_topics(user_id: str, profile_id: str, db: AsyncSession) -> None:
    """Create default topics for a new user."""
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


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_profile_id: Optional[str] = Header(None, alias="X-Profile-ID"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> User:
    """Resolve an API-key owner, or use the local self-hosted user."""
    if x_api_key is not None:
        api_key = await find_api_key(db, x_api_key)
        if api_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API key",
            )

        result = await db.execute(select(User).where(User.id == api_key.user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API key",
            )
        if x_profile_id is not None and x_profile_id != api_key.profile_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API key is bound to a different profile",
            )

        await touch_api_key(db, api_key, request.headers.get("user-agent"))
        await db.commit()

        user.current_api_key_id = api_key.id
        user.current_api_key_tools = api_key.enabled_tools
        user.current_profile_id = api_key.profile_id
        return user

    # For self-hosted, we use a single default user - no auth needed
    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()
    
    if not user:
        # Create default user
        user = User(
            id=str(uuid.uuid4()),
            name="Default User",
            preferences={},
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        # Create default profile for new user
        default_profile = Profile(
            id=str(uuid.uuid4()),
            user_id=user.id,
            name="Default",
            color="#e85d04",  # App accent color
            is_admin=True,
        )
        db.add(default_profile)
        await db.commit()
        
        # Store the profile_id for seeding topics
        x_profile_id = default_profile.id
        
        # Seed default topics for new user with profile_id
        await seed_default_topics(user.id, default_profile.id, db)
    
    # Get the current profile ID from header or default profile
    current_profile_id = x_profile_id
    if not current_profile_id:
        # Get the user's default profile
        result = await db.execute(
            select(Profile).where(
                Profile.user_id == user.id,
                Profile.is_admin == True,
            ).limit(1)
        )
        default_profile = result.scalar_one_or_none()
        if default_profile:
            current_profile_id = default_profile.id
        else:
            # Fallback to first profile
            result = await db.execute(
                select(Profile).where(Profile.user_id == user.id).limit(1)
            )
            first_profile = result.scalar_one_or_none()
            if first_profile:
                current_profile_id = first_profile.id
    
    # Attach current_profile_id to user object for use in routes
    user.current_api_key_id = None
    user.current_api_key_tools = None
    user.current_profile_id = current_profile_id
    
    return user


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Get current user information."""
    return user


@router.put("/me", response_model=UserResponse)
async def update_me(
    updates: UserCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user information."""
    if updates.name:
        user.name = updates.name
    if updates.email:
        user.email = updates.email
    if updates.preferences:
        user.preferences = updates.preferences
    
    await db.commit()
    await db.refresh(user)
    
    return user
