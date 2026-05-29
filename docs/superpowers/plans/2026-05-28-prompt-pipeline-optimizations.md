# Prompt Pipeline Optimizations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the LLM briefing pipeline's output quality, reliability, and cost by fixing token/length handling, removing prompt duplication, hardening JSON parsing with structured outputs, enabling prompt caching, and refining content-design rules.

**Architecture:** Three sequential LLM calls (`story_analyzer` → `facts_gatherer` → `briefing_writer`) run through a single `OpenRouterProvider`. We add a `response_format` passthrough + optional prompt-cache support at the provider layer, then update each agent. Pure helpers (token/word scaling, continuity text) are extracted into `prompts.py` so behavior is unit-testable without network calls.

**Tech Stack:** Python 3.11, FastAPI, httpx (OpenRouter REST), pytest + pytest-asyncio. Tests use a recording `FakeLLM` (no network).

---

## File Structure

- `backend/app/services/llm/base.py` — add `response_format` to abstract methods (Task 1).
- `backend/app/services/llm/openrouter.py` — extract `_build_payload`, add `response_format` + cache support (Tasks 1, 6).
- `backend/app/config.py` — add `llm_structured_outputs` and `llm_prompt_cache` flags (Tasks 1, 6).
- `backend/app/services/llm/prompts.py` — add `tokens_for_duration`, `target_words_for_duration` (Task 5).
- `backend/app/services/llm/agents/story_analyzer.py` — structured output + weather weighting (Task 2).
- `backend/app/services/llm/agents/facts_gatherer.py` — structured output (Task 3).
- `backend/app/services/llm/agents/briefing_writer.py` — consolidation, token/word scaling, caching, content rules (Tasks 4, 5, 6, 7).
- `backend/tests/conftest.py` — add reusable `FakeLLM` (Task 1).
- `backend/tests/test_llm_provider.py`, `test_story_analyzer.py`, `test_facts_gatherer.py`, `test_briefing_pacing.py`, `test_briefing_prompt.py` — new test files.

**Run tests with:** `backend/venv/bin/pytest` (system `python3` is 3.9 and too old). From `backend/`: `venv/bin/pytest tests/ -v`.

---

### Task 1: Provider `response_format` passthrough + recording `FakeLLM`

**Files:**
- Modify: `backend/app/services/llm/base.py`
- Modify: `backend/app/services/llm/openrouter.py`
- Modify: `backend/app/config.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_llm_provider.py`

- [ ] **Step 1: Add `FakeLLM` to conftest**

Append to `backend/tests/conftest.py`:

```python
from app.services.llm.base import LLMProvider, LLMResponse


class FakeLLM(LLMProvider):
    """Recording fake provider. Captures call kwargs; returns canned content."""

    def __init__(self, response_content: str = "{}"):
        self.response_content = response_content
        self.calls: list[dict] = []

    async def generate(self, prompt, system_prompt=None, max_tokens=4096,
                       temperature=0.7, response_format=None, briefing_id=None):
        self.calls.append({
            "prompt": prompt, "system_prompt": system_prompt,
            "max_tokens": max_tokens, "temperature": temperature,
            "response_format": response_format,
        })
        return LLMResponse(content=self.response_content, model="fake", usage={})

    async def generate_conversation(self, messages, max_tokens=4096,
                                   temperature=0.7, response_format=None, briefing_id=None):
        self.calls.append({
            "messages": messages, "max_tokens": max_tokens,
            "temperature": temperature, "response_format": response_format,
        })
        return LLMResponse(content=self.response_content, model="fake", usage={})

    async def close(self):
        pass
```

- [ ] **Step 2: Write failing provider test**

Create `backend/tests/test_llm_provider.py`:

```python
import pytest
from app.services.llm.openrouter import OpenRouterProvider


def test_build_payload_includes_response_format():
    p = OpenRouterProvider(api_key="test", model="anthropic/claude-3.5-sonnet")
    rf = {"type": "json_schema", "json_schema": {"name": "x", "schema": {}}}
    payload = p._build_payload(
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=100, temperature=0.3, response_format=rf,
    )
    assert payload["response_format"] == rf
    assert payload["max_tokens"] == 100
    assert payload["temperature"] == 0.3


def test_build_payload_omits_response_format_when_none():
    p = OpenRouterProvider(api_key="test", model="anthropic/claude-3.5-sonnet")
    payload = p._build_payload(
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=100, temperature=0.3, response_format=None,
    )
    assert "response_format" not in payload
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_llm_provider.py -v`
Expected: FAIL with `AttributeError: 'OpenRouterProvider' object has no attribute '_build_payload'`

