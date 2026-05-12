# Optimization Audit — augustus (May 2026)

> **Scope:** backend perf/async, LLM agent pipeline, frontend, infra/data.
> **Method:** static code review (read-only), four parallel exploration passes. Claims that need runtime measurement to size are flagged "needs measurement".
> **Source spec:** `docs/superpowers/specs/2026-05-11-optimization-audit-design.md` · **Plan:** `docs/superpowers/plans/2026-05-11-optimization-audit.md`
> **No code was changed by this audit.**
> Finding IDs: `F-B*` backend, `F-L*` LLM pipeline, `F-F*` frontend, `F-I*` infra/data. Ranked by impact ÷ effort (severity High/Med/Low × effort S/M/L).

---

## Executive summary

1. **F-F1 (High, S)** — The entire frontend ships as one ~667 KB JS chunk; no route-level code splitting. `App.tsx` statically imports all ~20 pages.
2. **F-I1 (High, S)** — No startup reconciliation: a briefing left `status=generating`/`pending` by a `--reload` or crash is stuck forever and bricks the on-demand queue + the "Generate" button. (Also surfaced by the backend pass as F-B3.)
3. **F-B1 (High, M)** — `GET /api/briefings` (the main list view) loads *every* briefing row with full `transcript` + huge `extra_data` JSON, then paginates/filters in Python. Latency and payload scale with history, not with `limit`.
4. **F-L1 (Med, S)** — Article pages are HTTP-fetched twice per briefing; the second round (in the facts agent) is serial — up to ~75 s of avoidable wall time.
5. **F-L4 (Med, S)** — Zero retry/back-off on transient OpenRouter errors; one 429/5xx on the *writer* call throws away all earlier (billed) LLM spend and fails the briefing.
6. **F-L3 (Med, S)** — `finish_reason == "length"` (truncation) is never detected — a truncated 32k-token writer response ships broken or crashes JSON parsing downstream.
7. **F-I4 (Med, S)** — SQLite engine has no WAL / `busy_timeout` / pool tuning; the scheduler + worker + polling API contend on one write lock → sporadic `database is locked`.
8. **F-I2 / F-I3 (Med, S/M)** — A killed generation leaves a corrupt `.mp3` on disk; `audio/` only ever grows (no retention policy), and in Docker it shares a volume with the SQLite DB.
9. **F-F3 (Med, M)** — Two independent `['briefings']` pollers + broad `invalidateQueries(['briefings'])` after every mark-listened/favorite + default `refetchOnWindowFocus` → the ~20× `GET /api/briefings` burst seen in logs.
10. **F-L2 (Med, S)** — `writer_max_tokens` is a flat 32768 regardless of model — inflates latency on all models and billed reasoning tokens on thinking models.

The cheapest high-value cluster to land first: **F-F1, F-I1, F-L1, F-L4, F-L3, F-I4, F-L2** — all S-effort, all High/Med severity.

---

## Findings table

| ID | Area | Severity | Effort | Summary |
|----|------|----------|--------|---------|
| F-F1 | Frontend | High | S | No route-level code splitting — one ~667 KB JS chunk |
| F-I1 | Infra | High | S | No startup reconciliation — stuck `generating` briefings brick the queue (= F-B3) |
| F-B1 | Backend | High | M | `GET /api/briefings` loads all rows + full transcript/extra_data, paginates in Python |
| F-L1 | LLM | Med | S | Article pages fetched twice per briefing; second round serial |
| F-L2 | LLM | Med | S | `writer_max_tokens=32768` flat, model-agnostic |
| F-L3 | LLM | Med | S | `finish_reason == "length"` truncation never detected |
| F-L4 | LLM | Med | S | No retry/back-off on transient OpenRouter 429/5xx |
| F-I2 | Infra | Med | S | Killed generation leaves corrupt `.mp3`; no atomic write, no orphan sweep |
| F-I4 | Infra | Med | S | SQLite engine: no WAL / busy_timeout / pool tuning under concurrent writers |
| F-B2 | Backend | Med | M | APScheduler jobs run on the event loop; email-batch sleep/poll task per scheduled briefing |
| F-B4 | Backend | Med | M | Three independent fetch phases (RSS / NewsAPI / custom-site) run serially before the LLM stages |
| F-B5 | Backend | Med | M | `get_last_script_for_topics` loads entire briefing history to filter a JSON field; missing indexes |
| F-L6 | LLM | Med | M | No caching of facts/articles across briefings on the same topic |
| F-L7 | LLM | Med | M | A late-stage failure redoes all earlier (billed) LLM calls — no stage checkpointing |
| F-F3 | Frontend | Med | M | Multiple `['briefings']` pollers + broad invalidations + `refetchOnWindowFocus` → request bursts |
| F-F4 | Frontend | Med | M | O(n) active-segment/chapter scans on every `timeupdate`; `segmentTimings`/`chapters` are unstable refs |
| F-I3 | Infra | Med | M | `audio/` grows unbounded — no retention policy; shares the DB volume in Docker |
| F-I5 | Infra | Med | M | Migrations not auto-run, not ordered, not tracked — schema drift on upgrade |
| F-B6 | Backend | Low | S | Script re-parsed with regex 4+ times per generation; chapter-stripping duplicated 3 ways |
| F-B7 | Backend | Low | S | `_send_batched_email_after_delay` handed a request-scoped DB session it can't safely use later |
| F-B8 | Backend | Low | S | `OpenRouterProvider` calls `get_settings.cache_clear()` on the hot path — blows the app-wide settings cache |
| F-B9 | Backend | Low | S | `Piper._check_piper_available` runs `subprocess.run` directly inside `async def` |
| F-B10 | Backend | Low | S | Sync file writes (multi-MB WAV buffers, ffmpeg concat list) done on the event loop |
| F-B11 | Backend | Low | S | `BriefingService.__init__` eagerly builds LLM/orchestrator/news/search even for pure-read endpoints |
| F-L5 | LLM | Low | S | Flat 120 s HTTP timeout, no connect/read split, no streaming |
| F-L8 | LLM | Low | S | Facts agent sends `full_content` AND a re-fetched `ADDITIONAL WEB CONTENT` for the same article |
| F-L9 | LLM | Low | S | Independent DB context lookups run *after* the LLM calls instead of concurrently up front |
| F-L10 | LLM | Low | S | Writer `OpenRouterProvider` (+ `httpx` client) recreated per briefing, never closed |
| F-F2 | Frontend | Low | S | `wavesurfer.js` is a dependency but unused |
| F-F5 | Frontend | Low | S | Many components independently re-fetch `settings`/`topics`/`casts` |
| F-F6 | Frontend | Low | S | Debug `console.log` of full `briefing.extra_data` ships to prod and fires nearly every render |
| F-F7 | Frontend | Low | S | `DashboardBriefs` reads `window.innerWidth` in render + extra resize listener; unmemoized cards |
| F-F8 | Frontend | Low | S | No brotli; PWA precaches the whole 667 KB bundle |
| F-I7 | Infra | Low | S | `piper.py` HTTP path leaks a temp WAV if MP3 conversion raises |
| F-I8 | Infra | Low | S | Per-task `create_async_engine` multiplies SQLite connection pools / leak window |
| F-I6 | Infra | Low | M | Docker runtime image heavier than needed; deps unpinned (`>=`), no `.dockerignore` |

---

## Detailed findings (ranked order)

### F-F1: No route-level code splitting — one ~667 KB JS chunk
- **Severity:** High · **Effort:** S
- **Symptom:** First load downloads + parses the entire app (all ~20 pages, framer-motion, axios, react-router, lucide, react-query) before anything renders. `frontend/dist/assets/index-*.js` ≈ 667 KB raw (~180–200 KB gzip).
- **Evidence:** `frontend/src/App.tsx:8-24` statically imports every page (`import DashboardBriefs from './pages/DashboardBriefs'`, `import Settings from './pages/Settings'`, … 20 pages). No `React.lazy`/`Suspense` anywhere in `src/`. `frontend/vite.config.ts` has no `build.rollupOptions.output.manualChunks`; build output is a single `index-*.js`.
- **Why it matters:** Load time / TTI, especially on mobile (this is a PWA). `Settings.tsx` (~1425 lines), `Onboarding.tsx`, `Mcp.tsx`, `DashboardGenerate.tsx` (~682 lines) are large and rarely needed at startup.
- **Recommended fix:** Convert page imports in `App.tsx` to `React.lazy(() => import('./pages/X'))` under a `<Suspense>` boundary; optionally add `manualChunks` to split vendor; lazy-load `framer-motion` (used only in `ProfileManagement.tsx`/`ProfileSwitcher.tsx`).
- **Risks / caveats:** Needs a Suspense fallback. Verify `vite-plugin-pwa` precache (`globPatterns: **/*.js`) still covers the new chunks (it will — they match `*.js`).

