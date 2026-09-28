# Voicebox Provider and Provider-Scoped Casts: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each cast belongs to one TTS provider. Casts follow the provider that is active in Settings. A new Voicebox provider generates briefings with the cloned voices on any Voicebox server.

**Architecture:**
- A provider registry (`app/services/tts/registry.py`) is the single source of truth for provider IDs, labels, capabilities, voice listing, and timeout budgets.
- Casts get a `tts_provider` column. An idempotent startup migration adds and backfills it. The database enforces one default cast per provider.
- `VoiceboxClient` covers the Voicebox HTTP API. `VoiceboxProvider` uses it to render lines with bounded concurrency and stitch them on disk.
- The frontend reads providers, voices, and counts from the API. It never hard-codes provider lists.

**Tech Stack:** FastAPI, async SQLAlchemy on SQLite, httpx (`MockTransport` in tests), pydub and the `wave` module, pytest with pytest-asyncio, React with TanStack Query, and vitest.

**Spec:** `docs/superpowers/specs/2026-09-27-voicebox-and-provider-casts-design.md`

## Global Constraints

- Work directly on `main` (AGENTS.md). Use exactly two feature commits: Task 6 ends Part 1, and Task 11 ends Part 2. The pre-commit hook bumps the patch version and stages the version files.
- Backend Python lives in `backend/venv`: run `backend/venv/bin/pytest` from `backend/`. System python3 is 3.9, which is too old.
- For node and npm, first run `eval "$(/opt/homebrew/bin/brew shellenv)"`, then work from `frontend/`.
- ffmpeg is not installed on the dev machine. Tests must not need it. Build WAVs with the `wave` module.
- Tests pass on `main` before this work starts: 202 backend and 99 frontend. They must still pass after every task.
- Provider IDs are exactly `piper`, `elevenlabs`, `gemini`, and `voicebox`.
- The Voicebox model table is the one in the spec's "Part 2 → Settings" section. Copy it verbatim.
- `VOICEBOX_URL` has no default. The placeholder text is `http://localhost:17493`.
- The error copy is verbatim:
  - `No {Label} cast yet. Create one on the Casts page.`
  - `'{cast name}' is a {Label} cast; your voice provider is {Label}.`
  - `'{voice}' isn't a Voicebox voice. Edit the cast.`
  - `Can't reach Voicebox at {url}.`
- Do not hard-code a version in the UI or API (AGENTS.md).
- Another session (`augustus-1a`) committed UI refactors to `main` during planning. Run `git pull`/`git log -3` before each task. If `CreateCast.tsx`, `Casts.tsx`, `Settings.tsx`, or `TtsSettings.tsx` changed since this plan was written, reapply that task's intent to the current code rather than pasting blocks blindly.

## Review Focus

1. **A cast from another provider on a schedule.** The schedule must still produce a briefing with the active provider's default cast. It must not fail. The implicit-mismatch test in Task 3 covers this.
2. **Switching provider leaves the frontend cast list stale.** After a Settings change, the dashboard cast picker must show the new provider's casts without a reload. Task 6 invalidates `['casts']` whenever `tts_provider` changes, and the manual check covers it.
3. **Several defaults in legacy data, or two concurrent set-default calls.** The migration deduplicates defaults and the unique index rejects a second one. The dedupe and index tests are in Task 1.
4. **Voicebox profile names with stray whitespace, such as the real `"Halie "`.** Resolution must still match `Halie`. The trimmed-name test is in Task 8.
5. **Voicebox lines in different sample rates.** Chatterbox is 24 kHz and other engines may be 44.1 kHz. The stitched output must not speed up or slow down any line. The mixed-rate stitch test is in Task 8.

---

# Part 1: Provider-scoped casts

### Task 1: Provider registry, cast provider column, and migration

**Files:**
- Create: `backend/app/services/tts/registry.py`
- Modify: `backend/app/models/cast.py`: add the column and the table indexes to `Cast`
- Create: `backend/app/migrations/add_tts_provider_to_casts.py`
- Modify: `backend/app/database.py`: `init_db()`
- Modify: `backend/tests/conftest.py`: add an autouse fixture that pins the provider
- Test: `backend/tests/test_cast_providers.py`

**Interfaces:**
- Produces:
  - `registry.TTS_PROVIDERS: dict[str, ProviderSpec]`
  - `registry.ProviderSpec(id: str, label: str, allows_custom_voice: bool)`
  - `registry.provider_label(provider: str) -> str`
  - `registry.active_tts_provider() -> str`
  - `registry.infer_cast_provider(voice_ids: Iterable[str], fallback: str) -> str`
  - `registry.list_provider_voices(provider: str) -> Awaitable[list[Voice]]`
  - `Cast.tts_provider: str`
  - `add_tts_provider_to_casts.upgrade(conn: AsyncConnection, fallback_provider: str) -> bool`

- [ ] **Step 1: Pin the provider for every test**

Append this to `backend/tests/conftest.py`:

```python
@pytest.fixture(autouse=True)
def _pin_tts_provider(monkeypatch):
    """Tests must not depend on the developer's .env TTS provider."""
    from app.config import get_settings
    monkeypatch.setenv("TTS_PROVIDER", "gemini")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
```

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_cast_providers.py`:

```python
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
```

- [ ] **Step 3: Run the tests and confirm they fail**

Run: `cd backend && venv/bin/pytest tests/test_cast_providers.py -v`
Expected: collection fails with `ModuleNotFoundError: No module named 'app.migrations.add_tts_provider_to_casts'`.

- [ ] **Step 4: Create the registry**

Create `backend/app/services/tts/registry.py`:

```python
"""Single source of truth for TTS providers: ids, labels, capabilities and voices.

Adding a provider = a registry entry, a TTSProvider class in the factory, a
voice-listing branch below and a Settings card. Nothing else hard-codes the list.
"""

import re
from dataclasses import dataclass
from typing import Iterable

from app.config import get_settings
from app.services.tts.base import Voice


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    label: str
    # The built-in catalogs for these providers are partial, so casts may use raw IDs.
    allows_custom_voice: bool


TTS_PROVIDERS: dict[str, ProviderSpec] = {
    "piper": ProviderSpec("piper", "Piper", allows_custom_voice=True),
    "elevenlabs": ProviderSpec("elevenlabs", "ElevenLabs", allows_custom_voice=True),
    "gemini": ProviderSpec("gemini", "Google Gemini", allows_custom_voice=False),
}


def provider_label(provider: str) -> str:
    spec = TTS_PROVIDERS.get(provider)
    return spec.label if spec else provider


def active_tts_provider() -> str:
    return get_settings().tts_provider


_ELEVENLABS_ID = re.compile(r"^[A-Za-z0-9]{20}$")
_KOKORO_VOICE = re.compile(r"^[a-z]{2}_[a-z]+$")  # af_heart, am_eric
_PIPER_MODEL = re.compile(r"^[a-z]{2}_[A-Z]{2}-")  # en_US-lessac-medium


def _looks_like_piper(voice_id: str) -> bool:
    return (
        ":" in voice_id
        or "," in voice_id  # Kokoro blends such as "af_heart:0.6,af_bella:0.4"
        or bool(_KOKORO_VOICE.match(voice_id))
        or bool(_PIPER_MODEL.match(voice_id))
    )


def infer_cast_provider(voice_ids: Iterable[str], fallback: str) -> str:
    """Best-effort provider for a legacy cast, judged from its member voice IDs."""
    from app.services.tts.gemini import GeminiProvider

    ids = [v.strip() for v in voice_ids if v and v.strip()]
    if not ids:
        return fallback
    if all(v in GeminiProvider.VOICES for v in ids):
        return "gemini"
    if any(_ELEVENLABS_ID.match(v) for v in ids):
        return "elevenlabs"
    if any(_looks_like_piper(v) for v in ids):
        return "piper"
    return fallback


async def list_provider_voices(provider: str) -> list[Voice]:
    """Voices a cast can use with this provider, de-duplicated by id."""
    if provider == "gemini":
        from app.services.tts.gemini import GeminiProvider
        voices = list(GeminiProvider.VOICES.values())
    elif provider == "elevenlabs":
        from app.services.tts.elevenlabs import ElevenLabsProvider
        voices = list(ElevenLabsProvider.VOICES.values())
    elif provider == "piper":
        from app.services.tts.piper import PiperProvider
        voices = list(PiperProvider.VOICES.values())
    else:
        raise ValueError(f"Unknown TTS provider: {provider}")
    unique: dict[str, Voice] = {}
    for voice in voices:
        unique.setdefault(voice.id, voice)
    return list(unique.values())
```

- [ ] **Step 5: Add the column and indexes to the model**

In `backend/app/models/cast.py`, change the SQLAlchemy import line to:

```python
from sqlalchemy import String, DateTime, ForeignKey, Integer, Boolean, Index, text
```

In `class Cast`, add these directly after `__tablename__ = "casts"`:

```python
    __table_args__ = (
        Index("ix_casts_scope_provider", "user_id", "profile_id", "tts_provider"),
        # The database, not just the service, guarantees one default per provider.
        Index(
            "uq_casts_one_default_per_provider",
            "user_id", "profile_id", "tts_provider",
            unique=True,
            sqlite_where=text("is_default = 1"),
        ),
    )
```

Add this directly after the `is_default` column:

```python
    tts_provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="gemini",
        doc="TTS provider whose voices this cast uses (see services/tts/registry.py)",
    )
