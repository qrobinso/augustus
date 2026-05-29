"""Migration to create api_keys and mcp_audit_log tables."""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings


async def migrate():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        result = await conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='api_keys'"
        ))
        if result.fetchone() is None:
            print("Creating 'api_keys' table...")
            await conn.execute(text("""
                CREATE TABLE api_keys (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    profile_id VARCHAR(36) NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    key_prefix VARCHAR(12) NOT NULL,
                    key_hash VARCHAR(64) NOT NULL UNIQUE,
                    enabled_tools JSON,
                    last_used_at DATETIME,
                    last_client VARCHAR(255),
                    revoked_at DATETIME,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (profile_id) REFERENCES profiles(id)
                )
            """))
            await conn.execute(text("CREATE INDEX idx_api_keys_user_id ON api_keys(user_id)"))
            await conn.execute(text("CREATE INDEX idx_api_keys_profile_id ON api_keys(profile_id)"))
            print("Created 'api_keys' table")
        else:
            print("'api_keys' table already exists")

        result = await conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='mcp_audit_log'"
        ))
        if result.fetchone() is None:
            print("Creating 'mcp_audit_log' table...")
            await conn.execute(text("""
                CREATE TABLE mcp_audit_log (
                    id VARCHAR(36) PRIMARY KEY,
                    api_key_id VARCHAR(36),
                    tool_name VARCHAR(100) NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    error VARCHAR(500),
                    duration_ms INTEGER,
                    client VARCHAR(255),
                    args_summary VARCHAR(500),
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE SET NULL
                )
            """))
            await conn.execute(text("CREATE INDEX idx_mcp_audit_api_key_id ON mcp_audit_log(api_key_id)"))
            await conn.execute(text("CREATE INDEX idx_mcp_audit_created_at ON mcp_audit_log(created_at)"))
            print("Created 'mcp_audit_log' table")
        else:
            print("'mcp_audit_log' table already exists")

        print("MCP migration complete!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
