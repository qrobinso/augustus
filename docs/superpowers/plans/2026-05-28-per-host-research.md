# Per-Host Research (Source Diversity) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run one persona-driven research pass per host (own queries → own sources → own facts), compose an attributed/asymmetric briefing, and show sources grouped by which host found them.

**Architecture:** A new `HostResearchAgent` researches the editor's selected stories through a single host's persona lens (LLM-generated persona-biased queries → `SearchService` retrieval → persona-flavored Q&A). The orchestrator fans these out concurrently per cast member, combines sources with `found_by` attribution, and feeds per-host research to `briefing_writer`. Gated by `HOST_RESEARCH_ENABLED` (default on); off falls back to today's single `facts_gatherer` pass.

**Tech Stack:** Python 3.11, FastAPI, httpx, pytest + pytest-asyncio (network-free via `FakeLLM`/`FakeSearch`); React/TypeScript frontend.

**Spec:** `docs/superpowers/specs/2026-05-28-per-host-research-design.md`

**Run backend tests:** from `backend/`: `venv/bin/pytest tests/ -v` (system python3 is 3.9 — too old; the venv is 3.11).

---

## File Structure

- `backend/app/config.py` — new flags (Task 1).
- `backend/tests/conftest.py` — extend `FakeLLM` (sequential responses) + add `FakeSearch` (Task 1).
- `backend/app/services/llm/agents/host_research.py` — **new**: `HostResearch` dataclass + `persona_angle()` + `HostResearchAgent` (Tasks 2–4).
- `backend/app/services/web_research.py` — `combine_host_sources()` host-aware merge (Task 5).
- `backend/app/services/llm/agents/orchestrator.py` — `gather_host_research()` + `write_briefing_script(host_research=...)` (Task 6).
- `backend/app/services/llm/agents/briefing_writer.py` — `write_briefing(host_research=...)` + prompt rendering (Task 7).
- `backend/app/services/briefing.py` — wire enabled path; store `found_by` sources (Task 8).
- `frontend/src/api/client.ts` + `frontend/src/pages/BriefingDetail.tsx` — `found_by` type + "sources by host" UI (Task 9).
- `.env.example` — document flags (Task 1).

---

### Task 1: Config flags + test fakes

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/tests/conftest.py`
- Modify: `.env.example`
- Test: `backend/tests/test_host_research_fakes.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_host_research_fakes.py`:

```python
import pytest
from app.services.search import SearchResult
from tests.conftest import FakeLLM, FakeSearch


@pytest.mark.asyncio
async def test_fakellm_returns_responses_in_sequence():
    fake = FakeLLM(response_content=["first", "second"])
    r1 = await fake.generate(prompt="a")
    r2 = await fake.generate(prompt="b")
    r3 = await fake.generate(prompt="c")  # exhausted -> repeats last
    assert (r1.content, r2.content, r3.content) == ("first", "second", "second")


@pytest.mark.asyncio
async def test_fakesearch_records_queries_and_returns_results():
    fake = FakeSearch(results=[SearchResult("T", "http://x.com", "s")])
    res = await fake.search("query one", num_results=3)
    content = await fake.fetch_page_content("http://x.com")
    assert fake.queries == ["query one"]
    assert res[0].url == "http://x.com"
    assert len(content) > 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_host_research_fakes.py -v`
Expected: FAIL (`FakeLLM` doesn't accept a list; `FakeSearch` undefined)

- [ ] **Step 3: Extend `FakeLLM` and add `FakeSearch` in conftest**

In `backend/tests/conftest.py`, replace the existing `FakeLLM` class body's `__init__` and add list handling, then add `FakeSearch`. The full updated `FakeLLM` plus new `FakeSearch`:

```python
class FakeLLM(LLMProvider):
    """Recording fake provider. Captures call kwargs; returns canned content.

    response_content may be a single string (repeated) or a list of strings
    returned in sequence (last entry repeats once exhausted).
    """

    def __init__(self, response_content="{}"):
        self._responses = [response_content] if isinstance(response_content, str) else list(response_content)
        self.calls: list[dict] = []

    def _next(self) -> str:
        if not self._responses:
            return ""
        if len(self._responses) == 1:
            return self._responses[0]
        return self._responses.pop(0)

    async def generate(self, prompt, system_prompt=None, max_tokens=4096,
                       temperature=0.7, response_format=None, briefing_id=None):
        self.calls.append({
            "prompt": prompt, "system_prompt": system_prompt,
            "max_tokens": max_tokens, "temperature": temperature,
            "response_format": response_format,
        })
        return LLMResponse(content=self._next(), model="fake", usage={})

    async def generate_conversation(self, messages, max_tokens=4096,
                                   temperature=0.7, response_format=None, briefing_id=None):
        self.calls.append({
            "messages": messages, "max_tokens": max_tokens,
            "temperature": temperature, "response_format": response_format,
        })
        return LLMResponse(content=self._next(), model="fake", usage={})

    async def close(self):
        pass


