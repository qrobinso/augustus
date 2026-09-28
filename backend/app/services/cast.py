"""Cast service for managing custom podcast casts."""

import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.cast import Cast, CastMember
from app.schemas.cast import CastCreate, CastUpdate
from app.services.tts.registry import provider_label


class NoCastForProviderError(LookupError):
    """The active TTS provider has no cast for this profile."""

    def __init__(self, provider: str):
        super().__init__(f"No {provider_label(provider)} cast yet. Create one on the Casts page.")
        self.provider = provider


class CastProviderMismatchError(ValueError):
    """A cast was used or edited with a provider it does not belong to."""


def provider_mismatch_message(cast_name: str, cast_provider: str, active_provider: str) -> str:
    return (
        f"'{cast_name}' is a {provider_label(cast_provider)} cast; "
        f"your voice provider is {provider_label(active_provider)}."
    )


class CastService:
    """Service for managing casts."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _scoped(query, user_id: str, profile_id: Optional[str], provider: Optional[str]):
        query = query.where(Cast.user_id == user_id)
        if profile_id:
            query = query.where(Cast.profile_id == profile_id)
        if provider:
            query = query.where(Cast.tts_provider == provider)
        return query

    def ensure_usable(self, cast: Cast, provider: str) -> None:
        if cast.tts_provider != provider:
            raise CastProviderMismatchError(provider_mismatch_message(cast.name, cast.tts_provider, provider))

    async def create_cast(
        self,
        user_id: str,
        cast_data: CastCreate,
        profile_id: Optional[str],
        provider: str,
    ) -> Cast:
        """Create a cast for the given provider; the provider's first cast becomes its default."""
        if len(cast_data.members) < 1 or len(cast_data.members) > 3:
            raise ValueError("Cast must have 1-3 members")
        orders = [m.order for m in cast_data.members]
        if sorted(orders) != list(range(len(cast_data.members))):
            raise ValueError("Member orders must be sequential starting from 0")

        existing = await self.db.scalar(
            self._scoped(select(func.count(Cast.id)), user_id, profile_id, provider)
        )
        cast = Cast(
            id=str(uuid.uuid4()),
            user_id=user_id,
            profile_id=profile_id,
            name=cast_data.name,
            description=cast_data.description,
            tts_provider=provider,
            is_default=existing == 0,
        )
        self.db.add(cast)
        await self.db.flush()
        for member_data in cast_data.members:
            self.db.add(CastMember(
                id=str(uuid.uuid4()),
                cast_id=cast.id,
                name=member_data.name,
                voice_id=member_data.voice_id,
                personality=member_data.personality,
                order=member_data.order,
            ))
        await self.db.commit()
        await self.db.refresh(cast)
        await self.db.refresh(cast, ["members"])
        return cast

    async def get_user_casts(
        self, user_id: str, profile_id: Optional[str] = None, provider: Optional[str] = None,
    ) -> list[Cast]:
        """Casts for a user/profile; provider=None returns every provider's casts."""
        result = await self.db.execute(
            self._scoped(select(Cast), user_id, profile_id, provider)
            .options(selectinload(Cast.members))
            .order_by(Cast.is_default.desc(), Cast.created_at.desc())
        )
        return list(result.scalars().all())

    async def count_by_provider(self, user_id: str, profile_id: Optional[str]) -> dict[str, int]:
        rows = await self.db.execute(
            self._scoped(select(Cast.tts_provider, func.count(Cast.id)), user_id, profile_id, None)
            .group_by(Cast.tts_provider)
        )
        return {provider: count for provider, count in rows.all()}

    async def get_cast(self, cast_id: str, user_id: str, profile_id: Optional[str] = None) -> Optional[Cast]:
        """Get a cast by ID (ensuring it belongs to user/profile).

        Args:
            cast_id: The cast ID
            user_id: The user ID (for authorization)
            profile_id: The profile ID (for authorization)

        Returns:
            Cast instance or None if not found
        """
        query = select(Cast).where(Cast.id == cast_id, Cast.user_id == user_id)

        if profile_id:
            query = query.where(Cast.profile_id == profile_id)

        result = await self.db.execute(
            query.options(selectinload(Cast.members))
        )
        return result.scalar_one_or_none()

    async def get_default_cast(self, user_id: str, profile_id: Optional[str], provider: str) -> Cast:
        """The provider's default cast. Promotes the oldest cast if none is marked.

        Raises NoCastForProviderError when the provider has no casts at all; casts
        are never created implicitly.
        """
        query = self._scoped(select(Cast), user_id, profile_id, provider).options(selectinload(Cast.members))
        default = (await self.db.execute(query.where(Cast.is_default == True))).scalar_one_or_none()  # noqa: E712
        if default:
            return default
        oldest = (await self.db.execute(query.order_by(Cast.created_at.asc()).limit(1))).scalar_one_or_none()
        if oldest is None:
            raise NoCastForProviderError(provider)
        oldest.is_default = True
        await self.db.commit()
        await self.db.refresh(oldest, ["members"])
        return oldest

    async def resolve_for_generation(
        self, user_id: str, profile_id: Optional[str], cast_id: Optional[str], provider: str,
    ) -> Cast:
        """The cast a queued briefing should use with `provider`.

        Explicit choices were validated at request time, so any mismatch here is
        implicit (a schedule's cast, a breakout's parent cast, or a provider switch
        while queued) and falls back to the provider's default.
        """
        if cast_id:
            cast = await self.get_cast(cast_id, user_id, profile_id)
            if cast and cast.tts_provider == provider:
                return cast
            reason = "not found" if cast is None else f"belongs to {cast.tts_provider}"
            print(f"[Cast] Cast {cast_id} {reason}; using the {provider} default")
        return await self.get_default_cast(user_id, profile_id, provider)

    async def update_cast(
        self,
        cast_id: str,
        user_id: str,
        cast_data: CastUpdate,
        profile_id: Optional[str],
        provider: str,
    ) -> Optional[Cast]:
        """Update a cast and its members.

        Args:
            cast_id: The cast ID
            user_id: The user ID (for authorization)
            cast_data: Cast update data
            profile_id: The profile ID (for authorization)
            provider: The active TTS provider; the cast must belong to it

        Returns:
            Updated Cast instance or None if not found
        """
        cast = await self.get_cast(cast_id, user_id, profile_id)
        if not cast:
            return None
        self.ensure_usable(cast, provider)

        # Update cast name if provided
        if cast_data.name is not None:
            cast.name = cast_data.name

        # Update cast description if provided
        if cast_data.description is not None:
            cast.description = cast_data.description

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

    async def delete_cast(self, cast_id: str, user_id: str, profile_id: Optional[str] = None) -> bool:
        """Delete a cast.

        Args:
            cast_id: The cast ID
            user_id: The user ID (for authorization)
            profile_id: The profile ID (for authorization)

        Returns:
            True if deleted, False if not found
        """
        cast = await self.get_cast(cast_id, user_id, profile_id)
        if not cast:
            return False

        # Prevent deleting default cast
        if cast.is_default:
            raise ValueError("Cannot delete the default cast")

        await self.db.delete(cast)
        await self.db.commit()

        return True

    async def set_default_cast(
        self, cast_id: str, user_id: str, profile_id: Optional[str], provider: str,
    ) -> Optional[Cast]:
        """Set a cast as the default for a user/profile within its provider.

        Args:
            cast_id: The cast ID
            user_id: The user ID (for authorization)
            profile_id: The profile ID (for authorization)
            provider: The active TTS provider; the cast must belong to it

        Returns:
            Updated Cast instance or None if not found
        """
        cast = await self.get_cast(cast_id, user_id, profile_id)
        if not cast:
            return None
        self.ensure_usable(cast, provider)
        await self._unset_default_casts(user_id, profile_id, provider)
        # Flush the unset first: the partial unique index allows one default per provider.
        await self.db.flush()
        cast.is_default = True
        await self.db.commit()
        await self.db.refresh(cast)

        return cast

    async def _unset_default_casts(self, user_id: str, profile_id: Optional[str], provider: str):
        """Unset all default casts for a user/profile within a provider."""
        result = await self.db.execute(
            self._scoped(select(Cast), user_id, profile_id, provider).where(Cast.is_default == True)  # noqa: E712
        )
        for cast in result.scalars().all():
            cast.is_default = False

    async def restore_default_cast(self, user_id: str, profile_id: Optional[str], provider: str) -> Cast:
        """Reset the Gemini default cast to the built-in hosts (Gemini voices only)."""
        if provider != "gemini":
            raise CastProviderMismatchError(
                f"Restore defaults is only available for Google Gemini casts, not {provider_label(provider)}."
            )
        query = (
            self._scoped(select(Cast), user_id, profile_id, "gemini")
            .where(Cast.is_default == True)  # noqa: E712
            .options(selectinload(Cast.members))
        )
        default_cast = (await self.db.execute(query)).scalar_one_or_none()

        if default_cast is None:
            default_cast = Cast(
                id=str(uuid.uuid4()),
                user_id=user_id,
                profile_id=profile_id,
                name="Augustus Daily",
                tts_provider="gemini",
                is_default=True,
            )
            self.db.add(default_cast)
            await self.db.flush()
            await self.db.refresh(default_cast, ["members"])

        # Update cast name
        default_cast.name = "Augustus Daily"

        # Delete existing members
        for member in list(default_cast.members):
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
            name="Sebastian",
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
