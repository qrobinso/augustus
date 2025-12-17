"""Authentication router - simplified for self-hosted use."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse

router = APIRouter()


async def get_current_user(
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get or create the current user (single user mode for self-hosted)."""
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
