# Podcast Experience Upgrades Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ID3 chapter embedding, live web research + source attribution, global briefing search, and an ephemeral play queue to Augustus.

**Architecture:** Backend is FastAPI + SQLAlchemy (async, aiosqlite) with a multi-agent briefing pipeline in `backend/app/services/briefing.py`. Frontend is React + Vite + Zustand. Three features are backend-touching (ID3, search, web research); the queue is frontend-only. No DB migration is required — web research reuses the existing `extra_data`/`sources` JSON fields.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x async, mutagen, pydub; React 18, TypeScript, Zustand, TanStack Query. New test infra: pytest + pytest-asyncio (backend), vitest (frontend pure logic).

**Environment notes for the implementer:**
- Run all backend commands with the venv interpreter: `backend/venv/bin/python` and `backend/venv/bin/pytest`.
- **ffmpeg/ffprobe are NOT installed.** Tests must not depend on them. The MP3 test fixture is built from raw MPEG frame bytes (provided below), which mutagen parses fine.
- Audio files are always written as `briefing_<id>.mp3` (`briefing.py:637`).
- The chapter object shape used throughout is `{"title": str, "start_time": float, "end_time": float}` (seconds).

---

## Task 0a: Backend test infrastructure

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/pytest.ini`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Add test deps to requirements**

Append to `backend/requirements.txt`:

```
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

- [ ] **Step 2: Install them**

Run: `backend/venv/bin/pip install pytest>=8.0.0 pytest-asyncio>=0.23.0`
Expected: installs successfully.

- [ ] **Step 3: Create `backend/pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
pythonpath = .
```

- [ ] **Step 4: Create `backend/tests/__init__.py`** (empty file)

```python
```

- [ ] **Step 5: Create `backend/tests/conftest.py`**

```python
"""Shared test fixtures."""
import os
import tempfile

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database import Base
# Import all models so Base.metadata is fully populated before create_all.
import app.models  # noqa: F401


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """In-memory async SQLite session with all tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


def make_silent_mp3(path: str, frames: int = 40) -> None:
    """Write a minimal valid MPEG-1 Layer III MP3 (128kbps, 44.1kHz, mono).

    No ffmpeg needed. Each frame is 417 bytes: a 4-byte header + zero padding.
    """
    header = bytes([0xFF, 0xFB, 0x90, 0xC0])
    frame = header + bytes(417 - len(header))
    with open(path, "wb") as f:
        f.write(frame * frames)


@pytest.fixture
def silent_mp3(tmp_path):
    """Path to a freshly generated silent MP3 file."""
    p = str(tmp_path / "test.mp3")
    make_silent_mp3(p)
    return p
```

- [ ] **Step 6: Verify infra runs**

Run: `cd backend && venv/bin/python -c "import app.models; from app.database import Base; print(len(Base.metadata.tables), 'tables')"`
Expected: prints a table count > 5 with no import errors.

- [ ] **Step 7: Commit**

```bash
git add backend/requirements.txt backend/pytest.ini backend/tests/__init__.py backend/tests/conftest.py
git commit -m "test: add backend pytest infrastructure"
```

---

## Task 0b: Frontend test infrastructure

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.ts`

- [ ] **Step 1: Install vitest**

Run: `cd frontend && npm install -D vitest@^1.6.0`
Expected: adds vitest to devDependencies.

- [ ] **Step 2: Add a test script to `frontend/package.json`**

In the `"scripts"` block, add:

```json
    "test": "vitest run",
```

- [ ] **Step 3: Create `frontend/vitest.config.ts`**

```ts
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
})
```

- [ ] **Step 4: Verify (no tests yet is OK)**

Run: `cd frontend && npx vitest run`
Expected: exits 0 with "No test files found" (passes).

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.ts
git commit -m "test: add frontend vitest infrastructure"
```

---

## Task 1: ID3 chapter embedding helper

**Files:**
- Modify: `backend/app/utils/audio.py`
- Create: `backend/tests/test_audio_chapters.py`

- [ ] **Step 1: Write the failing test** — create `backend/tests/test_audio_chapters.py`