- [ ] **Step 4: Add `response_format` to base abstract methods**

In `backend/app/services/llm/base.py`, add `response_format: Optional[dict] = None,` as a parameter (before `briefing_id`) to BOTH `generate` and `generate_conversation` abstract signatures.

- [ ] **Step 5: Implement `_build_payload` and thread `response_format` in openrouter.py**

In `backend/app/services/llm/openrouter.py`:

Add the method (place above `generate`):

```python
    def _build_payload(self, messages, max_tokens, temperature, response_format=None):
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        return payload
```

Change `generate` signature to add `response_format: Optional[dict] = None,` (before `briefing_id`) and pass it through to `generate_conversation`.

Change `generate_conversation` signature to add `response_format: Optional[dict] = None,` (before `briefing_id`). Replace the inline `payload = {...}` dict (lines ~124-129) with:

```python
        payload = self._build_payload(messages, max_tokens, temperature, response_format)
```

- [ ] **Step 6: Add config flag**

In `backend/app/config.py`, add near the other OpenRouter settings:

```python
    llm_structured_outputs: bool = True
```

- [ ] **Step 7: Run tests to verify pass**

Run: `cd backend && venv/bin/pytest tests/test_llm_provider.py -v`
Expected: PASS (2 passed)

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/llm/base.py backend/app/services/llm/openrouter.py backend/app/config.py backend/tests/conftest.py backend/tests/test_llm_provider.py
git commit -m "feat: add response_format passthrough to LLM provider"
```

---

### Task 2: story_analyzer structured output + weather weighting

**Files:**
- Modify: `backend/app/services/llm/agents/story_analyzer.py`
- Test: `backend/tests/test_story_analyzer.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_story_analyzer.py`:

```python
import pytest
from tests.conftest import FakeLLM
from app.services.llm.agents.story_analyzer import StoryAnalyzerAgent

ARTICLES = [{"title": "AI breakthrough", "summary": "x", "source": "Reuters", "category": "tech"}]


@pytest.mark.asyncio
async def test_passes_response_format_when_enabled(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    fake = FakeLLM(response_content='{"ranked_stories": [{"article_num": 1, "priority": 9, "reason": "r"}], "summary": "s"}')
    agent = StoryAnalyzerAgent(fake)
    ranked, summary, raw, usage = await agent.analyze_and_rank(ARTICLES, ["AI"], max_stories=5)
    assert ranked[0]["article_num"] == 1
    assert fake.calls[0]["response_format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_parses_plain_json_without_fences():
    fake = FakeLLM(response_content='{"ranked_stories": [], "summary": null}')
    agent = StoryAnalyzerAgent(fake)
    ranked, summary, raw, usage = await agent.analyze_and_rank(ARTICLES, ["AI"])
    assert ranked == []


def test_system_prompt_weather_is_weighted_not_absolute():
    agent = StoryAnalyzerAgent(FakeLLM())
    sp = agent._build_system_prompt(["AI"])
    assert "regardless of other factors" not in sp
    assert "weather" in sp.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_story_analyzer.py -v`
Expected: FAIL (`response_format` is `None`; weather text still contains "regardless of other factors")

- [ ] **Step 3: Add the JSON schema constant and pass response_format**

In `story_analyzer.py`, add near the top (after imports):

```python
RANKING_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "story_ranking",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "ranked_stories": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "article_num": {"type": "integer"},
                            "priority": {"type": "integer"},
                            "reason": {"type": "string"},
                        },
                        "required": ["article_num", "priority", "reason"],
                    },
                },
                "summary": {"type": "string"},
            },
            "required": ["ranked_stories", "summary"],
        },
    },
}
```

In `analyze_and_rank`, replace the `self.llm.generate(...)` call with:

```python
        from app.config import get_settings
        response_format = RANKING_SCHEMA if get_settings().llm_structured_outputs else None
        response = await self.llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=2048,
            temperature=0.3,
            response_format=response_format,
            briefing_id=briefing_id,
        )
