# Per-Host Research (Source Diversity) — Design

**Date:** 2026-05-28
**Status:** Approved (design); pending implementation plan

## Goal

Replace the single, persona-agnostic fact-gathering pass with **one persona-driven research pass per host**, so each host independently finds sources and facts that match how they think about a problem. The result is a briefing grounded in genuinely divergent sources — and a UI that shows which sources came from which host.

## Motivation

Today the pipeline runs:

1. `story_analyzer` (the "editor") ranks/filters articles → selected stories.
2. `facts_gatherer` does **one** pass: fetches article content, does web search, and generates Q&A facts. Persona-agnostic — both hosts draw from the same pool.
3. `briefing_writer` writes a multi-host script and *simulates* differing perspectives.

The conversational friction is already simulated, but both hosts argue from identical facts, so their "disagreement" is one model reinterpreting one body of research. The missing ingredient is **information asymmetry + source diversity**: an analytical host pulling data/methodology/primary sources, a skeptic pulling counterevidence/dissent — each bringing material the other didn't see.

## Scope

**In scope:**
- A `HostResearchAgent` that researches the editor's selected stories through a single host's persona lens.
- Orchestrator fan-out: one research pass per host, run concurrently.
- `briefing_writer` consuming per-host research with attribution (asymmetric conversation).
- Per-source host attribution (`found_by`) stored on the briefing and surfaced in the UI grouped by host.
- Config flag + cost guards; graceful fallback to today's single pass.

**Out of scope (v1):**
- Hosts surfacing *new* stories beyond the editor's selection (editor stays the gatekeeper).
- New personality data fields — research angle is derived from existing persona text.
- Any change to `story_analyzer` ranking logic.

## Design Decisions (resolved during brainstorming)

| Decision | Choice |
|---|---|
| Passes per cast size | One pass per host (1 host = 1 pass ≈ today, 2 = 2, 3 = 3), run concurrently |
| Research angle source | Derived from each host's existing persona description/guidelines (no new fields); non-research personas fall back to a neutral lens |
| Story set | Hosts research only the editor's selected stories; they diverge on *sources and framing*, not *which* stories |
| Default | `HOST_RESEARCH_ENABLED` defaults **on**; disabling falls back to the existing single `facts_gatherer` pass |
| Source attribution | Flat deduped source list; each source carries `found_by: [host_name, …]` (shared sources list multiple hosts) |
| UI | Briefing detail shows sources grouped by host, alongside the existing per-chapter source links |

## Architecture

```
story_analyzer (editor) → ranked stories
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                       ▼
 HostResearchAgent      HostResearchAgent       HostResearchAgent     ← asyncio.gather (concurrent)
   (host A persona)       (host B persona)        (host C persona)
        │                      │                       │
        └──────────────────────┼──────────────────────┘
                               ▼
                  combine + dedupe sources (found_by)
                               │
                               ▼
                       briefing_writer  → attributed, asymmetric script
```

When `HOST_RESEARCH_ENABLED` is off, the orchestrator uses the existing `facts_gatherer` single pass and the writer's existing `additional_facts` path — unchanged behavior.

## Components

### `HostResearchAgent` (new) — `backend/app/services/llm/agents/host_research.py`
**Responsibility:** research the editor's selected stories through one host's persona lens.

**Interface:**
```python
async def research(
    self,
    stories: list[dict],
    host_name: str,
    personality_name: str,
    briefing_id: Optional[str] = None,
) -> HostResearch
```

