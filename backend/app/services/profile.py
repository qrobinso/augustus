"""Profile service for managing user profiles."""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import Profile
from app.schemas.profile import ProfileCreate, ProfileUpdate


class ProfileService:
    """Service for profile operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user_profiles(self, user_id: str) -> list[Profile]:
        """Get all profiles for a user."""
        result = await self.db.execute(
            select(Profile)
            .where(Profile.user_id == user_id)
            .order_by(Profile.is_admin.desc(), Profile.created_at)
        )
        return list(result.scalars().all())
    
    async def get_profile(self, profile_id: str, user_id: str) -> Optional[Profile]:
        """Get a specific profile."""
        result = await self.db.execute(
            select(Profile).where(
                Profile.id == profile_id,
                Profile.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
    
    async def create_profile(self, user_id: str, data: ProfileCreate) -> Profile:
        """Create a new profile."""
        profile = Profile(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=data.name,
            emoji=data.emoji,
            is_admin=False,  # Only the first profile is admin
        )
        self.db.add(profile)
        await self.db.commit()
        await self.db.refresh(profile)
        return profile
    
    async def update_profile(
        self,
        profile_id: str,
        user_id: str,
        data: ProfileUpdate,
    ) -> Optional[Profile]:
        """Update a profile."""
        profile = await self.get_profile(profile_id, user_id)
        if not profile:
            return None
        
        if data.name is not None:
            profile.name = data.name
        if data.emoji is not None:
            profile.emoji = data.emoji
        
        await self.db.commit()
        await self.db.refresh(profile)
        return profile
    
    async def delete_profile(self, profile_id: str, user_id: str) -> bool:
        """Delete a profile. Cannot delete admin profile."""
        profile = await self.get_profile(profile_id, user_id)
        if not profile:
            return False
        
        if profile.is_admin:
            raise ValueError("Cannot delete admin profile")
        
        await self.db.delete(profile)
        await self.db.commit()
        return True
    
    async def get_default_profile(self, user_id: str) -> Optional[Profile]:
        """Get the admin/default profile for a user."""
        result = await self.db.execute(
            select(Profile).where(
                Profile.user_id == user_id,
                Profile.is_admin == True,
            )
        )
        return result.scalar_one_or_none()