```

- [ ] **Step 6: Write the migration**

Create `backend/app/migrations/add_tts_provider_to_casts.py`:

```python
"""Add casts.tts_provider, backfill it from member voices, and enforce one default per provider.

Runs on every startup from init_db() and is idempotent. It can also be run by hand:
    python -m app.migrations.add_tts_provider_to_casts
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.config import get_settings
from app.services.tts.registry import infer_cast_provider


async def upgrade(conn: AsyncConnection, fallback_provider: str) -> bool:
    """Return True when the column was added and backfilled on this run."""
    columns = [row[1] for row in (await conn.execute(text("PRAGMA table_info(casts)"))).fetchall()]
    if not columns:
        return False
    added = "tts_provider" not in columns
    if added:
        await conn.execute(text(
            "ALTER TABLE casts ADD COLUMN tts_provider VARCHAR(32) NOT NULL DEFAULT 'gemini'"
        ))
        voices: dict[str, list[str]] = {}
        for cast_id, voice_id in (await conn.execute(text("SELECT cast_id, voice_id FROM cast_members"))).fetchall():
            voices.setdefault(cast_id, []).append(voice_id)
        for (cast_id,) in (await conn.execute(text("SELECT id FROM casts"))).fetchall():
            provider = infer_cast_provider(voices.get(cast_id, []), fallback_provider)
            await conn.execute(
                text("UPDATE casts SET tts_provider = :provider WHERE id = :id"),
                {"provider": provider, "id": cast_id},
            )
            print(f"[Migration] Cast {cast_id} -> {provider}")
    # Keep only the newest default per (user, profile, provider) before enforcing uniqueness.
    await conn.execute(text("""
        UPDATE casts SET is_default = 0
        WHERE is_default = 1 AND id NOT IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY user_id, profile_id, tts_provider
                    ORDER BY updated_at DESC, created_at DESC
                ) AS rn
                FROM casts WHERE is_default = 1
            ) WHERE rn = 1
        )
    """))
    await conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_casts_scope_provider ON casts (user_id, profile_id, tts_provider)"
    ))
    await conn.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_casts_one_default_per_provider "
        "ON casts (user_id, profile_id, tts_provider) WHERE is_default = 1"
    ))
    return added


async def migrate():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        added = await upgrade(conn, settings.tts_provider)
    await engine.dispose()
    print("Added and backfilled casts.tts_provider" if added else "casts.tts_provider already present")


if __name__ == "__main__":
    asyncio.run(migrate())
```

- [ ] **Step 7: Run the migration on startup**

In `backend/app/database.py`, replace the body of `init_db()` after the model imports with:

```python
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Existing databases need columns that create_all cannot add.
        from app.migrations.add_tts_provider_to_casts import upgrade as upgrade_cast_providers
        await upgrade_cast_providers(conn, settings.tts_provider)
```

`settings` is already the module-level `get_settings()` result in `database.py`.

- [ ] **Step 8: Run the tests and confirm they pass**

Run: `cd backend && venv/bin/pytest tests/test_cast_providers.py -v && venv/bin/pytest -q`
Expected: the new tests pass, and the full suite passes (202 or more tests).

- [ ] **Step 9: Stage the changes**

Do not commit here. Part 1 commits once, at Task 6.

```bash
git add backend/app/services/tts/registry.py backend/app/models/cast.py backend/app/migrations/add_tts_provider_to_casts.py backend/app/database.py backend/tests/conftest.py backend/tests/test_cast_providers.py
```

---

### Task 2: Scope CastService to a provider

**Files:**
- Modify: `backend/app/services/cast.py` (rewrite the methods listed below)
- Modify: `backend/app/routers/casts.py`: pass the active provider through and map the new errors to HTTP 400
- Modify: `backend/app/routers/profiles.py`: `_seed_default_cast` stamps `tts_provider="gemini"`
- Test: `backend/tests/test_cast_service_providers.py`

**Interfaces:**
- Consumes: `registry.active_tts_provider()`, `registry.provider_label()`, and `Cast.tts_provider` from Task 1.
- Produces (all in `app.services.cast`):
  - `class NoCastForProviderError(LookupError)`, raised with the message `No {Label} cast yet. Create one on the Casts page.`
  - `class CastProviderMismatchError(ValueError)`
  - `provider_mismatch_message(cast_name: str, cast_provider: str, active_provider: str) -> str`
  - `CastService.create_cast(user_id, cast_data, profile_id, provider) -> Cast`
  - `CastService.get_user_casts(user_id, profile_id=None, provider: Optional[str]=None) -> list[Cast]`, where `None` means every provider
  - `CastService.get_default_cast(user_id, profile_id, provider) -> Cast`, which raises `NoCastForProviderError`
  - `CastService.set_default_cast(cast_id, user_id, profile_id, provider) -> Optional[Cast]`
  - `CastService.update_cast(cast_id, user_id, cast_data, profile_id, provider) -> Optional[Cast]`
  - `CastService.restore_default_cast(user_id, profile_id, provider) -> Cast`
  - `CastService.ensure_usable(cast: Cast, provider: str) -> None`, which raises `CastProviderMismatchError`
  - `CastService.count_by_provider(user_id, profile_id) -> dict[str, int]`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_cast_service_providers.py`:

```python
"""CastService respects the provider a cast belongs to."""
import pytest

from app.models.cast import Cast
from app.schemas.cast import CastCreate, CastMemberBase, CastUpdate
from app.services.cast import (
    CastProviderMismatchError, CastService, NoCastForProviderError, provider_mismatch_message,
)


def _cast(name, voice="Kore"):
    return CastCreate(name=name, members=[CastMemberBase(name="Alex", voice_id=voice, personality="Casual", order=0)])


@pytest.mark.asyncio
async def test_first_cast_per_provider_becomes_default_and_later_ones_do_not(db_session):
    service = CastService(db_session)
    first = await service.create_cast("u", _cast("One"), profile_id="p", provider="gemini")
    second = await service.create_cast("u", _cast("Two"), profile_id="p", provider="gemini")
    other = await service.create_cast("u", _cast("Kokoro", "am_eric"), profile_id="p", provider="piper")
    assert (first.is_default, second.is_default, other.is_default) == (True, False, True)
    assert first.tts_provider == "gemini" and other.tts_provider == "piper"
    # Regression: creating a cast must not clear the existing default.
    assert (await service.get_default_cast("u", "p", "gemini")).id == first.id


@pytest.mark.asyncio
async def test_listing_is_scoped_by_provider(db_session):
    service = CastService(db_session)
    await service.create_cast("u", _cast("G"), profile_id="p", provider="gemini")
    await service.create_cast("u", _cast("P", "am_eric"), profile_id="p", provider="piper")
    assert [c.name for c in await service.get_user_casts("u", "p", provider="piper")] == ["P"]
    assert {c.name for c in await service.get_user_casts("u", "p")} == {"G", "P"}
    assert await service.count_by_provider("u", "p") == {"gemini": 1, "piper": 1}


@pytest.mark.asyncio
async def test_default_missing_raises_with_user_facing_message(db_session):
    service = CastService(db_session)
    await service.create_cast("u", _cast("G"), profile_id="p", provider="gemini")
    with pytest.raises(NoCastForProviderError, match="^No Piper cast yet. Create one on the Casts page.$"):
        await service.get_default_cast("u", "p", "piper")


@pytest.mark.asyncio
async def test_default_promotes_oldest_when_none_marked(db_session):
    db_session.add_all([
        Cast(id="old", user_id="u", profile_id="p", name="Old", tts_provider="piper", is_default=False),
        Cast(id="new", user_id="u", profile_id="p", name="New", tts_provider="piper", is_default=False),
    ])
    await db_session.commit()
    default = await CastService(db_session).get_default_cast("u", "p", "piper")
    assert default.id == "old" and default.is_default is True


@pytest.mark.asyncio
async def test_set_default_switches_within_provider_and_rejects_other_providers(db_session):
    service = CastService(db_session)
    a = await service.create_cast("u", _cast("A"), profile_id="p", provider="gemini")
    b = await service.create_cast("u", _cast("B"), profile_id="p", provider="gemini")
    v = await service.create_cast("u", _cast("V", "am_eric"), profile_id="p", provider="piper")
    assert (await service.set_default_cast(b.id, "u", "p", "gemini")).is_default is True
    await db_session.refresh(a)
    assert a.is_default is False
    with pytest.raises(CastProviderMismatchError, match="'V' is a Piper cast; your voice provider is Google Gemini."):
        await service.set_default_cast(v.id, "u", "p", "gemini")


@pytest.mark.asyncio
async def test_update_rejects_casts_of_another_provider(db_session):
    service = CastService(db_session)
    v = await service.create_cast("u", _cast("V", "am_eric"), profile_id="p", provider="piper")
    with pytest.raises(CastProviderMismatchError):
        await service.update_cast(v.id, "u", CastUpdate(name="Renamed"), "p", "gemini")


@pytest.mark.asyncio
async def test_restore_default_is_gemini_only(db_session):
    service = CastService(db_session)
    with pytest.raises(CastProviderMismatchError, match="only available for Google Gemini"):
        await service.restore_default_cast("u", "p", "piper")
    restored = await service.restore_default_cast("u", "p", "gemini")
    assert restored.tts_provider == "gemini" and restored.is_default is True
    assert [m.voice_id for m in restored.members] == ["Kore", "Puck"]


def test_mismatch_message_copy():
    assert provider_mismatch_message("Gemini Pro Cast", "gemini", "piper") == (
        "'Gemini Pro Cast' is a Google Gemini cast; your voice provider is Piper."
    )
```

Part 1 tests use `piper` as the "other" provider because `voicebox` has no registry entry until Task 7.

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd backend && venv/bin/pytest tests/test_cast_service_providers.py -v`
Expected: `ImportError: cannot import name 'CastProviderMismatchError'`.

- [ ] **Step 3: Implement the service changes**

In `backend/app/services/cast.py`:

1. Update the imports and add the errors after them:

```python
import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.cast import Cast, CastMember
from app.schemas.cast import CastCreate, CastUpdate
from app.services.tts.registry import provider_label


class NoCastForProviderError(LookupError):
    """The active TTS provider has no cast for this profile."""

    def __init__(self, provider: str):
        super().__init__(f"No {provider_label(provider)} cast yet. Create one on the Casts page.")
        self.provider = provider


class CastProviderMismatchError(ValueError):
    """A cast was used or edited with a provider it does not belong to."""


def provider_mismatch_message(cast_name: str, cast_provider: str, active_provider: str) -> str:
    return (
        f"'{cast_name}' is a {provider_label(cast_provider)} cast; "
        f"your voice provider is {provider_label(active_provider)}."
    )
```

2. Add a scope helper at the top of `CastService`:

```python
    @staticmethod
    def _scoped(query, user_id: str, profile_id: Optional[str], provider: Optional[str]):
        query = query.where(Cast.user_id == user_id)
        if profile_id:
            query = query.where(Cast.profile_id == profile_id)
        if provider:
            query = query.where(Cast.tts_provider == provider)
        return query

    def ensure_usable(self, cast: Cast, provider: str) -> None:
        if cast.tts_provider != provider:
            raise CastProviderMismatchError(provider_mismatch_message(cast.name, cast.tts_provider, provider))
```

3. Replace `create_cast`. Keep the existing member-count and order validation lines, then continue:

```python
    async def create_cast(
        self,
        user_id: str,
        cast_data: CastCreate,
        profile_id: Optional[str],
        provider: str,
    ) -> Cast:
        """Create a cast for the given provider; the provider's first cast becomes its default."""
        if len(cast_data.members) < 1 or len(cast_data.members) > 3:
            raise ValueError("Cast must have 1-3 members")
        orders = [m.order for m in cast_data.members]
        if sorted(orders) != list(range(len(cast_data.members))):
            raise ValueError("Member orders must be sequential starting from 0")

        existing = await self.db.scalar(
            self._scoped(select(func.count(Cast.id)), user_id, profile_id, provider)
        )
        cast = Cast(
            id=str(uuid.uuid4()),
            user_id=user_id,
            profile_id=profile_id,
            name=cast_data.name,
            description=cast_data.description,
            tts_provider=provider,
            is_default=existing == 0,
        )
        self.db.add(cast)
        await self.db.flush()
        for member_data in cast_data.members:
            self.db.add(CastMember(
                id=str(uuid.uuid4()),
                cast_id=cast.id,
                name=member_data.name,
                voice_id=member_data.voice_id,
                personality=member_data.personality,
                order=member_data.order,
            ))
        await self.db.commit()
        await self.db.refresh(cast)
        await self.db.refresh(cast, ["members"])
        return cast
```

4. Replace `get_user_casts` and add `count_by_provider`:

```python
    async def get_user_casts(
        self, user_id: str, profile_id: Optional[str] = None, provider: Optional[str] = None,
    ) -> list[Cast]:
        """Casts for a user/profile; provider=None returns every provider's casts."""
        result = await self.db.execute(
            self._scoped(select(Cast), user_id, profile_id, provider)
            .options(selectinload(Cast.members))
            .order_by(Cast.is_default.desc(), Cast.created_at.desc())
        )
        return list(result.scalars().all())

    async def count_by_provider(self, user_id: str, profile_id: Optional[str]) -> dict[str, int]:
        rows = await self.db.execute(
            self._scoped(select(Cast.tts_provider, func.count(Cast.id)), user_id, profile_id, None)
            .group_by(Cast.tts_provider)
        )
        return {provider: count for provider, count in rows.all()}
```

5. Replace `get_default_cast`:

```python
    async def get_default_cast(self, user_id: str, profile_id: Optional[str], provider: str) -> Cast:
        """The provider's default cast. Promotes the oldest cast if none is marked.

        Raises NoCastForProviderError when the provider has no casts at all; casts
        are never created implicitly.
        """
        query = self._scoped(select(Cast), user_id, profile_id, provider).options(selectinload(Cast.members))
        default = (await self.db.execute(query.where(Cast.is_default == True))).scalar_one_or_none()  # noqa: E712
        if default:
            return default
        oldest = (await self.db.execute(query.order_by(Cast.created_at.asc()).limit(1))).scalar_one_or_none()
        if oldest is None:
            raise NoCastForProviderError(provider)
        oldest.is_default = True
        await self.db.commit()
        await self.db.refresh(oldest, ["members"])
        return oldest
```

6. `update_cast` gains a trailing `provider: str` parameter. Right after `if not cast: return None`, add `self.ensure_usable(cast, provider)`. Also remove the stray duplicate `await self.db.execute(select(CastMember)...)` statement that precedes the real member query.

7. Replace `set_default_cast` and `_unset_default_casts`:

```python
    async def set_default_cast(
        self, cast_id: str, user_id: str, profile_id: Optional[str], provider: str,
    ) -> Optional[Cast]:
        cast = await self.get_cast(cast_id, user_id, profile_id)
        if not cast:
            return None
        self.ensure_usable(cast, provider)
        await self._unset_default_casts(user_id, profile_id, provider)
        # Flush the unset first: the partial unique index allows one default per provider.
        await self.db.flush()
        cast.is_default = True
        await self.db.commit()
        await self.db.refresh(cast)
        return cast

    async def _unset_default_casts(self, user_id: str, profile_id: Optional[str], provider: str):
        result = await self.db.execute(
            self._scoped(select(Cast), user_id, profile_id, provider).where(Cast.is_default == True)  # noqa: E712
        )
        for cast in result.scalars().all():
            cast.is_default = False
```

8. Replace `restore_default_cast`. The member-creation block stays as it is (Alex/Kore and Sebastian/Puck):

```python
    async def restore_default_cast(self, user_id: str, profile_id: Optional[str], provider: str) -> Cast:
        """Reset the Gemini default cast to the built-in hosts (Gemini voices only)."""
        if provider != "gemini":
            raise CastProviderMismatchError(
                f"Restore defaults is only available for Google Gemini casts, not {provider_label(provider)}."
            )
        query = (
            self._scoped(select(Cast), user_id, profile_id, "gemini")
            .where(Cast.is_default == True)  # noqa: E712
            .options(selectinload(Cast.members))
        )
        default_cast = (await self.db.execute(query)).scalar_one_or_none()
        if default_cast is None:
            default_cast = Cast(
                id=str(uuid.uuid4()), user_id=user_id, profile_id=profile_id,
                name="Augustus Daily", tts_provider="gemini", is_default=True,
            )
            self.db.add(default_cast)
            await self.db.flush()
            await self.db.refresh(default_cast, ["members"])
        default_cast.name = "Augustus Daily"
        for member in list(default_cast.members):
            await self.db.delete(member)
        # ...existing alex (Kore, order 0) / sam (Puck, order 1) CastMember creation unchanged...
```

Keep the rest of the existing method (adding `alex` and `sam`, committing, and refreshing) as it is. Delete the old implicit-create body of `get_default_cast`; it is not reused.

- [ ] **Step 4: Wire the routers**

In `backend/app/routers/casts.py`:
- Import `from app.services.tts.registry import active_tts_provider` and `from app.services.cast import CastService, CastProviderMismatchError, NoCastForProviderError`.
- Update each call:
  - `create_cast(user.id, cast_data, profile_id=profile.id, provider=active_tts_provider())`
  - `update_cast(cast_id, user.id, cast_data, profile.id, active_tts_provider())`
  - `set_default_cast(cast_id, user.id, profile.id, active_tts_provider())`
  - `restore_default_cast(user.id, profile.id, active_tts_provider())`
  - `list_casts` stays as it is until Task 4.
- Wrap set-default and restore in `try/except CastProviderMismatchError as e: raise HTTPException(400, str(e))`. `update_cast` already maps `ValueError` to 400, and `CastProviderMismatchError` is a `ValueError`.
- Update the restore docstring to: `"""Restore the Gemini default cast to its original hosts (Alex/Kore, Sebastian/Puck)."""`

In `backend/app/routers/profiles.py` `_seed_default_cast`, add `tts_provider="gemini",` to the `Cast(...)` constructor.

- [ ] **Step 5: Run the tests**

Run: `cd backend && venv/bin/pytest tests/test_cast_service_providers.py -v && venv/bin/pytest -q`
Expected: the new tests pass. The full suite may fail in `briefing.py` callers of `get_default_cast`; Task 3 fixes those. If any failure is outside `briefing.py` or `breakout`, fix it now.

- [ ] **Step 6: Stage the changes**

```bash
git add backend/app/services/cast.py backend/app/routers/casts.py backend/app/routers/profiles.py backend/tests/test_cast_service_providers.py
```

---

### Task 3: Resolve the cast at generation time and check it at request time

**Files:**
- Modify: `backend/app/services/cast.py`: add `resolve_for_generation`
- Modify: `backend/app/services/briefing.py`: replace the step-5 cast lookup, and pass `provider_name` to TTS
- Modify: `backend/app/routers/briefings.py`: `generate_briefing` rejects a mismatched or missing cast
- Modify: `backend/app/services/breakout_request.py`: an explicit cast gets 400; an implicit cast falls back
- Test: `backend/tests/test_cast_resolution.py`

**Interfaces:**
- Consumes: the Task 2 service API.
- Produces: `CastService.resolve_for_generation(user_id: str, profile_id: Optional[str], cast_id: Optional[str], provider: str) -> Cast`. It raises `NoCastForProviderError`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_cast_resolution.py`:

