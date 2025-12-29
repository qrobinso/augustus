"""Migration to create articles table for storing fetched news articles."""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings


async def migrate():
    """Create articles table."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    
    async with engine.begin() as conn:
        # Check if articles table already exists
        result = await conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='articles'"
        ))
        articles_table_exists = result.fetchone() is not None
        
        if not articles_table_exists:
            print("Creating 'articles' table...")
            await conn.execute(text("""
                CREATE TABLE articles (
                    id VARCHAR(36) PRIMARY KEY,
                    title VARCHAR(500) NOT NULL,
                    summary TEXT,
                    url VARCHAR(1000) NOT NULL UNIQUE,
                    source VARCHAR(255) NOT NULL,
                    author VARCHAR(255),
                    content TEXT,
                    image_url VARCHAR(1000),
                    topic_id VARCHAR(36),
                    published DATETIME,
                    fetched_at DATETIME NOT NULL,
                    FOREIGN KEY (topic_id) REFERENCES topics(id)
                )
            """))
            
            # Create indexes for common queries
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_articles_topic_id ON articles(topic_id)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_articles_fetched_at ON articles(fetched_at DESC)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published DESC)
            """))
            
            print("Created 'articles' table with indexes")
        else:
            print("'articles' table already exists")
    
    await engine.dispose()
    print("Migration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())