### F-I1: No startup reconciliation — stuck `generating`/`pending` briefings brick the queue
- **Severity:** High · **Effort:** S · *(Backend pass independently filed this as F-B3.)*
- **Symptom:** When uvicorn `--reload` (WatchFiles) restarts the process or the container gets SIGTERM/SIGKILL mid-generation, the in-flight `asyncio.create_task(generate_briefing_task(...))` is killed. The briefing row stays `status="generating"` (or `"pending"`/`"queued"`). On the next request, `has_briefing_in_progress` returns 409 "You already have a briefing being generated or queued" — permanently; `has_any_active_briefing` also blocks the whole on-demand queue from advancing.
- **Evidence:** `backend/app/main.py:155-222` lifespan startup does `init_db()` + mkdir + `scheduler.start()` only — no pass that finds `status in (generating, pending)` rows and resets them. `backend/app/database.py:40-43` `init_db` is just `create_all`. `backend/app/services/briefing.py:1717-1735` `has_briefing_in_progress` matches `["pending","generating","queued"]`; `:1740-1747` `has_any_active_briefing`. `backend/app/routers/briefings.py:33-71` `generate_briefing_task` is fire-and-forget with `set_global_generating(True)` cleared only in `finally` (won't run on hard kill). `backend/app/services/briefing.py:1116-1118` — the cancellation-event registry is in-memory, also lost on restart.
- **Why it matters:** Availability. `dev.ps1:167-168` runs `--reload`, so this triggers on every code save during dev while a briefing is mid-pipeline; in Docker, on any restart mid-generation. Recovery currently requires hand-editing the DB.
- **Recommended fix:** In `lifespan` startup, after `init_db()`: `UPDATE briefings SET status='failed', error_message='Interrupted by server restart' WHERE status IN ('generating','pending')` (decide whether to re-`queued` instead for auto-resume — the pipeline overwrites `briefing_{id}.mp3` so it's safe to re-run).
- **Risks / caveats:** If you ever run >1 worker process (you don't today — single uvicorn process), this naive sweep races; gate behind a single-instance assumption or a process lock.

### F-B1: `GET /api/briefings` loads all rows + full transcript/extra_data, paginates in Python
- **Severity:** High · **Effort:** M
- **Symptom:** The main list view returns `transcript`, `sources`, and the entire `extra_data` JSON per briefing — which includes `segment_timings` (one entry per dialogue line, full text), `story_analysis_raw`, `facts_analysis_raw`, usage/cost dicts, `chapters`, etc. Each completed briefing's `extra_data` is easily tens-to-hundreds of KB. The endpoint also loads *every* matching row, then slices `[offset:offset+limit]` and filters `topic_ids` in Python.
- **Evidence:** `backend/app/schemas/briefing.py:53-72` — `BriefingResponse` includes `transcript`, `extra_data: dict`, `sources: list`. `backend/app/routers/briefings.py:99-102` — `[BriefingResponse.model_validate(b) for b in briefings]`. `backend/app/models/briefing.py:40,47-56` — `transcript Text`, `extra_data JSON`, `sources JSON` all selected by default `select(Briefing)`. `backend/app/services/briefing.py:1570-1598` — `list_briefings`: `select(Briefing)` with no column deferral → `result.scalars().all()` → `total = len(all_briefings)` → `briefings = all_briefings[offset:offset+limit]`; `topic_ids` filtering (`:1576-1590`) also post-hoc in Python.
- **Why it matters:** Latency, payload size, and event-loop JSON-parse CPU all scale with total briefing count and transcript size, not with `limit`. Gets progressively slower as history grows. The frontend list renders only title/date/duration.
- **Recommended fix:** Add a slim list schema (id, title, status, duration, created_at, listened, favorite, audio_url, cast_id, short transcript preview, plus only `chapters`/`topic_ids` from `extra_data`). Use `defer(Briefing.transcript, Briefing.extra_data, Briefing.sources)` / `load_only(...)` / `with_only_columns`. Push `LIMIT/OFFSET` into SQL; separate `func.count()` for `total`. For the `topic_ids` JSON filter, denormalize into a join table or use SQLite `json_each`.
- **Risks / caveats:** Audit the React list view first — confirm it doesn't read fields from `extra_data` before trimming. Impact magnitude needs measurement against a realistic briefing count.

### F-L1: Article pages fetched twice per briefing; second round serial
- **Severity:** Med · **Effort:** S
- **Symptom:** Each ranked article's URL is HTTP-fetched once (concurrently) by `briefing.py`, then fetched *again* — one article at a time — by the facts agent, sometimes plus a DuckDuckGo search + 2-3 more page fetches on failure.
- **Evidence:** `backend/app/services/briefing.py:2118` `article_content = await self.search.fetch_page_content(item.url)` (concurrent; stored as `full_content`). `backend/app/services/llm/agents/facts_gatherer.py:266-272` — `for i, story in enumerate(stories): content = await self._fetch_article_content(story)` (serial), and `_fetch_article_content` (`:104,116,124`) re-fetches `story['url']`, with a search + up-to-3 alternative-page fetches on failure, all inside that serial loop.
- **Why it matters:** With 5 stories, ~5 sequential network round-trips (15 s timeout each → up to ~75 s added wall clock) on top of work already done; plus redundant bandwidth/scraper load.
- **Recommended fix:** Pass the already-fetched `full_content` through and skip the re-fetch when present; if a separate "additional web content" pass is still wanted, run `_fetch_article_content` for all stories via `asyncio.gather`. Preserve the alternative-source fallback for the missing-body case.
- **Risks / caveats:** None significant.

### F-L2: `writer_max_tokens=32768` is flat and model-agnostic
- **Severity:** Med · **Effort:** S
- **Symptom:** The briefing writer always requests `max_tokens=32768` regardless of model. A ~10-minute script is ~3-4k tokens of dialogue; 32k is ~8× larger than needed for non-reasoning models.
- **Evidence:** `backend/app/config.py:56-60` `writer_max_tokens: int = 32768`. `backend/app/services/llm/agents/briefing_writer.py:794-802` — `writer_max_tokens = get_settings().writer_max_tokens; response = await self.llm.generate(..., max_tokens=writer_max_tokens, temperature=0.7, ...)`.
- **Why it matters:** On many providers a large `max_tokens` affects routing / slows time-to-first-token; on reasoning models it directly enables longer billed hidden reasoning. The config comment justifies it for thinking models but it's applied unconditionally.
- **Recommended fix:** Make the cap model-aware (~8k for non-reasoning models, keep ~32k only for known thinking models), or compute from duration (e.g. `~600 tokens/min × duration + buffer`); at minimum expose per-model.
- **Risks / caveats:** Needs per-model measurement; truncation (F-L3) becomes more likely if set too low.

### F-L3: `finish_reason == "length"` truncation never detected
- **Severity:** Med · **Effort:** S
- **Symptom:** The provider only inspects `finish_reason` when content is *empty*. A response truncated mid-script (`finish_reason="length"` with partial content) is returned as-is — a cut-off podcast for the writer; invalid JSON (→ fallback parsers or a hard `ValueError`) for facts/story-analyzer.
- **Evidence:** `backend/app/services/llm/openrouter.py:155-193` — `finish_reason` read only inside the `if not result_content:` branch (`:169-174`); the success-path `return LLMResponse(...)` never checks it. Downstream symptoms: `backend/app/services/llm/agents/facts_gatherer.py:330` `raise ValueError(f"Failed to parse facts agent JSON: {e1}")`; `backend/app/services/llm/agents/story_analyzer.py:204-205` `raise ValueError(...)`.
- **Why it matters:** Reliability + wasted spend — the 32k-token writer call is the most expensive in the pipeline; on truncation it's either shipped broken or fails the whole briefing *after* paying for analyzer + facts + writer.
- **Recommended fix:** Detect `finish_reason in ("length","max_tokens")` in `generate_conversation`; surface it on `LLMResponse` and either raise a typed `TruncatedResponseError` or auto-continue. Minimum viable: just flag it so callers decide.
- **Risks / caveats:** Continuation logic for free-form scripts is non-trivial.

### F-L4: No retry/back-off on transient OpenRouter errors
- **Severity:** Med · **Effort:** S
- **Symptom:** `response.raise_for_status()` is the entire error policy. A transient 429 (rate limit) or 502 on the *writer* call — after analyzer + facts have been billed — bubbles up; `generate_briefing` marks the briefing `failed` and there is no queue-level retry.
- **Evidence:** `backend/app/services/llm/openrouter.py:151` `response.raise_for_status()` (no retry wrapper in the file); `:155-160` handles only "no choices" with a `RuntimeError`. `backend/app/services/briefing.py:538-545` — `except Exception as e: briefing.status = "failed"; ...; raise`. `backend/app/services/briefing_queue.py` has no retry logic.
- **Why it matters:** $ + reliability — every failed late-stage call discards all earlier LLM spend for that briefing (compounds F-L7); 429s from OpenRouter are common under load.
- **Recommended fix:** Bounded exponential back-off (≈3 tries, jitter) for 429/5xx/timeouts in `generate_conversation`, respecting `Retry-After`. Don't retry 4xx auth/validation; cap total added latency.
- **Risks / caveats:** None significant.

### F-I2: Killed generation leaves corrupt `.mp3`; no atomic write, no orphan sweep
- **Severity:** Med · **Effort:** S
- **Symptom:** TTS writes directly to the final path `audio/briefing_{id}.mp3`. If the process is killed during synthesis/concat, or `generate_briefing` raises a non-cancellation exception, a half-written `.mp3` stays forever. `regenerate_audio` overwriting an existing good file then failing destroys the old audio and leaves a corrupt file.
- **Evidence:** `backend/app/services/briefing.py:961-962` and `:400-401` write to the final path. `:982-990` unlinks only on `BriefingCancelledException`; the generic `except Exception as e: briefing.status = "failed"` blocks at `:538-545` and `:1108-1118` have no `audio_path.unlink()`. No APScheduler job sweeps `audio/` for orphans (`main.py:172-195` registers only the three scheduler jobs).
- **Why it matters:** Disk growth + the briefing detail page can serve a truncated/corrupt file. Compounds F-I3.
- **Recommended fix:** Write TTS output to a temp path and atomically `rename` onto the final path only on success; `unlink` the temp on any failure. Add a periodic sweep deleting `audio/*.mp3` whose `briefing_{id}` has no `completed` row.
- **Risks / caveats:** None significant.

### F-I4: SQLite engine — no WAL / busy_timeout / pool tuning under concurrent writers
- **Severity:** Med · **Effort:** S
- **Symptom:** The async engine is created with no `connect_args`, no `busy_timeout`, no WAL, no pool config. Default journal mode is rollback (not WAL), so any open write transaction blocks all readers and a reader can block a writer. The scheduler fires `process_ondemand_briefing_queue` every 5 s (which writes: `queued_briefing.status = "pending"; await db.commit()`), `process_scheduled_briefing_queue` every 10 s, `check_scheduled_briefings` every minute — each on its own session. Meanwhile `update_progress` commits ~8× per generation and the API serves `GET /api/briefings` polling. On Windows file locking is coarser still.
- **Evidence:** `backend/app/database.py:12-16` — `create_async_engine(settings.database_url, echo=False, future=True)` (no `connect_args`, no PRAGMAs, no pool args). `backend/app/main.py:181-195` — the three interval jobs; `:127-128` `queued_briefing.status = "pending"; await db.commit()`. `backend/app/routers/briefings.py:45` — `generate_briefing_task` spins up a *second* `create_async_engine(db_url)` against the same file. The schedulers swallow exceptions (`main.py:53-54`, `:95-98`), so a lost commit just disappears.
- **Why it matters:** Sporadic `sqlite3.OperationalError: database is locked` → 500s on the API or silently-dropped scheduler commits; worsens as the table grows.
- **Recommended fix:** Cheap immediate win — connect-time hook: `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=10000; PRAGMA synchronous=NORMAL`. Reduce `update_progress` commit frequency (see F-B2). Longer term the workload (concurrent writer + scheduler + polling API) fits Postgres, and `database_url` → `postgresql+asyncpg://` is mostly config — but only after measuring; WAL alone may suffice for the single-user self-hosted target.
- **Risks / caveats:** Needs measurement — symptoms inferred from code, not observed `database is locked` logs yet.

### F-B2: APScheduler jobs run on the event loop; per-briefing email-batch sleep/poll task
- **Severity:** Med · **Effort:** M
- **Symptom:** "Run time of job ... was missed by 0:00:0X" warnings. The 5 s on-demand and 10 s scheduled jobs each open a session and run 1-3 queries every tick; when a briefing is generating, the loop is also busy with `to_thread` joins, `re` parsing, and large-JSON commits, so the short-interval jobs slip. Separately, each scheduled briefing spawns a long-lived `asyncio.sleep(90)` + `while waited < 600: await asyncio.sleep(5)` poll task.
- **Evidence:** `backend/app/main.py:181-195` — jobs at `seconds=10` and `seconds=5`; `check_scheduled_briefings` at `seconds=60` (`main.py:21-54`). `backend/app/services/scheduled_briefing.py:343-389` — `_send_batched_email_after_delay`'s sleep/poll loop, spawned via `asyncio.create_task` (`:317-326`). `backend/app/services/briefing.py:586-603` — `update_progress` does a full `await self.db.commit()` (writing the whole `extra_data` JSON) on every progress step plus a `select(Briefing)` cancellation check (`_check_cancelled`, `:54-75`), all on the loop between heavy `to_thread` calls.
- **Why it matters:** Missed-deadline warnings = loop starvation; worst case a queued briefing waits longer to start, and the email-poll task multiplies across concurrent scheduled briefings. (This is the noise the user originally asked about.)
- **Recommended fix:** (a) Replace `_send_batched_email_after_delay`'s sleep/poll loop with a single APScheduler `date` job or an `asyncio.Event` the queue sets when it drains. (b) Don't `commit()` the full `extra_data` on every progress tick — store progress in a lightweight column or in-memory map, or commit every other step.
- **Risks / caveats:** Behavior change to email-batching timing — test the batching window. "Missed by" warnings may persist while ffmpeg/`to_thread` joins are scheduled on the default executor — measure.

### F-B4: Three independent fetch phases run serially before the LLM stages
- **Severity:** Med · **Effort:** M
- **Symptom:** RSS fetch (step 1), NewsAPI fetch (step 2), and custom-site scrape (step 3) are awaited one after another despite being fully independent; later, `_get_recent_articles_for_topics` and `get_last_script_for_topics` are also awaited serially. NewsAPI additionally loops topics serially.
- **Evidence:** `backend/app/services/briefing.py:615-659` — `rss_items = await self.news.fetch_all_feeds()` → `await self.news.fetch_newsapi(...)` → `await self._fetch_custom_site_articles(...)`. `backend/app/services/news.py:131-167` `fetch_newsapi` — `for topic in topics: response = await self.client.get(...)` (not `gather`). `backend/app/services/briefing.py:819-839` — `recent_articles = await self._get_recent_articles_for_topics(...)` then `last_script = await self.get_last_script_for_topics(...)`. (Progress steps are step-numbered, which is *why* they're serial.)
- **Why it matters:** Wall time — the biggest easy latency win aside from the LLM/TTS calls themselves.
- **Recommended fix:** `asyncio.gather` the RSS / NewsAPI / custom-site fetches (and the per-topic NewsAPI calls); emit "Fetching sources" once before and "Sources fetched" after to keep the progress bar honest. Same for the two read-only continuity queries. **Caveat:** `_fetch_custom_site_articles` writes `last_fetched` via `self.db` — give the DB-touching part its own session or move the commit out before running concurrently.
- **Risks / caveats:** Concurrent use of the shared `self.db` session is unsafe — must isolate the DB-touching parts. Needs measurement to confirm the fetch phases are actually slow in practice.

### F-B5: `get_last_script_for_topics` loads entire history to filter a JSON field; missing indexes
- **Severity:** Med · **Effort:** M
- **Symptom:** `get_last_script_for_topics` selects *all* completed briefings for the user (each with full `transcript` + `extra_data`) just to find the first whose `extra_data['topic_ids']` set matches — runs in every generation when `topic_ids` is set. Plus core columns used in `WHERE`/`ORDER BY` are unindexed.
- **Evidence:** `backend/app/services/briefing.py:1491-1519` — `select(Briefing).where(... status=='completed', transcript.isnot(None)).order_by(generated_at.desc())` → `result.scalars().all()` → Python loop on `set(briefing.extra_data.get("topic_ids", []))`; no `LIMIT`, no column deferral. Same pattern in `list_briefings` topic filter (`:1576-1590`). `backend/app/models/briefing.py` — `user_id` has no `index=True` (only the implicit FK); `status`, `created_at`, `generated_at`, `cast_id` unindexed. `backend/app/models/article.py` — `topic_id`, `fetched_at` unindexed (only the URL unique constraint); `_get_recent_articles_for_topics` orders by `fetched_at` (`briefing.py:2268`), `_get_existing_article_urls`/`_save_articles` filter `Article.url.in_(...)` (`:2243,2196`). Only `backend/app/models/api_key.py:68-69,104-105` declares indexes.
- **Why it matters:** Memory + scan cost grow unbounded with history (compounds F-B1); missing indexes mean every `WHERE user_id=...`, `WHERE status=...`, `ORDER BY created_at`, `WHERE topic_id IN (...)` is a full scan (tolerable at small scale, free to fix).
- **Recommended fix:** For `get_last_script_for_topics`: add `.limit(50)` and `.options(load_only(Briefing.id, Briefing.transcript, Briefing.extra_data))`, or store a normalized `topic_ids` signature column to `WHERE` on. Add `index=True` to `Briefing.user_id/status/created_at/generated_at/cast_id` and `Article.topic_id/fetched_at`; consider composite `(user_id, status, created_at)`.
- **Risks / caveats:** Index changes need a migration (see F-I5). Real impact only material once history grows — measure.

### F-L6: No caching of facts/articles across briefings on the same topic
- **Severity:** Med · **Effort:** M
- **Symptom:** Two briefings on the same topic an hour apart independently fetch RSS/NewsAPI, scrape article pages, run the story-analyzer LLM call, and run the facts LLM call. The only reuse is dedup-by-URL against already-*saved* articles and passing the previous transcript/recent-article metadata as context — not reuse of the expensive facts output.
- **Evidence:** `backend/app/services/briefing.py:2080-2174` `_generate_additional_facts` always fetches content and calls `self.orchestrator.gather_additional_facts(...)` — no lookup of prior facts. `Article` rows store `summary`/`content` but not generated facts. `get_last_script_for_topics` (`:1471-1510`) and `_get_recent_articles_for_topics` (`:2247-2294`) feed *context* only. No `lru_cache`/memoization anywhere in the LLM path.
- **Why it matters:** $ — the facts call uses `max_tokens=16384` over full article bodies for up to 5 articles (`facts_gatherer.py:281`); regenerating it for an article already analyzed in a recent briefing is pure waste. Same for the story-analyzer pass when candidate sets overlap.
- **Recommended fix:** Persist generated facts keyed by `article.url` (or content hash) with a TTL; in `_generate_additional_facts`, only send articles lacking fresh cached facts to the LLM. Optionally cache `fetch_page_content` results by URL for a short window.
- **Risks / caveats:** Need a sensible TTL (developing-story facts go stale); add a "force refresh" path.

### F-L7: A late-stage failure redoes all earlier (billed) LLM calls — no stage checkpointing
- **Severity:** Med · **Effort:** M
- **Symptom:** If the writer call (step 7) fails, the briefing is marked `failed` and any retry restarts from step 1 — re-running news fetch, the story-analyzer LLM call, and the facts LLM call, all already succeeded and billed.
- **Evidence:** Pipeline is a single linear method `_generate_briefing_internal` (steps 4→5→7 at `backend/app/services/briefing.py:720-884`) with one terminal handler `except Exception: briefing.status = "failed"; ...; raise` (`:538-545` / `:1102-1115`). `ranked_items`, `additional_facts`, `raw_analysis`, `raw_facts_response` are locals only — not a resumable checkpoint. `generate_briefing` (`:168-248`) always calls `_generate_briefing_internal` from the top.
- **Why it matters:** $ — on retry you pay twice (or N times) for the analyzer and facts calls. With F-L4 (no in-call retry) this is the dominant avoidable-cost scenario.
- **Recommended fix:** Persist intermediate artifacts (ranked article IDs + ranking, generated facts JSON, raw responses) on the `Briefing` row as each stage completes; on retry, skip stages whose artifact already exists.
- **Risks / caveats:** Invalidate checkpoints if topics/cast/duration change between attempts.

### F-F3: Multiple `['briefings']` pollers + broad invalidations + `refetchOnWindowFocus` → request bursts
- **Severity:** Med · **Effort:** M
- **Symptom:** Backend logs show `GET /api/briefings?limit=10&offset=0` firing ~20× in a rapid burst.
- **Evidence:** Two components hold a `['briefings']`-prefixed query resolving to the same URL when unfiltered: `frontend/src/pages/DashboardBriefs.tsx:65-78` (`queryKey: ['briefings', ...filters, currentPage]`, `refetchInterval` 2000/10000 ms) and `frontend/src/pages/DashboardGenerate.tsx:58-64` (`queryKey: ['briefings']`, `refetchInterval` 2000/10000 ms). Many mutations broadly invalidate `['briefings']`: `frontend/src/components/AudioPlayer.tsx:95,107` (mark-listened fires ~5 s into every playback — `:196-204` — plus favorite), `frontend/src/pages/BriefingDetail.tsx:124,134,142,189`, `DashboardBriefs.tsx:111`, `DashboardGenerate.tsx:167,172,181`, `DashboardSchedules.tsx:69`, `ProfileSwitcher.tsx:49`, `Onboarding.tsx:1859` — `invalidateQueries({queryKey:['briefings']})` refetches every active `['briefings']`-prefixed query at once. `AudioPlayer.tsx:126` (`playNextUnlistenedBriefing`) calls `briefingsApi.list(10,0,false)` directly, bypassing React Query. React Query v5 defaults `refetchOnWindowFocus/Reconnect/Mount` to `true`; with `<React.StrictMode>` (`frontend/src/main.tsx:18`) double-invoking effects in dev, one tab focus + a mark-listened invalidation fans out to ~20 requests.
- **Why it matters:** Network/battery; backend load (compounds F-B1); can race the "wrong audio after switching" UX as briefing/cast queries re-fetch in storms.
- **Recommended fix:** One shared `['briefings']` query hook instead of two; replace broad `invalidateQueries(['briefings'])` after mark-listened/favorite with `queryClient.setQueryData` optimistic updates (already done in `Settings.tsx:199-207`); route auto-play-next through React Query; consider `refetchOnWindowFocus: false` in the `QueryClient` defaults; bump `staleTime` for the list.
- **Risks / caveats:** Needs measurement to confirm the exact multiplier; the polling during generation is intentional — keep it.

### F-F4: O(n) active-segment/chapter scans on every `timeupdate`; unstable `segmentTimings`/`chapters` refs
- **Severity:** Med · **Effort:** M
- **Symptom:** ~4×/sec for the playing briefing, `findActiveSegment` and `findActiveChapter` linear-scan the full lists; `formatTranscript()` rebuilds the entire transcript JSX (with `clsx`, `chapters.find()` per segment) on every `activeSegmentIndex` change.
- **Evidence:** `frontend/src/pages/BriefingDetail.tsx:283-295` (`findActiveSegment` — `for` loop over `segmentTimings`), `:548-560` (`findActiveChapter` — loop over `chapters`), subscribed via `audioManager.onTimeUpdate` at `:305-315` and `:572-582`. `formatTranscript` at `:592-718` does `chapters.find(...)` (`:602-605`) *inside* `segmentTimings.forEach` — O(segments × chapters) — and is called unconditionally in render (`:790+`). `segmentTimings = briefing?.extra_data?.segment_timings || []` (`:197`) and `chapters = briefing?.chapters || []` (`:200`) are new arrays each render unless `briefing` is referentially identical, so the `useCallback`s and the subscription effects (`:298-320`, `:566-587`) re-run whenever `briefing` re-fetches (see F-F3).
- **Why it matters:** Runtime jank during playback, especially long briefings (hundreds of segments) on mobile; worsened by F-F3's refetch storms producing fresh `briefing` objects.
- **Recommended fix:** `useMemo` `segmentTimings`/`chapters` keyed on `briefing?.id`; build a sorted lookup once and binary-search by time, or precompute a `chapterStartBySegmentIndex` map; `useMemo` the transcript JSX and derive only the *highlight* via cheap state; `React.memo` an extracted `<Segment>` component.
- **Risks / caveats:** Needs measurement on a realistic segment count; binary-search correctness needs unit coverage.

### F-I3: `audio/` grows unbounded — no retention policy; shares the DB volume in Docker
- **Severity:** Med · **Effort:** M
- **Symptom:** Audio is only deleted on explicit `DELETE /api/briefings/{id}`. Scheduled briefings run daily, each producing a multi-MB `.mp3` never pruned. No max-count, max-age, or max-disk policy anywhere.
- **Evidence:** `backend/app/services/briefing.py:1600-1642` `delete_briefing` is the only path calling `audio_path.unlink()` for completed briefings. No retention setting in `backend/app/config.py` (only `audio_storage_path`). No cleanup job among the three APScheduler jobs (`main.py:172-195`). `docker/docker-compose.yml:36-39` mounts `../data` (SQLite DB), `../audio`, `../models` — the DB and audio share a host disk.
- **Why it matters:** On a long-running self-hosted instance with daily schedules, `audio/` fills the host disk; because the SQLite DB is on the same mount, a full disk → `disk I/O error` → effectively total outage.
- **Recommended fix:** Add `briefing_retention_days` / `briefing_retention_count` settings + a daily APScheduler job deleting old briefings (and their audio). At minimum, provide a manual cleanup CLI command and document it.
- **Risks / caveats:** None significant.

### F-I5: Migrations not auto-run, not ordered, not tracked — schema drift on upgrade
- **Severity:** Med · **Effort:** M
- **Symptom:** `init_db()` only does `Base.metadata.create_all` — creates missing tables, never adds columns to existing tables. The hand-written `backend/app/migrations/*.py` scripts are not invoked anywhere in code; the only execution path documented is `docker/README.md:100-109` ("run `docker exec ... python -m app.migrations.add_profiles_table`" by hand, one at a time). No `schema_version` / applied-migrations table; order matters but nothing enforces it.
- **Evidence:** `grep` for `migrat` finds only the migration files, the docs, and `docker/README.md`. `backend/app/main.py:160-162` startup: `await init_db()` and nothing else. `backend/app/database.py:40-43` `init_db` is `create_all` only. `backend/app/migrations/add_profiles_table.py:86-145` ALTERs four tables in one `engine.begin()` block — half-failure leaves no record of progress (recoverable only because each step re-checks `PRAGMA table_info`). `rename_sendgrid_to_resend.py` / `fix_profiles_emoji_column.py` do `CREATE TABLE ..._new` → copy → `RENAME` — interrupted mid-rebuild can leave both the original and a stale `_new` table.
- **Why it matters:** Deploy friction + silent data-shape bugs — a self-hoster who `git pull`s + rebuilds gets new app code against the old schema; first request touching a new column 500s with `no such column`. Required ordering (`create_casts_tables` before `add_description_to_casts`; `add_profiles_table` → `update_profiles_emoji_to_color` → `fix_profiles_emoji_column`) is unenforced.
- **Recommended fix:** Either (a) run all migrations in a defined order at startup right after `init_db()`, recording applied ones in a `schema_version` table; or (b) adopt Alembic — `alembic init`, a baseline revision matching current `Base.metadata`, convert the ~13 scripts to revisions (or stamp the baseline and keep new changes Alembic-only), wire `alembic upgrade head` into the Dockerfile entrypoint / lifespan. Worth it given the project clearly intends ongoing schema evolution.
- **Risks / caveats:** Auto-running migrations on startup + multi-process would race (same caveat as F-I1); fine for the current single-process model.

### F-B6: Script re-parsed with regex 4+ times per generation; chapter-stripping duplicated 3 ways
- **Severity:** Low · **Effort:** S
- **Symptom:** After the LLM returns the script, overlapping regex passes run over the full text: title extraction (×2 patterns), chapter-marker stripping, chapter extraction, `_parse_script`, and `_split_segments_by_chapters` (which calls `_parse_script` again per chapter), plus `_map_chapters_to_timestamps` does another `re.sub` to strip chapters and `re.finditer` for positions.
- **Evidence:** `backend/app/services/briefing.py:899-934` — `re.search`/`re.sub` for TITLE (×2), `_extract_chapters` (`re.finditer`), `re.sub(r'\[CHAPTER:...\]', '', script)`, `_parse_script(script, ...)`, `_split_segments_by_chapters(script, ...)`. `:1131` `_parse_script` — `re.sub(r'\[CHAPTER:\s*.+?\]', '', script)` again; `:1260,1269` `_split_segments_by_chapters` calls `_parse_script` per chapter (N+1 more strips). `:1405,1417` `_map_chapters_to_timestamps` — another `re.sub` + `re.finditer`.
- **Why it matters:** CPU on the event loop (small in absolute terms — script is a few KB) and a maintenance hazard: three slightly different "split by chapters" code paths.
- **Recommended fix:** Parse once — strip chapter markers a single time into `clean_script` + record `(marker_title, char_offset)` list; derive `segments`, `segment_chunks`, `chapters`, and the chapter→timestamp mapping from those precomputed structures. Compile the `[CHAPTER:...]` regex module-level.
- **Risks / caveats:** Low-risk refactor but touches chapter-timing logic the user considers settled — keep the chunk-offset path untouched, only de-dup the parsing.

### F-B7: `_send_batched_email_after_delay` handed a request-scoped DB session it can't safely use later
- **Severity:** Low · **Effort:** S
- **Symptom:** `trigger_scheduled_briefing` creates a session via `async with async_session() as db:` and an `engine` it disposes in `finally`; before returning it spawns `asyncio.create_task(self._send_batched_email_after_delay(db=db, ...))`. The task sleeps 90 s + polls up to 10 min — by then the `async with` block has exited and `engine.dispose()` has run, so the passed `db` is closed/invalid. (Currently harmless: the task builds its own session and never uses the param — but it's a latent footgun, and the closure captures `self`/`self.db`.)
- **Evidence:** `backend/app/services/scheduled_briefing.py:259, 317-326` — `async with async_session() as db: ... asyncio.create_task(self._send_batched_email_after_delay(db=db, db_url=db_url, ...))`. `:340-341` — `finally: await engine.dispose()`. `:343-466` — the task does `await asyncio.sleep(90)`, poll loop, then creates its own `engine`/`async_session` (`:390-394`) for everything.
- **Why it matters:** Latent bug — any future code touching `db`/`self.db` inside that task hits a disposed engine.
- **Recommended fix:** Drop the `db` parameter; the task already builds its own session. Don't pass/capture `self` if avoidable (make it a module function).
- **Risks / caveats:** None — defensive cleanup.

### F-B8: `OpenRouterProvider` calls `get_settings.cache_clear()` on the hot path
- **Severity:** Low · **Effort:** S
- **Symptom:** Each time the provider resolves its model or (re)builds its `httpx` client and the value isn't in `os.environ`, it does `get_settings.cache_clear()` then `get_settings()` — `get_settings` is `@lru_cache` and used app-wide, so this forces a full `.env` re-parse + `Settings()` re-construction across the whole app, not just this provider.
- **Evidence:** `backend/app/services/llm/openrouter.py:44-45, 61-62` — `get_settings.cache_clear(); current_settings = get_settings()` inside the `model` and `client` properties. `backend/app/config.py:131-132` — `@lru_cache def get_settings(): ...`. Many call sites rely on the warm cache (`database.py:8`, `briefing.py:37`, `tts/factory.py:33,68`, `main.py:33,108,159`).
- **Why it matters:** Re-instantiating `Settings` on each LLM call adds avoidable latency and defeats `lru_cache`; also a correctness smell (modules that captured `settings = get_settings()` at import time won't see the refreshed object anyway).
- **Recommended fix:** If the goal is to pick up runtime API-key/model changes, read those specific values from a small mutable config store or re-query the changed DB/settings row — don't nuke the process-wide cache. At minimum, only `cache_clear()` when a change is actually detected.
- **Risks / caveats:** If a path genuinely depends on settings being re-read here (UI key edit mid-session), give it a deliberate refresh mechanism instead. Overlaps F-L10.

### F-B9: `Piper._check_piper_available` runs `subprocess.run` directly inside `async def`
- **Severity:** Low · **Effort:** S
- **Symptom:** When Piper is the configured TTS provider in CLI mode, the availability check blocks the event loop on a synchronous `subprocess.run` (process spawn + wait).
- **Evidence:** `backend/app/services/tts/piper.py:74-81` — `result = subprocess.run(["piper", "--help"], capture_output=True, text=True)` inside `async def _check_piper_available`. (The HTTP-mode branch at `:68-72` short-circuits; the rest of Piper's subprocess work is `asyncio.to_thread`-wrapped at `:206,401,434,526` — this is the one straggler.)
- **Why it matters:** Brief loop stall on first synthesis with the CLI provider; minor, Piper-only. Memoized, so a one-time hit.
- **Recommended fix:** `await asyncio.to_thread(subprocess.run, [...], ...)` like the other Piper calls.
- **Risks / caveats:** None.

### F-B10: Sync file writes (multi-MB WAV buffers, ffmpeg concat list) done on the event loop
- **Severity:** Low · **Effort:** S
- **Symptom:** `utils/audio.py:131-139` writes the ffmpeg `_concat_list.txt` with a sync `open(...)` inside `async def concatenate_audio_files` before the `to_thread`-wrapped ffmpeg call (tiny file). `tts/gemini.py` writes potentially several MB of WAV via sync `open(tmp_path, "wb")` inside `async def synthesize_conversation` (not in a `to_thread`).
- **Evidence:** `backend/app/utils/audio.py:131-139` — `list_file = output_path.parent / "_concat_list.txt"; with open(list_file, "w", ...) as f: f.write(...)` inside `async def`. `backend/app/services/tts/gemini.py:583-589` and `:266-267` — `with tempfile.NamedTemporaryFile(...); with open(tmp_path, "wb") as f: f.write(wav_data)` inside `async def`.
- **Why it matters:** Writing multi-MB WAV buffers synchronously stalls the loop briefly during every TTS finalize; a handful per briefing.
- **Recommended fix:** Move the WAV/list-file writes into the `asyncio.to_thread` block alongside ffmpeg/ffprobe (write + convert + duration in one off-thread step), or `asyncio.to_thread(path.write_bytes, data)`.
- **Risks / caveats:** None significant; polish. (Note: temp-file *cleanup* is otherwise solid — `tts/gemini.py:283-286,639-641`, `tts/factory.py:304-312`, and `audio.py:186-192` all use `try/finally` + `unlink()`.)

### F-B11: `BriefingService.__init__` eagerly builds LLM/orchestrator/news/search even for pure-read endpoints
- **Severity:** Low · **Effort:** S
- **Symptom:** `BriefingService.__init__` always does `get_llm_provider()` + `BriefingOrchestrator(...)` + `get_news_service()` + `get_search_service()`, even for the many call sites that only need DB reads (`get_briefing`, `list_briefings`, `update_*`, `cancel_briefing`, `has_any_active_briefing`, `regenerate_audio`). `routers/briefings.py` constructs `BriefingService(db)` on every briefings endpoint.
- **Evidence:** `backend/app/services/briefing.py:47-52` — eager construction in `__init__`. `backend/app/routers/briefings.py:87,122,192,218,245,273,301,328,398` — `service = BriefingService(db)` per request, including pure-read endpoints. (`news.py:47-61` and `openrouter.py` are cheap — no network in `__init__`, lazy `httpx` client — so the cost is small object churn / import coupling on hot read paths.)
- **Why it matters:** Minor allocation/coupling overhead on every API call; mostly a code smell.
- **Recommended fix:** Make `llm`/`orchestrator`/`news`/`search` lazy `@property`s so read-only endpoints don't construct them; optionally split a thin read service.
- **Risks / caveats:** None. (Also: `regenerate_audio` references `self.MAX_TTS_CHUNKS`/`self._merge_to_max_chunks` defined later in the class — works, but the coupling is worth noting.)

### F-L5: Flat 120 s HTTP timeout, no connect/read split, no streaming
- **Severity:** Low · **Effort:** S
- **Symptom:** Single `timeout=120.0` for the whole request; responses are non-streaming, so a slow 32k-token writer generation holds the connection (and the briefing worker) for up to 2 minutes with no progress signal, then fails hard.
- **Evidence:** `backend/app/services/llm/openrouter.py:79-88` — `httpx.AsyncClient(base_url=..., headers={...}, timeout=120.0)`; the request is a plain `self.client.post("/chat/completions", json=payload)` (`:146-150`) — no `stream=True`.
- **Why it matters:** Latency visibility / worker utilization; makes F-L3 worse (no early signal).
- **Recommended fix:** `httpx.Timeout(connect=10, read=120, write=30, pool=...)`; consider streaming the writer call so partial output can be salvaged and progress reported.
- **Risks / caveats:** Streaming changes the response-parsing path — modest refactor.

### F-L8: Facts agent sends `full_content` AND a re-fetched `ADDITIONAL WEB CONTENT` for the same article
- **Severity:** Low · **Effort:** S
- **Symptom:** For each story the facts user-prompt includes `FULL ARTICLE CONTENT` (the 3000-char body fetched by `briefing.py`) *and* `ADDITIONAL WEB CONTENT` (a fresh ≤5000-char fetch of the same page). When the original page succeeds both blocks are largely the same text.
- **Evidence:** `backend/app/services/llm/agents/facts_gatherer.py:158-176` — `full_content = story.get('full_content'); if full_content: story_text += f"\nFULL ARTICLE CONTENT...\n{full_content}\n"` … `additional = additional_content.get(i - 1); if additional: story_text += f"\nADDITIONAL WEB CONTENT...\n{additional}\n"`, with `additional_content[i] = await self._fetch_article_content(story)` (`:267-269`) re-fetching `story['url']` at `:104`.
- **Why it matters:** $ — up to ~8k chars (~2k tokens) of near-duplicate context per article × 5 into a `max_tokens=16384` call; also drives the extra fetch in F-L1.
- **Recommended fix:** One content source per article — prefer the already-fetched `full_content`; only fetch+append `ADDITIONAL WEB CONTENT` (an *alternative* source) when the original body is missing/short; de-dupe overlapping text before sending.
- **Risks / caveats:** Keep the alternative-source fallback for the missing-body case.

### F-L9: Independent DB context lookups run *after* the LLM calls instead of concurrently up front
- **Severity:** Low · **Effort:** S
- **Symptom:** The analyzer (step 4) → facts (step 5) → writer (step 7) LLM calls are genuinely dependent and can't be parallelized, but the `_get_recent_articles_for_topics` and `get_last_script_for_topics` DB lookups are independent of all three and currently run *after* them rather than being kicked off concurrently at pipeline start. Separately, the full topic list is re-serialized into the analyzer, facts, and writer prompts (3×), and the full ranked article set is carried in both the facts prompt (with bodies) and the writer prompt (with excerpts).
- **Evidence:** Serial chain: `backend/app/services/briefing.py:728` (`await self._analyze_and_rank_stories`), `:784` (`await self._generate_additional_facts`), `:867` (`await self.orchestrator.write_briefing_script`). Independent lookups done late: `:822` `recent_articles = await self._get_recent_articles_for_topics(...)`, `:831` `last_script = await self.get_last_script_for_topics(...)`. Re-serialized content: `facts_gatherer.py:158-163` (full body into facts prompt); `news.py:449-465` / `briefing_writer.py:659-664` (excerpts into writer prompt).
- **Why it matters:** Mostly latency (small upside — the three LLM calls dominate and are dependent) plus modest token duplication.
- **Recommended fix:** Launch `_get_recent_articles_for_topics` and `get_last_script_for_topics` as tasks at pipeline start, `await` at step 7. Consider whether the writer needs full article excerpts when it also receives the facts agent's distilled Q&A — if not, drop excerpts and pass distilled facts only, shrinking the most expensive prompt.
- **Risks / caveats:** Don't try to `gather` the three LLM calls — they depend on each other. Dropping writer excerpts needs a quality check.

### F-L10: Writer `OpenRouterProvider` (+ `httpx` client) recreated per briefing, never closed
- **Severity:** Low · **Effort:** S
- **Symptom:** When `OPENROUTER_WRITER_MODEL` is set, `BriefingOrchestrator.__init__` creates a second `OpenRouterProvider` (with its own `httpx.AsyncClient`) fresh on every orchestrator construction — i.e. per briefing — and never explicitly closes it.
- **Evidence:** `backend/app/services/llm/agents/orchestrator.py:33-38` — `if writer_model: writer_llm = OpenRouterProvider(model=writer_model)`. `backend/app/services/llm/openrouter.py:74-77` — the `client` property comment acknowledges an old client "can't await here" and is just left.
- **Why it matters:** Connection-pool churn (new TLS handshake per briefing for the writer model), leaked `AsyncClient` objects.
- **Recommended fix:** Cache the writer `OpenRouterProvider` keyed by model instead of recreating per briefing; close old clients properly.
- **Risks / caveats:** None significant. Overlaps F-B8's `cache_clear` point.

### F-F2: `wavesurfer.js` is a dependency but unused
- **Severity:** Low · **Effort:** S
- **Symptom:** `wavesurfer.js@^7.6.2` is in `dependencies` but no source file imports it (the audio UI is a custom progress bar in `AudioPlayer.tsx`).
- **Evidence:** `frontend/package.json:25` — `"wavesurfer.js": "^7.6.2"`; `grep -rn "wavesurfer|WaveSurfer" src/` → no matches.
- **Why it matters:** Install/CI weight; risk of accidental bundling later; confusion. (Not in the current bundle — tree-shaken out since it's never imported.)
- **Recommended fix:** Remove it from `package.json` (or actually use it for the waveform). Verify with a fresh build that bundle size is unchanged.
- **Risks / caveats:** Confirm no dynamic/string import elsewhere first (none found).

### F-F5: Many components independently re-fetch `settings`/`topics`/`casts`
- **Severity:** Low · **Effort:** S
- **Symptom:** `['settings']` is fetched by `App.tsx`, `BriefingDetail.tsx`, `AudioPlayer.tsx`, `DashboardBriefs.tsx`, `Settings.tsx`; `['topics']` by `BriefingDetail`, `AudioPlayer`, `DashboardBriefs`, `DashboardGenerate`, `Topics`; `['casts']` similarly. When `AudioPlayer` is mounted alongside `BriefingDetail`, both run `useQuery(['briefing', id])` and `useQuery(['cast', cast_id])`.
- **Evidence:** `frontend/src/App.tsx:32-35` (`['settings']`), `frontend/src/pages/BriefingDetail.tsx:85-88,94-97,102-113`, `frontend/src/components/AudioPlayer.tsx:58-81`, `frontend/src/pages/DashboardBriefs.tsx:86-101`, `frontend/src/pages/DashboardGenerate.tsx:67-76`.
- **Why it matters:** Mostly mitigated by the 5-min `staleTime` (dedupes within the window), but every `refetchOnWindowFocus` and every `invalidateQueries(['settings'])` (`Onboarding.tsx`, `Settings.tsx:1295`) fans out to all subscribers; extra requests on first navigation before the cache warms.
- **Recommended fix:** Acceptable as-is given React Query's dedup; if trimming, set `staleTime` on these slow-changing resources to a long value / `Infinity` and disable `refetchOnWindowFocus` for them.
- **Risks / caveats:** Low priority; verify nothing relies on settings refreshing on focus.

### F-F6: Debug `console.log` of full `briefing.extra_data` ships to prod and fires nearly every render
- **Severity:** Low · **Effort:** S
- **Symptom:** Every time `briefing` (re)loads — and effectively every render of the page, since the effect dep `chapters` is a fresh array each render — the whole `extra_data` blob (segment timings, raw analyses, costs) is logged to the browser console.
- **Evidence:** `frontend/src/pages/BriefingDetail.tsx:203-208` — `useEffect(() => { if (briefing) { console.log('[BriefingDetail] Briefing chapters:', chapters); console.log('[BriefingDetail] Briefing extra_data:', briefing.extra_data) } }, [briefing, chapters])`. `frontend/vite.config.ts` has no `esbuild.drop: ['console']`.
- **Why it matters:** Minor runtime cost + leaks internal data to the prod console; the unstable `chapters` dep makes it fire far more than intended.
- **Recommended fix:** Delete the debug effect (or gate on `import.meta.env.DEV`); add `esbuild: { drop: ['console','debugger'] }` to `vite.config.ts` for prod builds.
- **Risks / caveats:** None.

### F-F7: `DashboardBriefs` reads `window.innerWidth` in render + extra resize listener; unmemoized cards
- **Severity:** Low · **Effort:** S
- **Symptom:** Layout decisions (`window.innerWidth < 640`) are computed during render of each briefing card; a `resize` listener drives an `isMobile` state that re-renders the whole list; each card gets fresh inline `onClick` closures and `style={{...}}` objects; topic chips computed via `topics.filter(...)` per card per render.
- **Evidence:** `frontend/src/pages/DashboardBriefs.tsx:426,442` (`window.innerWidth < 640` inside `renderBriefingCard`), `:42-49` (resize listener → `setIsMobile`), `:213-580` (`renderBriefingCard` is a plain unmemoized function creating new `onClick`/`style` per render), `:849,873,886` (`topics.filter(...)` per card per render).
- **Why it matters:** Reading layout in render can force reflow; full-list re-render on every resize tick; GC churn. List is small (page size 10), so impact is modest and no virtualization is needed at this size.
- **Recommended fix:** Use `matchMedia`/CSS for the mobile breakpoint; extract a memoized `<BriefingCard>`; precompute the topic→briefing map once with `useMemo`.
- **Risks / caveats:** Low priority; only matters if page sizes grow.

### F-F8: No brotli; PWA precaches the whole 667 KB bundle
- **Severity:** Low · **Effort:** S
- **Symptom:** `nginx.conf` enables only `gzip` (no brotli); the service worker precaches `**/*.js` (the monolithic bundle) on install.
- **Evidence:** `frontend/nginx.conf` — `gzip on; gzip_types ... application/javascript;` (no `brotli`). `frontend/vite.config.ts:57` — `workbox.globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}']`.
- **Why it matters:** Slightly larger transfer than brotli; first PWA install downloads the entire bundle. Largely moot once F-F1 (code splitting) lands — then the precache covers many small chunks.
- **Recommended fix:** Add brotli to nginx (or precompress with `vite-plugin-compression`); revisit after code splitting.
- **Risks / caveats:** Do after F-F1.

### F-I7: `piper.py` HTTP path leaks a temp WAV if MP3 conversion raises
- **Severity:** Low · **Effort:** S
- **Symptom:** In `_synthesize_http`, when the response isn't already WAV/MP3-aligned: `with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp: tmp_path = ...` then *outside* any try/finally: `await self._convert_to_mp3(tmp_path, output_path); tmp_path.unlink()`. If `_convert_to_mp3` raises (other than the `FileNotFoundError`-copies branch), `tmp_path.unlink()` never runs. The CLI path (`piper.py:222-259`) correctly uses `try/finally`.
- **Evidence:** `backend/app/services/tts/piper.py:160-171` — the `with NamedTemporaryFile(...)` then bare `await self._convert_to_mp3(tmp_path, output_path); tmp_path.unlink()` (skipped on exception).
- **Why it matters:** Slow growth in the OS temp dir under repeated failures (e.g. misconfigured remote Piper + ffmpeg edge cases). Minor.
- **Recommended fix:** Wrap in `try/finally: if tmp_path.exists(): tmp_path.unlink()`, mirroring the CLI path.
- **Risks / caveats:** None; trivial.

### F-I8: Per-task `create_async_engine` multiplies SQLite connection pools / leak window
- **Severity:** Low · **Effort:** S
- **Symptom:** `generate_briefing_task`, `regenerate_audio_task`, and every migration script create a *fresh* `create_async_engine(db_url)`. The briefing tasks dispose it in `finally` — good — but at peak there are two+ SQLAlchemy engines/pools open against the same SQLite file (the lifespan one + the task one), each able to hold the single write lock, working against the "single writer" invariant (compounds F-I4). If any code between `create_async_engine` and the `async with` raised (none does today — latent), the engine leaks.
- **Evidence:** `backend/app/routers/briefings.py:41-71` — `engine = create_async_engine(db_url); async_session = async_sessionmaker(engine, ...)`; disposal only in `finally` (`:69`). `:366-378` — same in `regenerate_audio_task`. `backend/app/main.py:23-24` and `:59-61` — scheduler jobs reuse the shared `app.database.async_session_maker`, but the briefing worker does not.
- **Why it matters:** Minor connection/lock pressure + a "why are there two engines" code smell that compounds F-I4.
- **Recommended fix:** Have `generate_briefing_task`/`regenerate_audio_task` reuse `app.database.async_session_maker` (as the scheduler jobs do) unless there's a deliberate reason for an isolated pool (there doesn't appear to be).
- **Risks / caveats:** Verify the worker doesn't actually want isolation.

### F-I6: Docker runtime image heavier than needed; deps unpinned, no `.dockerignore`
- **Severity:** Low · **Effort:** M
- **Symptom:** `backend/Dockerfile` is single-stage from `python:3.11-slim` with `COPY . .` (copies the whole backend dir — `cli.py`, a local `venv/` if present, `__pycache__`, tests) plus `RUN apt-get install ffmpeg curl` (large). Piper voice models are *not* baked in (good — mounted volume), but the image still carries the full build of every dep with no multi-stage trim. `requirements.txt` is all `>=`, so builds days apart get different dependency sets.
- **Evidence:** `backend/Dockerfile:1-37` — no multi-stage, no `.dockerignore` (none in `git ls-files`), `COPY . .` with no exclusions, `ffmpeg`+`curl` in the final layer. `backend/requirements.txt:1-42` — every dep is `>=`, none `==` (the code already has a `python_version >= "3.13"` audioop hack — evidence of churn sensitivity). `docker/docker-compose.dev.yml:20` mounts `../backend:/app` over the image's `/app`, so dev runs against host source while prod runs the baked copy — divergence risk if a needed file is gitignored.
- **Why it matters:** Larger pulls/pushes, slower deploys; unpinned deps → non-reproducible builds (a breaking `google-genai`/`pydantic` minor could ship silently — exactly the class of issue that prompted the recent `google-genai>=1.20,<2` pin).
- **Recommended fix:** Add a `.dockerignore` (`venv/`, `__pycache__`, `*.db`, `audio/`, `models/`, tests, `cli.py` if not needed at runtime). Pin direct deps with `==` (or a lockfile / `pip-tools`). Optionally split a builder stage for wheels. `curl` is only used by the healthcheck — replace with a tiny Python `urllib` one-liner to drop it.
- **Risks / caveats:** Low urgency — the image works. Pinning is the highest-value, lowest-risk part.

---

## Inspected and healthy

### Backend performance & async
- TTS provider HTTP/SDK calls are correctly off-loaded: `gemini.py` wraps `genai` SDK calls in `asyncio.to_thread` (+ `cancellable_await`); `utils/audio.py` wraps every `ffmpeg`/`ffprobe` `subprocess.run` in `asyncio.to_thread`; `piper.py` routes CLI/`wave`/subprocess work through `asyncio.to_thread` (except F-B9); `elevenlabs.py` uses `asyncio.create_subprocess_exec`. OpenRouter and all scrapers use `httpx.AsyncClient`; RSS feed fetching is concurrent.
- The recent Gemini TTS chunking/concurrency work is sound (`MAX_TTS_CHUNKS=3` outer cap, `GEMINI_CHUNK_BYTE_BUDGET`, `max_concurrent_requests=3` outer / `1` inner, retry-with-backoff then split-in-half recovery, per-chunk PCM-byte duration estimation, order-preserving `asyncio.gather`, native WAV concat with no per-chunk ffmpeg) — as requested, not re-designed.
- Custom-site fetching and additional-facts page fetches are already parallelized with `asyncio.gather`, with DB writes deferred until after the gather (no session-from-multiple-tasks corruption).
- Cancellation plumbing is well-designed: in-memory `asyncio.Event` fast path before any DB query; `cancellable_await` races in-flight HTTP/SDK calls against the event.
- DB session lifecycle is per-request for routers (`get_db` dependency); background tasks create their own short-lived engine+session and `engine.dispose()` in `finally`; `expire_on_commit=False` avoids lazy re-fetch after commit. `Cast.members` is `selectinload`ed everywhere it's read; `Briefing.profile` and `CustomSite.topic` are `selectinload`ed in the pipeline — no obvious N+1 there.
- Queue double-processing within a single process is guarded (an `asyncio.Lock` + `_global_generating`/`_processing` flags, plus a DB `has_any_active_briefing()` check).

### LLM agent pipeline
- Cancellation plumbing is clean — `OpenRouterProvider.generate_conversation` wraps the POST in `cancellable_await(..., briefing_id)`; `briefing.py` calls `_check_cancelled` before/after every LLM step.
- Story-analyzer prompt already trims article bodies (`title/source/category` + `summary[:300]` per article, `max_tokens=8192`, `temperature=0.3`).
- Personality system prompts are tiny (~50 lines of short strings each; `base.py` returns `""` by default) — not a meaningful token cost.
- Article content is bounded before the LLM (3000-char truncation in `briefing.py`, 5000-char in `search.py`); `news.format_news_for_briefing` adds an excerpt only when it differs from the summary.
- Facts/story-analysis JSON parsing is defensively layered (3 fallback strategies) — a malformed-but-recoverable response doesn't force a re-call.
- `regenerate_audio` does NOT re-run the LLM pipeline — it reuses stored `script`/`segment_timings` (cast-only re-renders are free of LLM cost).
- The writer/standard model split is wired correctly — a separate `OpenRouterProvider(model=writer_model)` is created only when `OPENROUTER_WRITER_MODEL` is set, else the shared provider is reused.

### Frontend
- React Query is the data layer (`main.tsx`) with a sensible global `staleTime: 5min` / `retry: 1`; all page-level fetches go through `useQuery`/`useMutation`.
- `briefingsApi.list()` requests `limit/offset` and filters server-side; the list endpoint is paginated (`pageSize = 10`). (The over-fetch concern is on the backend payload, F-B1 — not the request shape.)
- No production source maps (`vite.config.ts` never sets `build.sourcemap`; `dist/assets/` has no `.map` files).
- The `audioManager` singleton is the correct fix for the "two players / wrong audio" bug class — exactly one `<audio>` element app-wide; switching briefings replaces `audio.src` rather than mounting a new element. Event-listener and MediaSession-handler lifecycles are cleaned up in effect returns.
- The transcript "follow" feature does NOT do layout read/write on every `timeupdate` — the handler only updates `activeSegmentIndex`; `scrollIntoView` is in a separate effect keyed on that index (so only every few seconds). (The O(n) *scan* per tick is still flagged as F-F4.)
- `Layout.tsx` memoizes derived nav items and uses store selectors so unrelated updates don't re-render the shell; `Settings.tsx` memoizes its heavy derived structures; `DashboardGenerate.tsx`'s animation interval is created once and cleared on unmount.

### Infrastructure & data
- Audio serving is streamed via Starlette `StaticFiles` (HTTP Range supported) — generated `.mp3`s are never read fully into memory to serve them.
- Single-writer serialization is intentional and largely respected (`briefing_queue._global_generating` + DB status checks) — the worst-case "two long writers fighting the SQLite write lock" is avoided by design.
- Migration scripts are individually idempotent (each guards with `PRAGMA table_info` / `sqlite_master` before `ALTER`/`CREATE`). (The *orchestration* of them is the problem — F-I5.)
- The cancellation path cleans up partial audio (`BriefingCancelledException` → unlink the partial `.mp3`).
- TTS temp-file cleanup uses `try/finally` in most places (`gemini.py`, `piper.py` CLI path); deleting a briefing deletes its audio file and `Article` rows.
- Docker layer ordering is correct for cache hits (`requirements.txt` / `package*.json` copied & installed before app source); persistent state (DB, audio, models) is on bind mounts, not baked into the image; `.gitignore` correctly excludes `*.db`, `data/`, `audio/`, `models/`, `*.mp3`, `*.onnx`.
- The scheduler shuts down gracefully (`scheduler.shutdown(wait=True)` + `close_db()` in the lifespan `finally`).

---

## Suggested next cycles

- **Quick-wins implementation cycle** — bundle the S-effort High/Med findings into one spec → plan: F-F1 (code splitting), F-I1/F-B3 (startup reconciliation), F-L4 (OpenRouter retry), F-L3 (truncation detection), F-I4 (SQLite WAL/busy_timeout), F-L2 (model-aware writer max_tokens), F-L1 (dedupe article fetches), F-I2 (atomic audio write), F-F6 (drop debug console.log), F-B8 (stop nuking the settings cache). Mostly independent; could even be split front-end vs back-end.
- **Backend latency cycle** — F-B1, F-B4, F-B5, F-B2 (parallelize fetch phases, slim list endpoint, indexes, scheduler/commit hygiene).
- **LLM cost cycle** — F-L6 (facts cache), F-L7 (stage checkpointing), F-L8/F-L9 (prompt de-dup).
- **Infra/ops cycle** — F-I3 (audio retention), F-I5 (Alembic), F-I6 (Docker slim + pin).
- *(Separately scoped, per the project plan: documentation build-out; test-suite build-out.)*