```python
"""Which cast a briefing uses, for explicit and implicit cast choices."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from app.database import get_db
from app.models.briefing import Briefing
from app.models.cast import Cast
from app.routers import briefings as routes
from app.routers.auth import get_current_user
from app.routers.profiles import get_current_profile
from app.services.cast import CastService, NoCastForProviderError


async def _seed(db, *casts):
    db.add_all(casts)
    await db.commit()


@pytest.mark.asyncio
async def test_resolve_uses_matching_cast(db_session):
    await _seed(db_session, Cast(id="g", user_id="u", profile_id="p", name="G", tts_provider="gemini", is_default=True))
    assert (await CastService(db_session).resolve_for_generation("u", "p", "g", "gemini")).id == "g"


@pytest.mark.asyncio
async def test_resolve_falls_back_for_other_provider_or_missing_cast(db_session):
    await _seed(db_session,
        Cast(id="g", user_id="u", profile_id="p", name="G", tts_provider="gemini", is_default=True),
        Cast(id="v", user_id="u", profile_id="p", name="V", tts_provider="piper", is_default=True))
    service = CastService(db_session)
    assert (await service.resolve_for_generation("u", "p", "v", "gemini")).id == "g"      # schedule's cast
    assert (await service.resolve_for_generation("u", "p", "gone", "gemini")).id == "g"   # deleted cast
    assert (await service.resolve_for_generation("u", "p", None, "gemini")).id == "g"


@pytest.mark.asyncio
async def test_resolve_raises_when_provider_has_no_cast(db_session):
    await _seed(db_session, Cast(id="g", user_id="u", profile_id="p", name="G", tts_provider="gemini", is_default=True))
    with pytest.raises(NoCastForProviderError):
        await CastService(db_session).resolve_for_generation("u", "p", "g", "piper")


@pytest.fixture
def api_app(db_session, monkeypatch):
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/briefings")
    async def db():
        yield db_session
    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u")
    app.dependency_overrides[get_current_profile] = lambda: SimpleNamespace(id="p", name="Listener")
    monkeypatch.setattr(routes, "process_generation_queue", AsyncMock())
    return app


async def _post(app, path, body):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(path, json=body)


@pytest.mark.asyncio
async def test_generate_rejects_explicit_cast_of_other_provider(api_app, db_session):
    await _seed(db_session,
        Cast(id="g", user_id="u", profile_id="p", name="G", tts_provider="gemini", is_default=True),
        Cast(id="v", user_id="u", profile_id="p", name="Vox", tts_provider="piper", is_default=True))
    response = await _post(api_app, "/api/briefings/generate", {"cast_id": "v"})
    assert response.status_code == 400
    assert response.json()["detail"] == "'Vox' is a Piper cast; your voice provider is Google Gemini."


@pytest.mark.asyncio
async def test_generate_fails_fast_without_any_cast_for_provider(api_app, db_session):
    response = await _post(api_app, "/api/briefings/generate", {})
    assert response.status_code == 400
    assert response.json()["detail"] == "No Google Gemini cast yet. Create one on the Casts page."


@pytest.mark.asyncio
async def test_breakout_explicit_mismatch_400_but_parent_mismatch_falls_back(api_app, db_session):
    await _seed(db_session,
        Cast(id="g", user_id="u", profile_id="p", name="G", tts_provider="gemini", is_default=True),
        Cast(id="v", user_id="u", profile_id="p", name="Vox", tts_provider="piper", is_default=True),
        Briefing(id="src", user_id="u", profile_id="p", title="Src", status="completed", cast_id="v",
                 extra_data={"chapters": [{"title": "Tides", "start_time": 0, "end_time": 10}]}))
    explicit = await _post(api_app, "/api/briefings/breakout", {"topic": "Tides", "cast_id": "v"})
    assert explicit.status_code == 400
    implicit = await _post(api_app, "/api/briefings/breakout", {"source_briefing_id": "src", "chapter_index": 0})
    assert implicit.status_code == 202
    assert implicit.json()["cast_id"] is None  # resolved to the Gemini default at generation time
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd backend && venv/bin/pytest tests/test_cast_resolution.py -v`
Expected: `AttributeError: 'CastService' object has no attribute 'resolve_for_generation'`.

- [ ] **Step 3: Implement `resolve_for_generation`**

Add this to `CastService` in `backend/app/services/cast.py`:

```python
    async def resolve_for_generation(
        self, user_id: str, profile_id: Optional[str], cast_id: Optional[str], provider: str,
    ) -> Cast:
        """The cast a queued briefing should use with `provider`.

        Explicit choices were validated at request time, so any mismatch here is
        implicit (a schedule's cast, a breakout's parent cast, or a provider switch
        while queued) and falls back to the provider's default.
        """
        if cast_id:
            cast = await self.get_cast(cast_id, user_id, profile_id)
            if cast and cast.tts_provider == provider:
                return cast
            reason = "not found" if cast is None else f"belongs to {cast.tts_provider}"
            print(f"[Cast] Cast {cast_id} {reason}; using the {provider} default")
        return await self.get_default_cast(user_id, profile_id, provider)
```

- [ ] **Step 4: Use it in the briefing pipeline**

In `backend/app/services/briefing.py`, replace step 5 from `cast_service = CastService(self.db)` through the `briefing.cast_id = cast.id` block with:

```python
            cast_service = CastService(self.db)
            # Read the provider once: the cast and the audio must use the same one
            # even if Settings change while this briefing generates.
            tts_provider = active_tts_provider()
            cast = await cast_service.resolve_for_generation(
                briefing.user_id, briefing.profile_id, briefing.cast_id, tts_provider,
            )
            # Record the cast actually used so the player shows the right hosts.
            briefing.cast_id = cast.id
```

Add the import `from app.services.tts.registry import active_tts_provider` near the other `app.services` imports. In the step-8 call `TTSFactory.synthesize_conversation(...)`, add `provider_name=tts_provider,`.

- [ ] **Step 5: Check at request time**

In `backend/app/routers/briefings.py` `generate_briefing`, replace the `if request.cast_id:` block with:

```python
        provider = active_tts_provider()
        cast_service = CastService(db)
        if request.cast_id:
            cast = await db.scalar(select(Cast).where(
                Cast.id == request.cast_id,
                Cast.user_id == user.id,
                Cast.profile_id == profile.id,
            ))
            if cast is None:
                raise HTTPException(404, "Cast not found in this profile")
            try:
                cast_service.ensure_usable(cast, provider)
            except CastProviderMismatchError as error:
                raise HTTPException(400, str(error))
        else:
            try:
                await cast_service.get_default_cast(user.id, profile.id, provider)
            except NoCastForProviderError as error:
                raise HTTPException(400, str(error))
```

Add the imports `from app.services.cast import CastService, CastProviderMismatchError, NoCastForProviderError` and `from app.services.tts.registry import active_tts_provider`.

In `backend/app/services/breakout_request.py`, replace the final cast block (from `cast_id = request.cast_id or ...` to the `return`) with:

```python
    provider = active_tts_provider()
    cast_id = request.cast_id or (parent.cast_id if parent else None)
    if cast_id:
        cast = await db.scalar(select(Cast).where(
            Cast.id == cast_id, Cast.user_id == user_id, Cast.profile_id == profile_id))
        usable = cast is not None and cast.tts_provider == provider
        if not usable:
            if request.cast_id:
                if cast is None:
                    raise HTTPException(404, "Cast not found in this profile")
                raise HTTPException(400, provider_mismatch_message(cast.name, cast.tts_provider, provider))
            cast_id = None  # A removed or other-provider parent cast falls back to the current default.
    if cast_id is None:
        try:
            await CastService(db).get_default_cast(user_id, profile_id, provider)
        except NoCastForProviderError as error:
            raise HTTPException(400, str(error))
    return metadata, topic_ids, cast_id
```

Add the imports `from app.services.cast import CastService, NoCastForProviderError, provider_mismatch_message` and `from app.services.tts.registry import active_tts_provider`.

- [ ] **Step 6: Run the tests**

Run: `cd backend && venv/bin/pytest tests/test_cast_resolution.py -v && venv/bin/pytest -q`
Expected: everything passes.

Existing tests that post to `/generate` or `/breakout` without a cast now get 400 from the fail-fast check. Search for them with `grep -rln "briefings/generate\|briefings/breakout\|resolve_breakout_request" tests`. Add this fixture to `backend/tests/conftest.py` and request it in each of those tests; the seed row is correct, not a workaround:

```python
@pytest_asyncio.fixture
async def gemini_default_cast(db_session):
    """Default Gemini cast for user 'u' / profile 'p' (the ids the API tests use)."""
    from app.models.cast import Cast
    cast = Cast(id="default-cast", user_id="u", profile_id="p", name="Default",
                tts_provider="gemini", is_default=True)
    db_session.add(cast)
    await db_session.commit()
    return cast
```

Stage `backend/tests/conftest.py` and every test file you changed.

- [ ] **Step 7: Stage the changes**

```bash
git add backend/app/services/cast.py backend/app/services/briefing.py backend/app/routers/briefings.py backend/app/services/breakout_request.py backend/tests/test_cast_resolution.py backend/tests/test_breakout_api.py
```

---

### Task 4: Cast API for providers, voices, and counts

**Files:**
- Modify: `backend/app/schemas/cast.py`
- Modify: `backend/app/routers/casts.py`: `list_casts`, plus new `/voices` and `/summary` routes declared before `/{cast_id}`
- Modify: `backend/mcp_server.py`: the `list_casts` description
- Test: `backend/tests/test_casts_api_providers.py`

**Interfaces:**
- Consumes: `registry.TTS_PROVIDERS`, `list_provider_voices`, `active_tts_provider`, `provider_label`, and `CastService.get_user_casts` / `count_by_provider`.
- Produces these HTTP endpoints, which Tasks 5 and 6 consume:
  - `GET /api/casts?provider=all|<id>` returns `{casts: CastResponse[], active_provider: str, providers: [{id, label, allows_custom_voice}]}`. `CastResponse` now includes `tts_provider`.
  - `GET /api/casts/voices?provider=<id>` returns `{provider, provider_label, voices: [{id, name, description}], allows_custom: bool}`. An unknown provider gets 400, and a failure while listing gets 502 with the error message.
  - `GET /api/casts/summary` returns `{active_provider, counts: {<provider>: int}}`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_casts_api_providers.py`:

```python
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from app.database import get_db
from app.models.cast import Cast
from app.routers import casts as routes
from app.routers.auth import get_current_user
from app.routers.profiles import get_current_profile


@pytest.fixture
def api(db_session):
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/casts")
    async def db():
        yield db_session
    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u")
    app.dependency_overrides[get_current_profile] = lambda: SimpleNamespace(id="p")
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def seeded(db_session):
    db_session.add_all([
        Cast(id="g", user_id="u", profile_id="p", name="G", tts_provider="gemini", is_default=True),
        Cast(id="e", user_id="u", profile_id="p", name="E", tts_provider="elevenlabs", is_default=True),
    ])
    await db_session.commit()


@pytest.mark.asyncio
async def test_list_defaults_to_active_provider_and_reports_providers(api, seeded):
    async with api as client:
        body = (await client.get("/api/casts")).json()
    assert [c["id"] for c in body["casts"]] == ["g"]
    assert body["casts"][0]["tts_provider"] == "gemini"
    assert body["active_provider"] == "gemini"
    assert {"id": "piper", "label": "Piper", "allows_custom_voice": True} in body["providers"]


@pytest.mark.asyncio
async def test_list_all_includes_every_provider(api, seeded):
    async with api as client:
        body = (await client.get("/api/casts", params={"provider": "all"})).json()
    assert {c["id"] for c in body["casts"]} == {"g", "e"}


@pytest.mark.asyncio
async def test_voices_for_active_and_named_provider(api):
    async with api as client:
        gemini = (await client.get("/api/casts/voices")).json()
        piper = (await client.get("/api/casts/voices", params={"provider": "piper"})).json()
        bad = await client.get("/api/casts/voices", params={"provider": "nope"})
    assert gemini["provider"] == "gemini" and gemini["allows_custom"] is False
    assert {"id": "Kore", "name": "Kore", "description": "Firm"} in gemini["voices"]
    assert piper["allows_custom"] is True and piper["provider_label"] == "Piper"
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_summary_counts(api, seeded):
    async with api as client:
        body = (await client.get("/api/casts/summary")).json()
    assert body == {"active_provider": "gemini", "counts": {"gemini": 1, "elevenlabs": 1}}
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd backend && venv/bin/pytest tests/test_casts_api_providers.py -v`
Expected: the tests fail because `active_provider` is missing and `/voices` returns 404, since it is matched by `/{cast_id}`.

- [ ] **Step 3: Add the schemas**

In `backend/app/schemas/cast.py`, add `tts_provider: str` to `CastResponse`. Then replace `CastListResponse` and add the new models:

```python
class ProviderInfo(BaseModel):
    id: str
    label: str
    allows_custom_voice: bool


class CastListResponse(BaseModel):
    """Casts plus the provider context the UI needs to explain them."""
    casts: list[CastResponse]
    active_provider: str
    providers: list[ProviderInfo]


class VoiceOption(BaseModel):
    id: str
    name: str
    description: Optional[str] = None


class CastVoicesResponse(BaseModel):
    provider: str
    provider_label: str
    voices: list[VoiceOption]
    allows_custom: bool


class CastSummaryResponse(BaseModel):
    active_provider: str
    counts: dict[str, int]
```

- [ ] **Step 4: Add the routes**

In `backend/app/routers/casts.py`, import `ProviderInfo, CastVoicesResponse, VoiceOption, CastSummaryResponse`, and import `TTS_PROVIDERS, list_provider_voices, provider_label` from the registry. Add `Query` to the fastapi import and `from typing import Optional`. Replace `list_casts` and add the two new routes directly below it. They must come before `@router.get("/{cast_id}")`:

```python
def _provider_infos() -> list[ProviderInfo]:
    return [ProviderInfo(id=s.id, label=s.label, allows_custom_voice=s.allows_custom_voice)
            for s in TTS_PROVIDERS.values()]


@router.get("", response_model=CastListResponse)
async def list_casts(
    provider: Optional[str] = Query(None, description="'all', a provider id, or omit for the active provider"),
    user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """List casts for the current profile; the active provider's casts by default."""
    active = active_tts_provider()
    scope = None if provider == "all" else (provider or active)
    casts = await CastService(db).get_user_casts(user.id, profile_id=profile.id, provider=scope)
    return CastListResponse(
        casts=[CastResponse.model_validate(c) for c in casts],
        active_provider=active,
        providers=_provider_infos(),
    )


@router.get("/voices", response_model=CastVoicesResponse)
async def list_voices(
    provider: Optional[str] = None,
    user: User = Depends(get_current_user),
):
    """Voices a cast can use with a provider (the active one by default)."""
    provider = provider or active_tts_provider()
    spec = TTS_PROVIDERS.get(provider)
    if spec is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown TTS provider: {provider}")
    try:
        voices = await list_provider_voices(provider)
    except Exception as error:  # provider servers (e.g. Voicebox) can be down
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error))
    return CastVoicesResponse(
        provider=provider,
        provider_label=spec.label,
        voices=[VoiceOption(id=v.id, name=v.name, description=v.description) for v in voices],
        allows_custom=spec.allows_custom_voice,
    )


@router.get("/summary", response_model=CastSummaryResponse)
async def cast_summary(
    user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: AsyncSession = Depends(get_db),
):
    """Cast counts per provider, for the Settings provider hint."""
    counts = await CastService(db).count_by_provider(user.id, profile.id)
    return CastSummaryResponse(active_provider=active_tts_provider(), counts=counts)