class FakeSearch:
    """Fake SearchService: records queries, returns canned results/content."""

    def __init__(self, results=None, page_content=None):
        from app.services.search import SearchResult
        self._results = results if results is not None else [
            SearchResult("Result A", "http://a.example", "snippet a"),
            SearchResult("Result B", "http://b.example", "snippet b"),
        ]
        self._page_content = page_content or ("fetched article content about the topic. " * 20)
        self.queries: list[str] = []

    async def search(self, query, num_results=3):
        self.queries.append(query)
        return self._results[:num_results]

    async def fetch_page_content(self, url):
        return self._page_content
```

- [ ] **Step 4: Add config flags**

In `backend/app/config.py`, near `llm_structured_outputs` / `llm_prompt_cache`, add:

```python
    host_research_enabled: bool = True
    host_research_max_sources_per_story: int = 3
    host_research_queries_per_story: int = 2
```

- [ ] **Step 5: Document flags in .env.example**

In `.env.example`, after the `LLM_PROMPT_CACHE` block, add:

```
# Optional: per-host research — each host independently researches the editor's
# selected stories through their persona's lens (default: true). When false, a
# single shared fact-gathering pass is used.
HOST_RESEARCH_ENABLED=true

# Optional: max web sources each host pulls per story (default: 3).
HOST_RESEARCH_MAX_SOURCES_PER_STORY=3

# Optional: persona-biased search queries generated per story, per host (default: 2).
HOST_RESEARCH_QUERIES_PER_STORY=2
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && venv/bin/pytest tests/test_host_research_fakes.py -v`
Expected: PASS (2 passed). Then `venv/bin/pytest tests/ -v` — full suite still green.

- [ ] **Step 7: Commit**

```bash
git add backend/app/config.py backend/tests/conftest.py backend/tests/test_host_research_fakes.py .env.example
git commit -m "feat: add per-host research config flags and test fakes"
```

---

### Task 2: `HostResearch` dataclass + `persona_angle` + query generation

**Files:**
- Create: `backend/app/services/llm/agents/host_research.py`
- Test: `backend/tests/test_host_research_queries.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_host_research_queries.py`:

```python
import json
import pytest
from tests.conftest import FakeLLM, FakeSearch
from app.services.llm.agents.host_research import HostResearchAgent, persona_angle

STORIES = [{"title": "AI chip launch", "summary": "new accelerator", "url": "http://news/1"}]


def test_persona_angle_is_persona_specific():
    analytical = persona_angle("Analytical")
    skeptic = persona_angle("Skeptic")
    assert analytical != skeptic
    assert "Analytical" in analytical


@pytest.mark.asyncio
async def test_generate_queries_returns_persona_queries_per_story():
    resp = json.dumps({"articles": [{"article_num": 1, "queries": ["benchmark data", "methodology"]}]})
    fake = FakeLLM(response_content=resp)
    agent = HostResearchAgent(fake, search_service=FakeSearch())
    queries = await agent._generate_queries(STORIES, "Alex", "Analytical")
    assert queries[0] == ["benchmark data", "methodology"]
    # Persona name reached the model.
    assert "Analytical" in fake.calls[0]["system_prompt"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_host_research_queries.py -v`
Expected: FAIL (module `host_research` does not exist)

- [ ] **Step 3: Create the module with the dataclass, angle helper, and query generation**

Create `backend/app/services/llm/agents/host_research.py`:

```python
"""Host Research Agent - persona-driven, per-host source research."""

import json
from dataclasses import dataclass, field
from typing import Optional

from app.config import get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.personalities import get_personality
from app.services.search import get_search_service


@dataclass
class HostResearch:
    """One host's research over the editor's selected stories."""

    host_name: str
    personality_name: str
    angle: str
    facts_by_story_index: dict[int, list[str]] = field(default_factory=dict)
    sources: list[dict] = field(default_factory=list)


def persona_angle(personality_name: str) -> str:
    """Short research-lens descriptor derived from the persona definition."""
    data = get_personality(personality_name).get_description()
    core = data.get("core_trait", "") or data.get("role", "")
    return f"{personality_name} — {core}".strip(" —")


QUERY_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "host_queries",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "articles": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "article_num": {"type": "integer"},
                            "queries": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["article_num", "queries"],
                    },
                }
            },
            "required": ["articles"],
        },
    },
}


