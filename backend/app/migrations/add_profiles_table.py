"""Migration to create profiles table and add profile_id to content tables."""

import asyncio
import uuid
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings


async def migrate():
    """Create profiles table, add profile_id columns, and migrate existing data."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    
    async with engine.begin() as conn:
        # Step 1: Check if profiles table already exists
        result = await conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='profiles'"
        ))
        profiles_table_exists = result.fetchone() is not None
        
        if not profiles_table_exists:
            print("Creating 'profiles' table...")
            await conn.execute(text("""
                CREATE TABLE profiles (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    emoji VARCHAR(10) NOT NULL DEFAULT '👤',
                    is_admin BOOLEAN NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON profiles(user_id)
            """))
            print("Created 'profiles' table")
        else:
            print("'profiles' table already exists")
        
        # Step 2: Create admin profile for each existing user
        print("Creating admin profiles for existing users...")
        result = await conn.execute(text("SELECT id, name FROM users"))
        users = result.fetchall()
        
        admin_profile_ids = {}  # Map user_id -> admin_profile_id
        
        for user_id, user_name in users:
            # Check if user already has an admin profile
            result = await conn.execute(text("""
                SELECT id FROM profiles WHERE user_id = :user_id AND is_admin = 1
            """), {"user_id": user_id})
            existing_admin = result.fetchone()
            
            if existing_admin:
                admin_profile_ids[user_id] = existing_admin[0]
                print(f"User {user_id} already has admin profile {existing_admin[0]}")
            else:
                # Create admin profile
                profile_id = str(uuid.uuid4())
                now = datetime.utcnow()
                
                # Use user's name or "Admin" as profile name
                profile_name = user_name if user_name and user_name != "Default User" else "Admin"
                
                await conn.execute(text("""
                    INSERT INTO profiles (id, user_id, name, emoji, is_admin, created_at, updated_at)
                    VALUES (:id, :user_id, :name, :emoji, :is_admin, :created_at, :updated_at)
                """), {
                    "id": profile_id,
                    "user_id": user_id,
                    "name": profile_name,
                    "emoji": "👤",
                    "is_admin": 1,
                    "created_at": now,
                    "updated_at": now,
                })
                admin_profile_ids[user_id] = profile_id
                print(f"Created admin profile {profile_id} for user {user_id}")
        
        # Step 3: Add profile_id column to topics
        result = await conn.execute(text("PRAGMA table_info(topics)"))
        topics_columns = [row[1] for row in result.fetchall()]
        
        if 'profile_id' not in topics_columns:
            print("Adding 'profile_id' column to 'topics' table...")
            await conn.execute(text("""
                ALTER TABLE topics ADD COLUMN profile_id VARCHAR(36)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_topics_profile_id ON topics(profile_id)
            """))
            print("Added 'profile_id' column to 'topics' table")
        else:
            print("'profile_id' column already exists in 'topics' table")
        
        # Step 4: Add profile_id column to briefings
        result = await conn.execute(text("PRAGMA table_info(briefings)"))
        briefings_columns = [row[1] for row in result.fetchall()]
        
        if 'profile_id' not in briefings_columns:
            print("Adding 'profile_id' column to 'briefings' table...")
            await conn.execute(text("""
                ALTER TABLE briefings ADD COLUMN profile_id VARCHAR(36)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_briefings_profile_id ON briefings(profile_id)
            """))
            print("Added 'profile_id' column to 'briefings' table")
        else:
            print("'profile_id' column already exists in 'briefings' table")
        
        # Step 5: Add profile_id column to casts
        result = await conn.execute(text("PRAGMA table_info(casts)"))
        casts_columns = [row[1] for row in result.fetchall()]
        
        if 'profile_id' not in casts_columns:
            print("Adding 'profile_id' column to 'casts' table...")
            await conn.execute(text("""
                ALTER TABLE casts ADD COLUMN profile_id VARCHAR(36)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_casts_profile_id ON casts(profile_id)
            """))
            print("Added 'profile_id' column to 'casts' table")
        else:
            print("'profile_id' column already exists in 'casts' table")
        
        # Step 6: Add profile_id column to scheduled_briefings
        result = await conn.execute(text("PRAGMA table_info(scheduled_briefings)"))
        scheduled_briefings_columns = [row[1] for row in result.fetchall()]
        
        if 'profile_id' not in scheduled_briefings_columns:
            print("Adding 'profile_id' column to 'scheduled_briefings' table...")
            await conn.execute(text("""
                ALTER TABLE scheduled_briefings ADD COLUMN profile_id VARCHAR(36)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_scheduled_briefings_profile_id ON scheduled_briefings(profile_id)
            """))
            print("Added 'profile_id' column to 'scheduled_briefings' table")
        else:
            print("'profile_id' column already exists in 'scheduled_briefings' table")
        
        # Step 7: Migrate existing data to admin profiles
        print("Migrating existing content to admin profiles...")
        
        for user_id, admin_profile_id in admin_profile_ids.items():
            # Update topics
            result = await conn.execute(text("""
                UPDATE topics SET profile_id = :profile_id 
                WHERE user_id = :user_id AND profile_id IS NULL
            """), {"profile_id": admin_profile_id, "user_id": user_id})
            print(f"Updated {result.rowcount} topics for user {user_id}")
            
            # Update briefings
            result = await conn.execute(text("""
                UPDATE briefings SET profile_id = :profile_id 
                WHERE user_id = :user_id AND profile_id IS NULL
            """), {"profile_id": admin_profile_id, "user_id": user_id})
            print(f"Updated {result.rowcount} briefings for user {user_id}")
            
            # Update casts
            result = await conn.execute(text("""
                UPDATE casts SET profile_id = :profile_id 
                WHERE user_id = :user_id AND profile_id IS NULL
            """), {"profile_id": admin_profile_id, "user_id": user_id})
            print(f"Updated {result.rowcount} casts for user {user_id}")
            
            # Update scheduled_briefings
            result = await conn.execute(text("""
                UPDATE scheduled_briefings SET profile_id = :profile_id 
                WHERE user_id = :user_id AND profile_id IS NULL
            """), {"profile_id": admin_profile_id, "user_id": user_id})
            print(f"Updated {result.rowcount} scheduled_briefings for user {user_id}")
        
        print("Migration complete!")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())