```

(The existing markdown-fence extraction + `json.loads` stays as a fallback for models that ignore the schema.)

- [ ] **Step 4: Soften the weather rule**

In `_build_system_prompt`, replace rule 1 (the `**WEATHER STORIES ARE ALWAYS TOP PRIORITY**` block, lines ~47) with:

```python
1. **WEATHER & SAFETY STORIES ARE HIGH PRIORITY** - Articles about severe weather, natural disasters, or public-safety emergencies should be weighted heavily because they affect daily life and safety. Rank them among the top stories when present, but still respect the user's chosen topics below.
```

- [ ] **Step 5: Run tests to verify pass**

Run: `cd backend && venv/bin/pytest tests/test_story_analyzer.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/llm/agents/story_analyzer.py backend/tests/test_story_analyzer.py
git commit -m "feat: structured output + weighted weather priority in story analyzer"
```

---

### Task 3: facts_gatherer structured output

**Files:**
- Modify: `backend/app/services/llm/agents/facts_gatherer.py`
- Test: `backend/tests/test_facts_gatherer.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_facts_gatherer.py`:

```python
import pytest
from tests.conftest import FakeLLM
from app.services.llm.agents.facts_gatherer import FactsGathererAgent

STORIES = [{"title": "T", "summary": "s", "source": "Reuters", "category": "tech", "url": "", "full_content": "c"}]
RESP = '{"articles": [{"article_num": 1, "title": "T", "questions_and_answers": [{"question": "q", "answer": "a"}]}]}'


@pytest.mark.asyncio
async def test_passes_response_format_when_enabled(monkeypatch):
    fake = FakeLLM(response_content=RESP)
    agent = FactsGathererAgent(fake)
    # Avoid network in _fetch_article_content
    async def _no_fetch(story):
        return None
    agent._fetch_article_content = _no_fetch
    facts, raw, usage = await agent.gather_facts(STORIES)
    assert fake.calls[0]["response_format"]["type"] == "json_schema"
    assert 0 in facts
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_facts_gatherer.py -v`
Expected: FAIL (`response_format` is `None`)

- [ ] **Step 3: Add schema constant and pass response_format**

In `facts_gatherer.py`, add near the top:

```python
FACTS_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "article_facts",
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

In `gather_facts`, replace the `self.llm.generate(...)` call (lines ~278-284) with:

```python
        from app.config import get_settings
        response_format = FACTS_SCHEMA if get_settings().llm_structured_outputs else None
        response = await self.llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=4096,
            temperature=0.5,
            response_format=response_format,
            briefing_id=briefing_id,
        )
```

(Keep the existing 3-strategy parse fallback unchanged — it now rarely triggers but stays as a safety net.)

- [ ] **Step 4: Run tests to verify pass**

Run: `cd backend && venv/bin/pytest tests/test_facts_gatherer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/llm/agents/facts_gatherer.py backend/tests/test_facts_gatherer.py
git commit -m "feat: structured output in facts gatherer"
```

---

### Task 4: briefing_writer — consolidate duplication, reduce emphasis, trim examples

**Files:**
- Modify: `backend/app/services/llm/agents/briefing_writer.py`
- Test: `backend/tests/test_briefing_prompt.py`

**Goal:** Each rule appears once. The **system prompt** owns the persona, style, output contract (TITLE/CHAPTER/[medium pause]/speaker format), the filler-phrase blacklist, and the AVOID/language guidelines. The **user prompt** carries only the variable content (news, facts, date, topics, name, duration) plus a short numbered requirements list that does NOT restate the format rules.

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_briefing_prompt.py`:

```python
import pytest
from tests.conftest import FakeLLM
from app.services.llm.agents.briefing_writer import BriefingWriterAgent

CAST = [{"name": "Alex", "personality": "Casual"}, {"name": "Sam", "personality": "Skeptic"}]


def _agent():
    return BriefingWriterAgent(FakeLLM())


def test_filler_blacklist_appears_once_across_both_prompts():
    a = _agent()
    sp = a._build_system_prompt(CAST, topics=["AI"])
    up = a._build_user_prompt(content="news", topics=["AI"], duration=10)
    # The filler-phrase rule lives in the system prompt only.
    assert "there's a lot to unpack here" in sp
    assert "there's a lot to unpack here" not in up


def test_output_format_example_only_in_system_prompt():
    a = _agent()
    up = a._build_user_prompt(content="news", topics=["AI"], duration=10)
    assert "TITLE: Tech & Business Update" not in up  # example lives in system prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_briefing_prompt.py -v`
Expected: FAIL (both strings currently appear in the user prompt too)

- [ ] **Step 3: Trim the user prompt**

