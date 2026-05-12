# Optimization Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `docs/optimization-audit-2026-05.md` — a prioritized, evidence-backed optimization findings report covering backend perf/async, the LLM agent pipeline, the frontend, and infra/data. No source changes.

**Architecture:** Four read-only exploration agents (one per area) run concurrently and each return a structured findings list with `file:line` evidence. A synthesis step merges them into one ranked report (impact ÷ effort). A self-review step checks coverage and evidence, then commits.

**Tech Stack:** Repo under audit: FastAPI + SQLAlchemy + APScheduler backend (`backend/`), React + Vite + TypeScript frontend (`frontend/`), SQLite, OpenRouter (LLM), Piper/ElevenLabs/Gemini (TTS), Docker. Tooling for this plan: the Agent tool with `subagent_type: Explore` (read-only) and `general-purpose` for synthesis.

**Reference spec:** `docs/superpowers/specs/2026-05-11-optimization-audit-design.md`

---

## File Structure

- Create: `docs/optimization-audit-2026-05.md` — the only output artifact. Structure defined in Task 5.
- No other files created or modified. The four research tasks produce in-memory agent reports consumed by Task 5; nothing is written to disk until Task 5.

## Conventions for all research tasks

Every research agent MUST return findings in this exact shape so synthesis is mechanical:

```
## Area: <area name>

### Healthy (inspected, no action needed)
- <bullet — what was checked and why it's fine>

### Findings
#### F-<area-letter><n>: <one-line title>
- **Severity:** High | Medium | Low
- **Effort:** S (<1 day) | M (1-3 days) | L (>3 days)
- **Symptom:** <what's observed>
- **Evidence:** <file:line refs, code excerpt, or log excerpt — REQUIRED, no finding without it>
- **Why it matters:** <impact — latency, cost, memory, scalability, DX>
- **Recommended fix:** <concrete change>
- **Risks / caveats:** <including "needs measurement" if the impact claim is unverified>
```

Area letters: backend = `B`, llm = `L`, frontend = `F`, infra = `I`. So findings are `F-B1`, `F-L3`, etc.

A research task is **done** when: (a) every claimed finding has concrete `file:line` evidence, (b) the "Healthy" section is non-empty (proves the area was actually inspected, not skimmed), (c) output follows the shape above exactly.

---

### Task 1: Backend performance & async research

**Files:**
- Create: none (returns a report to the orchestrator)
- Inspect: `backend/app/services/briefing.py`, `backend/app/services/briefing_queue.py`, `backend/app/services/cancellation.py`, `backend/app/main.py` (scheduler/lifespan), `backend/app/database.py`, `backend/app/routers/*.py`, `backend/app/services/tts/*.py`, `backend/app/utils/audio.py`, `backend/app/models/*.py`

- [ ] **Step 1: Dispatch the backend research agent**

Use the Agent tool, `subagent_type: Explore`, `description: "Audit backend perf & async"`. Prompt:

