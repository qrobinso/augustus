"""Host Research Agent - persona-driven, per-host source research."""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Optional

from app.config import get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.personalities import get_personality
from app.services.search import get_search_service
from app.services.evidence import attribute_claims


@dataclass
class HostResearch:
    """One host's research over the editor's selected stories."""

    host_name: str
    personality_name: str
    angle: str
    facts_by_story_index: dict[int, list[str]] = field(default_factory=dict)
    sources: list[dict] = field(default_factory=list)
    claims_by_story_index: dict[int, list[dict]] = field(default_factory=dict)


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
                                        "evidence": {"type": "array", "items": {
                                            "type": "object", "additionalProperties": False,
                                            "properties": {"url": {"type": "string"}, "excerpt": {"type": "string"}},
                                            "required": ["url", "excerpt"]}},
                                    },
                                    "required": ["question", "answer", "evidence"],
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


ONLINE_RESEARCH_MAX_TOKENS = 6144


class HostResearchAgent:
    """Researches the editor's selected stories through one host's persona lens."""

    def __init__(self, llm: LLMProvider, search_service=None, use_web_plugin: Optional[bool] = None):
        self.llm = llm
        self.search_service = search_service or get_search_service()
        self.use_web_plugin = (
            use_web_plugin if use_web_plugin is not None else (
                get_settings().host_research_web_plugin
                and getattr(llm, "supports_web_search_plugin", False)
            )
        )

    # ---------------------------------------------------------------- online path

    def _online_system_prompt(self, host_name: str, personality_name: str) -> str:
        personality = get_personality(personality_name)
        guidelines = "\n".join(f"- {g}" for g in (personality.get_behavioral_guidelines() or [])[:4])
        stance = personality.stance or persona_angle(personality_name)
        return (
            f"You are {host_name}, a podcast host ({personality_name}). Your stance: {stance}\n{guidelines}\n\n"
            "You have web search. Research the story below the way YOU would: look for the "
            "evidence, numbers, precedents, and angles your stance cares about, and for anything "
            "that would make you push back on the headline. Prefer primary sources and recent "
            "coverage. Then write 3-5 question/answer pairs you would bring to the conversation. "
            "Answers must be specific and grounded in what you found, with numbers where they exist.\n\n"
            'For each answer include evidence: exact source URL and a short verbatim excerpt from retrieved text. '
            'Use evidence: [] when no supporting passage is available. Never invent citations or quotes. '
            'Separate factual findings from interpretation; surface contradictory evidence and uncertainty. '
            'Output JSON only: {"questions_and_answers":[{"question":"...","answer":"...",'
            '"evidence":[{"url":"https://source.example/report","excerpt":"verbatim passage"}]}]}'
        )

    @staticmethod
    def _online_user_prompt(story: dict) -> str:
        return (
            f"STORY: {story.get('title', 'Untitled')}\n"
            f"Source: {story.get('source', 'unknown')}\n"
            f"URL: {story.get('url', 'unknown')}\n"
            f"Summary: {(story.get('summary') or '')[:600]}"
        )

    @staticmethod
    def _extract_json_object(text: str) -> Optional[dict]:
        """Pull the first JSON object out of a response that may include prose or fences."""
        if not text:
            return None
        candidate = text
        if "```" in text:
            m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if m:
                candidate = m.group(1)
        else:
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end > start:
                candidate = text[start:end + 1]
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    _MD_LINK = re.compile(r"\[([^\]]+)\]\((?:https?://)[^)]+\)")

    @classmethod
    def _plain_text(cls, text: str) -> str:
        """Markdown links become their label; the URL would otherwise be read aloud."""
        return cls._MD_LINK.sub(r"\1", text or "").strip()

    @staticmethod
    def _sources_from_annotations(annotations: list, host_name: str, story_index: int) -> list[dict]:
        sources = []
        for ann in annotations or []:
            cite = ann.get("url_citation") if isinstance(ann, dict) else None
            if not cite or not cite.get("url"):
                continue
            sources.append({
                "title": cite.get("title") or cite["url"],
                "url": cite["url"],
                "snippet": (cite.get("content") or "")[:6000],
                "found_by": [host_name],
                "story_index": story_index,
            })
        return sources

    async def _research_story_online(
        self, idx: int, story: dict, host_name: str, personality_name: str,
        briefing_id: Optional[str],
    ) -> tuple[int, list[str], list[dict], list[dict]]:
        settings = get_settings()
        plugins = [{
            "id": "web",
            "engine": settings.host_research_search_engine,
            "max_results": settings.host_research_max_sources_per_story,
        }]
        try:
            response = await self.llm.generate(
                prompt=self._online_user_prompt(story),
                system_prompt=self._online_system_prompt(host_name, personality_name),
                # Reasoning models spend thinking tokens from this budget on top of the
                # search excerpts they read; 2048 was observed to truncate the answer.
                max_tokens=ONLINE_RESEARCH_MAX_TOKENS,
                temperature=0.5,
                briefing_id=briefing_id,
                plugins=plugins,
            )
        except Exception as e:
            print(f"[HostResearch:{host_name}] online research failed for story {idx + 1}: {e!r}")
            return idx, [], [], []

        data = self._extract_json_object(response.content) or {}
        facts = [
            f"Question: {self._plain_text(qa.get('question', ''))}\nAnswer: {self._plain_text(qa.get('answer', ''))}"
            for qa in data.get("questions_and_answers", [])
            if isinstance(qa, dict) and qa.get("question") and qa.get("answer")
        ]
        sources = self._sources_from_annotations(getattr(response, "annotations", None), host_name, idx)
        if not facts:
            print(f"[HostResearch:{host_name}] no usable facts for story {idx + 1} (content: {response.content[:120]!r})")
        claims = attribute_claims(data.get("questions_and_answers", []), sources, host_name)
        return idx, facts, sources, claims

    async def _research_online(
        self, stories: list[dict], host_name: str, personality_name: str,
        briefing_id: Optional[str] = None,
    ) -> HostResearch:
        results = await asyncio.gather(*[
            self._research_story_online(i, story, host_name, personality_name, briefing_id)
            for i, story in enumerate(stories)
        ])
        facts_by_idx: dict[int, list[str]] = {}
        sources: list[dict] = []
        seen: set[str] = set()
        claims_by_idx = {}
        for idx, facts, story_sources, claims in results:
            claims_by_idx[idx] = claims
            if facts:
                facts_by_idx[idx] = facts
            for src in story_sources:
                if (idx, src["url"]) not in seen:
                    seen.add((idx, src["url"]))
                    sources.append(src)
        return HostResearch(
            host_name=host_name,
            personality_name=personality_name,
            angle=persona_angle(personality_name),
            facts_by_story_index=facts_by_idx,
            sources=sources,
            claims_by_story_index=claims_by_idx,
        )

    # ---------------------------------------------------------------- legacy path (DuckDuckGo)

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
                        collected.append(f"[Source: {url}]\n{page}")
                        sources.append({"url": url, "title": story.get("title", url), "content": page[:6000],
                                        "found_by": [host_name], "story_index": idx})
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
                            collected.append(f"[Source: {result.title} | {result.url}]\n{page}")
                            sources[-1]["content"] = page[:6000]
                    except Exception as e:
                        print(f"[HostResearch:{host_name}] fetch failed for {result.url}: {e}")

            if collected:
                content_by_idx[idx] = "\n\n".join(collected)

        return content_by_idx, sources

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

    def _facts_system_prompt(self, host_name: str, personality_name: str) -> str:
        angle = persona_angle(personality_name)
        return (
            f"You are {host_name}, a podcast host whose perspective is: {angle}.\n"
            "From the article content and additional sources you gathered, generate 3-5 "
            "questions and detailed, fact-grounded answers PER article, emphasizing the "
            "angles and evidence that fit your perspective. Prefer quantifiable data, "
            "specific evidence, and the implications you find most important. For each answer include evidence "
            "with an exact source URL and short verbatim excerpt from the supplied material; use [] if unsupported. "
            "Do not invent sources, quotes, or certainty. JSON only."
        )

    def _facts_user_prompt(self, stories: list[dict], content_by_idx: dict[int, str]) -> str:
        blocks = []
        for i, story in enumerate(stories, 1):
            content = content_by_idx.get(i - 1, story.get("summary", ""))
            blocks.append(f"ARTICLE {i}: {story.get('title', 'Untitled')}\nCONTENT:\n{content[:6000]}")
        return (
            "\n\n".join(blocks)
            + '\n\nOutput JSON: {"articles":[{"article_num":1,"title":"...",'
            '"questions_and_answers":[{"question":"...","answer":"...","evidence":[{"url":"...","excerpt":"..."}]}]}]}'
        )

    async def _generate_facts(
        self, stories: list[dict], content_by_idx: dict[int, str],
        host_name: str, personality_name: str, briefing_id: Optional[str] = None,
        sources: Optional[list[dict]] = None,
    ) -> tuple[dict[int, list[str]], dict[int, list[dict]]]:
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
            return {}, {}
        facts: dict[int, list[str]] = {}
        claims = {}
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
                claims[idx] = attribute_claims(article.get("questions_and_answers", []),
                    [source for source in (sources or []) if source.get("story_index") == idx], host_name)
        return facts, claims

    async def research(
        self, stories: list[dict], host_name: str, personality_name: str,
        briefing_id: Optional[str] = None,
    ) -> HostResearch:
        if self.use_web_plugin:
            return await self._research_online(stories, host_name, personality_name, briefing_id)
        queries_by_idx = await self._generate_queries(stories, host_name, personality_name, briefing_id)
        content_by_idx, sources = await self._gather_sources(stories, queries_by_idx, host_name)
        facts, claims = await self._generate_facts(stories, content_by_idx, host_name, personality_name, briefing_id, sources)
        return HostResearch(
            host_name=host_name,
            personality_name=personality_name,
            angle=persona_angle(personality_name),
            facts_by_story_index=facts,
            sources=sources,
            claims_by_story_index=claims,
        )
