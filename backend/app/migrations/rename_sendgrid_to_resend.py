"""Migration to rename sendgrid_api_key to resend_api_key in scheduled_briefings table."""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings


async def migrate():
    """Rename sendgrid_api_key column to resend_api_key."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    
    async with engine.begin() as conn:
        # Check if table exists
        result = await conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='scheduled_briefings'"
        ))
        table_exists = result.fetchone() is not None
        
        if not table_exists:
            print("'scheduled_briefings' table does not exist, skipping migration")
            await engine.dispose()
            return
        
        # Check if sendgrid_api_key column exists
        result = await conn.execute(text("PRAGMA table_info(scheduled_briefings)"))
        columns = {row[1]: row for row in result.fetchall()}
        
        if 'sendgrid_api_key' in columns and 'resend_api_key' not in columns:
            print("Renaming 'sendgrid_api_key' column to 'resend_api_key'...")
            # SQLite doesn't support ALTER TABLE RENAME COLUMN directly in older versions
            # We need to recreate the table with the new column name
            await conn.execute(text("""
                CREATE TABLE scheduled_briefings_new (
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
            
            # Copy data from old table to new table
            await conn.execute(text("""
                INSERT INTO scheduled_briefings_new 
                SELECT 
                    id, user_id, name, topic_ids, schedule_time, schedule_days,
                    notification_methods, email_recipients, webhook_url,
                    is_active, max_duration_minutes, sendgrid_api_key as resend_api_key,
                    last_generated_at, created_at, updated_at
                FROM scheduled_briefings
            """))
            
            # Drop old table
            await conn.execute(text("DROP TABLE scheduled_briefings"))
            
            # Rename new table
            await conn.execute(text("ALTER TABLE scheduled_briefings_new RENAME TO scheduled_briefings"))
            
            print("Renamed 'sendgrid_api_key' column to 'resend_api_key'")
        elif 'resend_api_key' in columns:
            print("'resend_api_key' column already exists, skipping migration")
        elif 'sendgrid_api_key' not in columns and 'resend_api_key' not in columns:
            # Neither column exists, add resend_api_key
            print("Adding 'resend_api_key' column to scheduled_briefings table...")
            await conn.execute(text(
                "ALTER TABLE scheduled_briefings ADD COLUMN resend_api_key VARCHAR(255)"
            ))
            print("Added 'resend_api_key' column")
        else:
            print("Migration not needed - column state is unexpected")
    
    await engine.dispose()
    print("Migration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())




