```python
"""Tests for ID3 chapter embedding."""
from mutagen.id3 import ID3

from app.utils.audio import embed_chapters_in_mp3


def test_embed_writes_chap_and_ctoc(silent_mp3):
    chapters = [
        {"title": "Intro", "start_time": 0.0, "end_time": 2.0},
        {"title": "Story One", "start_time": 2.0, "end_time": 5.0},
        {"title": "Wrap Up", "start_time": 5.0, "end_time": 7.5},
    ]
    ok = embed_chapters_in_mp3(silent_mp3, chapters, title="My Briefing")
    assert ok is True

    tags = ID3(silent_mp3)
    chaps = tags.getall("CHAP")
    ctocs = tags.getall("CTOC")
    assert len(chaps) == 3
    assert len(ctocs) == 1
    # Sorted by element id chp0/chp1/chp2; verify titles + start times round-trip.
    by_id = {c.element_id: c for c in chaps}
    assert by_id["chp0"].sub_frames.getall("TIT2")[0].text[0] == "Intro"
    assert by_id["chp0"].start_time == 0
    assert by_id["chp1"].start_time == 2000
    assert by_id["chp2"].end_time == 7500
    assert tags.getall("TIT2")[0].text[0] == "My Briefing"


def test_embed_is_idempotent(silent_mp3):
    chapters = [{"title": "A", "start_time": 0.0, "end_time": 1.0}]
    embed_chapters_in_mp3(silent_mp3, chapters)
    embed_chapters_in_mp3(silent_mp3, chapters)
    tags = ID3(silent_mp3)
    assert len(tags.getall("CHAP")) == 1
    assert len(tags.getall("CTOC")) == 1


def test_embed_empty_chapters_returns_false(silent_mp3):
    assert embed_chapters_in_mp3(silent_mp3, []) is False


def test_embed_bad_path_returns_false_no_raise():
    assert embed_chapters_in_mp3("/nonexistent/path/x.mp3", [{"title": "A", "start_time": 0.0, "end_time": 1.0}]) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_audio_chapters.py -v`
Expected: FAIL with `ImportError: cannot import name 'embed_chapters_in_mp3'`.

- [ ] **Step 3: Implement the helper** — append to `backend/app/utils/audio.py`

```python
def embed_chapters_in_mp3(filepath, chapters: list, title: Optional[str] = None) -> bool:
    """Embed ID3v2 CHAP/CTOC chapter frames into an MP3 so external players show chapters.

    Args:
        filepath: Path to the MP3 file (str or Path).
        chapters: list of {"title", "start_time", "end_time"} (seconds).
        title: Optional track title to set (TIT2).

    Returns:
        True if chapters were embedded; False on no-op or failure (never raises).
    """
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, CHAP, CTOC, TIT2, CTOCFlags

    try:
        path = str(filepath)
        if not path.lower().endswith(".mp3"):
            return False

        audio = MP3(path, ID3=ID3)
        if audio.tags is None:
            audio.add_tags()
        tags = audio.tags

        # Clear any existing chapter frames so this is idempotent.
        for key in list(tags.keys()):
            if key.startswith("CHAP") or key.startswith("CTOC"):
                del tags[key]

        if not chapters:
            audio.save()
            return False

        child_ids = []
        for i, ch in enumerate(chapters):
            element_id = f"chp{i}"
            child_ids.append(element_id)
            start_ms = int(float(ch.get("start_time") or 0) * 1000)
            end_raw = ch.get("end_time")
            end_ms = int(float(end_raw) * 1000) if end_raw is not None else start_ms
            chap_title = ch.get("title") or f"Chapter {i + 1}"
            tags.add(CHAP(
                element_id=element_id,
                start_time=start_ms,
                end_time=end_ms,
                sub_frames=[TIT2(encoding=3, text=[chap_title])],
            ))

        tags.add(CTOC(
            element_id="toc",
            flags=CTOCFlags.TOP_LEVEL | CTOCFlags.ORDERED,
            child_element_ids=child_ids,
            sub_frames=[TIT2(encoding=3, text=["Chapters"])],
        ))

        if title:
            tags.add(TIT2(encoding=3, text=[title]))

        audio.save()
        return True
    except Exception as e:
        print(f"[Audio] Failed to embed chapters into {filepath}: {e}")
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && venv/bin/pytest tests/test_audio_chapters.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/utils/audio.py backend/tests/test_audio_chapters.py
git commit -m "feat: add ID3 chapter embedding helper"
```

---

## Task 2: Wire chapter embedding into the briefing pipeline

**Files:**
- Modify: `backend/app/services/briefing.py` (storage step, near line 684 where `briefing.audio_filename` is set and chapters with timestamps exist)

- [ ] **Step 1: Locate the storage step**

Run: `cd backend && grep -n "briefing.audio_filename = audio_filename" app/services/briefing.py`
Expected: one match (~line 684). The code nearby already computed `chapters` (list of dicts with timestamps) and `audio_filename = f"briefing_{briefing.id}.mp3"`, saved into `AUDIO_STORAGE_PATH`.

- [ ] **Step 2: Confirm imports**

Run: `cd backend && grep -n "from app.utils.audio import\|import app.utils.audio\|get_audio_duration" app/services/briefing.py`
Expected: there is an existing import from `app.utils.audio`. Add `embed_chapters_in_mp3` to that import list. If no such import exists, add at top of file:
`from app.utils.audio import embed_chapters_in_mp3`

- [ ] **Step 3: Add the embed call after audio is saved and chapters are known**

Immediately after the audio file is written to disk and `chapters` (with real start/end times) is computed — i.e., right after `briefing.audio_filename = audio_filename` is set — insert:

```python
            # Embed ID3 chapters so external podcast players show them (new briefings only).
            try:
                if chapters:
                    audio_path = os.path.join(get_settings().audio_storage_path, audio_filename)
                    embed_chapters_in_mp3(audio_path, chapters, title=briefing.title)
            except Exception as e:
                print(f"[Briefing] Chapter embedding skipped: {e}")
```

