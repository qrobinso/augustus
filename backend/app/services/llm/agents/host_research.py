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
