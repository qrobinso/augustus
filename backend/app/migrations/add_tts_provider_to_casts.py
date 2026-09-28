"""Add casts.tts_provider, backfill it from member voices, and enforce one default per provider.

Runs on every startup from init_db() and is idempotent. It can also be run by hand:
    python -m app.migrations.add_tts_provider_to_casts
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.config import get_settings
from app.services.tts.registry import infer_cast_provider


async def upgrade(conn: AsyncConnection, fallback_provider: str) -> bool:
    """Return True when the column was added and backfilled on this run."""
    columns = [row[1] for row in (await conn.execute(text("PRAGMA table_info(casts)"))).fetchall()]
    if not columns:
        return False
    added = "tts_provider" not in columns
    if added:
        await conn.execute(text(
            "ALTER TABLE casts ADD COLUMN tts_provider VARCHAR(32) NOT NULL DEFAULT 'gemini'"
        ))
        voices: dict[str, list[str]] = {}
        for cast_id, voice_id in (await conn.execute(text("SELECT cast_id, voice_id FROM cast_members"))).fetchall():
            voices.setdefault(cast_id, []).append(voice_id)
        for (cast_id,) in (await conn.execute(text("SELECT id FROM casts"))).fetchall():
            provider = infer_cast_provider(voices.get(cast_id, []), fallback_provider)
            await conn.execute(
                text("UPDATE casts SET tts_provider = :provider WHERE id = :id"),
                {"provider": provider, "id": cast_id},
            )
            print(f"[Migration] Cast {cast_id} -> {provider}")
    # Keep only the newest default per (user, profile, provider) before enforcing uniqueness.
    await conn.execute(text("""
        UPDATE casts SET is_default = 0
        WHERE is_default = 1 AND id NOT IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY user_id, profile_id, tts_provider
                    ORDER BY updated_at DESC, created_at DESC
                ) AS rn
                FROM casts WHERE is_default = 1
            ) WHERE rn = 1
        )
    """))
    await conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_casts_scope_provider ON casts (user_id, profile_id, tts_provider)"
    ))
    await conn.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_casts_one_default_per_provider "
        "ON casts (user_id, COALESCE(profile_id, ''), tts_provider) WHERE is_default = 1"
    ))
    return added


async def migrate():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        added = await upgrade(conn, settings.tts_provider)
    await engine.dispose()
    print("Added and backfilled casts.tts_provider" if added else "casts.tts_provider already present")


if __name__ == "__main__":
    asyncio.run(migrate())