Note: `os` and `get_settings` are already imported in this module (verify with `grep -n "^import os\|get_settings" app/services/briefing.py`). Use the same path-construction style already used when the file was written — match the existing variable used for the audio directory if it differs from `get_settings().audio_storage_path`.

- [ ] **Step 4: Verify the module imports cleanly**

Run: `cd backend && venv/bin/python -c "import app.services.briefing"`
Expected: no errors.

- [ ] **Step 5: Manual smoke (optional but recommended)**

Generate a briefing via the running app, download the MP3, then run:
`backend/venv/bin/python -c "from mutagen.id3 import ID3; print(len(ID3('PATH/TO/briefing_x.mp3').getall('CHAP')), 'chapters')"`
Expected: chapter count matches the briefing.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/briefing.py
git commit -m "feat: embed ID3 chapters when generating briefings"
```

---

## Task 3: Global search — backend service + endpoint

**Files:**
- Modify: `backend/app/services/briefing.py` (`list_briefings`, starts line 1084)
- Modify: `backend/app/routers/briefings.py` (`list_briefings` endpoint, line 68)
- Create: `backend/tests/test_briefing_search.py`

- [ ] **Step 1: Write the failing test** — create `backend/tests/test_briefing_search.py`

```python
"""Tests for global briefing search (q param)."""
import pytest

from app.models.user import User
from app.models.briefing import Briefing
from app.services.briefing import BriefingService


async def _seed(db):
    user = User(id="u1", email="u@test.com")
    db.add(user)
    db.add_all([
        Briefing(id="b1", user_id="u1", title="Tech Roundup",
                 transcript="Apple announced a new chip today.", status="completed"),
        Briefing(id="b2", user_id="u1", title="World News",
                 transcript="Elections were held in several countries.", status="completed"),
        Briefing(id="b3", user_id="u1", title="Market Update",
                 transcript="The apple harvest affected commodity prices.", status="completed"),
    ])
    await db.commit()
    return user


@pytest.mark.asyncio
async def test_search_matches_title(db_session):
    await _seed(db_session)
    service = BriefingService(db_session)
    results, total = await service.list_briefings("u1", q="world")
    assert total == 1
    assert results[0].id == "b2"


@pytest.mark.asyncio
async def test_search_matches_transcript_case_insensitive(db_session):
    await _seed(db_session)
    service = BriefingService(db_session)
    results, total = await service.list_briefings("u1", q="APPLE")
    ids = {b.id for b in results}
    assert ids == {"b1", "b3"}
    assert total == 2


@pytest.mark.asyncio
async def test_empty_q_returns_all(db_session):
    await _seed(db_session)
    service = BriefingService(db_session)
    _, total = await service.list_briefings("u1", q="")
    assert total == 3


@pytest.mark.asyncio
async def test_search_escapes_like_wildcards(db_session):
    await _seed(db_session)
    service = BriefingService(db_session)
    # A literal '%' should match nothing, not act as wildcard.
    _, total = await service.list_briefings("u1", q="%")
    assert total == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_briefing_search.py -v`
Expected: FAIL — `list_briefings() got an unexpected keyword argument 'q'`.

- [ ] **Step 3: Add `q` to the service method**

In `backend/app/services/briefing.py`, change the `list_briefings` signature (line ~1084) to add `q` after `favorite`:

```python
        favorite: Optional[bool] = None,
        q: Optional[str] = None,
```

Then, after the existing `favorite` filter block and before ordering/pagination is applied, add:

```python
        # Apply text search across title + transcript if provided
        if q and q.strip():
            from sqlalchemy import or_
            escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            query = query.where(
                or_(
                    Briefing.title.ilike(pattern, escape="\\"),
                    Briefing.transcript.ilike(pattern, escape="\\"),
                )
            )
```

Important: this block MUST be added to the same `query` before the count and the limit/offset are applied, so `total` reflects the filtered set. Verify by reading how `total` is computed in the method (it runs a count on the filtered query). If the count query is built separately, apply the same `q` filter to it too.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && venv/bin/pytest tests/test_briefing_search.py -v`
Expected: 4 passed.

- [ ] **Step 5: Wire `q` into the endpoint**

In `backend/app/routers/briefings.py`, add to the `list_briefings` endpoint params (line ~68, after `favorite`):

```python
    q: Optional[str] = None,
```

And pass it through to the service call:

```python
        favorite=favorite,
        q=q,
```

- [ ] **Step 6: Verify endpoint module imports**