In `_build_user_prompt`, replace the returned `prompt = f"""..."""` block (lines ~612-680) with this leaner version (keeps content + variable context + a requirements list that references—does not restate—the format rules defined in the system prompt):

```python
        prompt = f"""Create an engaging {duration}-minute daily briefing podcast script from the news below.

{content}
{additional_facts_section}
{recent_articles_section}
{last_script_section}

CONTEXT:
- Current date/time: {current_date_time} (listener timezone: {timezone})
- Listener's name: {user_name_display}
- Topics to cover: {topics_str}
- Time of day: {time_of_day}
{name_instruction}

REQUIREMENTS:
1. Cover stories across ALL listed topics; lead with the most compelling one.
2. For each major story, explain what happened, why it matters, and what it means going forward; connect related stories.
3. Weave in the additional quantifiable facts above (when provided) for the matching article — ground the discussion in real numbers.
4. Have hosts ask insightful questions and offer distinct perspectives; present multiple viewpoints on contested topics.
5. End by recapping the key stories and takeaways.

Follow the title, chapter, transition, format, and language rules from the system instructions. Output the TITLE line, then the dialogue, and nothing else.

Generate the podcast script now:"""
```

- [ ] **Step 4: Reduce emphasis inflation in the system prompt**

In `_build_system_prompt`, in the `topic_instruction` blocks (lines ~283-313), change the leading `CRITICAL: You MUST mention...` to `In the opening, mention the topic(s) — vary the phrasing:`. Keep the example bullets. (This removes the shouted CRITICAL/MUST while preserving the instruction.)

- [ ] **Step 5: Trim intro examples from 3 to 2**

In `_build_system_prompt`, in each `intro_examples = [...]` list (the six branches, lines ~235-277), keep only the first TWO entries in each list. This reduces near-duplicate examples.

- [ ] **Step 6: Run tests to verify pass**

Run: `cd backend && venv/bin/pytest tests/test_briefing_prompt.py -v`
Expected: PASS (2 passed)

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/llm/agents/briefing_writer.py backend/tests/test_briefing_prompt.py
git commit -m "refactor: deduplicate briefing prompts and reduce emphasis inflation"
```

---

### Task 5: briefing_writer — duration-scaled max_tokens + word-count target

**Files:**
- Modify: `backend/app/services/llm/prompts.py`
- Modify: `backend/app/services/llm/agents/briefing_writer.py`
- Test: `backend/tests/test_briefing_pacing.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_briefing_pacing.py`:

```python
import pytest
from tests.conftest import FakeLLM
from app.services.llm.prompts import tokens_for_duration, target_words_for_duration
from app.services.llm.agents.briefing_writer import BriefingWriterAgent

CAST = [{"name": "Alex", "personality": "Casual"}]


def test_word_target_scales_with_duration():
    assert target_words_for_duration(10) == 1500
    assert target_words_for_duration(20) == 3000


def test_tokens_scale_and_clamp():
    assert tokens_for_duration(5) >= 1024          # floor
    assert tokens_for_duration(30) > tokens_for_duration(10)
    assert tokens_for_duration(120) <= 16384       # ceiling


@pytest.mark.asyncio
async def test_write_briefing_uses_scaled_tokens_and_word_target():
    fake = FakeLLM(response_content="TITLE: x\nAlex: hi")
    agent = BriefingWriterAgent(fake)
    await agent.write_briefing(content="news", topics=["AI"], cast_members=CAST, duration=20)
    call = fake.calls[0]
    assert call["max_tokens"] == tokens_for_duration(20)
    assert "3000" in call["prompt"]  # word target injected into user prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_briefing_pacing.py -v`
Expected: FAIL (`ImportError: cannot import name 'tokens_for_duration'`)

- [ ] **Step 3: Add pure helpers to prompts.py**

Append to `backend/app/services/llm/prompts.py`:

```python
WORDS_PER_MINUTE = 150


def target_words_for_duration(duration_minutes: int) -> int:
    """Approximate spoken word count for a briefing of the given length."""
    return int(duration_minutes) * WORDS_PER_MINUTE


def tokens_for_duration(duration_minutes: int) -> int:
    """max_tokens budget for a script of the given length.

    ~1.5 tokens/word for English, plus headroom for the title and markup.
    Clamped to a sane [1024, 16384] range.
    """
    words = target_words_for_duration(duration_minutes)
    tokens = int(words * 1.5) + 512
    return max(1024, min(tokens, 16384))
```

