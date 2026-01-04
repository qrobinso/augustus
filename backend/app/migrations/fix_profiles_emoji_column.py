"""Migration to fix profiles table - remove emoji NOT NULL constraint."""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings


async def migrate():
    """Recreate profiles table without emoji column (or with emoji having a default)."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    
    async with engine.begin() as conn:
        # SQLite approach: recreate the table without the emoji column
        # 1. Create new table with correct schema
        # 2. Copy data
        # 3. Drop old table
        # 4. Rename new table
        
        print("Recreating profiles table without emoji column...")
        
        # Step 1: Create new table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS profiles_new (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36) NOT NULL,
                name VARCHAR(100) NOT NULL,
                color VARCHAR(7) NOT NULL DEFAULT '#8B5CF6',
                is_admin BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """))
        print("Created profiles_new table")
        
        # Step 2: Copy data from old table
        await conn.execute(text("""
            INSERT INTO profiles_new (id, user_id, name, color, is_admin, created_at, updated_at)
            SELECT id, user_id, name, COALESCE(color, '#8B5CF6'), is_admin, created_at, updated_at
            FROM profiles
        """))
        print("Copied data to profiles_new")
        
        # Step 3: Drop old table
        await conn.execute(text("DROP TABLE profiles"))
        print("Dropped old profiles table")
        
        # Step 4: Rename new table
        await conn.execute(text("ALTER TABLE profiles_new RENAME TO profiles"))
        print("Renamed profiles_new to profiles")
        
        # Step 5: Recreate index
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON profiles(user_id)
        """))
        print("Recreated index")
        
        print("Migration complete!")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())

