"""Migration to convert profile emoji field to color field."""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings


async def migrate():
    """Convert emoji column to color column in profiles table."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    
    async with engine.begin() as conn:
        # Check current columns in profiles table
        result = await conn.execute(text("PRAGMA table_info(profiles)"))
        columns = {row[1]: row for row in result.fetchall()}
        
        has_emoji = 'emoji' in columns
        has_color = 'color' in columns
        
        if has_color:
            print("'color' column already exists in profiles table")
        else:
            print("Adding 'color' column to profiles table...")
            await conn.execute(text("""
                ALTER TABLE profiles ADD COLUMN color VARCHAR(7) NOT NULL DEFAULT '#8B5CF6'
            """))
            print("Added 'color' column")
        
        # Note: SQLite doesn't support DROP COLUMN easily, so we'll leave emoji for now
        # It will just be ignored by the application
        if has_emoji:
            print("Note: 'emoji' column still exists but will be ignored by the application")
        
        print("Migration complete!")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())

