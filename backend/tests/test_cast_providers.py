"""Provider inference, the cast provider column migration, and default uniqueness."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from app.migrations.add_tts_provider_to_casts import upgrade
from app.services.tts.registry import infer_cast_provider, provider_label


@pytest.mark.parametrize("voices, expected", [
    (["Kore", "Puck"], "gemini"),
    (["Zephyr"], "gemini"),
    (["CVRACyqNcQefTlxMj9bt", "rfkTsdZrVWEVhDycUYn9"], "elevenlabs"),
    (["af_heart:0.6,af_bella:0.4", "am_eric"], "piper"),
    (["en_US-lessac-medium"], "piper"),
    (["Puke", "Gacrux"], "fallback"),   # one typo means not all Gemini, and nothing else matches
    (["host1", "host2"], "fallback"),   # aliases are ambiguous between providers
    ([], "fallback"),
])
def test_infer_cast_provider(voices, expected):
    assert infer_cast_provider(voices, "fallback") == expected


def test_provider_label_known_and_unknown():
    assert provider_label("gemini") == "Google Gemini"
    assert provider_label("mystery") == "mystery"


LEGACY_SCHEMA = [
    """CREATE TABLE casts (id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36), profile_id VARCHAR(36),
       name VARCHAR(255), description VARCHAR(2000), is_default BOOLEAN, created_at DATETIME, updated_at DATETIME)""",
    """CREATE TABLE cast_members (id VARCHAR(36) PRIMARY KEY, cast_id VARCHAR(36), name VARCHAR(255),
       voice_id VARCHAR(255), personality VARCHAR(255), "order" INTEGER, created_at DATETIME)""",
]


async def _legacy_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        for ddl in LEGACY_SCHEMA:
            await conn.execute(text(ddl))
        casts = [
            ("g", 1, "2026-01-01"), ("e", 0, "2026-01-02"), ("k", 0, "2026-01-03"),
            ("x", 0, "2026-01-04"), ("g2", 1, "2026-01-05"),
        ]
        for cid, is_default, ts in casts:
            await conn.execute(text(
                "INSERT INTO casts VALUES (:id,'u','p',:id,NULL,:d,:ts,:ts)"), {"id": cid, "d": is_default, "ts": ts})
        members = [("g", "Kore"), ("g", "Puck"), ("e", "CVRACyqNcQefTlxMj9bt"),
                   ("k", "af_heart:0.6,af_bella:0.4"), ("x", "Puke"), ("g2", "Zephyr")]
        for i, (cid, voice) in enumerate(members):
            await conn.execute(text(
                "INSERT INTO cast_members VALUES (:id,:c,'Host',:v,'Casual',0,NULL)"), {"id": f"m{i}", "c": cid, "v": voice})
    return engine


@pytest.mark.asyncio
async def test_upgrade_backfills_dedupes_and_is_idempotent():
    engine = await _legacy_engine()
    async with engine.begin() as conn:
        assert await upgrade(conn, "voicebox") is True
    async with engine.begin() as conn:
        rows = dict((await conn.execute(text("SELECT id, tts_provider FROM casts"))).fetchall())
        assert rows == {"g": "gemini", "e": "elevenlabs", "k": "piper", "x": "voicebox", "g2": "gemini"}
        defaults = [r[0] for r in (await conn.execute(text("SELECT id FROM casts WHERE is_default = 1"))).fetchall()]
        assert defaults == ["g2"]  # the newest Gemini default wins
        assert await upgrade(conn, "voicebox") is False  # the second run is a no-op
    await engine.dispose()


@pytest.mark.asyncio
async def test_unique_default_per_provider_is_enforced():
    engine = await _legacy_engine()
    async with engine.begin() as conn:
        await upgrade(conn, "gemini")
    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await conn.execute(text("UPDATE casts SET is_default = 1 WHERE id = 'g'"))
    async with engine.begin() as conn:
        # A default for a different provider is allowed.
        await conn.execute(text("UPDATE casts SET is_default = 1 WHERE id = 'e'"))
    await engine.dispose()


@pytest.mark.asyncio
async def test_orm_schema_matches_migration(db_session):
    """Fresh databases get the same column and indexes from create_all, and upgrade is a no-op."""
    conn = await db_session.connection()
    assert await upgrade(conn, "gemini") is False
    indexes = {r[1] for r in (await conn.execute(text("PRAGMA index_list(casts)"))).fetchall()}
    assert {"ix_casts_scope_provider", "uq_casts_one_default_per_provider"} <= indexes


@pytest.mark.asyncio
async def test_unique_default_per_provider_covers_null_profile_on_create_all(db_session):
    """A NULL profile_id must not let two defaults slip past the unique index (create_all schema)."""
    conn = await db_session.connection()
    await conn.execute(text(
        "INSERT INTO casts (id, user_id, profile_id, name, is_default, tts_provider, created_at, updated_at) "
        "VALUES ('a','u',NULL,'A',1,'piper','2026-01-01','2026-01-01')"
    ))
    with pytest.raises(IntegrityError):
        await conn.execute(text(
            "INSERT INTO casts (id, user_id, profile_id, name, is_default, tts_provider, created_at, updated_at) "
            "VALUES ('b','u',NULL,'B',1,'piper','2026-01-02','2026-01-02')"
        ))


@pytest.mark.asyncio
async def test_unique_default_per_provider_covers_null_profile_after_upgrade():
    """Same guarantee on a legacy database once upgrade() has run, with profile_id NULL."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        for ddl in LEGACY_SCHEMA:
            await conn.execute(text(ddl))
        await conn.execute(text(
            "INSERT INTO casts VALUES ('a','u',NULL,'A',NULL,1,'2026-01-01','2026-01-01')"
        ))
        await upgrade(conn, "piper")
    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await conn.execute(text(
                "INSERT INTO casts (id, user_id, profile_id, name, description, is_default, "
                "created_at, updated_at, tts_provider) "
                "VALUES ('b','u',NULL,'B',NULL,1,'2026-01-02','2026-01-02','piper')"
            ))
    await engine.dispose()
