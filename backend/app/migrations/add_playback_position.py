"""Migration to add playback_position column to briefings table."""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings


async def migrate():
    """Add playback_position column to briefings table for resume functionality."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    
    async with engine.begin() as conn:
        # Check if column already exists
        result = await conn.execute(text("PRAGMA table_info(briefings)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'playback_position' not in columns:
            print("Adding 'playback_position' column to briefings table...")
            await conn.execute(text(
                "ALTER TABLE briefings ADD COLUMN playback_position FLOAT"
            ))
            print("Added 'playback_position' column")
        else:
            print("'playback_position' column already exists")
    
    await engine.dispose()
    print("Migration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())