Run: `cd backend && venv/bin/python -c "import app.routers.briefings"`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/briefing.py backend/app/routers/briefings.py backend/tests/test_briefing_search.py
git commit -m "feat: add global briefing search (q over title + transcript)"
```

---

## Task 4: Global search — frontend

**Files:**
- Modify: `frontend/src/api/client.ts` (`briefingsApi.list`, line ~272)
- Modify: `frontend/src/pages/DashboardBriefs.tsx`

- [ ] **Step 1: Add `q` to the API client**

In `frontend/src/api/client.ts`, extend `briefingsApi.list` signature and params:

```ts
  list: async (
    limit = 10,
    offset = 0,
    listened?: boolean,
    cast_id?: string,
    topic_ids?: string[],
    favorite?: boolean,
    q?: string
  ) => {
```

Then before the `api.get` call, add:

```ts
    if (q && q.trim()) {
      params.set('q', q.trim())
    }
```

- [ ] **Step 2: Add search state + debounce in DashboardBriefs.tsx**

Read the file first to match its existing patterns. Add near the other filter state:

```tsx
  const [searchInput, setSearchInput] = useState('')
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    const t = setTimeout(() => setSearchQuery(searchInput), 300)
    return () => clearTimeout(t)
  }, [searchInput])
```

- [ ] **Step 3: Include `searchQuery` in the briefings query**

Find the `useQuery` whose `queryKey` is `['briefings', ...]` and whose `queryFn` calls `briefingsApi.list(...)`. Add `searchQuery` to BOTH the `queryKey` array and the `briefingsApi.list(...)` call (as the new last `q` argument). Example:

```tsx
    queryKey: ['briefings', page, listenedFilter, favoriteFilter, castFilter, topicFilter, searchQuery],
    queryFn: () => briefingsApi.list(limit, page * limit, listenedFilter, castFilter, topicFilter, favoriteFilter, searchQuery),
```

(Match the exact existing argument order/names already present in the file — only append `searchQuery`.)

- [ ] **Step 4: Add the search input to the filter bar**

In the filter bar JSX, add an input bound to `searchInput`. Use the existing input styling classes already present in the file (e.g. reuse a className from another text input). Add a clear (X) button when `searchInput` is non-empty:

```tsx
  <div className="relative">
    <input
      type="search"
      value={searchInput}
      onChange={(e) => setSearchInput(e.target.value)}
      placeholder="Search briefings…"
      className="input w-full" /* match existing input class in this file */
      aria-label="Search briefings"
    />
  </div>
```

- [ ] **Step 5: Bypass grouping while searching**

Where the component splits results into "Unplayed"/"Listened" groups, guard it: when `searchQuery.trim()` is non-empty, render a single flat list of returned briefings instead of the grouped sections, and show an empty state (`No briefings match "<searchQuery>"`) when the list is empty. Reuse the existing briefing-card rendering.

- [ ] **Step 6: Typecheck + build**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: no type errors, build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/pages/DashboardBriefs.tsx
git commit -m "feat: add briefing search bar to dashboard"
```

---

## Task 5: Queue store slice + tests

**Files:**
- Modify: `frontend/src/store/useStore.ts`
- Create: `frontend/src/store/queue.ts` (pure queue reducer logic, unit-testable without React)
- Create: `frontend/src/store/queue.test.ts`

Rationale: keep the queue mutation logic as pure functions in `queue.ts` so it is testable in vitest (node env) without mounting the store/audio manager. `useStore.ts` imports and uses them.

- [ ] **Step 1: Write the failing test** — create `frontend/src/store/queue.test.ts`

```ts
import { describe, it, expect } from 'vitest'
import { addToQueue, playNext, removeFromQueue, reorderQueue, type QueueItem } from './queue'

const item = (id: string): QueueItem => ({ id, type: 'briefing', title: id, audioUrl: `/audio/${id}.mp3` })

describe('queue logic', () => {
  it('appends to queue, no duplicates', () => {
    let q: QueueItem[] = []
    q = addToQueue(q, item('a'))
    q = addToQueue(q, item('b'))
    q = addToQueue(q, item('a')) // duplicate ignored
    expect(q.map(i => i.id)).toEqual(['a', 'b'])
  })

  it('playNext inserts at head and dedupes existing', () => {
    let q: QueueItem[] = [item('a'), item('b')]
    q = playNext(q, item('b')) // moves b to head
    expect(q.map(i => i.id)).toEqual(['b', 'a'])
    q = playNext(q, item('c'))
    expect(q.map(i => i.id)).toEqual(['c', 'b', 'a'])
  })

  it('removeFromQueue removes by id', () => {
    const q = removeFromQueue([item('a'), item('b'), item('c')], 'b')
    expect(q.map(i => i.id)).toEqual(['a', 'c'])
  })

  it('reorderQueue moves item between indices', () => {
    const q = reorderQueue([item('a'), item('b'), item('c')], 0, 2)
    expect(q.map(i => i.id)).toEqual(['b', 'c', 'a'])
  })

  it('reorderQueue is a no-op for out-of-range indices', () => {
    const orig = [item('a'), item('b')]
    expect(reorderQueue(orig, 5, 0).map(i => i.id)).toEqual(['a', 'b'])
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/store/queue.test.ts`
Expected: FAIL — cannot resolve `./queue`.

- [ ] **Step 3: Create `frontend/src/store/queue.ts`**

