"""Migration to add use_newsapi column to topics table."""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings


async def migrate():
    """Add use_newsapi column to topics table."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    
    async with engine.begin() as conn:
        # Check if column already exists
        result = await conn.execute(text("PRAGMA table_info(topics)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'use_newsapi' not in columns:
            print("Adding 'use_newsapi' column to topics table...")
            await conn.execute(text(
                "ALTER TABLE topics ADD COLUMN use_newsapi BOOLEAN DEFAULT 1"
            ))
            print("Added 'use_newsapi' column")
        else:
            print("'use_newsapi' column already exists")
    
    await engine.dispose()
    print("Migration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())