```

- [ ] **Step 5: Update the MCP description**

In `backend/mcp_server.py`, set the `list_casts` description to:
`"List casts for the connected profile. Only casts for the active voice (TTS) provider are listed; each cast has tts_provider. Pass cast ids from this list."`

If `tests/test_mcp_server_tools.py` compares descriptions, update the expected string there.

- [ ] **Step 6: Run the tests**

Run: `cd backend && venv/bin/pytest tests/test_casts_api_providers.py -v && venv/bin/pytest -q`
Expected: everything passes.

- [ ] **Step 7: Stage the changes**

```bash
git add backend/app/schemas/cast.py backend/app/routers/casts.py backend/mcp_server.py backend/tests/test_casts_api_providers.py backend/tests/test_mcp_server_tools.py
```

---

### Task 5: Frontend cast/provider logic and API client

**Files:**
- Modify: `frontend/src/api/client.ts`: cast types and `castsApi`
- Create: `frontend/src/pages/castProviders.ts`
- Test: `frontend/src/pages/castProviders.test.ts`

**Interfaces:**
- Consumes: the Task 4 endpoints.
- Produces:
  - In `client.ts`: the types `ProviderInfo`, `CastList`, `VoiceOption`, `CastVoices`, and `CastSummary`.
  - `castsApi.list(profileId?: string, provider?: string): Promise<CastList>`
  - `castsApi.voices(provider?: string): Promise<CastVoices>`
  - `castsApi.summary(): Promise<CastSummary>`
  - In `castProviders.ts`: `CUSTOM_VOICE`, `providerLabel`, `splitCastsByProvider`, `voiceChoice`, `voiceName`, and `castCountHint`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/pages/castProviders.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import type { Cast, ProviderInfo, VoiceOption } from '../api/client'
import { castCountHint, providerLabel, splitCastsByProvider, voiceChoice, voiceName } from './castProviders'

const cast = (id: string, tts_provider: string, is_default = false) =>
  ({ id, tts_provider, is_default, name: id, members: [] }) as unknown as Cast

const providers: ProviderInfo[] = [
  { id: 'gemini', label: 'Google Gemini', allows_custom_voice: false },
  { id: 'voicebox', label: 'Voicebox', allows_custom_voice: false },
]
const voices: VoiceOption[] = [{ id: 'vb-1', name: 'Dad' }, { id: 'vb-2', name: 'Kevin' }]

describe('castProviders', () => {
  it('labels known providers and passes unknown ids through', () => {
    expect(providerLabel(providers, 'voicebox')).toBe('Voicebox')
    expect(providerLabel(providers, 'mystery')).toBe('mystery')
  })

  it('splits casts into active and other providers, keeping order', () => {
    const { active, other } = splitCastsByProvider([cast('a', 'gemini'), cast('b', 'voicebox'), cast('c', 'gemini')], 'gemini')
    expect(active.map(c => c.id)).toEqual(['a', 'c'])
    expect(other.map(c => c.id)).toEqual(['b'])
  })

  it('classifies a member voice against the provider list', () => {
    expect(voiceChoice('', voices, false)).toEqual({ kind: 'empty' })
    expect(voiceChoice('vb-2', voices, false)).toEqual({ kind: 'listed', voice: voices[1] })
    expect(voiceChoice('af_heart:0.6', voices, true)).toEqual({ kind: 'custom' })
    expect(voiceChoice('Zephyr', voices, false)).toEqual({ kind: 'missing' })
  })

  it('shows voice names, falling back to the raw id', () => {
    expect(voiceName('vb-1', voices)).toBe('Dad')
    expect(voiceName('raw-id', voices)).toBe('raw-id')
  })

  it('explains how many casts the chosen provider has', () => {
    expect(castCountHint('Voicebox', 0)).toBe('No Voicebox casts yet. Create one before your next briefing.')
    expect(castCountHint('Google Gemini', 1)).toBe('1 Google Gemini cast')
    expect(castCountHint('Google Gemini', 3)).toBe('3 Google Gemini casts')
    expect(castCountHint('Piper', undefined)).toBe('')
  })
})
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd frontend && eval "$(/opt/homebrew/bin/brew shellenv)" && npx vitest run src/pages/castProviders.test.ts`
Expected: FAIL with `Failed to resolve import "./castProviders"`.

- [ ] **Step 3: Update the client types and API**

In `frontend/src/api/client.ts`, add `tts_provider: string` to `interface Cast` and add these types after it:

```ts
export interface ProviderInfo {
  id: string
  label: string
  allows_custom_voice: boolean
}

export interface CastList {
  casts: Cast[]
  active_provider: string
  providers: ProviderInfo[]
}

export interface VoiceOption {
  id: string
  name: string
  description?: string | null
}

export interface CastVoices {
  provider: string
  provider_label: string
  voices: VoiceOption[]
  allows_custom: boolean
}

export interface CastSummary {
  active_provider: string
  counts: Record<string, number>
}
```

Replace `castsApi.list`, and add the two new methods after `get`:

```ts
  /** Casts for the active TTS provider; pass provider 'all' for every provider. */
  list: async (profileId?: string, provider?: string) => {
    const { data } = await api.get<CastList>('/api/casts', {
      params: provider ? { provider } : undefined,
      headers: profileId ? { 'X-Profile-ID': profileId } : undefined,
    })
    return data
  },

  voices: async (provider?: string) => {
    const { data } = await api.get<CastVoices>('/api/casts/voices', { params: provider ? { provider } : undefined })
    return data
  },

  summary: async () => {
    const { data } = await api.get<CastSummary>('/api/casts/summary')
    return data
  },
```

- [ ] **Step 4: Implement the logic module**

Create `frontend/src/pages/castProviders.ts`:

```ts
import type { Cast, ProviderInfo, VoiceOption } from '../api/client'

/** Select value that reveals the free-text voice ID input. */
export const CUSTOM_VOICE = '__custom__'

export function providerLabel(providers: ProviderInfo[], id: string): string {
  return providers.find(p => p.id === id)?.label ?? id
}

export function splitCastsByProvider(casts: Cast[], activeProvider: string): { active: Cast[]; other: Cast[] } {
  return {
    active: casts.filter(c => c.tts_provider === activeProvider),
    other: casts.filter(c => c.tts_provider !== activeProvider),
  }
}

export type VoiceChoice =
  | { kind: 'empty' }
  | { kind: 'listed'; voice: VoiceOption }
  | { kind: 'custom' }
  | { kind: 'missing' }

/** How a member's saved voice relates to the provider's voice list. */
export function voiceChoice(voiceId: string, voices: VoiceOption[], allowsCustom: boolean): VoiceChoice {
  if (!voiceId.trim()) return { kind: 'empty' }
  const voice = voices.find(v => v.id === voiceId)
  if (voice) return { kind: 'listed', voice }
  return allowsCustom ? { kind: 'custom' } : { kind: 'missing' }
}

export function voiceName(voiceId: string, voices: VoiceOption[]): string {
  return voices.find(v => v.id === voiceId)?.name ?? voiceId
}

export function castCountHint(label: string, count: number | undefined): string {
  if (count === undefined) return ''
  if (count === 0) return `No ${label} casts yet. Create one before your next briefing.`
  return `${count} ${label} cast${count === 1 ? '' : 's'}`
}
```

- [ ] **Step 5: Run the tests and the type check**

Run: `cd frontend && npx vitest run && npx tsc --noEmit`
Expected: vitest passes. `tsc` may report errors where callers read `castsApi.list()`. `.casts` is still valid, so errors are only expected for places that build a `Cast` literal. Fix any error in the caller by adding `tts_provider`.

- [ ] **Step 6: Stage the changes**

```bash
git add frontend/src/api/client.ts frontend/src/pages/castProviders.ts frontend/src/pages/castProviders.test.ts
```

---

### Task 6: Provider-aware cast UI, then commit Part 1

**Files:**
- Create: `frontend/src/components/VoicePicker.tsx`
- Modify: `frontend/src/pages/CreateCast.tsx`
- Modify: `frontend/src/pages/Casts.tsx`
- Modify: `frontend/src/components/settings/TtsSettings.tsx`: add `castCount` and `castsHref` props
- Modify: `frontend/src/pages/Settings.tsx`: summary query, the hint, and `['casts']` invalidation
- Modify: `frontend/src/pages/DashboardBriefs.tsx`: the filter lists every provider's casts
- Modify: `frontend/src/pages/CreateSchedule.tsx`: a note when the saved cast belongs to another provider
- Modify: `frontend/src/pages/DashboardGenerate.tsx`: a warning when the provider has no cast

**Interfaces:**
- Consumes: everything from Task 5.
- Produces: `VoicePicker` props `{ id: string; value: string; onChange(v: string): void; voices: CastVoices | undefined; loading: boolean; error?: string; disabled?: boolean }`.

- [ ] **Step 1: Write `VoicePicker`**

Create `frontend/src/components/VoicePicker.tsx`:

```tsx
import { useState } from 'react'
import type { CastVoices } from '../api/client'
import { CUSTOM_VOICE, voiceChoice } from '../pages/castProviders'

interface VoicePickerProps {
  id: string
  value: string
  onChange: (voiceId: string) => void
  voices: CastVoices | undefined
  loading: boolean
  error?: string
  disabled?: boolean
}

/** Voice dropdown fed by the active provider; free-text only where the provider allows it. */
export default function VoicePicker({ id, value, onChange, voices, loading, error, disabled }: VoicePickerProps) {
  const list = voices?.voices ?? []
  const allowsCustom = voices?.allows_custom ?? false
  const choice = voiceChoice(value, list, allowsCustom)
  const [customOpen, setCustomOpen] = useState(choice.kind === 'custom')
  const showCustom = allowsCustom && (customOpen || choice.kind === 'custom')

  if (error) {
    return <p className="text-sm text-red-400">{error}</p>
  }

  return (
    <div className="space-y-2">
      <select
        id={id}
        className="input w-full"
        disabled={disabled || loading}
        required={!showCustom}
        value={showCustom ? CUSTOM_VOICE : choice.kind === 'listed' ? value : ''}
        onChange={(e) => {
          if (e.target.value === CUSTOM_VOICE) {
            setCustomOpen(true)
            return
          }
          setCustomOpen(false)
          onChange(e.target.value)
        }}
      >
        <option value="" disabled>
          {loading ? 'Loading voices…' : list.length ? 'Choose a voice' : 'No voices available'}
        </option>
        {list.map(v => (
          <option key={v.id} value={v.id}>
            {v.name}{v.description ? ` — ${v.description}` : ''}
          </option>
        ))}
        {allowsCustom && <option value={CUSTOM_VOICE}>Custom voice ID…</option>}
      </select>
      {showCustom && (
        <input
          type="text"
          className="input w-full"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Voice ID"
          required
          disabled={disabled}
        />
      )}
      {choice.kind === 'missing' && (
        <p className="text-xs text-yellow-400">
          “{value}” isn't a {voices?.provider_label} voice. Choose one from the list.
        </p>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Use it in `CreateCast`**

In `frontend/src/pages/CreateCast.tsx`:
- Add the imports `VoicePicker` and `{ voiceChoice }`.
- Add these queries after the personalities query:

```tsx
  const { data: voices, isLoading: voicesLoading, error: voicesError } = useQuery({
    queryKey: ['cast-voices'],
    queryFn: () => castsApi.voices(),
    staleTime: 30_000,
  })
  // Casts belong to the provider active when they were created.
  const readOnly = isEditing && !!existingCast && !!voices && existingCast.tts_provider !== voices.provider
```

- Under the header's `<p>` subtitle, add a provider badge:

```tsx
            {voices && (
              <p className="mt-1 text-xs text-augustus-400">
                These hosts use <span className="font-medium text-accent">{voices.provider_label}</span> voices
                {' · '}change the provider in Settings.
              </p>
            )}
```

- Directly above `<form>`, add the read-only notice:

```tsx
      {readOnly && existingCast && (
        <div className="mb-6 rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-3 text-sm text-yellow-300">
          This cast uses another provider's voices. Switch the voice provider in Settings to edit it.
        </div>
      )}
```

- Wrap the "Cast Details" and "Members" cards in `<fieldset disabled={readOnly} className="space-y-6">…</fieldset>`, leaving the Cancel/Create buttons outside it. Render the submit button only when `!readOnly`, so Cancel stays usable on a read-only cast.
- Replace the whole "Voice ID" `<div>` (label, input, and helper `<p>`) with:

```tsx
                  <div>
                    <label className="label" htmlFor={`member-${index}-voice`}>Voice *</label>
                    <VoicePicker
                      id={`member-${index}-voice`}
                      value={member.voice_id}
                      onChange={(voiceId) => updateMember(index, 'voice_id', voiceId)}
                      voices={voices}
                      loading={voicesLoading}
                      error={voicesError ? `Couldn't load voices: ${(voicesError as Error).message}` : undefined}
                      disabled={isLoading}
                    />
                  </div>
```

- In `handleSubmit`, after the `voice_id.trim()` check inside the loop, add:

```tsx
      if (voices && voiceChoice(member.voice_id, voices.voices, voices.allows_custom).kind === 'missing') {
        alert(`Member ${i + 1}: choose a ${voices.provider_label} voice`)
        return
      }
```

- [ ] **Step 3: Update the Casts page**

In `frontend/src/pages/Casts.tsx`:
- Change the list query to `queryKey: ['casts', 'all'], queryFn: () => castsApi.list(undefined, 'all')`.
- Add a voices query: `const { data: voices } = useQuery({ queryKey: ['cast-voices'], queryFn: () => castsApi.voices(), staleTime: 30_000 })`.
- Compute the lists:

```tsx
  const activeProvider = data?.active_provider ?? ''
  const label = providerLabel(data?.providers ?? [], activeProvider)
  const { active: casts, other: otherCasts } = splitCastsByProvider(data?.casts ?? [], activeProvider)
  const [showOther, setShowOther] = useState(false)
```

Import `useState` from react, `ChevronDown` from lucide-react, and `providerLabel, splitCastsByProvider, voiceName` from `./castProviders`.

- Replace the header title block with:

```tsx
        <div>
          <h1 className="text-2xl sm:text-3xl font-display font-semibold text-white mb-1 sm:mb-2">
            {label ? `${label} casts` : 'Casts'}
          </h1>
          <p className="text-sm sm:text-base text-augustus-400">
            Hosts for your active voice provider ·{' '}
            <button type="button" className="text-accent hover:underline" onClick={() => navigate('/settings')}>
              Change in Settings
            </button>
          </p>
        </div>
