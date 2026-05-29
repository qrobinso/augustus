# Podcast Experience Upgrades — Design Spec

**Date:** 2026-05-24
**Branch:** `feature/podcast-experience-upgrades`
**Status:** Proposed

## Overview

Four independent features that move Augustus toward a world-class podcast
experience. Each is self-contained and can ship independently:

1. **ID3 chapter embedding** — write chapters into the MP3 so external players (Apple Podcasts, Overcast, etc.) show them.
2. **Live web research + source attribution** — fill thin stories with web search, attribute sources both in audio and as clickable transcript links.
3. **Global search** — search across briefing titles and transcripts.
4. **Queue / playlist UI** — an ephemeral, reorderable "Up Next" play queue.

Decisions already made with the user:
- Web research trigger: **only when a top story's scraped content/facts are thin.**
- Source attribution: **spoken attribution + clickable transcript→source links** (existing sources list retained).
- Queue: **ephemeral play queue** (no persistent playlists), persisted to localStorage for reload resilience.
- ID3 chapters: **new briefings only** (no backfill of existing MP3s).
- Search engine: **SQL `LIKE`** over title + transcript (no FTS5, no migration).

Non-goals: persistent playlists, FTS5, backfilling existing audio, podcast RSS output feed (separate future feature).

---

## Feature 1 — ID3 Chapter Embedding

### Goal
External podcast players that read ID3v2 chapter frames (`CHAP`/`CTOC`) display the same chapters the in-app player shows.

### Approach
- New helper in `backend/app/utils/audio.py`:
  `embed_chapters_in_mp3(filepath: str, chapters: list[dict], title: str | None = None) -> bool`
  - Uses **mutagen** (already a dependency) to write `CTOC` (table of contents) + one `CHAP` frame per chapter, each with a nested `TIT2` (chapter title) sub-frame.
  - `chapters` items are `{title, start_time, end_time}` (seconds, floats) — the existing shape stored on briefings.
  - Times converted to integer milliseconds for `start_time`/`end_time` on each `CHAP`.
  - Optionally sets the track `TIT2` title on the file when `title` is provided.
  - Idempotent: clears any existing `CHAP`/`CTOC` frames before writing.
  - Returns `True` on success, `False` on failure; never raises into the pipeline.
- Wire into the generation pipeline in `backend/app/services/briefing.py` after the MP3 is written and chapters with real timestamps are computed (around the storage step, `briefing.py:~684`). Guard: only call when `audio_filename` ends in `.mp3` and `chapters` is non-empty.