```ts
export interface QueueItem {
  id: string
  type: 'briefing'
  title: string
  audioUrl: string
  transcript?: string
  chapters?: Array<{ title: string; start_time: number; end_time?: number }>
}

/** Append item to the end, ignoring if its id is already queued. */
export function addToQueue(queue: QueueItem[], item: QueueItem): QueueItem[] {
  if (queue.some(q => q.id === item.id)) return queue
  return [...queue, item]
}

/** Put item at the head; remove any existing copy first. */
export function playNext(queue: QueueItem[], item: QueueItem): QueueItem[] {
  return [item, ...queue.filter(q => q.id !== item.id)]
}

export function removeFromQueue(queue: QueueItem[], id: string): QueueItem[] {
  return queue.filter(q => q.id !== id)
}

export function reorderQueue(queue: QueueItem[], from: number, to: number): QueueItem[] {
  if (from < 0 || from >= queue.length || to < 0 || to >= queue.length || from === to) {
    return queue
  }
  const next = [...queue]
  const [moved] = next.splice(from, 1)
  next.splice(to, 0, moved)
  return next
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/store/queue.test.ts`
Expected: 5 passed.

- [ ] **Step 5: Add queue state to the store**

In `frontend/src/store/useStore.ts`:

Add import at top:

```ts
import { addToQueue, playNext as playNextQueue, removeFromQueue, reorderQueue, type QueueItem } from './queue'
```

Add to the `AudioState` interface:

```ts
  queue: QueueItem[]
```

Add to the `AppState` interface (action signatures):

```ts
  addToQueue: (item: QueueItem) => void
  playNext: (item: QueueItem) => void
  removeFromQueue: (id: string) => void
  reorderQueue: (from: number, to: number) => void
  clearQueue: () => void
  playFromQueueHead: () => boolean  // returns true if a queued item was started
```

In the store body, initialize `queue: []` (next to `currentAudio: null`) and add the actions:

```ts
  queue: [],
  addToQueue: (item) => set({ queue: addToQueue(get().queue, item) }),
  playNext: (item) => set({ queue: playNextQueue(get().queue, item) }),
  removeFromQueue: (id) => set({ queue: removeFromQueue(get().queue, id) }),
  reorderQueue: (from, to) => set({ queue: reorderQueue(get().queue, from, to) }),
  clearQueue: () => set({ queue: [] }),
  playFromQueueHead: () => {
    const { queue, playAudio } = get()
    if (queue.length === 0) return false
    const [head, ...rest] = queue
    set({ queue: rest })
    playAudio({ ...head, initialPosition: 0 })
    return true
  },
```

- [ ] **Step 6: Persist the queue to localStorage**

In the `persist(...)` config at the bottom of the file, extend `partialize` to also persist the queue:

```ts
      partialize: (state) => ({
        currentProfile: state.currentProfile,
        queue: state.queue,
      }),
```

- [ ] **Step 7: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/store/queue.ts frontend/src/store/queue.test.ts frontend/src/store/useStore.ts
git commit -m "feat: add ephemeral play queue to store"
```

---

## Task 6: Queue playback integration + UI

**Files:**
- Modify: `frontend/src/components/AudioPlayer.tsx`
- Modify: `frontend/src/pages/DashboardBriefs.tsx`
- Modify: `frontend/src/pages/BriefingDetail.tsx`

- [ ] **Step 1: Advance to queue head on track end**

In `AudioPlayer.tsx`, the `onEnded` handler (~line 216) currently resets position and calls `playNextUnlistenedBriefing()`. Pull `playFromQueueHead` and `queue` from the store, and change the end-of-track logic so the queue wins:

```tsx
    const unsubEnded = audioManager.onEnded(() => {
      setIsPlaying(false)
      if (currentAudio?.type === 'briefing' && currentAudio.id) {
        savePositionMutation.mutate({ id: currentAudio.id, position: 0 })
        lastSavedPositionRef.current = 0
        // Queue takes priority over auto-play-next.
        const startedFromQueue = playFromQueueHead()
        if (!startedFromQueue) {
          playNextUnlistenedBriefing()
        }
      }
    })
