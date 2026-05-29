"""API key generation, hashing and lookup helpers."""

import hashlib
import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey

KEY_PREFIX = "aug_"


def generate_raw_key() -> str:
    """Generate a new raw API key string."""
    return KEY_PREFIX + secrets.token_urlsafe(32)


def hash_key(raw_key: str) -> str:
    """SHA-256 hash of a raw key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def key_prefix_display(raw_key: str) -> str:
    """First chars to show in UI (e.g. aug_abc12...)."""
    return raw_key[:8]


async def find_api_key(db: AsyncSession, raw_key: str) -> Optional[ApiKey]:
    """Look up an active (non-revoked) API key by raw value."""
    if not raw_key or not raw_key.startswith(KEY_PREFIX):
        return None
    digest = hash_key(raw_key)
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == digest)
    )
    api_key = result.scalar_one_or_none()
    if not api_key or api_key.revoked_at is not None:
        return None
    return api_key


async def touch_api_key(
    db: AsyncSession, api_key: ApiKey, client: Optional[str]
) -> None:
    """Update last_used metadata. Caller commits."""
    api_key.last_used_at = datetime.utcnow()
    if client:
        api_key.last_client = client[:255]
