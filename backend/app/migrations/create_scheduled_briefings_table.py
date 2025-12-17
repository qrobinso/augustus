"""Migration to create scheduled_briefings table."""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings


async def migrate():
    """Create scheduled_briefings table."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    
    async with engine.begin() as conn:
        # Check if table already exists
        result = await conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='scheduled_briefings'"
        ))
        table_exists = result.fetchone() is not None
        
        if not table_exists:
            print("Creating 'scheduled_briefings' table...")
            await conn.execute(text("""
                CREATE TABLE scheduled_briefings (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    name VARCHAR(500) NOT NULL,
                    topic_ids TEXT NOT NULL DEFAULT '[]',
                    schedule_time VARCHAR(10) NOT NULL,
                    schedule_days TEXT NOT NULL DEFAULT '[]',
                    notification_methods TEXT NOT NULL DEFAULT '[]',
                    email_recipients TEXT NOT NULL DEFAULT '[]',
                    webhook_url VARCHAR(500),
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    max_duration_minutes INTEGER NOT NULL DEFAULT 5,
                    resend_api_key VARCHAR(255),
                    last_generated_at DATETIME,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """))
            print("Created 'scheduled_briefings' table")
        else:
            print("'scheduled_briefings' table already exists")
    
    await engine.dispose()
    print("Migration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())
