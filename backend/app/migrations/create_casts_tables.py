"""Migration to create casts and cast_members tables, add cast_id columns, and seed default casts."""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings


async def migrate():
    """Create casts tables, add cast_id columns, and seed default casts."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    
    async with engine.begin() as conn:
        # Check if casts table already exists
        result = await conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='casts'"
        ))
        casts_table_exists = result.fetchone() is not None
        
        if not casts_table_exists:
            print("Creating 'casts' table...")
            await conn.execute(text("""
                CREATE TABLE casts (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    is_default BOOLEAN NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """))
            print("Created 'casts' table")
        else:
            print("'casts' table already exists")
        
        # Check if cast_members table already exists
        result = await conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cast_members'"
        ))
        cast_members_table_exists = result.fetchone() is not None
        
        if not cast_members_table_exists:
            print("Creating 'cast_members' table...")
            await conn.execute(text("""
                CREATE TABLE cast_members (
                    id VARCHAR(36) PRIMARY KEY,
                    cast_id VARCHAR(36) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    voice_id VARCHAR(255) NOT NULL,
                    personality VARCHAR(255) NOT NULL,
                    "order" INTEGER NOT NULL,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY (cast_id) REFERENCES casts(id) ON DELETE CASCADE
                )
            """))
            print("Created 'cast_members' table")
        else:
            print("'cast_members' table already exists")
        
        # Add cast_id column to briefings table
        result = await conn.execute(text(
            "PRAGMA table_info(briefings)"
        ))
        briefings_columns = [row[1] for row in result.fetchall()]
        
        if 'cast_id' not in briefings_columns:
            print("Adding 'cast_id' column to 'briefings' table...")
            await conn.execute(text("""
                ALTER TABLE briefings ADD COLUMN cast_id VARCHAR(36)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_briefings_cast_id ON briefings(cast_id)
            """))
            print("Added 'cast_id' column to 'briefings' table")
        else:
            print("'cast_id' column already exists in 'briefings' table")
        
        # Add cast_id column to scheduled_briefings table
        result = await conn.execute(text(
            "PRAGMA table_info(scheduled_briefings)"
        ))
        scheduled_briefings_columns = [row[1] for row in result.fetchall()]
        
        if 'cast_id' not in scheduled_briefings_columns:
            print("Adding 'cast_id' column to 'scheduled_briefings' table...")
            await conn.execute(text("""
                ALTER TABLE scheduled_briefings ADD COLUMN cast_id VARCHAR(36)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_scheduled_briefings_cast_id ON scheduled_briefings(cast_id)
            """))
            print("Added 'cast_id' column to 'scheduled_briefings' table")
        else:
            print("'cast_id' column already exists in 'scheduled_briefings' table")
        
        # Add cast_id column to deepcasts table
        result = await conn.execute(text(
            "PRAGMA table_info(deepcasts)"
        ))
        deepcasts_columns = [row[1] for row in result.fetchall()]
        
        if 'cast_id' not in deepcasts_columns:
            print("Adding 'cast_id' column to 'deepcasts' table...")
            await conn.execute(text("""
                ALTER TABLE deepcasts ADD COLUMN cast_id VARCHAR(36)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_deepcasts_cast_id ON deepcasts(cast_id)
            """))
            print("Added 'cast_id' column to 'deepcasts' table")
        else:
            print("'cast_id' column already exists in 'deepcasts' table")
        
        # Add cast_id column to stations table
        result = await conn.execute(text(
            "PRAGMA table_info(stations)"
        ))
        stations_columns = [row[1] for row in result.fetchall()]
        
        if 'cast_id' not in stations_columns:
            print("Adding 'cast_id' column to 'stations' table...")
            await conn.execute(text("""
                ALTER TABLE stations ADD COLUMN cast_id VARCHAR(36)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_stations_cast_id ON stations(cast_id)
            """))
            print("Added 'cast_id' column to 'stations' table")
        else:
            print("'cast_id' column already exists in 'stations' table")
        
        # Seed default casts for all existing users
        print("Seeding default casts for existing users...")
        
        # Get all user IDs
        result = await conn.execute(text("SELECT id FROM users"))
        user_ids = [row[0] for row in result.fetchall()]
        
        # Use Gemini voices as defaults
        voice_host1 = "Kore"
        voice_host2 = "Puck"
        
        for user_id in user_ids:
            # Check if user already has a default cast
            result = await conn.execute(text("""
                SELECT id FROM casts WHERE user_id = :user_id AND is_default = 1
            """), {"user_id": user_id})
            existing_cast = result.fetchone()
            
            if not existing_cast:
                # Create default cast
                import uuid
                cast_id = str(uuid.uuid4())
                alex_id = str(uuid.uuid4())
                sam_id = str(uuid.uuid4())
                
                from datetime import datetime
                now = datetime.utcnow()
                
                await conn.execute(text("""
                    INSERT INTO casts (id, user_id, name, is_default, created_at, updated_at)
                    VALUES (:id, :user_id, :name, :is_default, :created_at, :updated_at)
                """), {
                    "id": cast_id,
                    "user_id": user_id,
                    "name": "Alex and Sam",
                    "is_default": 1,
                    "created_at": now,
                    "updated_at": now,
                })
                
                await conn.execute(text("""
                    INSERT INTO cast_members (id, cast_id, name, voice_id, personality, "order", created_at)
                    VALUES (:id, :cast_id, :name, :voice_id, :personality, :order, :created_at)
                """), {
                    "id": alex_id,
                    "cast_id": cast_id,
                    "name": "Alex",
                    "voice_id": voice_host1,
                    "personality": "Casual",
                    "order": 0,
                    "created_at": now,
                })
                
                await conn.execute(text("""
                    INSERT INTO cast_members (id, cast_id, name, voice_id, personality, "order", created_at)
                    VALUES (:id, :cast_id, :name, :voice_id, :personality, :order, :created_at)
                """), {
                    "id": sam_id,
                    "cast_id": cast_id,
                    "name": "Sam",
                    "voice_id": voice_host2,
                    "personality": "Analytical",
                    "order": 1,
                    "created_at": now,
                })
                
                print(f"Created default cast for user {user_id}")
            else:
                print(f"User {user_id} already has a default cast")
    
    await engine.dispose()
    print("Migration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())