```

- In the empty state, use the text `No {label} casts yet. Briefings need one before they can play.` and the button text `Create a {label} cast`.
- In a member row, use `Voice: {voiceName(member.voice_id, voices?.voices ?? [])}`.
- Render the Restore Defaults button only when `activeProvider === 'gemini'`. Otherwise render nothing in that slot for the default cast.
- Change the restore confirmation copy to `'Restore the default cast to Alex and Sebastian with the built-in Gemini voices?'`.
- After the grid, add the collapsed section for other providers:

```tsx
      {otherCasts.length > 0 && (
        <div className="mt-8">
          <button
            type="button"
            onClick={() => setShowOther(v => !v)}
            className="flex items-center gap-2 text-sm text-augustus-400 hover:text-augustus-300"
            aria-expanded={showOther}
          >
            <ChevronDown className={clsx('w-4 h-4 transition-transform', showOther && 'rotate-180')} />
            {otherCasts.length} cast{otherCasts.length === 1 ? '' : 's'} for other providers
          </button>
          {showOther && (
            <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 opacity-60">
              {otherCasts.map(cast => (
                <div key={cast.id} className="rounded-lg border border-augustus-700 bg-augustus-800/30 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h3 className="font-semibold text-white">{cast.name}</h3>
                      <span className="mt-1 inline-block rounded bg-augustus-700 px-1.5 py-0.5 text-xs text-augustus-300">
                        {providerLabel(data?.providers ?? [], cast.tts_provider)}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <button onClick={() => handleEdit(cast)} className="btn-icon btn btn-ghost" title="View">
                        <Pencil className="w-4 h-4" />
                      </button>
                      {!cast.is_default && (
                        <button onClick={() => handleDelete(cast)} className="btn-icon btn btn-ghost text-red-400" title="Delete">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                  <p className="mt-2 text-xs text-augustus-500">
                    {cast.members.map(m => m.name).join(', ')} · switch provider in Settings to use
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
```

All the mutations here already invalidate `['casts']`, which also invalidates `['casts','all']` because TanStack Query matches key prefixes.

- [ ] **Step 4: Add the cast hint to Settings**

In `frontend/src/components/settings/TtsSettings.tsx`, add these props:

```tsx
  /** Casts that exist for the selected provider; undefined while loading. */
  castCount: number | undefined
  providerLabel: string
  onOpenCasts: () => void
```

Import `castCountHint` from `'../../pages/castProviders'`. After the provider-option row `</div>` (the one closing `flex flex-col sm:flex-row`), add:

```tsx
          {castCountHint(providerLabel, castCount) && (
            <p className={clsx('mt-2 text-xs', castCount === 0 ? 'text-yellow-400' : 'text-augustus-500')}>
              {castCountHint(providerLabel, castCount)}{' '}
              <button type="button" onClick={onOpenCasts} className="text-accent hover:underline">
                {castCount === 0 ? 'Create a cast →' : 'Manage casts →'}
              </button>
            </p>
          )}
```

In `frontend/src/pages/Settings.tsx`:
- Import `castsApi`, `providerLabel`, and `useProfileNavigate` if they are missing.
- Add these queries:

```tsx
  const { data: castSummary } = useQuery({ queryKey: ['casts', 'summary'], queryFn: () => castsApi.summary() })
  const { data: castList } = useQuery({ queryKey: ['casts'], queryFn: () => castsApi.list() })
```

- Pass these to `<TtsSettings>`:

```tsx
              castCount={castSummary ? (castSummary.counts[ttsProvider] ?? 0) : undefined}
              providerLabel={providerLabel(castList?.providers ?? [], ttsProvider)}
              onOpenCasts={() => navigate('/casts')}
```

- In `updateMutation.onSuccess`, after `setQueryData`, add:

```tsx
      // Casts are per provider: every cast list and picker must follow a provider switch.
      if ('tts_provider' in variables) {
        queryClient.invalidateQueries({ queryKey: ['casts'] })
        queryClient.invalidateQueries({ queryKey: ['cast-voices'] })
      }
```

- [ ] **Step 5: Update the pickers**

- **`DashboardBriefs.tsx`**: this page filters past briefings, which can have used any provider. Change the query to `queryKey: ['casts', 'all'], queryFn: () => castsApi.list(undefined, 'all')`.
- **`CreateSchedule.tsx`**: directly after the cast `<select>`'s closing `</div>` (still inside `{castsData && ...}`), and also as a sibling block when `castsData.casts.length <= 1`, add:

```tsx
          {existingSchedule?.cast_id && castsData && !castsData.casts.some(c => c.id === existingSchedule.cast_id) && (
            <p className="text-xs text-augustus-500">
              This schedule's saved cast uses another voice provider, so it will use your default{' '}
              {providerLabel(castsData.providers, castsData.active_provider)} cast.
            </p>
          )}
```

Import `providerLabel` from `./castProviders`. Also initialise `selectedCastId` only when the saved cast is in the list. Where it currently calls `setSelectedCastId(existingSchedule.cast_id)`, guard it with `if (castsData?.casts.some(c => c.id === existingSchedule.cast_id))`, and add `castsData` to that effect's dependencies.

- **`DashboardGenerate.tsx`**: before the "Cast selector" block, add:

```tsx
      {castsData && casts.length === 0 && (
        <div className="mb-4 rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-3 text-sm text-yellow-300">
          No {providerLabel(castsData.providers, castsData.active_provider)} cast yet.{' '}
          <button type="button" className="underline" onClick={() => navigate('/casts/create')}>Create one</button>
          {' '}to generate briefings.
        </div>
      )}
```

Import `providerLabel`, and use whatever navigate hook the file already has. Leave `BreakoutDialog.tsx` unchanged: its `castsApi.list(scope!.id)` already returns the active provider's casts.

- [ ] **Step 6: Verify Part 1**

Run:

```bash
cd backend && venv/bin/pytest -q
cd ../frontend && eval "$(/opt/homebrew/bin/brew shellenv)" && npx vitest run && npx tsc --noEmit && npm run build
```

Expected: all four pass.

The first start runs the migration against the real database. Back it up first:

```bash
cp backend/augustus.db backend/augustus.db.pre-provider-casts
```

Then run the app with `./dev.sh`. In the backend log, check the `[Migration] Cast … -> provider` lines against the casts you expect. Log in and check:
- With `TTS_PROVIDER=gemini`, the Casts page title reads "Google Gemini casts". Your ElevenLabs and Piper casts appear under "N casts for other providers".
- In Settings, click ElevenLabs: the hint shows "2 ElevenLabs casts" (or your real count). The dashboard cast picker switches to ElevenLabs casts without a reload.
- Create a cast: the Voice field is a dropdown of Gemini voices.
- Switch back to Gemini.

- [ ] **Step 7: Commit Part 1**

```bash
git add docs/superpowers/specs/2026-09-27-voicebox-and-provider-casts-design.md docs/superpowers/plans/2026-09-27-voicebox-and-provider-casts.md frontend/src
git status --short   # confirm only intended files are staged; do not add backend/scripts or dev.sh
git commit -m "$(cat <<'EOF'
feat: casts belong to the active TTS provider

Casts gain a tts_provider (backfilled from member voices at startup) and
the database enforces one default per provider. Casts, pickers and the
cast editor follow the provider chosen in Settings, voices come from a
dropdown, and briefings fail with a clear message when the provider has
no cast. Also fixes cast creation clearing the profile's default.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# Part 2: Voicebox provider

### Task 7: Voicebox HTTP client and configuration

**Files:**
- Modify: `backend/app/config.py`: add `voicebox_url`, `voicebox_model`, `voicebox_concurrency`, and `voicebox_briefing_timeout_minutes`
- Create: `backend/app/services/tts/voicebox_client.py`
- Modify: `backend/app/services/tts/registry.py`: add the `voicebox` spec, a voices branch, and `briefing_timeout_minutes`
- Modify: `backend/app/services/briefing.py`: the timeout uses `briefing_timeout_minutes(active_tts_provider())`
- Test: `backend/tests/test_voicebox_client.py`

**Interfaces:**
- Produces:
  - `VOICEBOX_MODELS: dict[str, tuple[str, Optional[str]]]`, mapping a model name to `(engine, model_size)`
  - `MIN_TESTED_VERSION = (0, 5, 0)`
  - `VoiceboxProfile(id, name, language, voice_type, preset_engine)`, a frozen dataclass
  - `VoiceboxModel(name, display_name, engine, model_size)`, a frozen dataclass
  - `class VoiceboxError(RuntimeError)`
  - `VoiceboxClient(base_url: str, transport: httpx.AsyncBaseTransport | None = None)` with these methods:
    - `close()`
    - `version() -> str`
    - `list_profiles(max_age: float = 30.0) -> list[VoiceboxProfile]`
    - `list_tts_models() -> list[VoiceboxModel]`
    - `generate(profile_id, text, language, engine, model_size) -> str`
    - `wait_until_done(generation_id, timeout: float) -> None`
    - `download_audio(generation_id, dest: Path) -> None`
    - `delete_generation(generation_id) -> None`
    - `cancel_generation(generation_id) -> None`
  - `registry.briefing_timeout_minutes(provider: str) -> int`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_voicebox_client.py`:

```python
"""VoiceboxClient against a fake Voicebox server (httpx.MockTransport)."""
import json

import httpx
import pytest

from app.services.tts import voicebox_client as vc
from app.services.tts.voicebox_client import VoiceboxClient, VoiceboxError


PROFILES = [
    {"id": "p-halie", "name": "Halie ", "language": "en", "voice_type": "cloned", "preset_engine": None},
    {"id": "p-heart", "name": "Heart (kokoro)", "language": "en", "voice_type": "preset", "preset_engine": "kokoro"},
]
MODELS = {"models": [
    {"model_name": "chatterbox-turbo", "display_name": "Chatterbox Turbo", "downloaded": True},
    {"model_name": "qwen-tts-1.7B", "display_name": "Qwen TTS 1.7B", "downloaded": True},
    {"model_name": "qwen-tts-0.6B", "display_name": "Qwen TTS 0.6B", "downloaded": False},
    {"model_name": "whisper-base", "display_name": "Whisper Base", "downloaded": True},
    {"model_name": "future-tts-9", "display_name": "Future", "downloaded": True},
]}


class FakeVoicebox:
    """Routes requests like Voicebox 0.5.0 and records them."""

    def __init__(self, status="completed", error=None):
        self.requests: list[httpx.Request] = []
        self.status, self.error = status, error

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path, method = request.url.path, request.method
        if path == "/openapi.json":
            return httpx.Response(200, json={"info": {"version": "0.5.0"}})
        if path == "/profiles":
            return httpx.Response(200, json=PROFILES)
        if path == "/models/status":
            return httpx.Response(200, json=MODELS)
        if path == "/generate" and method == "POST":
            return httpx.Response(200, json={"id": "gen-1", "status": "generating"})
        if path == "/generate/gen-1/status":
            event = {"id": "gen-1", "status": "generating"}
            done = {"id": "gen-1", "status": self.status, "error": self.error}
            body = f"data: {json.dumps(event)}\n\ndata: {json.dumps(done)}\n\n"
            return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})
        if path == "/audio/gen-1":
            return httpx.Response(200, content=b"RIFFfake", headers={"content-type": "audio/x-wav"})
        if path in ("/history/gen-1", "/generate/gen-1/cancel"):
            return httpx.Response(200, json={"message": "ok"})
        return httpx.Response(404)


@pytest.fixture(autouse=True)
def _clear_profile_cache():
    vc._profile_cache.clear()


def client_for(fake):
    return VoiceboxClient("http://vb.local:17493/", transport=httpx.MockTransport(fake))


@pytest.mark.asyncio
async def test_version_profiles_and_cache():
    fake = FakeVoicebox()
    client = client_for(fake)
    assert await client.version() == "0.5.0"
    profiles = await client.list_profiles()
    assert profiles[0].name == "Halie " and profiles[1].preset_engine == "kokoro"
    await client.list_profiles()
    assert sum(r.url.path == "/profiles" for r in fake.requests) == 1  # cached
    await client.close()


@pytest.mark.asyncio
async def test_models_are_downloaded_known_tts_only():
    client = client_for(FakeVoicebox())
    models = await client.list_tts_models()
    assert [(m.name, m.engine, m.model_size) for m in models] == [
        ("chatterbox-turbo", "chatterbox_turbo", None),
        ("qwen-tts-1.7B", "qwen", "1.7B"),
    ]
    await client.close()


@pytest.mark.asyncio
async def test_generate_wait_download_delete(tmp_path):
    fake = FakeVoicebox()
    client = client_for(fake)
    gen = await client.generate("p-halie", "Hello", "en", "qwen", "1.7B")
    assert gen == "gen-1"
    body = json.loads(fake.requests[-1].content)
    assert body == {"profile_id": "p-halie", "text": "Hello", "language": "en", "engine": "qwen", "model_size": "1.7B"}
    await client.wait_until_done(gen, timeout=5)
    dest = tmp_path / "line.wav"
    await client.download_audio(gen, dest)
    assert dest.read_bytes() == b"RIFFfake"
    await client.delete_generation(gen)
    assert fake.requests[-1].method == "DELETE"
    await client.close()


@pytest.mark.asyncio
async def test_failed_generation_raises_with_voicebox_error_and_id():
    client = client_for(FakeVoicebox(status="failed", error="CUDA OOM"))
    with pytest.raises(VoiceboxError, match="gen-1.*CUDA OOM"):
        await client.wait_until_done("gen-1", timeout=5)
    await client.close()


@pytest.mark.asyncio
async def test_unreachable_server_has_readable_error():
    def boom(request):
        raise httpx.ConnectError("refused", request=request)
    client = VoiceboxClient("http://vb.local:17493", transport=httpx.MockTransport(boom))
    with pytest.raises(VoiceboxError, match=r"^Can't reach Voicebox at http://vb.local:17493\.$"):
        await client.list_profiles()
    await client.close()


def test_model_table_matches_spec():
    assert vc.VOICEBOX_MODELS["tada-3b-ml"] == ("tada", "3B")
    assert vc.VOICEBOX_MODELS["qwen-custom-voice-0.6B"] == ("qwen_custom_voice", "0.6B")
    assert vc.VOICEBOX_MODELS["breeze-tts-2"] == ("breeze", None)
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd backend && venv/bin/pytest tests/test_voicebox_client.py -v`
Expected: `ModuleNotFoundError: No module named 'app.services.tts.voicebox_client'`.

- [ ] **Step 3: Add the configuration**

In `backend/app/config.py`, after the Gemini TTS block, add:

```python
    # Voicebox TTS (self-hosted; see services/tts/voicebox_client.py)
    voicebox_url: Optional[str] = None  # e.g. http://localhost:17493
    voicebox_model: str = ""  # empty = first downloaded TTS model the server reports
    voicebox_concurrency: int = 2  # lines in flight; the server queues them on its GPU
    voicebox_briefing_timeout_minutes: int = 60  # long episodes on one GPU outlast the global cap
```

- [ ] **Step 4: Implement the client**

Create `backend/app/services/tts/voicebox_client.py`:

```python
"""HTTP client for a self-hosted Voicebox server (tested against API 0.5.0)."""

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

# Voicebox model name -> (engine, model_size) for POST /generate. The only
# Voicebox-version-specific table in Augustus: unknown models are skipped.
VOICEBOX_MODELS: dict[str, tuple[str, Optional[str]]] = {
    "qwen-tts-1.7B": ("qwen", "1.7B"),
    "qwen-tts-0.6B": ("qwen", "0.6B"),
    "qwen-custom-voice-1.7B": ("qwen_custom_voice", "1.7B"),
    "qwen-custom-voice-0.6B": ("qwen_custom_voice", "0.6B"),
    "luxtts": ("luxtts", None),
    "chatterbox-tts": ("chatterbox", None),
    "chatterbox-turbo": ("chatterbox_turbo", None),
    "tada-1b": ("tada", "1B"),
    "tada-3b-ml": ("tada", "3B"),
    "kokoro": ("kokoro", None),
    "breeze-tts-2": ("breeze", None),
}
MIN_TESTED_VERSION = (0, 5, 0)
PROFILE_CACHE_SECONDS = 30.0

# base_url -> (fetched_at, profiles); shared by the voices API and synthesis.
_profile_cache: dict[str, tuple[float, list["VoiceboxProfile"]]] = {}


class VoiceboxError(RuntimeError):
    """A Voicebox failure with a message fit to show on a failed briefing."""


@dataclass(frozen=True)
class VoiceboxProfile:
    id: str
    name: str
    language: str
    voice_type: str
    preset_engine: Optional[str]


@dataclass(frozen=True)
class VoiceboxModel:
    name: str
    display_name: str
    engine: str
    model_size: Optional[str]


def parse_version(version: str) -> tuple[int, ...]:
    parts = []
    for piece in version.split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


class VoiceboxClient:
    def __init__(self, base_url: str, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0, connect=5.0),
            transport=transport,
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = await self._http.request(method, path, **kwargs)
        except httpx.TransportError as error:
            raise VoiceboxError(f"Can't reach Voicebox at {self.base_url}.") from error
        if response.status_code >= 400:
            raise VoiceboxError(f"Voicebox {method} {path} failed with HTTP {response.status_code}.")
        return response

    async def version(self) -> str:
        return (await self._request("GET", "/openapi.json")).json().get("info", {}).get("version", "")

    async def list_profiles(self, max_age: float = PROFILE_CACHE_SECONDS) -> list[VoiceboxProfile]:
        cached = _profile_cache.get(self.base_url)
        if cached and time.monotonic() - cached[0] < max_age:
            return cached[1]
        raw = (await self._request("GET", "/profiles")).json()
        profiles = [
            VoiceboxProfile(
                id=p["id"], name=p.get("name") or p["id"], language=p.get("language") or "en",
                voice_type=p.get("voice_type") or "cloned", preset_engine=p.get("preset_engine"),
            )
            for p in raw
        ]
        _profile_cache[self.base_url] = (time.monotonic(), profiles)
        return profiles

    async def list_tts_models(self) -> list[VoiceboxModel]:
        models = []
        for m in (await self._request("GET", "/models/status")).json().get("models", []):
            name = m.get("model_name", "")
            if not m.get("downloaded"):
                continue
            if name not in VOICEBOX_MODELS:
                print(f"[Voicebox] Skipping model {name!r}: not a TTS model Augustus knows")
                continue
            engine, size = VOICEBOX_MODELS[name]
            models.append(VoiceboxModel(name, m.get("display_name") or name, engine, size))
        return models

    async def generate(self, profile_id: str, text: str, language: str, engine: str,
                       model_size: Optional[str]) -> str:
        body = {"profile_id": profile_id, "text": text, "language": language, "engine": engine}
        if model_size:
            body["model_size"] = model_size
        return (await self._request("POST", "/generate", json=body)).json()["id"]

    async def wait_until_done(self, generation_id: str, timeout: float) -> None:
        """Follow the status event stream until the generation completes or fails."""
        async def follow() -> Optional[dict]:
            last = None
            try:
                async with self._http.stream(
                    "GET", f"/generate/{generation_id}/status",
                    timeout=httpx.Timeout(timeout, connect=5.0),
                ) as response:
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        last = json.loads(line[5:].strip())
                        if last.get("status") in ("completed", "failed"):
                            return last
            except httpx.TransportError as error:
                raise VoiceboxError(f"Can't reach Voicebox at {self.base_url}.") from error
            return last

        try:
            event = await asyncio.wait_for(follow(), timeout=timeout)
        except asyncio.TimeoutError:
            raise VoiceboxError(f"Voicebox generation {generation_id} timed out after {int(timeout)}s.")
        if not event or event.get("status") not in ("completed", "failed"):
            # The stream ended early; ask once for the stored result.
            event = (await self._request("GET", f"/history/{generation_id}")).json()
        if event.get("status") == "failed":
            raise VoiceboxError(f"Voicebox generation {generation_id} failed: {event.get('error') or 'unknown error'}")
        if event.get("status") != "completed":
            raise VoiceboxError(f"Voicebox generation {generation_id} ended as {event.get('status')!r}.")

    async def download_audio(self, generation_id: str, dest: Path) -> None:
        try:
            async with self._http.stream("GET", f"/audio/{generation_id}") as response:
                if response.status_code >= 400:
                    raise VoiceboxError(f"Voicebox audio for {generation_id} failed with HTTP {response.status_code}.")
                with open(dest, "wb") as out:
                    async for chunk in response.aiter_bytes():
                        out.write(chunk)
        except httpx.TransportError as error:
            raise VoiceboxError(f"Can't reach Voicebox at {self.base_url}.") from error

    async def delete_generation(self, generation_id: str) -> None:
        """Best effort: history cleanup must never fail a briefing."""
        try:
            await self._http.delete(f"/history/{generation_id}")
        except httpx.HTTPError as error:
            print(f"[Voicebox] Could not delete generation {generation_id}: {error}")

    async def cancel_generation(self, generation_id: str) -> None:
        try:
            await self._http.post(f"/generate/{generation_id}/cancel")
        except httpx.HTTPError as error:
            print(f"[Voicebox] Could not cancel generation {generation_id}: {error}")
```

- [ ] **Step 5: Extend the registry and the briefing timeout**

In `backend/app/services/tts/registry.py`:

1. Add this entry to `TTS_PROVIDERS`:

```python
    "voicebox": ProviderSpec("voicebox", "Voicebox", allows_custom_voice=False),
```

2. Add this branch to `list_provider_voices`, before the `else`:

```python
    elif provider == "voicebox":
        from app.services.tts.voicebox_client import VoiceboxClient
        url = get_settings().voicebox_url
        if not url:
            raise ValueError("Add your Voicebox server URL in Settings first.")
        client = VoiceboxClient(url)
        try:
            profiles = await client.list_profiles()
        finally:
            await client.close()
        voices = [
            Voice(id=p.id, name=p.name.strip(),
                  description="Preset voice" if p.voice_type == "preset" else "Cloned voice",
                  language=p.language)
            for p in profiles
        ]
```

3. Append:

```python
def briefing_timeout_minutes(provider: str) -> int:
    """Overall generation budget; slow self-hosted providers get a larger one."""
    settings = get_settings()
    minutes = settings.briefing_timeout_minutes
    if provider == "voicebox":
        minutes = max(minutes, settings.voicebox_briefing_timeout_minutes)
    return minutes
```

In `backend/app/services/briefing.py`, change `timeout_minutes = get_settings().briefing_timeout_minutes` to `timeout_minutes = briefing_timeout_minutes(active_tts_provider())`, and import `briefing_timeout_minutes` from the registry.

Add these tests to `tests/test_voicebox_client.py`:

```python
def test_briefing_timeout_budget(monkeypatch):
    from app.config import get_settings
    from app.services.tts.registry import briefing_timeout_minutes
    monkeypatch.setenv("BRIEFING_TIMEOUT_MINUTES", "15")
    monkeypatch.setenv("VOICEBOX_BRIEFING_TIMEOUT_MINUTES", "60")
    get_settings.cache_clear()
    assert briefing_timeout_minutes("gemini") == 15
    assert briefing_timeout_minutes("voicebox") == 60


def test_parse_version():
    assert vc.parse_version("0.5.0") == (0, 5, 0)
    assert vc.parse_version("1.2.3rc1") == (1, 2, 3)
```

- [ ] **Step 6: Run the tests**

Run: `cd backend && venv/bin/pytest tests/test_voicebox_client.py -v && venv/bin/pytest -q`
Expected: everything passes.

- [ ] **Step 7: Stage the changes**

```bash
git add backend/app/config.py backend/app/services/tts/voicebox_client.py backend/app/services/tts/registry.py backend/app/services/briefing.py backend/tests/test_voicebox_client.py
```

---

### Task 8: VoiceboxProvider with concurrent rendering and streamed stitching

**Files:**
- Create: `backend/app/services/tts/voicebox.py`
- Modify: `backend/app/services/tts/factory.py`: add the `voicebox` branch
- Test: `backend/tests/test_voicebox_provider.py`

**Interfaces:**
- Consumes: `VoiceboxClient`, `VoiceboxProfile`, `VoiceboxModel`, `VoiceboxError`, and `VOICEBOX_MODELS` from Task 7, plus `cancellable_await` from `app.services.cancellation`.
- Produces:
  - `VoiceboxProvider(client: VoiceboxClient | None = None, model: str | None = None, concurrency: int | None = None)`
  - `stitch_wavs(paths: list[Path], output: Path, gap_seconds: float) -> list[float]`, which returns the duration of each line
  - `TTSFactory.get_provider("voicebox")`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_voicebox_provider.py`:

```python
"""VoiceboxProvider: voice resolution, engine choice, ordering, stitching, cleanup."""
import asyncio
import wave
from pathlib import Path

import pytest

from app.services.tts.voicebox import VoiceboxProvider, stitch_wavs
from app.services.tts.voicebox_client import VoiceboxError, VoiceboxModel, VoiceboxProfile


def write_wav(path: Path, seconds: float, rate: int) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))


class FakeClient:
    """Stands in for VoiceboxClient; each line's WAV length is taken from its text."""

    base_url = "http://vb.local:17493"

    def __init__(self, fail_on: str | None = None, delays: dict[str, float] | None = None):
        self.profiles = [
            VoiceboxProfile("p-halie", "Halie ", "en", "cloned", None),
            VoiceboxProfile("p-dad", "Dad", "en", "cloned", None),
            VoiceboxProfile("p-heart", "Heart (kokoro)", "en", "preset", "kokoro"),
        ]
        self.models = [VoiceboxModel("qwen-tts-1.7B", "Qwen", "qwen", "1.7B"),
                       VoiceboxModel("chatterbox-turbo", "Turbo", "chatterbox_turbo", None)]
        self.generated: list[dict] = []
        self.deleted: list[str] = []
        self.cancelled: list[str] = []
        self.fail_on, self.delays = fail_on, delays or {}
        self._texts: dict[str, str] = {}

    async def list_profiles(self, max_age=30.0):
        return self.profiles

    async def list_tts_models(self):
        return self.models

    async def generate(self, profile_id, text, language, engine, model_size):
        gen_id = f"g{len(self.generated)}"
        self.generated.append({"id": gen_id, "profile_id": profile_id, "text": text, "engine": engine, "model_size": model_size})
        self._texts[gen_id] = text
        return gen_id

    async def wait_until_done(self, generation_id, timeout):
        await asyncio.sleep(self.delays.get(self._texts[generation_id], 0))
        if self._texts[generation_id] == self.fail_on:
            raise VoiceboxError(f"Voicebox generation {generation_id} failed: boom")

    async def download_audio(self, generation_id, dest):
        seconds = float(self._texts[generation_id].split("s:")[0]) if "s:" in self._texts[generation_id] else 0.5
        write_wav(dest, seconds, 24000)

    async def delete_generation(self, generation_id):
        self.deleted.append(generation_id)

    async def cancel_generation(self, generation_id):
        self.cancelled.append(generation_id)

    async def close(self):
        pass


def script(*lines):
    return [{"speaker": speaker, "text": text} for speaker, text in lines]


@pytest.mark.asyncio
async def test_resolves_by_id_or_trimmed_case_insensitive_name_and_picks_engine(tmp_path):
    client = FakeClient()
    provider = VoiceboxProvider(client=client, model="qwen-tts-1.7B")
    result = await provider.synthesize_conversation(
        script(("HOST1", "1s: hello"), ("HOST2", "1s: hi"), ("HOST3", "1s: hey")),
        tmp_path / "out.wav",
        voice_map={"HOST1": "halie", "HOST2": "p-dad", "HOST3": "Heart (kokoro)"},
    )
    assert [g["profile_id"] for g in client.generated] == ["p-halie", "p-dad", "p-heart"]
    assert [(g["engine"], g["model_size"]) for g in client.generated] == [
        ("qwen", "1.7B"), ("qwen", "1.7B"), ("kokoro", None)]  # the preset keeps its own engine
    assert sorted(client.deleted) == ["g0", "g1", "g2"]  # history cleaned up
    assert result.format == "wav" and result.audio_path.exists()


@pytest.mark.asyncio
async def test_unknown_voice_fails_with_edit_the_cast_message(tmp_path):
    provider = VoiceboxProvider(client=FakeClient(), model="qwen-tts-1.7B")
    with pytest.raises(VoiceboxError, match=r"^'Zephyr' isn't a Voicebox voice\. Edit the cast\.$"):
        await provider.synthesize_conversation(script(("HOST1", "x")), tmp_path / "o.wav", voice_map={"HOST1": "Zephyr"})


@pytest.mark.asyncio
async def test_model_not_downloaded_or_unknown(tmp_path):
    with pytest.raises(VoiceboxError, match="isn't downloaded"):
        await VoiceboxProvider(client=FakeClient(), model="tada-1b").synthesize_conversation(
            script(("HOST1", "x")), tmp_path / "o.wav", voice_map={"HOST1": "Dad"})
    with pytest.raises(VoiceboxError, match="isn't supported"):
        await VoiceboxProvider(client=FakeClient(), model="mystery").synthesize_conversation(
            script(("HOST1", "x")), tmp_path / "o.wav", voice_map={"HOST1": "Dad"})


@pytest.mark.asyncio
async def test_empty_model_setting_uses_first_downloaded(tmp_path):
    client = FakeClient()
    await VoiceboxProvider(client=client, model="").synthesize_conversation(
        script(("HOST1", "x")), tmp_path / "o.wav", voice_map={"HOST1": "Dad"})
    assert client.generated[0]["engine"] == "qwen"


@pytest.mark.asyncio
async def test_concurrent_lines_keep_script_order_and_timings(tmp_path):
    # The first line finishes last; the output must still be in script order.
    client = FakeClient(delays={"1s: first": 0.05})
    provider = VoiceboxProvider(client=client, model="qwen-tts-1.7B", concurrency=3)
    result = await provider.synthesize_conversation(
        script(("HOST1", "1s: first"), ("HOST2", "2s: second"), ("HOST1", "0.5s: third")),
        tmp_path / "out.wav", voice_map={"HOST1": "Dad", "HOST2": "Halie"},
    )
    timings = result.segment_timings
    assert [t.text for t in timings] == ["1s: first", "2s: second", "0.5s: third"]
    assert [round(t.start_seconds, 2) for t in timings] == [0.0, 1.25, 3.5]  # 250 ms gaps
    assert round(result.duration_seconds, 2) == 4.0


@pytest.mark.asyncio
async def test_failed_line_cleans_up_every_generation(tmp_path):
    client = FakeClient(fail_on="bad")
    provider = VoiceboxProvider(client=client, model="qwen-tts-1.7B", concurrency=1)
    with pytest.raises(VoiceboxError, match="failed: boom"):
        await provider.synthesize_conversation(
            script(("HOST1", "ok"), ("HOST1", "bad"), ("HOST1", "never")),
            tmp_path / "o.wav", voice_map={"HOST1": "Dad"})
    assert set(client.deleted) == {g["id"] for g in client.generated}
    assert "never" not in [g["text"] for g in client.generated]
    assert not any(p.name.startswith(".voicebox-") for p in tmp_path.iterdir())  # temp dir removed


@pytest.mark.asyncio
async def test_cancellation_cancels_in_flight_generation(tmp_path):
    from app.services import cancellation
    from app.services.cancellation import BriefingCancelledException
    client = FakeClient(delays={"slow": 5})
    provider = VoiceboxProvider(client=client, model="qwen-tts-1.7B", concurrency=1)
    cancellation.register("b1")
    try:
        task = asyncio.create_task(provider.synthesize_conversation(
            script(("HOST1", "slow")), tmp_path / "o.wav", voice_map={"HOST1": "Dad"}, briefing_id="b1"))
        await asyncio.sleep(0.05)
        cancellation.signal("b1")
        with pytest.raises(BriefingCancelledException):
            await task
    finally:
        cancellation.unregister("b1")
    assert client.cancelled == ["g0"] and client.deleted == ["g0"]


def test_stitch_mixed_sample_rates_preserves_durations(tmp_path):
    a, b = tmp_path / "a.wav", tmp_path / "b.wav"
    write_wav(a, 1.0, 24000)
    write_wav(b, 2.0, 44100)
    out = tmp_path / "out.wav"
    durations = stitch_wavs([a, b], out, gap_seconds=0.25)
    assert [round(d, 2) for d in durations] == [1.0, 2.0]
    with wave.open(str(out)) as w:
        assert w.getframerate() == 24000 and w.getnchannels() == 1
        assert round(w.getnframes() / w.getframerate(), 2) == 3.25
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd backend && venv/bin/pytest tests/test_voicebox_provider.py -v`
Expected: `ModuleNotFoundError: No module named 'app.services.tts.voicebox'`.

- [ ] **Step 3: Implement the provider**

Create `backend/app/services/tts/voicebox.py`:

```python
"""Voicebox TTS provider: one Voicebox generation per script line, stitched locally.

Lines render with bounded concurrency so the server always has the next line
queued; output order follows the script. Audio is streamed to disk and
stitched one line at a time, so memory stays flat for long episodes.
"""

import asyncio
import shutil
import tempfile
import time
import wave
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.services.tts.base import SegmentTiming, TTSProvider, TTSResult, Voice
from app.services.tts.voicebox_client import (
    VOICEBOX_MODELS, VoiceboxClient, VoiceboxError, VoiceboxProfile,
)
from app.utils.audio import convert_to_mp3

GAP_SECONDS = 0.25
LINE_TIMEOUT_SECONDS = 300.0  # the first line may wait for a model to load


def stitch_wavs(paths: list[Path], output: Path, gap_seconds: float) -> list[float]:
    """Append WAVs into one mono WAV at the first file's rate; returns each line's duration."""
    from pydub import AudioSegment

    first = AudioSegment.from_wav(paths[0])
    rate, width = first.frame_rate, first.sample_width
    gap = b"\x00" * (int(gap_seconds * rate) * width)
    durations: list[float] = []
    with wave.open(str(output), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(width)
        out.setframerate(rate)
        for index, path in enumerate(paths):
            segment = AudioSegment.from_wav(path).set_channels(1).set_frame_rate(rate).set_sample_width(width)
            out.writeframes(segment.raw_data)
            durations.append(len(segment.raw_data) / (rate * width))
            if index < len(paths) - 1:
                out.writeframes(gap)
    return durations


def _normalize(name: str) -> str:
    return " ".join(name.split()).casefold()


def _first_error(error: BaseException) -> BaseException:
    """The first real failure inside (possibly nested) exception groups."""
    while isinstance(error, BaseExceptionGroup):
        real = [e for e in error.exceptions if not isinstance(e, asyncio.CancelledError)]
        error = (real or list(error.exceptions))[0]
    return error


class VoiceboxProvider(TTSProvider):
    def __init__(
        self,
        client: Optional[VoiceboxClient] = None,
        model: Optional[str] = None,
        concurrency: Optional[int] = None,
    ):
        settings = get_settings()
        if client is None:
            if not settings.voicebox_url:
                raise ValueError("Voicebox server URL required")
            client = VoiceboxClient(settings.voicebox_url)
        self.client = client
        self.model = settings.voicebox_model if model is None else model
        self.concurrency = max(1, concurrency or settings.voicebox_concurrency)

    async def close(self):
        await self.client.close()

    def list_voices(self) -> list[Voice]:
        # Voices are live on the server; the cast API uses registry.list_provider_voices.
        return []

    async def _resolve_voices(self, voice_ids: set[str]) -> dict[str, VoiceboxProfile]:
        profiles = await self.client.list_profiles()
        by_id = {p.id: p for p in profiles}
        by_name = {_normalize(p.name): p for p in profiles}
        resolved = {}
        for voice_id in voice_ids:
            profile = by_id.get(voice_id) or by_name.get(_normalize(voice_id))
            if profile is None:
                raise VoiceboxError(f"'{voice_id}' isn't a Voicebox voice. Edit the cast.")
            resolved[voice_id] = profile
        return resolved

    async def _default_engine(self) -> tuple[str, Optional[str]]:
        downloaded = await self.client.list_tts_models()
        if not self.model:
            if not downloaded:
                raise VoiceboxError(f"No supported TTS model is downloaded on {self.client.base_url}.")
            return downloaded[0].engine, downloaded[0].model_size
        if self.model not in VOICEBOX_MODELS:
            raise VoiceboxError(f"Voicebox model '{self.model}' isn't supported by Augustus.")
        if self.model not in {m.name for m in downloaded}:
            raise VoiceboxError(f"Voicebox model '{self.model}' isn't downloaded on {self.client.base_url}.")
        return VOICEBOX_MODELS[self.model]

    async def _render_line(
        self, text: str, profile: VoiceboxProfile, engine: tuple[str, Optional[str]],
        dest: Path, briefing_id: Optional[str],
    ) -> None:
        from app.services.cancellation import cancellable_await

        engine_name, size = (profile.preset_engine, None) if profile.voice_type == "preset" else engine
        started = time.monotonic()
        generation_id = await self.client.generate(profile.id, text, profile.language, engine_name, size)
        try:
            wait = self.client.wait_until_done(generation_id, LINE_TIMEOUT_SECONDS)
            if briefing_id:
                await cancellable_await(wait, briefing_id)
            else:
                await wait
            await self.client.download_audio(generation_id, dest)
        except BaseException:
            await asyncio.shield(self.client.cancel_generation(generation_id))
            raise
        finally:
            await asyncio.shield(self.client.delete_generation(generation_id))
        print(f"[Voicebox] {generation_id} ({profile.name.strip()}, {engine_name}) {time.monotonic() - started:.1f}s")

    async def synthesize_conversation(
        self,
        script: list[dict],
        output_path: Path,
        voice_map: Optional[dict[str, str]] = None,
        briefing_id: Optional[str] = None,
        style_prompt: Optional[str] = None,  # not supported by Voicebox engines yet
    ) -> TTSResult:
        voice_map = voice_map or {}
        lines = [
            (segment.get("speaker", "HOST1"), segment["text"].strip())
            for segment in script if segment.get("text", "").strip()
        ]
        if not lines:
            raise VoiceboxError("The script has no lines to speak.")
        voice_for = {speaker: voice_map.get(speaker, speaker) for speaker, _ in lines}
        profiles = await self._resolve_voices(set(voice_for.values()))
        engine = await self._default_engine()

        started = time.monotonic()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        workdir = Path(tempfile.mkdtemp(prefix=".voicebox-", dir=output_path.parent))
        try:
            paths = [workdir / f"{i:05d}.wav" for i in range(len(lines))]
            semaphore = asyncio.Semaphore(self.concurrency)

            async def render(i: int) -> None:
                async with semaphore:
                    speaker, text = lines[i]
                    await self._render_line(text, profiles[voice_for[speaker]], engine, paths[i], briefing_id)

            try:
                async with asyncio.TaskGroup() as group:  # the first failure cancels the rest
                    for i in range(len(lines)):
                        group.create_task(render(i))
            except BaseExceptionGroup as group_error:
                # Callers expect VoiceboxError / BriefingCancelledException, not a group.
                raise _first_error(group_error) from None

            wav_path = workdir / "episode.wav"
            durations = await asyncio.to_thread(stitch_wavs, paths, wav_path, GAP_SECONDS)
            fmt = await self._finalize(wav_path, output_path)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        timings, cursor = [], 0.0
        for index, ((speaker, text), duration) in enumerate(zip(lines, durations)):
            timings.append(SegmentTiming(index, speaker, text, cursor, cursor + duration, duration))
            cursor += duration + (GAP_SECONDS if index < len(lines) - 1 else 0.0)
        elapsed = time.monotonic() - started
        print(f"[Voicebox] {len(lines)} lines, {cursor:.1f}s audio in {elapsed:.1f}s "
              f"(real-time factor {elapsed / max(cursor, 0.01):.2f})")
        return TTSResult(output_path, cursor, "conversation", fmt, timings)

    async def _finalize(self, wav_path: Path, output_path: Path) -> str:
        if output_path.suffix.lower() == ".mp3":
            if await convert_to_mp3(wav_path, output_path):
                return "mp3"
            print("[Voicebox] MP3 conversion unavailable (ffmpeg missing); keeping WAV audio")
        shutil.move(str(wav_path), output_path)
        return "wav"

    async def synthesize(
        self, text: str, voice_id: str, output_path: Path, briefing_id: Optional[str] = None,
    ) -> TTSResult:
        return await self.synthesize_conversation(
            [{"speaker": "HOST1", "text": text}], output_path, {"HOST1": voice_id}, briefing_id=briefing_id,
        )
```

Notes for the implementer:
- `TaskGroup` raises a `BaseExceptionGroup`. `_first_error` unwraps it (skipping the siblings' `CancelledError`), so callers see a `VoiceboxError` or `BriefingCancelledException`. This was verified on the venv's Python 3.11. Errors from stitching or MP3 conversion are not groups and propagate unchanged.
- Python 3.11 is required; both the venv and Docker use 3.11.
- When MP3 conversion is unavailable, the WAV is moved to `output_path`, so a `.mp3` name can hold WAV data. That matches the Gemini provider's existing fallback. Docker has ffmpeg, so this only happens in local dev.

- [ ] **Step 4: Register the provider in the factory**

In `backend/app/services/tts/factory.py`, add `from app.services.tts.voicebox import VoiceboxProvider` and this branch before the `else`:

```python
        elif provider_name == "voicebox":
            if not settings.voicebox_url:
                raise ValueError("Voicebox server URL required")
            return VoiceboxProvider()
```

Update the docstring to list all four provider names.

- [ ] **Step 5: Run the tests**

Run: `cd backend && venv/bin/pytest tests/test_voicebox_provider.py -v && venv/bin/pytest -q`
Expected: everything passes. If `test_cancellation_cancels_in_flight_generation` hangs, `cancellable_await` is being bypassed; check that `briefing_id` is passed through.

- [ ] **Step 6: Stage the changes**

```bash
git add backend/app/services/tts/voicebox.py backend/app/services/tts/factory.py backend/tests/test_voicebox_provider.py
```

---

### Task 9: Voicebox settings API

**Files:**
- Modify: `backend/app/routers/settings.py`
- Test: `backend/tests/test_voicebox_settings.py`

**Interfaces:**
- Consumes: `VoiceboxClient`, `parse_version`, `MIN_TESTED_VERSION`, and `registry.TTS_PROVIDERS`.
- Produces:
  - Settings fields `voicebox_url`, `voicebox_model`, and `voicebox_configured` in the GET and PUT responses.
  - `GET /api/settings/voicebox/models?url=` returns `{models: [{name, display_name}]}`. It requires login.
  - `POST /api/settings/validate/voicebox {url}` returns `{valid, message, version, voice_count, warning}`. It requires login.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_voicebox_settings.py`:

```python
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

from app.routers import settings as routes
from app.routers.auth import get_current_user
from app.services.tts import voicebox_client as vc
from tests.test_voicebox_client import FakeVoicebox


@pytest.fixture
def isolated_settings(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("TTS_PROVIDER=gemini\n")
    monkeypatch.setattr(routes, "find_env_file", lambda: env_file)
    for key in ("VOICEBOX_URL", "VOICEBOX_MODEL"):
        monkeypatch.setenv(key, "")  # setenv (not delenv) so writes by update_settings are undone
    from app.config import get_settings
    get_settings.cache_clear()
    yield env_file
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_voicebox_round_trip_and_selection_requires_url(isolated_settings):
    with pytest.raises(HTTPException) as err:
        await routes.update_settings(routes.SettingsUpdate(tts_provider="voicebox"))
    assert err.value.status_code == 400
    result = await routes.update_settings(routes.SettingsUpdate(
        voicebox_url="http://vb.local:17493", voicebox_model="chatterbox-turbo", tts_provider="voicebox"))
    assert (result.tts_provider, result.voicebox_url, result.voicebox_model, result.voicebox_configured) == (
        "voicebox", "http://vb.local:17493", "chatterbox-turbo", True)
    assert "VOICEBOX_URL=http://vb.local:17493" in isolated_settings.read_text()
    with pytest.raises(HTTPException):  # cannot clear the URL while Voicebox is the provider
        await routes.update_settings(routes.SettingsUpdate(voicebox_url=""))


def test_update_validates_provider_and_url():
    with pytest.raises(ValidationError):
        routes.SettingsUpdate(tts_provider="mystery")
    with pytest.raises(ValidationError):
        routes.SettingsUpdate(voicebox_url="ftp://vb.local")
    routes.SettingsUpdate(voicebox_url="")  # clearing is allowed by the schema


@pytest.fixture
def api(monkeypatch):
    vc._profile_cache.clear()
    fake = FakeVoicebox()
    monkeypatch.setattr(routes, "VoiceboxClient",
                        lambda url: vc.VoiceboxClient(url, transport=httpx.MockTransport(fake)))
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/settings")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u")
    return app


@pytest.mark.asyncio
async def test_validate_and_models(api):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://test") as client:
        ok = (await client.post("/api/settings/validate/voicebox", json={"url": "http://vb.local:17493"})).json()
        models = (await client.get("/api/settings/voicebox/models", params={"url": "http://vb.local:17493"})).json()
        bad = await client.post("/api/settings/validate/voicebox", json={"url": "file:///etc/passwd"})
    assert ok == {"valid": True, "message": "Connected to Voicebox 0.5.0 · 2 voices",
                  "version": "0.5.0", "voice_count": 2, "warning": None}
    assert models == {"models": [{"name": "chatterbox-turbo", "display_name": "Chatterbox Turbo"},
                                 {"name": "qwen-tts-1.7B", "display_name": "Qwen TTS 1.7B"}]}
    assert bad.status_code == 422


@pytest.mark.parametrize("path", ["/voicebox/models", "/validate/voicebox"])
def test_new_voicebox_endpoints_require_login(path):
    """These endpoints make the server call a caller-supplied URL, so they must not be public."""
    route = next(r for r in routes.router.routes if r.path == path)
    assert any(dep.call is get_current_user for dep in route.dependant.dependencies)
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd backend && venv/bin/pytest tests/test_voicebox_settings.py -v`
Expected: `TypeError`/`ValidationError` about the unknown field `voicebox_url`.

- [ ] **Step 3: Implement the settings changes**

In `backend/app/routers/settings.py`:

1. Add the imports:

```python
from app.routers.auth import get_current_user
from app.services.tts.registry import TTS_PROVIDERS
from app.services.tts.voicebox_client import MIN_TESTED_VERSION, VoiceboxClient, VoiceboxError, parse_version
```

2. `SettingsResponse` gains `voicebox_url: Optional[str] = None`, `voicebox_model: str = ""`, and `voicebox_configured: bool = False`.

3. In `SettingsUpdate`, change `tts_provider` to `Optional[str] = None`, and add a validator. Add these fields:

```python
    voicebox_url: Optional[str] = Field(default=None, max_length=300, pattern=r"^(https?://[^\s]+)?$")
    voicebox_model: Optional[str] = Field(default=None, max_length=80, pattern=r"^[a-zA-Z0-9._-]*$")

    @field_validator("tts_provider")
    @classmethod
    def _known_tts_provider(cls, value):
        if value is not None and value not in TTS_PROVIDERS:
            raise ValueError(f"Unknown TTS provider: {value}")
        return value
```

Import `field_validator` from pydantic.

4. In `get_current_settings()`, add:

```python
        "voicebox_url": os.environ.get("VOICEBOX_URL") or env_vars.get("VOICEBOX_URL") or None,
        "voicebox_model": os.environ.get("VOICEBOX_MODEL") or env_vars.get("VOICEBOX_MODEL", ""),
```

5. In `get_settings_endpoint()`, pass `voicebox_url=settings["voicebox_url"]`, `voicebox_model=settings["voicebox_model"]`, and `voicebox_configured=bool(settings["voicebox_url"])`.

6. At the very top of `update_settings`, before the `try:` (the `try` wraps every exception as a 500), add:

```python
    current = get_current_settings()
    url_after = current["voicebox_url"] if updates.voicebox_url is None else updates.voicebox_url
    provider_after = updates.tts_provider or current["tts_provider"]
    if provider_after == "voicebox" and not url_after:
        raise HTTPException(
            status_code=400,
            detail="Add your Voicebox server URL before choosing Voicebox"
            if updates.tts_provider else "Choose another voice provider before removing the Voicebox URL",
        )
```

7. Inside the `try`, next to the `PIPER_URL` block, add:

```python
        for field in ("voicebox_url", "voicebox_model"):
            value = getattr(updates, field)
            if value is not None:
                env_updates[field.upper()] = value
                os.environ[field.upper()] = value
```

8. Add the endpoints near the other validators:

```python
class VoiceboxUrlRequest(BaseModel):
    url: str = Field(..., max_length=300, pattern=r"^https?://[^\s]+$")


@router.post("/validate/voicebox")
async def validate_voicebox(request: VoiceboxUrlRequest, user=Depends(get_current_user)):
    """Check a Voicebox server: reachable, API version, and how many voices it has."""
    client = VoiceboxClient(request.url)
    try:
        version = await client.version()
        voices = await client.list_profiles(max_age=0)
    except VoiceboxError as error:
        return {"valid": False, "message": str(error), "version": None, "voice_count": 0, "warning": None}
    finally:
        await client.close()
    warning = None
    if parse_version(version) < MIN_TESTED_VERSION:
        warning = (f"Voicebox {version} is older than the tested "
                   f"{'.'.join(map(str, MIN_TESTED_VERSION))}; some features may not work.")
    return {
        "valid": True,
        "message": f"Connected to Voicebox {version} · {len(voices)} voice{'s' if len(voices) != 1 else ''}",
        "version": version,
        "voice_count": len(voices),
        "warning": warning,
    }


@router.get("/voicebox/models")
async def voicebox_models(
    url: str = Query(..., max_length=300, pattern=r"^https?://[^\s]+$"),
    user=Depends(get_current_user),
):
    """Downloaded TTS models on a Voicebox server that Augustus knows how to use."""
    client = VoiceboxClient(url)
    try:
        models = await client.list_tts_models()
    except VoiceboxError as error:
        raise HTTPException(status_code=502, detail=str(error))
    finally:
        await client.close()
    return {"models": [{"name": m.name, "display_name": m.display_name} for m in models]}
```

Import `Query` from fastapi if it is not already imported.

- [ ] **Step 4: Run the tests**

Run: `cd backend && venv/bin/pytest tests/test_voicebox_settings.py -v && venv/bin/pytest -q`
Expected: everything passes.

- [ ] **Step 5: Stage the changes**

```bash
git add backend/app/routers/settings.py backend/tests/test_voicebox_settings.py
```

---

### Task 10: Voicebox card in Settings

**Files:**
- Modify: `frontend/src/api/client.ts`: `AppSettings`, the `settingsApi.update` keys, `validateVoicebox`, and `getVoiceboxModels`
- Modify: `frontend/src/components/settings/settingsLogic.ts` and `settingsLogic.test.ts`
- Create: `frontend/src/components/settings/VoiceboxSettings.tsx`
- Modify: `frontend/src/components/settings/TtsSettings.tsx`
- Modify: `frontend/src/pages/Settings.tsx`
- Modify: `frontend/src/pages/BriefingDetail.tsx`: show the Voicebox model next to the provider

**Interfaces:**
- Consumes: the Task 9 endpoints.
- Produces:
  - `isServerUrl(url: string): boolean`
  - `ttsProviderUpdate(selected: string, saved: string, voiceboxUrl: string): string | null`, which returns the provider value to save, or `null` to hold back
  - The `VoiceboxSettings` component

- [ ] **Step 1: Write the failing tests**

Append to `frontend/src/components/settings/settingsLogic.test.ts`:

```ts
import { isServerUrl, ttsProviderUpdate } from './settingsLogic'

describe('voicebox settings logic', () => {
  it('accepts only http(s) server URLs', () => {
    expect(isServerUrl('http://192.168.4.44:17493')).toBe(true)
    expect(isServerUrl('https://voicebox.home')).toBe(true)
    expect(isServerUrl('')).toBe(false)
    expect(isServerUrl('192.168.4.44:17493')).toBe(false)
    expect(isServerUrl('ftp://x')).toBe(false)
  })

  it('holds back switching to Voicebox until a URL is set', () => {
    expect(ttsProviderUpdate('voicebox', 'gemini', '')).toBeNull()
    expect(ttsProviderUpdate('voicebox', 'gemini', 'http://vb:17493')).toBe('voicebox')
    expect(ttsProviderUpdate('gemini', 'gemini', '')).toBeNull()      // unchanged
    expect(ttsProviderUpdate('piper', 'voicebox', '')).toBe('piper')
  })
})
```

If `describe`, `it`, or `expect` are not already imported at the top of the file, add them to the existing `vitest` import instead of adding a second import.

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd frontend && npx vitest run src/components/settings/settingsLogic.test.ts`
Expected: FAIL; `isServerUrl` is not exported.

- [ ] **Step 3: Implement the logic and the API client**

Append to `frontend/src/components/settings/settingsLogic.ts`:

```ts
export function isServerUrl(url: string): boolean {
  return /^https?:\/\/\S+$/.test(url.trim())
}

/** Provider to save, or null when nothing should be sent yet. */
export function ttsProviderUpdate(selected: string, saved: string, voiceboxUrl: string): string | null {
  if (selected === saved) return null
  if (selected === 'voicebox' && !isServerUrl(voiceboxUrl)) return null
  return selected
}
```

In `frontend/src/api/client.ts`:
- `AppSettings` gains `voicebox_url?: string | null`, `voicebox_model: string`, and `voicebox_configured: boolean`.
- The `settingsApi.update` parameter type gains `voicebox_url: string` and `voicebox_model: string`.
- Add these methods to `settingsApi`:

```ts
  validateVoicebox: async (url: string) => {
    const { data } = await api.post<{ valid: boolean; message: string; version: string | null; voice_count: number; warning: string | null }>(
      '/api/settings/validate/voicebox', { url })
    return data
  },

  getVoiceboxModels: async (url: string) => {
    const { data } = await api.get<{ models: Array<{ name: string; display_name: string }> }>(
      '/api/settings/voicebox/models', { params: { url } })
    return data.models
  },
```

- [ ] **Step 4: Write `VoiceboxSettings`**

Create `frontend/src/components/settings/VoiceboxSettings.tsx`:

```tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, Loader2, XCircle } from 'lucide-react'
import { settingsApi } from '../../api/client'
import { isServerUrl } from './settingsLogic'

interface VoiceboxSettingsProps {
  url: string
  onUrlChange: (value: string) => void
  model: string
  onModelChange: (value: string) => void
}

type TestResult = Awaited<ReturnType<typeof settingsApi.validateVoicebox>>

/** Connect a self-hosted Voicebox server and choose the model its cloned voices use. */
export default function VoiceboxSettings({ url, onUrlChange, model, onModelChange }: VoiceboxSettingsProps) {
  const [testing, setTesting] = useState(false)
  const [result, setResult] = useState<TestResult | null>(null)
  const validUrl = isServerUrl(url)

  const { data: models, isLoading: modelsLoading, error: modelsError } = useQuery({
    queryKey: ['voicebox-models', url.trim()],
    queryFn: () => settingsApi.getVoiceboxModels(url.trim()),
    enabled: validUrl,
    staleTime: 60_000,
    retry: false,
  })

  const testConnection = async () => {
    setTesting(true)
    try {
      setResult(await settingsApi.validateVoicebox(url.trim()))
    } catch (error) {
      setResult({ valid: false, message: (error as Error).message, version: null, voice_count: 0, warning: null })
    } finally {
      setTesting(false)
    }
  }

  return (
    <>
      <div>
        <label className="label" htmlFor="voicebox-url">Voicebox server URL</label>
        <div className="flex gap-2">
          <input
            id="voicebox-url"
            type="url"
            value={url}
            onChange={(e) => { onUrlChange(e.target.value); setResult(null) }}
            placeholder="http://localhost:17493"
            className="input flex-1"
          />
          <button type="button" className="btn btn-secondary" onClick={testConnection} disabled={!validUrl || testing}>
            {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Test connection'}
          </button>
        </div>
        <p className="text-xs text-augustus-500 mt-1">
          Where your Voicebox app is running. Clear it to disconnect (choose another provider first).
        </p>
        {!url.trim() && (
          <p className="text-xs text-yellow-400 mt-1">Add your Voicebox server URL to use Voicebox.</p>
        )}
        {url.trim() && !validUrl && (
          <p className="text-xs text-red-400 mt-1">Start the URL with http:// or https://</p>
        )}
        {result && (
          <p className={`mt-2 flex items-center gap-1.5 text-sm ${result.valid ? 'text-green-400' : 'text-red-400'}`}>
            {result.valid ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
            {result.message}
          </p>
        )}
        {result?.warning && <p className="mt-1 text-xs text-yellow-400">{result.warning}</p>}
      </div>

      <div>
        <label className="label" htmlFor="voicebox-model">Model</label>
        <select
          id="voicebox-model"
          className="input w-full"
          value={model}
          onChange={(e) => onModelChange(e.target.value)}
          disabled={!validUrl || modelsLoading || !!modelsError}
        >
          <option value="">{modelsLoading ? 'Loading models…' : 'First available model'}</option>
          {(models ?? []).map(m => (
            <option key={m.name} value={m.name}>{m.display_name}</option>
          ))}
        </select>
        <p className="text-xs text-augustus-500 mt-1">
          {modelsError
            ? `Couldn't load models: ${(modelsError as Error).message}`
            : 'Used for your cloned voices. Preset voices always use their own engine.'}
        </p>
      </div>
    </>
  )
}
```

- [ ] **Step 5: Wire it into Settings**

In `frontend/src/components/settings/TtsSettings.tsx`:
- Add the props `voiceboxUrl`, `onVoiceboxUrlChange`, `voiceboxModel`, and `onVoiceboxModelChange`, all typed as `string` or `(value: string) => void`.
- Import `VoiceboxSettings`.
- Add a fourth `ProviderOption` after Gemini:

```tsx
            <ProviderOption
              selected={provider === 'voicebox'}
              onSelect={() => onProviderChange('voicebox')}
              name="Voicebox"
              ready={settings?.voicebox_configured}
              description="Self-hosted, your cloned voices"
            />
```

- Change the options container to `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4`, replacing `flex flex-col sm:flex-row`, so four cards fit. In `ProviderOption`, drop `flex-1` from the button class.
- After the Gemini block, add:

```tsx
        {provider === 'voicebox' && (
          <VoiceboxSettings
            url={voiceboxUrl}
            onUrlChange={onVoiceboxUrlChange}
            model={voiceboxModel}
            onModelChange={onVoiceboxModelChange}
          />
        )}
```

In `frontend/src/pages/Settings.tsx`:
- Add state: `const [voiceboxUrl, setVoiceboxUrl] = useState('')` and `const [voiceboxModel, setVoiceboxModel] = useState('')`.
- Hydrate in the settings effect: `setVoiceboxUrl(settings.voicebox_url || '')` and `setVoiceboxModel(settings.voicebox_model || '')`.
- In `handleSave`, replace `if (ttsProvider !== settings.tts_provider) updates.tts_provider = ttsProvider` with:

```tsx
    if ((voiceboxUrl || '') !== (settings.voicebox_url || '') && (voiceboxUrl === '' || isServerUrl(voiceboxUrl))) {
      updates.voicebox_url = voiceboxUrl.trim()
    }
    if ((voiceboxModel || '') !== (settings.voicebox_model || '')) updates.voicebox_model = voiceboxModel
    const providerUpdate = ttsProviderUpdate(ttsProvider, settings.tts_provider, voiceboxUrl)
    if (providerUpdate) updates.tts_provider = providerUpdate
```

- Import `isServerUrl` and `ttsProviderUpdate` from `../components/settings/settingsLogic`. Add `voiceboxUrl` and `voiceboxModel` to the `useCallback` dependency array.
- Pass the four new props to `<TtsSettings>`.

In `frontend/src/pages/BriefingDetail.tsx`, next to the existing `settings.tts_provider === 'gemini' && settings.gemini_model` line, add the Voicebox equivalent. Use the same markup and show `settings.voicebox_model || 'first available model'`.

- [ ] **Step 6: Verify**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npm run build`
Expected: all pass.

- [ ] **Step 7: Stage the changes**

```bash
git add frontend/src
```

---

### Task 11: Live verification against a real Voicebox, then commit Part 2

**Files:** no new files. This task verifies the work and commits it.

- [ ] **Step 1: Run the full automated suites**

```bash
cd backend && venv/bin/pytest -q
cd ../frontend && eval "$(/opt/homebrew/bin/brew shellenv)" && npx vitest run && npx tsc --noEmit && npm run build
cd .. && python3 scripts/version.py --check
```

Expected: all pass, and the version check reports the three files in sync.

- [ ] **Step 2: Run a live check against `http://192.168.4.44:17493`**

Start the app with `./dev.sh`.

1. In Settings, choose Voicebox. Confirm the "Add your Voicebox server URL" hint appears and the provider change is not saved yet.
2. Enter `http://192.168.4.44:17493` and click **Test connection**. Expect "Connected to Voicebox 0.5.0 · 9 voices".
3. The model dropdown lists the downloaded TTS models (Qwen, Chatterbox, Kokoro, TADA, and so on) and no Whisper or LLM models. Choose **Chatterbox Turbo**.
4. The provider hint reads "No Voicebox casts yet…". Click **Create a cast →**.
5. The cast editor badge reads "These hosts use Voicebox voices". Build Alex = Dad and Sam = Kevin from the dropdown and save. It becomes the default.
6. The Casts page title reads "Voicebox casts", and the other casts appear under "N casts for other providers".
7. Generate a Short briefing. Expect: it completes, both voices are audible, chapters line up with the transcript, and the backend log shows lines per second and the real-time factor.
8. Check the Voicebox history for leftover items:

```bash
curl -s "http://192.168.4.44:17493/history?limit=5" | python3 -c "import json,sys; print([i['text'][:40] for i in json.load(sys.stdin)['items']])"
```

   No lines from this briefing should be listed.
9. Start another briefing and cancel it mid-audio. It shows as cancelled, and the Voicebox history has no leftovers.
10. Switch the provider to Gemini. The dashboard picker and Casts page show Gemini casts without a reload. Switch back to Voicebox.

If any step fails, stop and debug with superpowers:systematic-debugging before committing.

- [ ] **Step 3: Commit Part 2**

```bash
git add backend frontend
git status --short   # do not stage backend/scripts/ or dev.sh (untracked, unrelated)
git commit -m "$(cat <<'EOF'
feat: Voicebox TTS provider for self-hosted cloned voices

Connect any Voicebox server in Settings (URL, connection test, model
choice from the server's downloaded models) and build casts from its
voice profiles. Lines render with bounded concurrency over Voicebox's
status stream, stream to disk and are stitched in script order; history
items are always cleaned up, cancellation stops in-flight lines, and
Voicebox briefings get a longer timeout budget.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: Ask about the release bump**

Ask the user whether this is a feature release. If yes, run `python3 scripts/version.py --bump minor`, verify with `--check`, and commit the three version files separately. Otherwise leave the automatic patch bumps as they are.