```

Add `playFromQueueHead` (and `queue`) to the destructured store values and to the effect's dependency array.

- [ ] **Step 2: Add an "Up Next" panel toggle in the expanded player**

In the expanded view's bottom controls (near the chapters/transcript toggle, ~line 1120), add a button that toggles a `showQueue` state (`const [showQueue, setShowQueue] = useState(false)`). When on, render the queue above the controls (similar placement to the chapters panel ~line 785):

```tsx
{showQueue && (
  <div className="mb-2 sm:mb-3 max-h-40 overflow-auto bg-augustus-950/50 rounded-lg p-2">
    {queue.length === 0 ? (
      <p className="text-xs text-augustus-500 px-2 py-1">Queue is empty</p>
    ) : (
      <div className="space-y-1">
        {queue.map((q, i) => (
          <div key={q.id} className="flex items-center gap-2 p-1.5 rounded bg-augustus-900/50">
            <span className="flex-1 text-sm text-augustus-200 truncate">{q.title}</span>
            <button onClick={() => reorderQueue(i, i - 1)} disabled={i === 0} aria-label="Move up" className="btn-icon btn btn-ghost p-1">▲</button>
            <button onClick={() => reorderQueue(i, i + 1)} disabled={i === queue.length - 1} aria-label="Move down" className="btn-icon btn btn-ghost p-1">▼</button>
            <button onClick={() => removeFromQueue(q.id)} aria-label="Remove" className="btn-icon btn btn-ghost p-1">✕</button>
          </div>
        ))}
        <button onClick={clearQueue} className="text-xs text-augustus-400 hover:text-white px-2 py-1">Clear queue</button>
      </div>
    )}
  </div>
)}
```

Pull `queue, reorderQueue, removeFromQueue, clearQueue` from the store. Use a lucide icon (e.g. `ListVideo` or `ListOrdered`) for the toggle button instead of the ▲▼✕ glyphs if you prefer consistency — match the existing icon usage in the file.

- [ ] **Step 3: Add "Play next" / "Add to queue" actions on briefing cards**

In `DashboardBriefs.tsx`, for each completed briefing card with audio, add two small actions (in the existing card action area) calling `useStore`'s `playNext` and `addToQueue` with a `QueueItem` built from the briefing:

```tsx
const toQueueItem = (b: Briefing): QueueItem => ({
  id: b.id, type: 'briefing', title: b.title, audioUrl: b.audio_url!,
  transcript: b.transcript, chapters: b.chapters,
})
```

Wire buttons: `onClick={() => addToQueue(toQueueItem(b))}` and `onClick={() => playNext(toQueueItem(b))}`. Only render when `b.status === 'completed' && b.audio_url`.

- [ ] **Step 4: Add the same actions on the detail page**

In `BriefingDetail.tsx`, add "Add to queue" / "Play next" buttons in the action area (near the existing favorite/download/delete buttons), building the `QueueItem` the same way and guarding on completed + audio.

- [ ] **Step 5: Typecheck + build**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: no errors, build succeeds.

- [ ] **Step 6: Manual verification**

With the app running: add two briefings to the queue, play a third, let it finish (or seek to end). Confirm playback advances to the queue head and the item leaves the Up Next list. Reload the page and confirm the queue persists.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/AudioPlayer.tsx frontend/src/pages/DashboardBriefs.tsx frontend/src/pages/BriefingDetail.tsx
git commit -m "feat: queue UI and auto-advance playback"
```

---

## Task 7: Web research — content sufficiency + research gap-fill

**Files:**
- Create: `backend/app/services/web_research.py`
- Create: `backend/tests/test_web_research.py`
- Modify: `backend/app/config.py` (add settings with defaults)

- [ ] **Step 1: Add config settings**

In `backend/app/config.py`, add fields to the Settings class (match the existing field/default style in that file):

```python
    web_research_enabled: bool = True
    web_research_min_content_chars: int = 600
    web_research_min_facts: int = 2
    web_research_max_stories: int = 3
```

- [ ] **Step 2: Write the failing test** — create `backend/tests/test_web_research.py`

```python
"""Tests for web research gap-fill helpers."""
import pytest

from app.services.web_research import (
    story_needs_research,
    select_stories_for_research,
    merge_sources,
)


class FakeItem:
    def __init__(self, title, content="", url=""):
        self.title = title
        self.content = content
        self.url = url


def test_story_needs_research_thin_content():
    assert story_needs_research(FakeItem("A", content="short"), facts=[], min_chars=600, min_facts=2) is True


def test_story_needs_research_sufficient_content():
    assert story_needs_research(FakeItem("A", content="x" * 700), facts=["f1", "f2"], min_chars=600, min_facts=2) is False


def test_story_needs_research_few_facts():
    assert story_needs_research(FakeItem("A", content="x" * 700), facts=["only one"], min_chars=600, min_facts=2) is True


def test_select_stories_caps_at_max():
    items = [FakeItem(f"s{i}", content="short") for i in range(10)]
    facts_by_index = {i: [] for i in range(10)}
    selected = select_stories_for_research(items, facts_by_index, min_chars=600, min_facts=2, max_stories=3)
    assert len(selected) == 3
    assert selected == [0, 1, 2]


def test_merge_sources_dedupes_by_url():
    existing = [{"title": "A", "url": "http://a.com"}]
    new = [{"title": "A dup", "url": "http://a.com"}, {"title": "B", "url": "http://b.com"}]
    merged = merge_sources(existing, new)
    urls = [s["url"] for s in merged]
    assert urls == ["http://a.com", "http://b.com"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_web_research.py -v`
Expected: FAIL — module `app.services.web_research` not found.

- [ ] **Step 4: Create `backend/app/services/web_research.py`**