**Behavior, per host:**
1. **Derive research angle.** Turn the host's persona (`get_personality(personality_name).get_description()` + `get_behavioral_guidelines()`) into a short "research lens" string (analytical → data/methodology/primary sources; skeptic → counterevidence/dissent/unproven claims; neutral default for non-research personas). Derived via the LLM as part of step 2's prompt (no separate round-trip required).
2. **Query + retrieve.** For each story, generate persona-biased search queries and pull sources via the existing `SearchService` (reusing `facts_gatherer`'s `_fetch_article_content` / `search` logic). Cap sources per story via config.
3. **Generate facts.** Produce persona-flavored Q&A grounded in *that host's* retrieved sources, using structured output (`response_format`, gated by the existing `llm_structured_outputs` flag) with the same parse-fallback safety net as `facts_gatherer`.
4. **Return** a `HostResearch`.

**Data shape:**
```python
@dataclass
class HostResearch:
    host_name: str
    personality_name: str
    angle: str                                  # the derived research lens
    facts_by_story_index: dict[int, list[str]]  # story idx → formatted Q&A strings
    sources: list[dict]                          # each tagged found_by=[host_name]
```

`HostResearchAgent` reuses `facts_gatherer`'s content-fetch/search helpers (extract shared helpers if cleaner; `facts_gatherer` stays as the fallback path).

### Orchestrator — `backend/app/services/llm/agents/orchestrator.py`
- New method `gather_host_research(stories, cast_members, briefing_id)` that fans out one `HostResearchAgent.research(...)` per cast member via `asyncio.gather`, then combines sources (dedupe by URL, union of `found_by`). Returns `list[HostResearch]` + the merged source list.
- `write_briefing_script` gains a `host_research: Optional[list[HostResearch]]` param forwarded to the writer.

### `briefing_writer` — `backend/app/services/llm/agents/briefing_writer.py`
- `write_briefing` accepts `host_research: Optional[list[HostResearch]]`.
- When present, `_build_user_prompt` renders a per-host research section ("Alex (Analytical) came in with: …; Sam (Skeptic) found: …") so each host speaks from their own findings.
- When absent (flag off), the existing `additional_facts` path is used unchanged.

### `briefing.py` orchestration — `backend/app/services/briefing.py`
- When `HOST_RESEARCH_ENABLED`: call `orchestrator.gather_host_research(...)`, pass `host_research` into `write_briefing_script`, and store the merged sources (with `found_by`) on `briefing.sources`.
- Else: existing `facts_gatherer` path, unchanged.
- The existing `web_research` gap-fill remains available for the fallback path; per-host research subsumes it when enabled.

### Source attribution + frontend
- **`merge_sources`** (or a host-aware combiner) produces a flat deduped list where each source dict has `found_by: [host_name, …]`.
- **`briefing.sources`** stores these; the existing per-chapter `chapter_sources` mapping (by title) is unaffected and inherits `found_by`.
- **API:** `found_by` rides along in the existing sources payload (extend the TS `Source`/client type with `found_by?: string[]`). No new endpoint.
- **UI ([BriefingDetail.tsx](../../../frontend/src/pages/BriefingDetail.tsx)):** add a "Sources by host" view — sources grouped under each host (e.g. "Alex (Analytical) · 5 sources", "Sam (Skeptic) · 4 sources"); a source surfaced by multiple hosts appears under each (or carries a "both" badge). Sits alongside the existing per-chapter links.

## Configuration

- `HOST_RESEARCH_ENABLED: bool = True` — master toggle; off → existing single-pass behavior.
- `HOST_RESEARCH_MAX_SOURCES_PER_STORY: int` — per-host source cap (reuse/align with existing `WEB_RESEARCH_*` limits).
- Reuse existing `WEB_RESEARCH_*` and `llm_structured_outputs` settings.

Document all new flags in `.env.example`.

## Data Flow

1. Editor selects stories (unchanged).
2. Orchestrator fans out `HostResearchAgent.research` per host (concurrent).
3. Each agent: derive angle → persona queries → retrieve sources → persona Q&A facts.
4. Orchestrator merges sources (dedupe + `found_by`), returns `list[HostResearch]`.
5. Writer builds an attributed user prompt → asymmetric script.
6. `briefing.sources` stored with `found_by`; frontend groups sources by host.

## Error Handling

- **One host's research fails:** log and continue — that host contributes empty facts and no sources; the briefing still generates (no whole-pipeline failure).
- **All research fails / search unavailable:** fall back to the editor's original article content (as today).
- **Cancellation:** thread `briefing_id` through `asyncio.gather` tasks (existing `cancellable_await`).
- **Structured-output parse failure:** existing tolerant parse fallback applies per host.

## Testing

All with a fake LLM + fake `SearchService` (no network):
- Persona-angle derivation yields distinct lenses for analytical vs skeptic vs a neutral persona.
- Orchestrator fans out exactly one pass per cast member (1/2/3 hosts) and runs them concurrently.
- Per-host facts stay tagged/separate; nothing bleeds between hosts.
- Source combine: dedupe by URL; `found_by` is the union of hosts that surfaced a shared source.
- Writer receives attributed `host_research` and the rendered prompt contains each host's section.
- Config flag: off → `facts_gatherer` single pass + existing `additional_facts` path (no regression).
- Frontend: sources group correctly by host; a shared source shows under both.

## Out-of-Scope / Future

- Per-host *story* selection (hosts proposing their own stories).
- Explicit `research_angle` fields on personalities (if derived angles prove too weak).
- Cross-host "rebuttal" round before writing.