- [ ] **Step 4: Use the helpers in briefing_writer.py**

Update the import (lines ~6-9):

```python
from app.services.llm.prompts import (
    COMPLEXITY_LEVELS,
    get_complexity_instruction,
    tokens_for_duration,
    target_words_for_duration,
)
```

In `_build_user_prompt`, just before the `prompt = f"""..."""` assignment, add:

```python
        word_target = target_words_for_duration(duration)
```

In that user-prompt f-string (from Task 4), change the `REQUIREMENTS` intro line to include the target, e.g. add as the final requirement:

```python
6. Aim for roughly {word_target} words of spoken dialogue (~{duration} minutes at a natural pace).
```

In `write_briefing`, change the `self.llm.generate(...)` call to scale tokens:

```python
        response = await self.llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=tokens_for_duration(duration),
            temperature=0.7,
            briefing_id=briefing_id,
        )
```

- [ ] **Step 5: Run tests to verify pass**

Run: `cd backend && venv/bin/pytest tests/test_briefing_pacing.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/llm/prompts.py backend/app/services/llm/agents/briefing_writer.py backend/tests/test_briefing_pacing.py
git commit -m "fix: scale max_tokens and add word-count target by briefing duration"
```

---

### Task 6: Prompt caching for the static system prefix

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/services/llm/openrouter.py`
- Modify: `backend/app/services/llm/agents/briefing_writer.py`
- Test: `backend/tests/test_prompt_cache.py`

**Approach:** OpenRouter passes Anthropic/Gemini prompt-cache breakpoints via a content array with `cache_control`. We add an opt-in flag and a helper that wraps a system string as a cached content block, then have the briefing writer mark its (large, stable) system prompt cacheable.

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_prompt_cache.py`:

```python
import pytest
from app.services.llm.openrouter import cached_system_message


def test_cached_system_message_structure():
    msg = cached_system_message("big stable prompt")
    assert msg["role"] == "system"
    assert msg["content"][0]["type"] == "text"
    assert msg["content"][0]["text"] == "big stable prompt"
    assert msg["content"][0]["cache_control"] == {"type": "ephemeral"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_prompt_cache.py -v`
Expected: FAIL (`ImportError: cannot import name 'cached_system_message'`)

- [ ] **Step 3: Add the helper + config flag**

In `backend/app/config.py` add:

```python
    llm_prompt_cache: bool = False
```

In `backend/app/services/llm/openrouter.py`, add at module level (below imports):

```python
def cached_system_message(text: str) -> dict:
    """Build a system message whose content is marked for provider prompt caching."""
    return {
        "role": "system",
        "content": [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}],
    }
```

- [ ] **Step 4: Use caching in briefing_writer when enabled**

In `write_briefing` (briefing_writer.py), replace the single `generate(...)` call with a branch that uses `generate_conversation` + a cached system message when the flag is on:

```python
        from app.config import get_settings
        from app.services.llm.openrouter import cached_system_message

        max_tokens = tokens_for_duration(duration)
        if get_settings().llm_prompt_cache:
            messages = [
                cached_system_message(system_prompt),
                {"role": "user", "content": user_prompt},
            ]
            response = await self.llm.generate_conversation(
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
                briefing_id=briefing_id,
            )
        else:
            response = await self.llm.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=0.7,
                briefing_id=briefing_id,
            )
        return response
```

- [ ] **Step 5: Run tests to verify pass**

Run: `cd backend && venv/bin/pytest tests/test_prompt_cache.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/app/services/llm/openrouter.py backend/app/services/llm/agents/briefing_writer.py backend/tests/test_prompt_cache.py
git commit -m "feat: opt-in prompt caching for the briefing system prompt"
```

---

### Task 7: briefing_writer — soften disfluencies + title-based continuity

**Files:**
- Modify: `backend/app/services/llm/agents/briefing_writer.py`
- Test: `backend/tests/test_briefing_continuity.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_briefing_continuity.py`:

```python
from app.services.llm.agents.briefing_writer import build_continuity_section, NON_SPEECH_SOUNDS_GUIDE


def test_continuity_lists_prior_titles():
    section = build_continuity_section(["Story A", "Story B"])
    assert "Story A" in section
    assert "Story B" in section
    assert "do not repeat" in section.lower()


def test_continuity_empty_when_no_titles():
    assert build_continuity_section([]) == ""


def test_disfluency_guide_is_not_aggressive():
    # The over-stuffing language was removed.
    assert "OFTEN (2-4 times per segment)" not in NON_SPEECH_SOUNDS_GUIDE
    assert "FREQUENTLY (3-5 times per segment)" not in NON_SPEECH_SOUNDS_GUIDE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_briefing_continuity.py -v`
