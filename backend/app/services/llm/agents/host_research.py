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
    if not core:
        return personality_name
    return f"{personality_name} — {core}"


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
            "evidence, and viewpoints you would personally dig into. Every query must stay "
            "on the specific story's subject; do not broaden into adjacent topics, however "
            "interesting. Return JSON only."
        )

    def _query_user_prompt(
        self, stories: list[dict], queries_per_story: int, topics: Optional[list[str]] = None,
    ) -> str:
        lines = []
        for i, s in enumerate(stories, 1):
            category = s.get("category")
            category_line = f"\nCategory: {category}" if category else ""
            lines.append(
                f"ARTICLE {i}: {s.get('title', 'Untitled')}{category_line}\nSummary: {s.get('summary', '')[:200]}"
            )
        topics_line = f"Briefing topics: {', '.join(topics)}\n\n" if topics else ""
        return (
            topics_line
            + f"Propose up to {queries_per_story} search queries per article, from your perspective.\n\n"
            + "\n\n".join(lines)
            + '\n\nOutput JSON: {"articles":[{"article_num":1,"queries":["..."]}]}'
        )

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

    async def _generate_queries(
        self, stories: list[dict], host_name: str, personality_name: str,
        briefing_id: Optional[str] = None, topics: Optional[list[str]] = None,
    ) -> dict[int, list[str]]:
        settings = get_settings()
        response_format = QUERY_SCHEMA if settings.llm_structured_outputs else None
        response = await self.llm.generate(
            prompt=self._query_user_prompt(stories, settings.host_research_queries_per_story, topics),
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

    def _facts_system_prompt(self, host_name: str, personality_name: str) -> str:
        angle = persona_angle(personality_name)
        return (
            f"You are {host_name}, a podcast host whose perspective is: {angle}.\n"
            "From the article content and additional sources you gathered, generate 3-5 "
            "questions and detailed, fact-grounded answers PER article, emphasizing the "
            "angles and evidence that fit your perspective. Prefer quantifiable data, "
            "specific evidence, and the implications you find most important. Only report "
            "facts about the story itself — if a gathered source turned out to be about "
            "something else, ignore it. JSON only."
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
        briefing_id: Optional[str] = None, topics: Optional[list[str]] = None,
    ) -> HostResearch:
        queries_by_idx = await self._generate_queries(stories, host_name, personality_name, briefing_id, topics)
        content_by_idx, sources = await self._gather_sources(stories, queries_by_idx, host_name)
        facts = await self._generate_facts(stories, content_by_idx, host_name, personality_name, briefing_id)
        return HostResearch(
            host_name=host_name,
            personality_name=personality_name,
            angle=persona_angle(personality_name),
            facts_by_story_index=facts,
            sources=sources,
        )