```python
"""Helpers for deciding when to augment thin stories with live web research."""
from typing import Optional


def story_needs_research(item, facts: Optional[list], min_chars: int, min_facts: int) -> bool:
    """A story is 'thin' if its content is short OR it has too few usable facts."""
    content = getattr(item, "content", "") or ""
    facts = facts or []
    if len(content.strip()) < min_chars:
        return True
    if len(facts) < min_facts:
        return True
    return False


def select_stories_for_research(
    items: list,
    facts_by_index: dict,
    min_chars: int,
    min_facts: int,
    max_stories: int,
) -> list:
    """Return up to max_stories indices of thin stories, preserving rank order."""
    selected = []
    for i, item in enumerate(items):
        if story_needs_research(item, facts_by_index.get(i), min_chars, min_facts):
            selected.append(i)
        if len(selected) >= max_stories:
            break
    return selected


def merge_sources(existing: list, new: list) -> list:
    """Append new sources to existing, deduped by url, preserving order."""
    seen = {s.get("url") for s in existing if s.get("url")}
    merged = list(existing)
    for s in new:
        url = s.get("url")
        if url and url not in seen:
            seen.add(url)
            merged.append(s)
    return merged
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && venv/bin/pytest tests/test_web_research.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/web_research.py backend/tests/test_web_research.py backend/app/config.py
git commit -m "feat: add web research gap-fill helpers and config"
```

---

## Task 8: Web research — integrate into facts gathering

**Files:**
- Modify: `backend/app/services/briefing.py` (`_generate_additional_facts` and/or the Step 5 call site ~line 481-491)

- [ ] **Step 1: Read the facts-gathering implementation**

Run: `cd backend && grep -n "_generate_additional_facts\|research_topic\|get_search_service\|self.search" app/services/briefing.py`
Read `_generate_additional_facts` fully to see how `ranked_items` and the returned `additional_facts` (dict index→list[str]) are produced.

- [ ] **Step 2: Add a research pass that augments thin stories BEFORE/while gathering facts**

Inside `_generate_additional_facts` (or immediately after it returns, then re-run facts for augmented items — simplest is inside, right after an initial facts pass), implement:

```python
        from app.services.web_research import select_stories_for_research, merge_sources
        from app.services.search import get_search_service

        settings = get_settings()
        if settings.web_research_enabled:
            thin_indices = select_stories_for_research(
                ranked_items,
                additional_facts,  # dict index -> list[str]
                min_chars=settings.web_research_min_content_chars,
                min_facts=settings.web_research_min_facts,
                max_stories=settings.web_research_max_stories,
            )
            if thin_indices:
                search = get_search_service()
                try:
                    for idx in thin_indices:
                        item = ranked_items[idx]
                        query = item.title
                        try:
                            research_text, sources = await search.research_topic(query, num_sources=3)
                        except Exception as e:
                            print(f"[Briefing] Web research failed for '{query}': {e}")
                            continue
                        if research_text:
                            # Enrich the item's content so the writer/facts have more to work with.
                            item.content = (getattr(item, "content", "") or "") + "\n\n[Web research]\n" + research_text
                        # Record sources for attribution (store on the item for later mapping).
                        if sources:
                            item.research_sources = [{"name": s.title, "url": s.url} for s in sources]
                finally:
                    await search.close()
```

Note: `ranked_items` elements are `NewsItem`-like objects with `.title`, `.content`, `.url`, `.to_dict()`. Setting `item.content` and `item.research_sources` as attributes is fine (Python objects). If `NewsItem` is a dataclass with `__slots__` or frozen, instead carry research into a parallel dict `research_by_index[idx] = {"text":..., "sources":...}` and return it from `_generate_additional_facts` alongside facts. Choose based on what you find in Step 1; prefer the parallel-dict approach if attribute assignment is unsafe.

- [ ] **Step 3: Append research sources into briefing.sources**

Where `briefing.sources = [item.to_dict() for item in ranked_items]` is set (~line 461), after it add:

```python
            # Fold any web-research sources into the briefing's source list (deduped).
            research_sources = []
            for item in ranked_items:
                for s in getattr(item, "research_sources", []) or []:
                    research_sources.append(s)
            if research_sources:
                from app.services.web_research import merge_sources
                briefing.sources = merge_sources(briefing.sources, research_sources)
```

(If you used the parallel-dict approach, iterate that dict instead.)

- [ ] **Step 4: Verify module imports**

Run: `cd backend && venv/bin/python -c "import app.services.briefing"`
Expected: no errors.

- [ ] **Step 5: Re-run all backend tests**

Run: `cd backend && venv/bin/pytest -v`
Expected: all prior tests still pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/briefing.py
git commit -m "feat: gap-fill thin stories with live web research"
```

---

## Task 9: Web research — spoken attribution + chapter_sources mapping

**Files:**
- Modify: `backend/app/services/llm/agents/briefing_writer.py`
- Modify: `backend/app/services/briefing.py` (chapter mapping / storage, ~line 842-1025 and storage block)

- [ ] **Step 1: Add attribution guidance to the writer prompt**

In `briefing_writer.py`, locate the system prompt construction. Add a concise instruction (do not rewrite the whole prompt — append a bullet) such as:

```python
        attribution_guidance = (
            "\n- When you state a key fact or figure, attribute it to its source "
            "naturally in speech (e.g. \"according to Reuters\", \"the BBC reports\"). "
            "Attribute the most important claims; do not cite a source in every sentence."
        )