class HostResearchAgent:
    """Researches the editor's selected stories through one host's persona lens."""

    def __init__(self, llm: LLMProvider, search_service=None):
        self.llm = llm
        self.search_service = search_service or get_search_service()

    def _query_system_prompt(self, host_name: str, personality_name: str) -> str:
        angle = persona_angle(personality_name)
        guidelines = get_personality(personality_name).get_behavioral_guidelines() or []
        guidelines_text = "\n".join(f"- {g}" for g in guidelines)
        return (
            f"You are {host_name}, a podcast host whose perspective is: {angle}.\n"
            f"{guidelines_text}\n\n"
            "For each news story, propose web search queries that would surface sources "
            "matching YOUR perspective and the way you think about problems — the angles, "
            "evidence, and viewpoints you would personally dig into. Return JSON only."
        )

    def _query_user_prompt(self, stories: list[dict], queries_per_story: int) -> str:
        lines = []
        for i, s in enumerate(stories, 1):
            lines.append(f"ARTICLE {i}: {s.get('title', 'Untitled')}\nSummary: {s.get('summary', '')[:200]}")
        return (
            f"Propose up to {queries_per_story} search queries per article, from your perspective.\n\n"
            + "\n\n".join(lines)
            + '\n\nOutput JSON: {"articles":[{"article_num":1,"queries":["..."]}]}'
        )

    async def _generate_queries(
        self, stories: list[dict], host_name: str, personality_name: str,
        briefing_id: Optional[str] = None,
    ) -> dict[int, list[str]]:
        settings = get_settings()
        response_format = QUERY_SCHEMA if settings.llm_structured_outputs else None
        response = await self.llm.generate(
            prompt=self._query_user_prompt(stories, settings.host_research_queries_per_story),
            system_prompt=self._query_system_prompt(host_name, personality_name),
            max_tokens=1024,
            temperature=0.5,
            response_format=response_format,
            briefing_id=briefing_id,
        )
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return {}
        result: dict[int, list[str]] = {}
        for article in data.get("articles", []):
            idx = article.get("article_num", 0) - 1
            queries = [q for q in article.get("queries", []) if q]
            if 0 <= idx < len(stories) and queries:
                result[idx] = queries
        return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/bin/pytest tests/test_host_research_queries.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/llm/agents/host_research.py backend/tests/test_host_research_queries.py
git commit -m "feat: host research agent - persona angle and query generation"
```

---

### Task 3: Source gathering (retrieval tagged with found_by)

**Files:**
- Modify: `backend/app/services/llm/agents/host_research.py`
- Test: `backend/tests/test_host_research_sources.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_host_research_sources.py`:

```python
import pytest
from app.services.search import SearchResult
from tests.conftest import FakeLLM, FakeSearch
from app.services.llm.agents.host_research import HostResearchAgent

STORIES = [{"title": "AI chip launch", "summary": "x", "url": "http://news/1"}]


@pytest.mark.asyncio
async def test_gather_sources_tags_found_by_and_returns_content():
    search = FakeSearch(results=[SearchResult("Deep Dive", "http://deep.example", "s")])
    agent = HostResearchAgent(FakeLLM(), search_service=search)
    queries_by_idx = {0: ["benchmark data"]}
    content_by_idx, sources = await agent._gather_sources(STORIES, queries_by_idx, "Alex")
    # Content fetched for the story.
    assert 0 in content_by_idx and len(content_by_idx[0]) > 0
    # Sources tagged with the host.
    assert sources
    assert all(src["found_by"] == ["Alex"] for src in sources)
    assert any(src["url"] == "http://deep.example" for src in sources)
    # The persona query was actually issued.
    assert "benchmark data" in search.queries
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_host_research_sources.py -v`
Expected: FAIL (`_gather_sources` undefined)

- [ ] **Step 3: Add `_gather_sources` to `HostResearchAgent`**

In `backend/app/services/llm/agents/host_research.py`, add this method to the class:

```python
    async def _gather_sources(
        self, stories: list[dict], queries_by_idx: dict[int, list[str]], host_name: str,
    ) -> tuple[dict[int, str], list[dict]]:
        """Run this host's queries, returning per-story content and found_by-tagged sources."""
        settings = get_settings()
        max_sources = settings.host_research_max_sources_per_story
        content_by_idx: dict[int, str] = {}
        sources: list[dict] = []
        seen_urls: set[str] = set()

        for idx, story in enumerate(stories):
            collected: list[str] = []

            # Always include the original article content as a baseline.
            url = story.get("url")
            if url:
                try:
                    page = await self.search_service.fetch_page_content(url)
                    if page and len(page) > 200:
                        collected.append(page)
                except Exception as e:
                    print(f"[HostResearch:{host_name}] fetch failed for {url}: {e}")

            # Persona-biased searches.
            for query in queries_by_idx.get(idx, []):
                try:
                    results = await self.search_service.search(query, num_results=max_sources)
                except Exception as e:
                    print(f"[HostResearch:{host_name}] search failed for '{query}': {e}")
                    continue
                for result in results:
                    if result.url in seen_urls:
                        continue
                    seen_urls.add(result.url)
                    sources.append({
                        "title": result.title,
                        "url": result.url,
                        "snippet": getattr(result, "snippet", ""),
                        "found_by": [host_name],
                        "story_index": idx,
                    })
                    if len([s for s in sources if s["story_index"] == idx]) > max_sources:
                        continue
                    try:
                        page = await self.search_service.fetch_page_content(result.url)
                        if page and len(page) > 200:
                            collected.append(f"[Source: {result.title}]\n{page}")
                    except Exception as e:
                        print(f"[HostResearch:{host_name}] fetch failed for {result.url}: {e}")

            if collected:
                content_by_idx[idx] = "\n\n".join(collected)

        return content_by_idx, sources
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/bin/pytest tests/test_host_research_sources.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/llm/agents/host_research.py backend/tests/test_host_research_sources.py
git commit -m "feat: host research source gathering with found_by tagging"
```

---

### Task 4: Facts generation + `research()` end-to-end

**Files:**
- Modify: `backend/app/services/llm/agents/host_research.py`
- Test: `backend/tests/test_host_research_agent.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_host_research_agent.py`:

```python
import json
import pytest
from app.services.search import SearchResult
from tests.conftest import FakeLLM, FakeSearch
from app.services.llm.agents.host_research import HostResearchAgent, HostResearch