Expected: FAIL (`ImportError: cannot import name 'build_continuity_section'`)

- [ ] **Step 3: Add `build_continuity_section` helper**

In `briefing_writer.py`, add at module level (below the `CONVERSATIONAL_DYNAMICS` constant):

```python
def build_continuity_section(prior_titles: list[str]) -> str:
    """Build the 'previously covered' section from prior story titles.

    Using titles (not a raw transcript tail) gives the model a precise list of
    what to avoid repeating, without biasing toward the previous wrap-up.
    """
    titles = [t for t in (prior_titles or []) if t]
    if not titles:
        return ""
    lines = "\n".join(f"- {t}" for t in titles)
    return (
        "\n\n=== ALREADY COVERED IN THE LAST BRIEFING (do not repeat) ===\n"
        "These stories were covered last time. Do not repeat them; only reference "
        "one if there is a genuine update or new angle.\n"
        f"{lines}\n"
    )
```

- [ ] **Step 4: Use title-based continuity in `_build_user_prompt`**

Change `_build_user_prompt` to accept `prior_titles: Optional[list[str]] = None` (add to its signature, before the closing paren). Replace the `last_script_section` logic (lines ~588-610) so that when `prior_titles` is provided it uses `build_continuity_section(prior_titles)`; keep the raw-`last_script` tail only as a fallback when no titles are passed:

```python
        last_script_section = ""
        if prior_titles:
            last_script_section = build_continuity_section(prior_titles)
        elif last_script:
            script_preview = last_script[-2000:] if len(last_script) > 2000 else last_script
            last_script_section = (
                "\n\n=== LAST BRIEFING (continuity reference) ===\n"
                "Maintain tone and continuity; do not repeat stories already covered.\n"
                f"{script_preview}\n"
            )
```

In `write_briefing`, pass `prior_titles` through. Add `prior_titles: Optional[list[str]] = None,` to `write_briefing`'s signature and forward it into the `_build_user_prompt(...)` call. (The orchestrator/caller can populate it later from ranked story titles; default `None` preserves current behavior.)

- [ ] **Step 5: Soften the disfluency guide**

In the `NON_SPEECH_SOUNDS_GUIDE` constant (lines ~14-43), replace the `CRITICAL - USE FREQUENTLY:` block and the first two `Guidelines:` bullets with measured language:

```python
USE NATURALLY (do not overdo it):
- [uhm] - occasionally, at genuine thinking or transition points, to soften delivery.
- [short pause] - to break up longer sentences or set up an important point.
```

And change the first guideline bullet to:
```python
- Use [uhm] and [short pause] where they make speech feel natural — a few per segment, not in every sentence.
```

- [ ] **Step 6: Run tests to verify pass**

Run: `cd backend && venv/bin/pytest tests/test_briefing_continuity.py -v`
Expected: PASS (3 passed)

- [ ] **Step 7: Run the full backend suite**

Run: `cd backend && venv/bin/pytest tests/ -v`
Expected: all green (existing audio/search/research tests + the 5 new files)

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/llm/agents/briefing_writer.py backend/tests/test_briefing_continuity.py
git commit -m "feat: title-based continuity and softer disfluency guidance"
```

---

## Self-Review Notes

- **Spec coverage:** Tier 1 → Task 5; Tier 2 → Task 4; Tier 3 → Tasks 1-3; Tier 4 → Task 6; Tier 5 (disfluency, weather, last_script) → Tasks 7 and 2. All covered.
- **Type consistency:** `response_format` added to `base.py`, `openrouter.py`, and `FakeLLM` with matching signatures. `tokens_for_duration`/`target_words_for_duration` defined in Task 5 and used the same way in tests. `build_continuity_section`/`cached_system_message` defined before use.
- **Ordering:** Provider (1) precedes agents that use `response_format` (2, 3). briefing_writer restructure (4) precedes token/word (5), caching (6), and content (7) so later tasks edit the consolidated file.
- **Risk note:** structured outputs and caching are both behind config flags (`llm_structured_outputs` default on, `llm_prompt_cache` default off) so an unsupported model can be reverted without code changes.