> You are auditing the `augustus` FastAPI backend for **performance and async** issues. Read-only — do not edit anything. Repo root is the working directory; backend code is under `backend/app/`.
>
> Investigate, with evidence (`file:line`):
> 1. **Briefing pipeline** (`services/briefing.py`): walk `generate_briefing` (and the regeneration path) end to end. Which steps run serially that are independent and could run concurrently? Where is wall time spent (LLM calls, TTS, ffmpeg, DB)? Any redundant work (re-parsing the script multiple times, re-reading files)?
> 2. **Queue & scheduler** (`services/briefing_queue.py`, `main.py` lifespan/APScheduler jobs `process_scheduled_briefing_queue` @10s and `process_ondemand_briefing_queue` @5s): is meaningful work done on the event loop inside these jobs (causing the "Run time of job ... was missed by" warnings)? Are the intervals reasonable? Is there a thundering-herd or double-processing risk?
> 3. **DB access** (`database.py`, `routers/*.py`, `services/*.py`): session lifecycle (per-request? long-lived?), N+1 query patterns, lazy vs eager relationship loading, missing indexes on columns used in `WHERE`/`ORDER BY` (cross-check `models/*.py`), `SELECT *` of large rows (e.g. briefing transcript/audio metadata) when only a few columns are needed.
> 4. **Sync-in-async blocking**: CPU- or IO-bound calls made directly in `async def` without `asyncio.to_thread` / a thread pool — ffmpeg/ffprobe subprocess calls, file reads/writes, the OpenRouter and TTS SDK calls. Note any already correctly wrapped.
> 5. **TTS pipeline** (`services/tts/*`, `utils/audio.py`): confirm the recent gemini chunking + concurrency changes are sound (don't re-design them). Look for temp-file churn, redundant WAV→MP3 conversions, loading whole audio files into memory unnecessarily, missing cleanup of temp files on error paths.
> 6. **Background task lifecycle**: what happens to an in-flight briefing when uvicorn reloads (`WatchFiles detected changes ... Waiting for background tasks to complete`) or shuts down? Is state left inconsistent (briefing stuck "generating")?
>
> Also list what you inspected and found healthy. Return your answer in EXACTLY this format: [paste the "Conventions for all research tasks" block above, with area name "Backend performance & async" and area letter `B`].

- [ ] **Step 2: Verify the agent output meets the done bar**

Check: every finding has `file:line` evidence; "Healthy" section non-empty; format matches. If not, send the agent a follow-up via SendMessage asking it to fix the specific gap. Do not proceed until it passes.

- [ ] **Step 3: Save the raw output**

Keep the agent's report in the orchestrator's working notes (you'll paste all four into Task 5). No commit yet.

---

### Task 2: LLM agent pipeline research

**Files:**
- Create: none
- Inspect: `backend/app/services/llm/agents/orchestrator.py`, `facts_gatherer.py`, `story_analyzer.py`, `briefing_writer.py`, `site_generator.py`, `topic_generator.py`, `backend/app/services/llm/openrouter.py`, `backend/app/services/llm/base.py`, `backend/app/services/llm/personalities/*.py`, `backend/app/config.py` (model + token settings)

- [ ] **Step 1: Dispatch the LLM pipeline research agent**

Use the Agent tool, `subagent_type: Explore`, `description: "Audit LLM agent pipeline"`. Prompt:

> You are auditing the `augustus` backend's **LLM agent pipeline** for cost and latency. Read-only. Code under `backend/app/services/llm/`.
>
> Investigate, with evidence (`file:line`):
> 1. **Call graph**: trace which agents call the LLM and in what order during a briefing (`orchestrator.py` → `facts_gatherer.py` → `story_analyzer.py` → `briefing_writer.py`, plus `site_generator.py`, `topic_generator.py`). Build the sequence of LLM calls. Which are strictly serial but independent (could be `asyncio.gather`-ed)? Are any calls made per-story in a loop that could be batched into one call?
> 2. **Prompt size / token waste**: how big are the system prompts (`personalities/*.py`, agent prompt templates)? Is full article body text passed when a summary would do? Is the same context (e.g. the full topic list, prior briefing) re-sent to multiple agents? Is `writer_max_tokens=32768` (config) appropriate, or does it inflate cost on non-reasoning models?
> 3. **OpenRouter client** (`openrouter.py`): retry policy, timeouts, streaming vs non-streaming, how errors/truncation (`finish_reason=length`) are handled, whether `openrouter_model` vs `openrouter_writer_model` split is used effectively, any per-call overhead (re-creating the client, re-fetching model lists).
> 4. **Caching**: are facts/articles fetched per briefing re-used across briefings on the same topic within a window? Could prompt prefixes (stable system prompt + tools) benefit from provider-side prompt caching? Is there any local memoization?
> 5. **Failure cost**: when a late-stage agent fails and the pipeline retries, does it redo earlier successful (paid) LLM calls?
>
> Also list what you inspected and found healthy. Return your answer in EXACTLY this format: [paste the "Conventions" block, area name "LLM agent pipeline", area letter `L`].

- [ ] **Step 2: Verify the agent output meets the done bar**

Same checks as Task 1 Step 2.

- [ ] **Step 3: Save the raw output**

Keep in working notes.

---

### Task 3: Frontend research

**Files:**
- Create: none
- Inspect: `frontend/vite.config.*`, `frontend/package.json`, `frontend/src/App.tsx`, `frontend/src/api/client.ts`, `frontend/src/components/Layout.tsx`, `frontend/src/pages/BriefingDetail.tsx`, `frontend/src/pages/Settings.tsx`, `frontend/src/pages/Topics.tsx`, and any React Query / state setup files

- [ ] **Step 1: Dispatch the frontend research agent**

Use the Agent tool, `subagent_type: Explore`, `description: "Audit frontend perf"`. Prompt:

> You are auditing the `augustus` **React + Vite + TypeScript frontend** for performance. Read-only. Code under `frontend/src/`.
>
> Investigate, with evidence (`file:line`):
> 1. **Bundle / build**: `vite.config.*` and `package.json` — is there route-level code splitting (`React.lazy` / dynamic import) or is everything in one chunk? Any heavyweight dependencies (charting, markdown, audio libs, moment, lodash) that could be trimmed or lazy-loaded? Source maps in prod?
> 2. **Data fetching** (`api/client.ts` and callers): is React Query (or similar) used? Polling intervals — the backend logs show `GET /api/briefings?limit=10&offset=0` firing ~20× in a burst; find what drives that (a `refetchInterval`, a `useEffect` with a bad dep array, multiple mounted components each polling). Stale-time / cache config. Are list responses over-fetched (full transcripts) when only metadata is shown?
> 3. **Render hotspots**: `BriefingDetail.tsx` (audio player + transcript auto-scroll/follow), `Settings.tsx`, `Topics.tsx`, `Layout.tsx` — unmemoized derived values recomputed each render, `useEffect`s that run on every render, large lists rendered without virtualization, props that change identity each render causing child re-renders. Note prior bugs around switching briefings / wrong audio playing — confirm the current code doesn't re-decode or re-fetch audio unnecessarily.
> 4. **Audio player specifically**: how is the `<audio>` element / source managed across briefing switches? Any leak (old element not cleaned up, multiple players)? Auto-scroll transcript: does it run a layout read/write on every `timeupdate` (fires ~4×/s)?
>
> Also list what you inspected and found healthy. Return your answer in EXACTLY this format: [paste the "Conventions" block, area name "Frontend", area letter `F`].

- [ ] **Step 2: Verify the agent output meets the done bar**

Same checks as Task 1 Step 2.

- [ ] **Step 3: Save the raw output**

Keep in working notes.

---

### Task 4: Infrastructure & data research

**Files:**
- Create: none
- Inspect: `backend/app/database.py`, `backend/app/migrations/*.py`, `backend/app/config.py`, `docker/`, `docker-compose*.yml` (wherever they live), `dev.bat`, `dev.ps1`, `backend/requirements.txt`, audio/file storage settings

- [ ] **Step 1: Dispatch the infra research agent**

Use the Agent tool, `subagent_type: Explore`, `description: "Audit infra & data"`. Prompt:

> You are auditing the `augustus` app's **infrastructure and data layer**. Read-only.
>
> Investigate, with evidence (`file:line`):
> 1. **SQLite vs Postgres**: the app does background briefing generation, has APScheduler jobs polling every 5–10s, and serves an API concurrently. Find concrete SQLite pain points for *this* workload — `database is locked` risk under concurrent writes, single-writer limitation vs the queue worker, WAL mode on or off (`database.py` connect args), whether long transactions block the scheduler. Don't give a generic "use Postgres" — cite the specific code that would hurt.
> 2. **Migrations**: `backend/app/migrations/*.py` are hand-written one-off scripts. How are they invoked (on startup? manually?)? Are they idempotent / ordered / tracked (is there a `schema_version` table)? What breaks if two run out of order or one half-fails? Would Alembic be warranted?
> 3. **Docker** (`docker/`): image size (base image, do they install build tools / ffmpeg / piper models into the final image?), layer ordering for cache hits (requirements copied before source?), dev vs prod parity, whether the DB and audio files are on a volume or baked into the image.
> 4. **File / audio storage**: where do generated briefing `.mp3` files live relative to the DB? Is there any cleanup of old briefings' audio, or does it grow unbounded? Temp files (`tempfile.NamedTemporaryFile(...)` in the TTS code) — are they reliably removed on error paths? Are large audio files ever read fully into memory?
> 5. **Background-task lifecycle**: on uvicorn `--reload` (WatchFiles) or SIGTERM, are in-flight briefings cancelled cleanly, finished, or orphaned (left `status=generating` forever)? Is there a startup reconciliation that re-queues or fails orphaned briefings?
>
> Also list what you inspected and found healthy. Return your answer in EXACTLY this format: [paste the "Conventions" block, area name "Infrastructure & data", area letter `I`].

- [ ] **Step 2: Verify the agent output meets the done bar**

Same checks as Task 1 Step 2.

- [ ] **Step 3: Save the raw output**

Keep in working notes.

> **Note on parallelism:** Tasks 1–4 are independent and read-only. Dispatch all four agents in a single message (multiple Agent tool calls) so they run concurrently, then do the Step-2 verification for each as they return. If executing inline, this is one batch.

---

### Task 5: Synthesize the report

**Files:**
- Create: `docs/optimization-audit-2026-05.md`

- [ ] **Step 1: Merge findings and assign global ranking**

Collect all findings from Tasks 1–4 (already in `F-<letter><n>` form). Compute a rank key = severity weight × effort weight where High=3/Med=2/Low=1 and S=3/M=2/L=1 (so a High-severity/S-effort finding ranks highest). Sort descending; break ties by severity then by area order B, L, F, I.

- [ ] **Step 2: Write `docs/optimization-audit-2026-05.md`**

Use this exact skeleton, filled in from the merged findings — no placeholders, every finding fully written out:

```markdown
# Optimization Audit — augustus (May 2026)

> Scope: backend perf/async, LLM agent pipeline, frontend, infra/data.
> Method: static code review (read-only). Claims needing runtime measurement are flagged.
> Source spec: docs/superpowers/specs/2026-05-11-optimization-audit-design.md
> No code was changed by this audit.

## Executive summary

<5–10 bullets, highest-ranked findings, each: `**F-XN** (Severity, Effort) — one line`>

## Findings table

| ID | Area | Severity | Effort | Summary |
|----|------|----------|--------|---------|
| F-B1 | Backend | High | S | ... |
| ... | | | | |

## Detailed findings

### F-B1: <title>
- **Severity:** ...
- **Effort:** ...
- **Symptom:** ...
- **Evidence:** ...
- **Why it matters:** ...
- **Recommended fix:** ...
- **Risks / caveats:** ...

<...repeat for every finding, in ranked order...>

## Inspected and healthy

### Backend performance & async
- ...
### LLM agent pipeline
- ...
### Frontend
- ...
### Infrastructure & data
- ...

## Suggested next cycles

- Implement <the top N quick wins> — own spec → plan.
- (Separately scoped, per project plan: documentation build-out; test suite build-out.)
```

- [ ] **Step 2b: Sanity-check the written report**

Open `docs/optimization-audit-2026-05.md` and verify: every row in the findings table has a matching `### F-XN` detail section and vice versa; every detail section has a non-empty Evidence line; the "Inspected and healthy" section has bullets for all four areas; no "TBD"/"TODO"/"..." left in the prose (the `...` in the skeleton above are fill-ins, not literal). Fix anything in place.

- [ ] **Step 3: Commit**

```bash
git add docs/optimization-audit-2026-05.md
git commit -m "Add May 2026 optimization audit report

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Present to the user

**Files:** none

- [ ] **Step 1: Summarize**

Post a short summary in chat: the top 5 findings (ID, severity, one line each), the total count by area, and the path to the full report. Ask whether they want to (a) proceed to implement selected findings, (b) move on to the documentation cycle, or (c) the test-suite cycle. Do not start any of those without a new go-ahead.

---

## Self-Review (completed by plan author)

**Spec coverage:**
- Spec §"Scope — areas covered" 1 (Backend perf & async) → Task 1. ✓
- Spec §Scope 2 (LLM agent pipeline) → Task 2. ✓
- Spec §Scope 3 (Frontend) → Task 3. ✓
- Spec §Scope 4 (Infra & data) → Task 4. ✓
- Spec §"Report structure" (exec summary, findings table, detailed findings, appendix of healthy) → Task 5 Step 2 skeleton. ✓
- Spec §"Method" (parallel agents, "needs measurement" flag) → Conventions block + Task 1–4 prompts + report header. ✓
- Spec §Deliverable (single committed MD file, no code changes) → Task 5 Step 2/3; no task modifies source. ✓
- Spec §"Out of scope" (no security review, no re-design of TTS changes) → stated in Task 1 prompt and report header. ✓
- Spec §"Success criteria" (actionable, evidence-cited, all 4 areas covered, self-contained) → enforced by the "done bar" in Conventions and Task 5 Step 2b. ✓

**Placeholder scan:** The `...` and `<...>` in the Task 5 skeleton are explicitly labeled as fill-ins, and Step 2b requires removing them. No "TBD"/"implement later" in actual plan steps. ✓

**Type/name consistency:** Finding ID scheme `F-<area-letter><n>` with letters B/L/F/I is defined once in Conventions and used identically in Tasks 1–5. The rank-key weighting is defined once in Task 5 Step 1. ✓
