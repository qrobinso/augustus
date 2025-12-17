"""Migration to add listened columns to briefings table."""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings


async def migrate():
    """Add listened and listened_at columns to briefings table."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    
    async with engine.begin() as conn:
        # Check if columns already exist
        result = await conn.execute(text("PRAGMA table_info(briefings)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'listened' not in columns:
            print("Adding 'listened' column to briefings table...")
            await conn.execute(text(
                "ALTER TABLE briefings ADD COLUMN listened BOOLEAN DEFAULT 0"
            ))
            print("Added 'listened' column")
        else:
            print("'listened' column already exists")
        
        if 'listened_at' not in columns:
            print("Adding 'listened_at' column to briefings table...")
            await conn.execute(text(
                "ALTER TABLE briefings ADD COLUMN listened_at DATETIME"
            ))
            print("Added 'listened_at' column")
        else:
            print("'listened_at' column already exists")
    
    await engine.dispose()
    print("Migration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())


