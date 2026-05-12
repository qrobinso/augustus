# Optimization Audit — Design Spec

**Date:** 2026-05-11
**Status:** Approved (design)
**Type:** Analysis / report (no code changes this cycle)

## Goal

Produce a single, prioritized optimization findings document for the augustus
app, covering backend performance, the LLM agent pipeline, the frontend, and
infrastructure/data. The report informs later, separately-scoped work; it does
not itself change code.

## Deliverable

- One Markdown file: `docs/optimization-audit-2026-05.md`, committed to git.
- No source changes in this cycle. Each finding includes a recommended fix and
  effort estimate so follow-up cycles can be scoped from it.

## Method

Dispatch parallel exploration agents — one per area below — to trace the
relevant code paths and gather evidence (`file:line` references, concrete code
excerpts, measured numbers where available). Synthesize the agent outputs into
one report. Where a claim needs runtime measurement that can't be produced in
this environment, flag it as "needs measurement" rather than asserting it.

## Scope — areas covered

### 1. Backend performance & async
- `backend/app/services/briefing.py` — the briefing generation pipeline:
  step sequencing, where time is spent, opportunities to parallelize.
- `backend/app/services/briefing_queue.py` and the APScheduler jobs
  (`process_scheduled_briefing_queue`, `process_ondemand_briefing_queue`) —
  polling intervals, "missed by" warnings, work done on the event loop.
- DB access patterns across `routers/*` and `services/*` — N+1 queries,
  lazy vs eager loading, missing indexes, session lifecycle.
- Sync-in-async blocking — CPU/IO-bound calls not wrapped in `asyncio.to_thread`
  (ffmpeg/ffprobe, file IO, the LLM/TTS SDKs).
- The TTS pipeline (`services/tts/*`, `utils/audio.py`) — chunking strategy,
  concurrency, WAV/MP3 conversion, temp-file churn. (Recent changes to
  `tts/gemini.py` and the briefing chunk cap are in scope to confirm they're
  sound, not to re-litigate.)

### 2. LLM agent pipeline
- `backend/app/services/llm/agents/*` — orchestrator → facts_gatherer →
  story_analyzer → briefing_writer → site_generator: call graph, which calls
  are serial that could be concurrent, redundant context passed between agents.
- Prompt sizes and token usage — oversized system prompts, full-article text
  vs summaries, repeated boilerplate, `writer_max_tokens` headroom.
- `backend/app/services/llm/openrouter.py` — retry/timeout config, streaming
  vs non-streaming, model selection (`openrouter_model`,
  `openrouter_writer_model`), error handling.
- Caching opportunities — facts/articles reuse across briefings, prompt-prefix
  reuse.

### 3. Frontend
- Vite build — bundle size, code-splitting / lazy routes, large dependencies.
- React render hotspots — `pages/BriefingDetail.tsx` (audio player, transcript
  auto-scroll), `pages/Settings.tsx`, `pages/Topics.tsx`, `components/Layout.tsx`:
  unnecessary re-renders, unmemoized derived state, effects that re-run too often.
- Data fetching — `api/client.ts`, React Query (or equivalent) usage, polling
  intervals (e.g. briefing-list refetch loops seen in logs), cache invalidation.
- The audio player specifically — known prior bugs around switching briefings;
  confirm current implementation doesn't re-fetch or re-decode unnecessarily.

### 4. Infrastructure & data
- SQLite vs Postgres given the workload (background generation, concurrent
  writes, scheduler) — concrete pain points, not a generic recommendation.
- Migrations — the ad-hoc `backend/app/migrations/*.py` scripts vs a migration
  tool; ordering/idempotency risks.
- Docker setup (`docker/`) — image size, layer caching, dev vs prod parity.
- Audio/file storage — growth over time, cleanup of temp files and old
  briefing audio, where files live relative to the DB.
- Background-task lifecycle — what happens to in-flight briefings on
  `WatchFiles` reload / shutdown (observed in logs: "Waiting for background
  tasks to complete").

## Report structure

1. **Executive summary** — top 5–10 findings, one line each, with severity.
2. **Findings table** — columns: ID, area, severity (High/Med/Low), estimated
   effort (S/M/L), one-line summary. Sorted by impact ÷ effort.
3. **Detailed findings** — one subsection per finding:
   - Symptom / observation
   - Evidence (`file:line`, code excerpt, or log excerpt)
   - Why it matters (impact)
   - Recommended fix
   - Risks / caveats / "needs measurement" notes
4. **Appendix** — areas inspected but found healthy (so the absence of a
   finding is explicit, not an oversight).

## Out of scope

- Security review (separate effort — `security-review` skill / SECURITY.md).
- Correctness bugs without a performance angle.
- Anything requiring load-testing or profiling infrastructure not available in
  this environment — flagged as "needs measurement" instead.
- Re-designing the recent TTS/chunking changes — only confirming soundness.

## Success criteria

- Every finding is actionable: a developer can read it and know what to change
  and roughly how much work it is.
- Every finding cites evidence in the codebase.
- The four scoped areas each have either findings or an explicit "healthy" note.
- The report is self-contained — no need to re-explore to act on it.

## Follow-up cycles (not part of this spec)

- Implement selected optimizations (own spec → plan).
- Documentation build-out (own spec → plan).
- Test suite build-out (own spec → plan).