```

Append `attribution_guidance` to the system prompt string that is already built. Keep it additive so existing behavior/tests are unaffected.

- [ ] **Step 2: Build `chapter_sources` during chapter mapping**

In `briefing.py`, find where chapters are finalized with timestamps (the chapter-to-segment mapping, ~line 842-1025) and where `ranked_items` are available. The existing code derives chapters from stories when no `[CHAPTER:]` markers exist; in both cases build a `chapter_sources` dict keyed by chapter index:

```python
            # Map each chapter to its story's sources for clickable transcript attribution.
            chapter_sources = {}
            for ci, chapter in enumerate(chapters):
                # Best-effort: align chapter index to the ranked story of the same index.
                if ci < len(ranked_items):
                    item = ranked_items[ci]
                    srcs = []
                    if getattr(item, "url", None):
                        srcs.append({"name": getattr(item, "source", "") or item.title, "url": item.url})
                    for s in getattr(item, "research_sources", []) or []:
                        srcs.append(s)
                    if srcs:
                        chapter_sources[str(ci)] = srcs
```

- [ ] **Step 3: Persist `chapter_sources` into extra_data**

Where `briefing.extra_data` is populated before save (the storage block), add the key:

```python
            briefing.extra_data = {
                **(briefing.extra_data or {}),
                "chapter_sources": chapter_sources,
            }
```

Match the existing way `extra_data` is assigned in this file (it already stores costs, usage, cast_member_names, segment_timings) — merge the key in rather than overwriting.

- [ ] **Step 4: Verify module imports + tests**

Run: `cd backend && venv/bin/python -c "import app.services.briefing, app.services.llm.agents.briefing_writer" && venv/bin/pytest -q`
Expected: imports clean, all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/briefing.py backend/app/services/llm/agents/briefing_writer.py
git commit -m "feat: spoken source attribution and per-chapter source mapping"
```

---

## Task 10: Web research — frontend source links on detail page

**Files:**
- Modify: `frontend/src/api/client.ts` (Briefing type — ensure `extra_data` is accessible)
- Modify: `frontend/src/pages/BriefingDetail.tsx`

- [ ] **Step 1: Confirm the Briefing type exposes extra_data**

Run: `cd frontend && grep -n "extra_data\|interface Briefing\|chapters" src/api/client.ts`
If `extra_data` is not on the `Briefing` type, add `extra_data?: Record<string, any>` to it.

- [ ] **Step 2: Render per-chapter sources in the detail page**

In `BriefingDetail.tsx`, where chapters are listed, read `briefing.extra_data?.chapter_sources` (object keyed by stringified chapter index). Under each chapter row, if `chapter_sources[String(index)]` exists, render the source links:

```tsx
{chapterSources?.[String(index)]?.length ? (
  <div className="mt-1 flex flex-wrap gap-2">
    {chapterSources[String(index)].map((s: { name: string; url: string }, i: number) => (
      <a key={i} href={s.url} target="_blank" rel="noopener noreferrer"
         className="text-xs text-accent hover:underline inline-flex items-center gap-1">
        <ExternalLink className="w-3 h-3" /> {s.name}
      </a>
    ))}
  </div>
) : null}
```

where `const chapterSources = briefing?.extra_data?.chapter_sources as Record<string, {name:string;url:string}[]> | undefined`.

Fallback: the existing flat "Sources" section remains for briefings without `chapter_sources`. Do not remove it.

- [ ] **Step 3: Typecheck + build**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: no errors, build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/pages/BriefingDetail.tsx
git commit -m "feat: clickable per-chapter source links on briefing detail"
```

---

## Final verification

- [ ] **Backend tests**

Run: `cd backend && venv/bin/pytest -v`
Expected: all tests pass.

- [ ] **Frontend tests + build**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npm run build`
Expected: tests pass, no type errors, build succeeds.

- [ ] **End-to-end smoke** (app running via `./dev.sh`)

1. Generate a briefing on a niche topic (to trigger thin-story web research). Confirm it completes, the detail page shows per-chapter source links, and the spoken transcript includes at least one attribution.
2. Download the MP3 and confirm embedded chapters: `backend/venv/bin/python -c "from mutagen.id3 import ID3; print(len(ID3('PATH').getall('CHAP')))"`.
3. Search for a word you know is in a transcript; confirm it appears in results and grouping is bypassed.
4. Add two briefings to the queue, play a third to the end, confirm auto-advance and queue persistence across reload.

## Notes on spec coverage

- ID3 chapters (new only): Tasks 1–2. No backfill (per decision).
- Web research (gap-fill) + spoken attribution + per-chapter links: Tasks 7–10.
- Global search (LIKE, title+transcript): Tasks 3–4.
- Ephemeral queue (localStorage-persisted): Tasks 5–6.
- No DB migration anywhere; older briefings degrade gracefully (no `chapter_sources`, no embedded chapters).
