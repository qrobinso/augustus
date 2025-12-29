"""Migration to add favorite column to briefings table."""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings


async def migrate():
    """Add favorite column to briefings table."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    
    async with engine.begin() as conn:
        # Check if column already exists
        result = await conn.execute(text("PRAGMA table_info(briefings)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'favorite' not in columns:
            print("Adding 'favorite' column to briefings table...")
            await conn.execute(text(
                "ALTER TABLE briefings ADD COLUMN favorite BOOLEAN DEFAULT 0"
            ))
            print("Added 'favorite' column")
        else:
            print("'favorite' column already exists")
    
    await engine.dispose()
    print("Migration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())