### Edge cases
- Empty/None chapters → skip embedding (no-op, return False).
- Non-MP3 file (shouldn't happen since pipeline always writes `.mp3`) → skip.
- Embedding failure must NOT fail briefing generation — log a warning and continue.

### Testing
- Unit test `embed_chapters_in_mp3` against a tiny generated/sample MP3: assert `CTOC` exists, `CHAP` count == len(chapters), each chapter's start/end ms and title round-trip via mutagen read-back.
- Test idempotency: embedding twice yields the same single set of frames.
- Test failure path: passing a bogus path returns False and does not raise.

---

## Feature 2 — Live Web Research + Source Attribution

### Goal
When a selected top story lacks sufficient scraped content, enrich it with live web search; attribute sources in the spoken script and link transcript content to source URLs.

### Trigger (gap-fill)
In the facts-gathering stage (`briefing.py` calls `FactsGathererAgent` ~`briefing.py:481-491`):
- For each ranked story, assess content sufficiency. **Thin** = scraped/full content below a character threshold (default `WEB_RESEARCH_MIN_CONTENT_CHARS = 600`) OR fewer than a minimum number of usable facts after gathering (default `WEB_RESEARCH_MIN_FACTS = 2`).
- For thin stories only, call existing `SearchService.research_topic(query, ...)` (`backend/app/services/search.py:146`) using the story title (plus topic) as the query. Cap results (e.g., top 3 pages, existing default) to bound latency/cost.
- Merge returned research text into the content passed to the facts gatherer for that story, and collect the returned source URLs/titles.
- Concurrency/limits: cap the number of stories that trigger research per briefing (default `WEB_RESEARCH_MAX_STORIES = 3`) to bound latency.

### Spoken attribution
- Pass a per-story list of source display-names (publication/domain names) into the briefing writer (`briefing_writer.py`).
- Add an instruction to the writer prompt: when stating a key fact, attribute it to its source naturally ("according to Reuters…", "the BBC reports…"). Keep it natural, not every sentence.
- This is additive prompt guidance; if the model omits attribution, audio is still valid.

### Transcript → source links
- Persist a `chapter_sources` mapping in `briefing.extra_data`, **keyed by chapter index** (string keys for JSON):
  `{ "0": [{name, url}], "1": [...] }`. The pipeline already maps chapters to the stories they came from during chapter-timestamp computation; we reuse that association to attach each story's sources (scraped + web-research) to its chapter index. Stories that don't map cleanly to a chapter contribute to the flat `sources` list only.
- Web-research source URLs are also appended to the existing `briefing.sources` list (deduped by URL) so the detail-page sources section stays complete.
- Frontend (`BriefingDetail.tsx`): render the source links inline under each chapter using `chapter_sources[chapterIndex]`. Falls back gracefully to the flat sources list when the map is absent (older briefings).

### Configuration
Add settings/env (with defaults) so behavior is tunable without code changes:
- `WEB_RESEARCH_ENABLED` (default `true`)
- `WEB_RESEARCH_MIN_CONTENT_CHARS` (default `600`)
- `WEB_RESEARCH_MIN_FACTS` (default `2`)
- `WEB_RESEARCH_MAX_STORIES` (default `3`)

### Edge cases
- Search failure / timeout / zero results → log and proceed with whatever content exists (story is never dropped because research failed).
- `SearchService` already handles its own HTTP client lifecycle; ensure it is closed/awaited correctly within the generation flow.
- No network (offline self-host) → research silently no-ops.
- Older briefings without `story_sources` → detail page shows flat sources list as today.

### Testing
- Unit: sufficiency check correctly flags thin vs sufficient stories at the thresholds.
- Unit: research results merge into content and source list is deduped by URL.
- Unit (mocked SearchService): a thin story triggers `research_topic`; a sufficient story does not.
- Failure injection: `research_topic` raising → generation continues, sources unchanged.

---

## Feature 3 — Global Search

### Goal
Find briefings by words in the title or transcript.

### Backend
- Extend `list_briefings` endpoint (`backend/app/routers/briefings.py:68`) with optional `q: Optional[str] = None`.
- Extend `BriefingService.list_briefings(...)` to accept `q`. When `q` is non-empty:
  - Apply a case-insensitive `LIKE %q%` filter across `Briefing.title` OR `Briefing.transcript`, in addition to the existing profile/listened/cast/topic/favorite filters.
  - Keep existing ordering (newest first) and pagination; `total` reflects the filtered count.
- Optionally return a short matched snippet per result. **Decision:** compute the snippet on the frontend from the already-returned `transcript` (no backend change needed) to keep the endpoint simple. If transcript is large, the snippet is derived client-side from the first match.

### Frontend
- Add a debounced (~300ms) search input to the existing filter bar in `DashboardBriefs.tsx`.
- Wire `q` into the `briefingsApi.list(...)` call and the `['briefings', ...]` query key so results refetch on query change.
- When `q` is active: show a flat result list (bypass the Unplayed/Listened grouping), display the title with a highlighted match and a small transcript snippet around the first match.
- Empty state: "No briefings match '<q>'." Clearing the box restores the normal grouped view.

### Edge cases
- Empty/whitespace `q` → treated as no search (normal listing).
- Very long transcripts → snippet generation bounded to a window around the match.
- `LIKE` special chars (`%`, `_`) in user input → escaped before binding.

### Testing
- Service unit tests: `q` matches title-only, transcript-only, both; respects profile scope and combines with other filters; pagination/total correct; `%`/`_` escaped.
- Frontend: debounce fires one request; clearing restores grouped view (light test or manual verification).

---

## Feature 4 — Queue / Playlist UI (Ephemeral)

### Goal
A reorderable "Up Next" queue: add briefings, auto-advance through them, reorder/remove/clear. Survives reload (localStorage) but is not a saved/named collection.

### Store (`frontend/src/store/useStore.ts`)
- Add `queue: QueueItem[]` where `QueueItem` is the minimal audio payload already used by `currentAudio` (`{id, type, title, audioUrl, transcript?, chapters?}`).
- Actions:
  - `addToQueue(item)` — append if not already present.
  - `playNext(item)` — insert at head of queue.
  - `removeFromQueue(id)` — remove by id.
  - `reorderQueue(fromIndex, toIndex)` — move within queue.
  - `clearQueue()`.
  - `playFromQueueHead()` — pop head, set as `currentAudio`, start playback.
- Persist `queue` to localStorage (manual subscribe or zustand `persist` for just the queue slice), restored on load.

### Playback integration (`AudioPlayer.tsx`)
- In the existing `onEnded` handler (`AudioPlayer.tsx:216`): if `queue` is non-empty, play the queue head (`playFromQueueHead`) **before** the existing `playNextUnlistenedBriefing()` fallback. If the queue is empty, keep current auto-play-next behavior.
- Saving playback position / mark-listened logic for the finished briefing is unchanged.

### UI
- **Up Next panel:** in the expanded player view, a toggle (next to the chapters/transcript toggle) opens an "Up Next" list showing queued items with reorder handles, remove buttons, and a "Clear" action. Empty state hidden or shows "Queue is empty."
- **Add actions:** on briefing cards (`DashboardBriefs.tsx`) and the detail page (`BriefingDetail.tsx`), add "Play next" and "Add to queue" actions (e.g., in an overflow menu or as small buttons), enabled only for `completed` briefings with audio.
- Reorder can be simple up/down buttons (no DnD dependency) to keep scope tight; DnD is a possible later enhancement.

### Edge cases
- Adding the currently-playing briefing to the queue → allowed but it won't duplicate-play (it advances normally).
- A queued briefing deleted elsewhere → on attempted play, if audio 404s, skip to next queue item.
- localStorage unavailable / corrupt → start with empty queue (defensive parse).

### Testing
- Store unit tests: add/playNext/remove/reorder/clear behave correctly; no duplicates on add; head-play pops correctly.
- Persistence: queue round-trips through localStorage (mocked).
- Integration (manual or light): finishing a briefing with a non-empty queue advances to the queue head, not the auto-next briefing.

---

## Cross-cutting

- **No DB migration** required: Feature 2 uses existing `extra_data`/`sources` JSON; Features 1/3/4 add no columns. (Search reuses existing columns; queue is client-side.)
- **Backwards compatibility:** all features degrade gracefully for briefings created before this work (no `story_sources`, no embedded chapters) — UI falls back to existing behavior.
- **Settings surface:** Feature 2 thresholds are env/settings-driven with sensible defaults; no UI required for v1 (can be added later).
- **Failure isolation:** ID3 embedding and web research must never fail a briefing; both are wrapped and logged.

## Suggested implementation order
1. ID3 chapter embedding (smallest, isolated, testable).
2. Global search (backend + frontend, isolated).
3. Queue UI (frontend-only).
4. Live web research + attribution (largest; touches pipeline + writer prompt + detail UI).