STORIES = [{"title": "AI chip launch", "summary": "x", "url": "http://news/1"}]


@pytest.mark.asyncio
async def test_research_returns_populated_hostresearch():
    queries_resp = json.dumps({"articles": [{"article_num": 1, "queries": ["benchmark data"]}]})
    facts_resp = json.dumps({"articles": [{"article_num": 1, "title": "AI chip launch",
                             "questions_and_answers": [{"question": "How fast?", "answer": "2x faster per benchmarks."}]}]})
    fake = FakeLLM(response_content=[queries_resp, facts_resp])  # query call, then facts call
    search = FakeSearch(results=[SearchResult("Deep Dive", "http://deep.example", "s")])
    agent = HostResearchAgent(fake, search_service=search)

    research = await agent.research(STORIES, "Alex", "Analytical")
    assert isinstance(research, HostResearch)
    assert research.host_name == "Alex"
    assert "Analytical" in research.angle
    assert research.facts_by_story_index[0]  # has facts
    assert any(s["found_by"] == ["Alex"] for s in research.sources)


@pytest.mark.asyncio
async def test_research_survives_query_failure():
    # Non-JSON query response -> no queries; still returns HostResearch with baseline content/facts.
    facts_resp = json.dumps({"articles": [{"article_num": 1, "title": "AI chip launch",
                             "questions_and_answers": [{"question": "Q", "answer": "A grounded in the article."}]}]})
    fake = FakeLLM(response_content=["not json", facts_resp])
    agent = HostResearchAgent(fake, search_service=FakeSearch())
    research = await agent.research(STORIES, "Sam", "Skeptic")
    assert research.host_name == "Sam"
    assert research.facts_by_story_index[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_host_research_agent.py -v`
Expected: FAIL (`research` undefined)

- [ ] **Step 3: Add facts generation + `research` to `HostResearchAgent`**

In `backend/app/services/llm/agents/host_research.py`, add the facts schema at module level (below `QUERY_SCHEMA`):

```python
FACTS_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "host_facts",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "articles": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "article_num": {"type": "integer"},
                            "title": {"type": "string"},
                            "questions_and_answers": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "question": {"type": "string"},
                                        "answer": {"type": "string"},
                                    },
                                    "required": ["question", "answer"],
                                },
                            },
                        },
                        "required": ["article_num", "title", "questions_and_answers"],
                    },
                }
            },
            "required": ["articles"],
        },
    },
}
```

Then add these methods to the class:

```python
    def _facts_system_prompt(self, host_name: str, personality_name: str) -> str:
        angle = persona_angle(personality_name)
        return (
            f"You are {host_name}, a podcast host whose perspective is: {angle}.\n"
            "From the article content and additional sources you gathered, generate 3-5 "
            "questions and detailed, fact-grounded answers PER article, emphasizing the "
            "angles and evidence that fit your perspective. Prefer quantifiable data, "
            "specific evidence, and the implications you find most important. JSON only."
        )

    def _facts_user_prompt(self, stories: list[dict], content_by_idx: dict[int, str]) -> str:
        blocks = []
        for i, story in enumerate(stories, 1):
            content = content_by_idx.get(i - 1, story.get("summary", ""))
            blocks.append(f"ARTICLE {i}: {story.get('title', 'Untitled')}\nCONTENT:\n{content[:6000]}")
        return (
            "\n\n".join(blocks)
            + '\n\nOutput JSON: {"articles":[{"article_num":1,"title":"...",'
            '"questions_and_answers":[{"question":"...","answer":"..."}]}]}'
        )

    async def _generate_facts(
        self, stories: list[dict], content_by_idx: dict[int, str],
        host_name: str, personality_name: str, briefing_id: Optional[str] = None,
    ) -> dict[int, list[str]]:
        settings = get_settings()
        response_format = FACTS_SCHEMA if settings.llm_structured_outputs else None
        response = await self.llm.generate(
            prompt=self._facts_user_prompt(stories, content_by_idx),
            system_prompt=self._facts_system_prompt(host_name, personality_name),
            max_tokens=4096,
            temperature=0.5,
            response_format=response_format,
            briefing_id=briefing_id,
        )
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return {}
        facts: dict[int, list[str]] = {}
        for article in data.get("articles", []):
            idx = article.get("article_num", 0) - 1
            if not (0 <= idx < len(stories)):
                continue
            formatted = [
                f"Question: {qa.get('question','')}\nAnswer: {qa.get('answer','')}"
                for qa in article.get("questions_and_answers", [])
                if qa.get("question") and qa.get("answer")
            ]
            if formatted:
                facts[idx] = formatted
        return facts

    async def research(
        self, stories: list[dict], host_name: str, personality_name: str,
        briefing_id: Optional[str] = None,
    ) -> HostResearch:
        queries_by_idx = await self._generate_queries(stories, host_name, personality_name, briefing_id)
        content_by_idx, sources = await self._gather_sources(stories, queries_by_idx, host_name)
        facts = await self._generate_facts(stories, content_by_idx, host_name, personality_name, briefing_id)
        return HostResearch(
            host_name=host_name,
            personality_name=personality_name,
            angle=persona_angle(personality_name),
            facts_by_story_index=facts,
            sources=sources,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/bin/pytest tests/test_host_research_agent.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/llm/agents/host_research.py backend/tests/test_host_research_agent.py
git commit -m "feat: host research facts generation and end-to-end research()"
```

---

### Task 5: Host-aware source combine

**Files:**
- Modify: `backend/app/services/web_research.py`
- Test: `backend/tests/test_combine_host_sources.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_combine_host_sources.py`:

```python
from app.services.web_research import combine_host_sources


def test_combine_dedupes_by_url_and_unions_found_by():
    a = [{"title": "X", "url": "http://x.com", "found_by": ["Alex"]}]
    b = [
        {"title": "X dup", "url": "http://x.com", "found_by": ["Sam"]},
        {"title": "Y", "url": "http://y.com", "found_by": ["Sam"]},
    ]
    merged = combine_host_sources([a, b])
    by_url = {s["url"]: s for s in merged}
    assert sorted(by_url["http://x.com"]["found_by"]) == ["Alex", "Sam"]
    assert by_url["http://y.com"]["found_by"] == ["Sam"]
    assert len(merged) == 2


def test_combine_preserves_order_first_seen():
    a = [{"title": "A", "url": "http://a.com", "found_by": ["Alex"]}]
    b = [{"title": "B", "url": "http://b.com", "found_by": ["Sam"]}]
    merged = combine_host_sources([a, b])
    assert [s["url"] for s in merged] == ["http://a.com", "http://b.com"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_combine_host_sources.py -v`
Expected: FAIL (`combine_host_sources` undefined)

- [ ] **Step 3: Add `combine_host_sources` to web_research.py**

In `backend/app/services/web_research.py`, add:

```python
def combine_host_sources(source_lists: list[list[dict]]) -> list[dict]:
    """Flatten per-host source lists, dedupe by URL, union the found_by host names.

    Order follows first appearance across the lists.
    """
    by_url: dict[str, dict] = {}
    order: list[str] = []
    for sources in source_lists:
        for src in sources:
            url = src.get("url")
            if not url:
                continue
            if url not in by_url:
                merged = dict(src)
                merged["found_by"] = list(src.get("found_by", []))
                by_url[url] = merged
                order.append(url)
            else:
                existing = by_url[url]
                for host in src.get("found_by", []):
                    if host not in existing["found_by"]:
                        existing["found_by"].append(host)
    return [by_url[u] for u in order]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/bin/pytest tests/test_combine_host_sources.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/web_research.py backend/tests/test_combine_host_sources.py
git commit -m "feat: host-aware source combine with found_by union"
```

---

### Task 6: Orchestrator fan-out

**Files:**
- Modify: `backend/app/services/llm/agents/orchestrator.py`
- Test: `backend/tests/test_orchestrator_host_research.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_orchestrator_host_research.py`:

```python
import json
import pytest
from app.services.search import SearchResult
from tests.conftest import FakeLLM, FakeSearch
from app.services.llm.agents.orchestrator import BriefingOrchestrator

STORIES = [{"title": "S1", "summary": "x", "url": "http://news/1"}]
CAST = [{"name": "Alex", "personality": "Analytical", "order": 0},
        {"name": "Sam", "personality": "Skeptic", "order": 1}]


@pytest.mark.asyncio
async def test_gather_host_research_runs_one_pass_per_host(monkeypatch):
    q = json.dumps({"articles": [{"article_num": 1, "queries": ["q"]}]})
    f = json.dumps({"articles": [{"article_num": 1, "title": "S1",
                   "questions_and_answers": [{"question": "Q", "answer": "A"}]}]})
    orch = BriefingOrchestrator(FakeLLM())
    # Inject deterministic per-host agents.
    from app.services.llm.agents.host_research import HostResearchAgent
    orch._make_host_agent = lambda: HostResearchAgent(
        FakeLLM(response_content=[q, f]),
        search_service=FakeSearch(results=[SearchResult("R", "http://r.example", "s")]),
    )
    research_list, sources = await orch.gather_host_research(STORIES, CAST)
    assert [r.host_name for r in research_list] == ["Alex", "Sam"]
    assert all(s.get("found_by") for s in sources)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_orchestrator_host_research.py -v`
Expected: FAIL (`gather_host_research` / `_make_host_agent` undefined)

- [ ] **Step 3: Add fan-out to the orchestrator**

In `backend/app/services/llm/agents/orchestrator.py`, add imports at top:

```python
import asyncio
from app.services.llm.agents.host_research import HostResearchAgent, HostResearch
from app.services.web_research import combine_host_sources
```

Add to `BriefingOrchestrator` a factory (so tests can override) and the fan-out method:

```python
    def _make_host_agent(self) -> HostResearchAgent:
        return HostResearchAgent(self.llm)

    async def gather_host_research(
        self,
        stories: list[dict],
        cast_members: list[dict],
        briefing_id: Optional[str] = None,
    ) -> tuple[list[HostResearch], list[dict]]:
        """Run one persona-driven research pass per host, concurrently."""
        ordered = sorted(cast_members, key=lambda m: m.get("order", 0))

        async def _one(member: dict) -> HostResearch:
            agent = self._make_host_agent()
            return await agent.research(
                stories=stories,
                host_name=member.get("name", "Host"),
                personality_name=member.get("personality", "Casual"),
                briefing_id=briefing_id,
            )

        research_list = await asyncio.gather(*[_one(m) for m in ordered])
        combined_sources = combine_host_sources([r.sources for r in research_list])
        return list(research_list), combined_sources
```

Then add `prior_titles` already exists; add `host_research` to `write_briefing_script` signature (before `enable_non_speech_sounds`) and forward it:

```python
        host_research: Optional[list] = None,
```
and in the forwarded `self.briefing_writer.write_briefing(...)` call add:
```python
            host_research=host_research,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/bin/pytest tests/test_orchestrator_host_research.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/llm/agents/orchestrator.py backend/tests/test_orchestrator_host_research.py
git commit -m "feat: orchestrator concurrent per-host research fan-out"
```

---

### Task 7: Briefing writer consumes per-host research

**Files:**
- Modify: `backend/app/services/llm/agents/briefing_writer.py`
- Test: `backend/tests/test_briefing_writer_host_research.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_briefing_writer_host_research.py`:

```python
import pytest
from tests.conftest import FakeLLM
from app.services.llm.agents.briefing_writer import BriefingWriterAgent, build_host_research_section
from app.services.llm.agents.host_research import HostResearch

CAST = [{"name": "Alex", "personality": "Analytical"}, {"name": "Sam", "personality": "Skeptic"}]


def test_build_host_research_section_attributes_facts_to_each_host():
    research = [
        HostResearch("Alex", "Analytical", "Analytical — data", {0: ["Question: Q1\nAnswer: data point"]}, []),
        HostResearch("Sam", "Skeptic", "Skeptic — doubt", {0: ["Question: Q2\nAnswer: a caveat"]}, []),
    ]
    stories = [{"title": "AI chip launch"}]
    section = build_host_research_section(research, stories)
    assert "Alex" in section and "Sam" in section
    assert "data point" in section and "a caveat" in section
    assert "AI chip launch" in section


def test_build_host_research_section_empty_when_none():
    assert build_host_research_section(None, []) == ""


@pytest.mark.asyncio
async def test_write_briefing_includes_host_research_in_prompt():
    fake = FakeLLM(response_content="TITLE: x\nAlex: hi")
    agent = BriefingWriterAgent(fake)
    research = [HostResearch("Alex", "Analytical", "Analytical — data", {0: ["Question: Q\nAnswer: deep data"]}, [])]
    await agent.write_briefing(content="news", topics=["AI"], cast_members=CAST, duration=10,
                               ranked_items=[type("I", (), {"title": "AI chip launch"})()],
                               host_research=research)
    assert "deep data" in fake.calls[0]["prompt"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_briefing_writer_host_research.py -v`
Expected: FAIL (`build_host_research_section` undefined; `host_research` not a param)

- [ ] **Step 3: Add the section builder and param**

In `backend/app/services/llm/agents/briefing_writer.py`, add a module-level helper (below `build_continuity_section`):

```python
def build_host_research_section(host_research, stories) -> str:
    """Render each host's own research so the writer can stage an asymmetric debate."""
    if not host_research:
        return ""

    def _title(idx):
        if stories and 0 <= idx < len(stories):
            item = stories[idx]
            return getattr(item, "title", None) or (item.get("title") if isinstance(item, dict) else None) or f"Story {idx+1}"
        return f"Story {idx+1}"

    blocks = ["\n\n=== WHAT EACH HOST RESEARCHED (bring your own findings to the conversation) ==="]
    for hr in host_research:
        blocks.append(f"\n{hr.host_name} ({hr.angle}):")
        if not hr.facts_by_story_index:
            blocks.append("- (no distinct findings)")
            continue
        for idx, facts in hr.facts_by_story_index.items():
            blocks.append(f"On \"{_title(idx)}\":")
            for fact in facts:
                blocks.append(f"  - {fact}")
    blocks.append(
        "\nEach host should speak primarily from THEIR OWN findings above. Let the differing "
        "research drive genuine discussion - one host can raise a point the other didn't have."
    )
    return "\n".join(blocks)
```

In `_build_user_prompt`, add parameter `host_research=None` to the signature (before the closing paren) and `stories_for_titles=None`. Compute the section before the prompt f-string:

```python
        host_research_section = build_host_research_section(host_research, ranked_items)
```

Wait — `_build_user_prompt` does not currently receive `ranked_items`. It receives `ranked_items` already (used for additional_facts). Confirm by reading the signature; `ranked_items` IS a param of `_build_user_prompt`. Use it for titles.

Then include `{host_research_section}` in the user-prompt f-string, immediately after `{additional_facts_section}`. When `host_research` is provided, it supplements (the orchestrator path won't pass `additional_facts`, so only this section renders).

In `write_briefing`, add `host_research: Optional[list] = None,` to the signature (before `enable_non_speech_sounds`) and pass `host_research=host_research` into the `self._build_user_prompt(...)` call.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/bin/pytest tests/test_briefing_writer_host_research.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/llm/agents/briefing_writer.py backend/tests/test_briefing_writer_host_research.py
git commit -m "feat: briefing writer renders attributed per-host research"
```

---

### Task 8: Wire the enabled path in briefing.py

**Files:**
- Modify: `backend/app/services/briefing.py`
- Test: `backend/tests/test_briefing_host_research_wiring.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_briefing_host_research_wiring.py`:

```python
import pytest
from app.services.briefing import BriefingService


@pytest.mark.asyncio
async def test_merge_host_sources_into_briefing_sources():
    # Pure helper: editor sources + host sources -> combined, found_by preserved, deduped.
    svc = BriefingService.__new__(BriefingService)  # no __init__ (no providers needed)
    editor = [{"title": "Editor A", "url": "http://a.com"}]
    host = [{"title": "A dup", "url": "http://a.com", "found_by": ["Alex"]},
            {"title": "Host B", "url": "http://b.com", "found_by": ["Sam"]}]
    merged = svc._merge_sources_for_storage(editor, host)
    by_url = {s["url"]: s for s in merged}
    assert by_url["http://a.com"]["found_by"] == ["Alex"]   # editor source gains attribution
    assert by_url["http://b.com"]["found_by"] == ["Sam"]
    assert len(merged) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_briefing_host_research_wiring.py -v`
Expected: FAIL (`_merge_sources_for_storage` undefined)

- [ ] **Step 3: Add the storage-merge helper and wire the enabled path**

In `backend/app/services/briefing.py`, import the combiner near the existing web_research import:

```python
from app.services.web_research import select_stories_for_research, merge_sources, combine_host_sources
```

Add a small helper method to `BriefingService`:

```python
    def _merge_sources_for_storage(self, editor_sources: list[dict], host_sources: list[dict]) -> list[dict]:
        """Combine editor story sources with host-discovered sources, keyed by URL.

        Editor sources are listed first; a host-discovered URL that matches an editor
        source contributes its found_by attribution to that entry.
        """
        by_url: dict[str, dict] = {}
        order: list[str] = []
        for src in editor_sources:
            url = src.get("url")
            if not url:
                continue
            entry = dict(src)
            entry.setdefault("found_by", list(src.get("found_by", [])))
            by_url[url] = entry
            order.append(url)
        for src in host_sources:
            url = src.get("url")
            if not url:
                continue
            if url in by_url:
                for host in src.get("found_by", []):
                    if host not in by_url[url]["found_by"]:
                        by_url[url]["found_by"].append(host)
            else:
                entry = dict(src)
                entry["found_by"] = list(src.get("found_by", []))
                by_url[url] = entry
                order.append(url)
        return [by_url[u] for u in order]
```

Then wire the enabled path. In the briefing generation flow, where `additional_facts` is generated (around line 491, the `self._generate_additional_facts(...)` call) and where `write_briefing_script(...)` is called (around line 573), branch on the flag. Replace the facts-generation block with:

```python
            host_research = None
            if get_settings().host_research_enabled and len(cast_members) >= 1:
                stories_for_research = [item.to_dict() for item in ranked_items]
                host_research, host_sources = await self.orchestrator.gather_host_research(
                    stories=stories_for_research,
                    cast_members=cast_members,
                    briefing_id=briefing_id,
                )
                additional_facts = {}  # writer uses host_research instead
                briefing.sources = self._merge_sources_for_storage(
                    [item.to_dict() for item in ranked_items], host_sources
                )
                print(f"[Briefing] Per-host research complete for {len(host_research)} host(s)")
            else:
                additional_facts, raw_facts_response, facts_usage = await self._generate_additional_facts(
                    # ... existing arguments unchanged ...
                )
```

(Keep the existing `_generate_additional_facts` call exactly as it is today inside the `else`. Read the current arguments at the call site and preserve them verbatim.)

In the `write_briefing_script(...)` call, add:

```python
                host_research=host_research,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/bin/pytest tests/test_briefing_host_research_wiring.py -v`
Expected: PASS. Then `venv/bin/pytest tests/ -v` — full suite green.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/briefing.py backend/tests/test_briefing_host_research_wiring.py
git commit -m "feat: wire per-host research path into briefing generation"
```

---

### Task 9: Frontend — sources grouped by host

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/BriefingDetail.tsx`
- Test: `frontend/src/pages/briefingSources.test.ts` (pure grouping helper)

- [ ] **Step 1: Add `found_by` to the Source type**

In `frontend/src/api/client.ts`, find the source/`Source` type used for `briefing.sources` (a story dict with `title`, `url`, `source`, etc.) and add:

```typescript
  found_by?: string[]
```

If sources are currently typed loosely (e.g. `any[]`), introduce a `BriefingSource` interface with `title`, `url`, `source?`, `found_by?: string[]` and use it for the sources field.

- [ ] **Step 2: Write a failing test for the grouping helper**

Create `frontend/src/pages/briefingSources.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { groupSourcesByHost } from "./briefingSources";

describe("groupSourcesByHost", () => {
  it("groups sources under each host in found_by", () => {
    const sources = [
      { title: "A", url: "http://a", found_by: ["Alex"] },
      { title: "B", url: "http://b", found_by: ["Alex", "Sam"] },
      { title: "C", url: "http://c" }, // editor source, no host
    ];
    const groups = groupSourcesByHost(sources);
    expect(groups["Alex"].map((s) => s.title)).toEqual(["A", "B"]);
    expect(groups["Sam"].map((s) => s.title)).toEqual(["B"]);
    expect(groups["Alex"]).toHaveLength(2);
  });

  it("returns empty object when no host attribution present", () => {
    expect(groupSourcesByHost([{ title: "C", url: "http://c" }])).toEqual({});
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/briefingSources.test.ts`
Expected: FAIL (module `briefingSources` not found)

- [ ] **Step 4: Implement the grouping helper**

Create `frontend/src/pages/briefingSources.ts`:

```typescript
export interface BriefingSource {
  title?: string;
  url?: string;
  source?: string;
  found_by?: string[];
}

/** Group sources by each host listed in found_by. Sources with no found_by are omitted. */
export function groupSourcesByHost(
  sources: BriefingSource[]
): Record<string, BriefingSource[]> {
  const groups: Record<string, BriefingSource[]> = {};
  for (const src of sources) {
    for (const host of src.found_by ?? []) {
      (groups[host] ??= []).push(src);
    }
  }
  return groups;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/briefingSources.test.ts`
Expected: PASS

- [ ] **Step 6: Render the grouped sources in BriefingDetail**

In `frontend/src/pages/BriefingDetail.tsx`, import the helper and render a "Sources by host" section when any source has `found_by`. Use `briefing.sources` (the full list). Example block to place near the existing sources/chapter-sources rendering:

```tsx
import { groupSourcesByHost } from "./briefingSources";

// ...inside the component, after sources are available:
const hostGroups = groupSourcesByHost(briefing?.sources ?? []);
const hostNames = Object.keys(hostGroups);

// ...in JSX, where sources are shown:
{hostNames.length > 0 && (
  <div className="mt-6">
    <h3 className="text-white font-semibold mb-3">Sources by host</h3>
    <div className="space-y-4">
      {hostNames.map((host) => (
        <div key={host}>
          <p className="text-sm text-augustus-300 mb-1">
            {host} · {hostGroups[host].length} source
            {hostGroups[host].length === 1 ? "" : "s"}
          </p>
          <ul className="space-y-1">
            {hostGroups[host].map((s, i) => (
              <li key={`${host}-${i}`} className="text-xs text-augustus-400">
                {s.url ? (
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className="hover:text-accent">
                    {s.title || s.url}
                  </a>
                ) : (
                  s.title
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  </div>
)}
```

Match the surrounding Tailwind/class conventions already used in the file (the `augustus-*`/`accent` palette is established there).

- [ ] **Step 7: Verify build + tests**

Run: `cd frontend && npx vitest run` (grouping test green) and `npx tsc --noEmit` (no type errors). If practical, run the dev server and confirm the "Sources by host" section renders on a briefing that has per-host sources.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/pages/briefingSources.ts frontend/src/pages/briefingSources.test.ts frontend/src/pages/BriefingDetail.tsx
git commit -m "feat: show briefing sources grouped by host"
```

---

## Self-Review Notes

- **Spec coverage:** `HostResearchAgent` (Tasks 2–4) ✓; persona angle from existing persona text (Task 2, `persona_angle` + persona in prompts) ✓; one pass per host concurrently (Task 6 `asyncio.gather`) ✓; editor stories only (stories passed in; hosts never select stories) ✓; default-on flag + fallback (Tasks 1, 8) ✓; `found_by` attribution (Tasks 3, 5, 8) ✓; UI grouped by host (Task 9) ✓; error handling — query/facts JSON failure returns empty and `research()` still returns (Task 4 second test), one host failing doesn't abort `gather` (sources just smaller); structured-output gating reused ✓; tests network-free via `FakeLLM`/`FakeSearch` ✓.
- **Type consistency:** `HostResearch(host_name, personality_name, angle, facts_by_story_index, sources)` defined in Task 2 and constructed identically in Tasks 4/6/7 tests. `found_by: list[str]` consistent across Tasks 3/5/8/9. `gather_host_research -> (list[HostResearch], list[dict])` matches its use in Task 8. `build_host_research_section(host_research, stories)` signature matches Task 7 usage.
- **Placeholder scan:** Task 8 Step 3 intentionally says "preserve existing `_generate_additional_facts` arguments verbatim" — the implementer must read the current call site (around line 491) rather than guess; this is a deliberate instruction to avoid transcribing a long arg list that could drift, not a placeholder for logic.
- **Concurrency note (Task 6):** each `_make_host_agent()` builds its own `HostResearchAgent` so concurrent passes don't share mutable state; they share the singleton `SearchService`, which is stateless per call (httpx client is concurrency-safe).
```
