# Listener-aware Story Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver new developments relative to a profile’s listening history, with inspectable evidence.

**Architecture:** Add profile-scoped story/development records and independent listening intervals. Extend the existing editor and chapter contracts, then persist completed coverage and display evidence/preferences in show notes.

**Tech Stack:** FastAPI, SQLAlchemy async SQLite, React/TypeScript, Vitest, pytest.

**Spec:** docs/superpowers/specs/2026-09-04-story-memory-design.md

## Global Constraints
- No new dependencies.
- Preserve existing untracked backend/scripts and dev.sh.
- Work on feature/story-memory in this checkout; do not publish or push.
- No paid generation or changes to the live database during automated tests.
- Profile-scoped memory; historical listened flags never imply chapter coverage.

### Task 1: Listening coverage
**Files:** Create backend/app/models/listening.py, backend/app/services/listening.py, backend/tests/test_listening.py, frontend/src/utils/listeningCoverage.ts and its test. Modify backend/app/database.py (register model), backend/app/routers/briefings.py, backend/app/schemas/briefing.py, frontend/src/api/client.ts, frontend/src/components/AudioPlayer.tsx.
**Interfaces:** POST /api/briefings/{id}/listening accepts {ranges: [[start, end], ...]} and returns {ranges, chapter_coverage: {"0": 0.8}, episode_coverage: 0.8}. ListeningService(db).record(briefing, ranges) merges without committing outside its transaction; ListeningService(db).coverage(briefing) returns the same payload. Persistent row keyed by briefing_id. Memory reads coverage only, never listened.
- [x] Write tests proving seeking does not count, repeated intervals are idempotent, partial listening marks only covered chapters, ownership blocks another profile, malformed ranges fail, and empty/legacy records stay unknown. Example: record [[0, 40], [20, 60]] against chapters [0,50] and [50,100] yields chapter coverage {"0": 1.0, "1": 0.2}.
- [x] Run DEBUG=false venv/bin/python -m pytest tests/test_listening.py -q and npm test -- src/utils/listeningCoverage.test.ts; confirm new behavior fails first.
- [x] Implement interval union, playback sampling with wall-clock/rate checks and seek/pause reset, periodic reliable flushing, new endpoint, and 80% completion instead of five-second completion. Scope queued uploads to their original profile.
- [x] Run targeted tests and frontend build; inspect the diff.

### Task 2: Story memory and editorial integration
**Files:** Create backend/app/models/story.py, backend/app/services/story_memory.py, backend/tests/test_story_memory.py, backend/tests/test_story_memory_pipeline.py. Modify backend/app/database.py, backend/app/services/briefing.py, backend/app/services/news.py, backend/app/services/llm/agents/story_analyzer.py, orchestrator.py, briefing_writer.py.
**Interfaces:** StoryMemoryService(db).context(user_id, profile_id) -> list[dict]; .save(briefing, items, chapters, claims) -> dict[str, dict] (chapter_stories), .set_preference(user_id, profile_id, story_id, preference). Editor receives story_memory and emits article_num, priority, reason, story_key, development, change_type. NewsItem carries those optional editorial fields. New chapter format: [CHAPTER: 1 | Human title]. Chapter rows store article_index (zero based).
- [x] Write tests using two profiles and different topic combinations: heard rehash excluded, unheard rehash eligible, new update preserved, duplicate story keys collapse, invalid IDs fail safely, failed episodes excluded. Example: profile A hears chapter 0 of “Launch scheduled”; “Launch delayed” references the same story and remains selectable, while profile B receives no A history.
- [x] Run targeted pytest and observe missing behavior.
- [x] Implement scoped tables/context, ranking validation, numbered chapters, successful persistence, empty-day completion, and proportionate duration. Remove URL-history suppression from the generation path while preserving within-batch dedup.
- [x] Run focused pipeline tests with real orchestration and fake I/O, then the existing backend suite.

### Task 3: Claim evidence and visible story controls
**Files:** Create backend/app/services/evidence.py, backend/tests/test_evidence.py, frontend/src/components/StoryDevelopments.tsx. Modify host_research.py, briefing_writer.py, briefing.py, backend/app/routers/briefings.py, backend/app/schemas/briefing.py, frontend/src/api/client.ts, frontend/src/pages/BriefingDetail.tsx.
**Interfaces:** Stored claims are {text, sources: [{url, title, excerpt}], attribution: supported|unverified, found_by: [...]}; preserve only URLs from retrieved sources and excerpts present in retrieved text. POST/PATCH story preference uses exact profile ownership. chapter_stories contains story_id, title, development, change_type, preference, claims. Frontend component may own its API types to avoid unrelated client churn.
- [x] Write failing tests for fabricated citations, mismatched quotes, provider legacy facts, and unsupported claim handling. Example: claim cites https://invented.test while retrieval contains only https://source.test -> no supported evidence.
- [x] Implement evidence parsing and writer instructions; store claim evidence with developments; show notes expose sources and preferences with loading/error feedback.
- [x] Run claim, preference, and writer tests; build frontend.

### Task 4: Review and verify the release
- [x] Run DEBUG=false venv/bin/python -m pytest -q, npm test, npm run build, and git diff --check.
- [x] Review full changed code for profile leaks, listening overcounts, citation mistakes, persistence on failed runs, migration registration, and legacy compatibility.
- [x] Fix verified findings, rerun affected tests, document behavior and limitations in README, and report exact validation outcomes.

## Execution decisions
- User approved the substantive design; proceed through implementation without another approval gate.
- Use this checkout on a new feature branch so the user sees the result; leave unrelated untracked files untouched.
- Baseline frontend: 7 passing. Backend: 81 passing with DEBUG=false (environment DEBUG=release is not a valid boolean); two existing Pydantic deprecation warnings.

## Final verification

- Backend: `DEBUG=false venv/bin/python -m pytest -q --tb=short` — 114 passed; two existing Pydantic deprecation warnings.
- Frontend: `npm test` — 15 passed; `npm run build` — passed with the existing large-bundle advisory.
- `git diff --check` — passed.
- Independent review found two P2 issues (upload queue blocking on permanent failures; ambiguous chapter boundaries). Both were reproduced, fixed, regression-tested, and accepted on scoped re-review.
- New story preferences use `backend/app/routers/stories.py` and `frontend/src/api/storyMemory.ts` to keep ownership clear. No new dependencies.
- Work remains uncommitted on `feature/story-memory`; no push, deployment, live database write, or paid provider generation was performed.
