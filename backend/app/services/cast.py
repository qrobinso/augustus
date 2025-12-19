"""Cast service for managing custom podcast casts."""

import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.cast import Cast, CastMember
from app.models.user import User
from app.schemas.cast import CastCreate, CastUpdate


class CastService:
    """Service for managing casts."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_cast(
        self,
        user_id: str,
        cast_data: CastCreate,
    ) -> Cast:
        """Create a new cast with members.
        
        Args:
            user_id: The user ID creating the cast
            cast_data: Cast creation data
            
        Returns:
            Created Cast instance
        """
        # Validate member count
        if len(cast_data.members) < 1 or len(cast_data.members) > 3:
            raise ValueError("Cast must have 1-3 members")
        
        # Validate order values
        orders = [m.order for m in cast_data.members]
        if sorted(orders) != list(range(len(cast_data.members))):
            raise ValueError("Member orders must be sequential starting from 0")
        
        # If this is being set as default, unset other defaults
        is_default = cast_data.members[0].order == 0 if cast_data.members else False
        if is_default:
            await self._unset_default_casts(user_id)
        
        # Create cast
        cast = Cast(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=cast_data.name,
            is_default=False,  # Only set via set_default_cast
        )
        self.db.add(cast)
        await self.db.flush()
        
        # Create cast members
        for member_data in cast_data.members:
            member = CastMember(
                id=str(uuid.uuid4()),
                cast_id=cast.id,
                name=member_data.name,
                voice_id=member_data.voice_id,
                personality=member_data.personality,
                order=member_data.order,
            )
            self.db.add(member)
        
        await self.db.commit()
        await self.db.refresh(cast)
        
        # Load members
        await self.db.refresh(cast, ["members"])
        
        return cast
    
    async def get_user_casts(self, user_id: str) -> list[Cast]:
        """Get all casts for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            List of Cast instances
        """
        result = await self.db.execute(
            select(Cast)
            .where(Cast.user_id == user_id)
            .options(selectinload(Cast.members))
            .order_by(Cast.is_default.desc(), Cast.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_cast(self, cast_id: str, user_id: str) -> Optional[Cast]:
        """Get a cast by ID (ensuring it belongs to user).
        
        Args:
            cast_id: The cast ID
            user_id: The user ID (for authorization)
            
        Returns:
            Cast instance or None if not found
        """
        result = await self.db.execute(
            select(Cast)
            .where(Cast.id == cast_id, Cast.user_id == user_id)
            .options(selectinload(Cast.members))
        )
        return result.scalar_one_or_none()
    
    async def get_default_cast(self, user_id: str) -> Cast:
        """Get or create the default cast for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            Default Cast instance
        """
        # Try to find existing default cast
        result = await self.db.execute(
            select(Cast)
            .where(Cast.user_id == user_id, Cast.is_default == True)
            .options(selectinload(Cast.members))
        )
        default_cast = result.scalar_one_or_none()
        
        if default_cast:
            return default_cast
        
        # Create default cast with standard voices
        # Gemini voices: Kore (female) and Puck (male) - these are good defaults
        cast = Cast(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name="Alex and Sam",
            is_default=True,
        )
        self.db.add(cast)
        await self.db.flush()
        
        # Create default members with Gemini voices
        alex = CastMember(
            id=str(uuid.uuid4()),
            cast_id=cast.id,
            name="Alex",
            voice_id="Kore",  # Gemini voice
            personality="Casual",
            order=0,
        )
        sam = CastMember(
            id=str(uuid.uuid4()),
            cast_id=cast.id,
            name="Sam",
            voice_id="Puck",  # Gemini voice
            personality="Analytical",
            order=1,
        )
        self.db.add(alex)
        self.db.add(sam)
        
        await self.db.commit()
        await self.db.refresh(cast)
        await self.db.refresh(cast, ["members"])
        
        return cast
    
    async def update_cast(
        self,
        cast_id: str,
        user_id: str,
        cast_data: CastUpdate,
    ) -> Optional[Cast]:
        """Update a cast and its members.
        
        Args:
            cast_id: The cast ID
            user_id: The user ID (for authorization)
            cast_data: Cast update data
            
        Returns:
            Updated Cast instance or None if not found
        """
        cast = await self.get_cast(cast_id, user_id)
        if not cast:
            return None
        
        # Update cast name if provided
        if cast_data.name is not None:
            cast.name = cast_data.name
        
        # Update members if provided
        if cast_data.members is not None:
            # Validate member count
            if len(cast_data.members) < 1 or len(cast_data.members) > 3:
                raise ValueError("Cast must have 1-3 members")
            
            # Validate order values
            orders = [m.order for m in cast_data.members]
            if sorted(orders) != list(range(len(cast_data.members))):
                raise ValueError("Member orders must be sequential starting from 0")
            
            # Delete existing members
            await self.db.execute(
                select(CastMember).where(CastMember.cast_id == cast_id)
            )
            result = await self.db.execute(
                select(CastMember).where(CastMember.cast_id == cast_id)
            )
            for member in result.scalars().all():
                await self.db.delete(member)
            
            # Create new members
            for member_data in cast_data.members:
                member = CastMember(
                    id=str(uuid.uuid4()),
                    cast_id=cast.id,
                    name=member_data.name,
                    voice_id=member_data.voice_id,
                    personality=member_data.personality,
                    order=member_data.order,
                )
                self.db.add(member)
        
        await self.db.commit()
        await self.db.refresh(cast)
        await self.db.refresh(cast, ["members"])
        
        return cast
    
    async def delete_cast(self, cast_id: str, user_id: str) -> bool:
        """Delete a cast.
        
        Args:
            cast_id: The cast ID
            user_id: The user ID (for authorization)
            
        Returns:
            True if deleted, False if not found
        """
        cast = await self.get_cast(cast_id, user_id)
        if not cast:
            return False
        
        # Prevent deleting default cast
        if cast.is_default:
            raise ValueError("Cannot delete the default cast")
        
        await self.db.delete(cast)
        await self.db.commit()
        
        return True
    
    async def set_default_cast(self, cast_id: str, user_id: str) -> Optional[Cast]:
        """Set a cast as the default for a user.
        
        Args:
            cast_id: The cast ID
            user_id: The user ID (for authorization)
            
        Returns:
            Updated Cast instance or None if not found
        """
        cast = await self.get_cast(cast_id, user_id)
        if not cast:
            return None
        
        # Unset other defaults
        await self._unset_default_casts(user_id)
        
        # Set this cast as default
        cast.is_default = True
        await self.db.commit()
        await self.db.refresh(cast)
        
        return cast
    
    async def _unset_default_casts(self, user_id: str):
        """Unset all default casts for a user."""
        result = await self.db.execute(
            select(Cast).where(Cast.user_id == user_id, Cast.is_default == True)
        )
        for cast in result.scalars().all():
            cast.is_default = False
    
    async def restore_default_cast(self, user_id: str) -> Cast:
        """Restore the default cast to its original values.
        
        Args:
            user_id: The user ID
            
        Returns:
            Restored Cast instance
        """
        # Find the default cast
        result = await self.db.execute(
            select(Cast)
            .where(Cast.user_id == user_id, Cast.is_default == True)
            .options(selectinload(Cast.members))
        )
        default_cast = result.scalar_one_or_none()
        
        if not default_cast:
            # No default cast exists, create one
            return await self.get_default_cast(user_id)
        
        # Update cast name
        default_cast.name = "Alex and Sam"
        
        # Delete existing members
        for member in default_cast.members:
            await self.db.delete(member)
        
        # Create default members with Gemini voices
        alex = CastMember(
            id=str(uuid.uuid4()),
            cast_id=default_cast.id,
            name="Alex",
            voice_id="Kore",  # Gemini voice
            personality="Casual",
            order=0,
        )
        sam = CastMember(
            id=str(uuid.uuid4()),
            cast_id=default_cast.id,
            name="Sam",
            voice_id="Puck",  # Gemini voice
            personality="Analytical",
            order=1,
        )
        self.db.add(alex)
        self.db.add(sam)
        
        await self.db.commit()
        await self.db.refresh(default_cast)
        await self.db.refresh(default_cast, ["members"])
        
        return default_cast


