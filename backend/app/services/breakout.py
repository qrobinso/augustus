"""Focused, source-backed research for on-demand breakout episodes."""

import re
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional
from urllib.parse import urlparse

from app.config import get_settings
from app.services.search import SearchService


class BreakoutResearchError(ValueError):
    """Raised when focused research cannot retrieve enough usable evidence."""


@dataclass
class BreakoutResearch:
    """Prompt-ready research plus the fetched pages that support it."""

    content: str
    sources: list[dict]


_ANGLES = (
    ("Foundations", "background history definitions and foundational context"),
    ("Mechanisms", "mechanism how it works incentives constraints and causal factors"),
    ("Evidence", "evidence data case studies examples outcomes and limitations"),
    ("Competing viewpoints and implications", "competing viewpoints criticism uncertainty implications and future effects"),
)


_PLUGIN_MAX_TOKENS = 4096
_MD_LINK = re.compile(r"\[([^\]]+)\]\((?:https?://)[^)]+\)")


def _uses_web_plugin(llm) -> bool:
    return bool(
        llm is not None
        and getattr(llm, "supports_web_search_plugin", False)
        and get_settings().host_research_web_plugin
    )


async def _research_with_web_plugin(
    llm, topic: str, focus: str, check_cancelled,
) -> tuple[list[str], list[dict], set[str]]:
    """One web-search-enabled model call per angle; citations become sources.

    This is the same retrieval path host research uses, so it keeps working when
    the DuckDuckGo HTML endpoint serves a bot challenge instead of results.
    """
    settings = get_settings()
    plugins = [{"id": "web", "engine": settings.host_research_search_engine, "max_results": 5}]
    system_prompt = (
        "You have web search. Research the topic below for the requested angle only. "
        "Search, read the retrieved pages, and write 2-4 paragraphs of specific, "
        "grounded findings with numbers, names, and dates where they exist. Separate "
        "facts from interpretation and flag uncertainty. Plain prose, no markdown, "
        "no invented sources."
    )
    sections, sources, seen_urls, angles = [], [], set(), set()
    for angle, angle_query in _ANGLES:
        if check_cancelled:
            await check_cancelled()
        prompt = f"TOPIC: {topic}\nFOCUS: {focus or 'none'}\nANGLE ({angle}): {angle_query}"
        try:
            response = await llm.generate(
                prompt=prompt, system_prompt=system_prompt,
                max_tokens=_PLUGIN_MAX_TOKENS, temperature=0.4, plugins=plugins,
            )
        except Exception as e:
            print(f"[Breakout] web plugin research failed for angle {angle!r}: {e!r}")
            continue
        cited = []
        for ann in getattr(response, "annotations", None) or []:
            cite = ann.get("url_citation") if isinstance(ann, dict) else None
            url = cite.get("url") if cite else None
            if not url or url in seen_urls:
                continue
            excerpt = " ".join((cite.get("content") or "").split())[:4000]
            if len(excerpt) < 200:
                continue
            seen_urls.add(url)
            title = cite.get("title") or url
            sources.append({
                "title": title, "url": url,
                "source": urlparse(url).hostname or url,
                "summary": excerpt[:1200], "excerpt": excerpt[:1200],
                "research_angle": angle, "retrieval": "web_plugin",
            })
            cited.append(f"Source: {title}\nURL: {url}\nRetrieved excerpt:\n{excerpt}")
        if not cited:
            print(f"[Breakout] web plugin returned no cited pages for angle {angle!r}")
            continue
        angles.add(angle)
        # Markdown links become their label; the writer must never read a URL aloud.
        findings = " ".join(_MD_LINK.sub(r"\1", response.content or "").split())[:4000]
        sections.append(
            f"=== {angle.upper()} ===\nFindings:\n{findings}\n\n" + "\n\n".join(cited)
        )
    return sections, sources, angles


async def _research_with_page_fetches(
    search: SearchService, topic: str, focus: str, check_cancelled,
) -> tuple[list[str], list[dict], set[str], int]:
    """Search, then fetch real pages; snippets are never treated as content."""
    focus_clause = f" Focus: {focus}." if focus else ""
    sources: list[dict] = []
    sections: list[str] = []
    seen_urls: set[str] = set()
    represented_angles: set[str] = set()
    result_count = 0

    for angle, angle_query in _ANGLES:
        if check_cancelled:
            await check_cancelled()
        query = f"{topic}.{focus_clause} {angle_query} reliable sources"
        results = await search.search(query, num_results=5)
        result_count += len(results)
        angle_parts = []
        for result in results:
            if result.url in seen_urls:
                continue
            if check_cancelled:
                await check_cancelled()
            content = await search.fetch_page_content(result.url)
            normalized = " ".join((content or "").split())
            if len(normalized) < 200:
                continue
            seen_urls.add(result.url)
            represented_angles.add(angle)
            excerpt = normalized[:4000]
            hostname = urlparse(result.url).hostname or result.url
            sources.append(
                {
                    "title": result.title,
                    "url": result.url,
                    "source": hostname,
                    "summary": excerpt[:1200],
                    "excerpt": excerpt[:1200],
                    "research_angle": angle,
                    "retrieval": "fetched_page",
                }
            )
            angle_parts.append(
                f"Source: {result.title}\nURL: {result.url}\nFetched page content:\n{excerpt}"
            )
            # One solid page per angle gives better breadth than repeatedly
            # harvesting the same search angle.
            break
        if angle_parts:
            sections.append(f"=== {angle.upper()} ===\n" + "\n\n".join(angle_parts))
    return sections, sources, represented_angles, result_count


async def research_breakout(
    search: SearchService,
    topic: str,
    focus: str = "",
    source_context: str = "",
    check_cancelled: Optional[Callable[[], Awaitable[None]]] = None,
    llm=None,
) -> BreakoutResearch:
    """Gather real retrieved content for several complementary angles on one topic.

    When the LLM provider supports a web search plugin (the path host research
    uses) it is tried first; otherwise, or when it comes back thin, pages are
    discovered through the search service and fetched directly. At least two
    retrieved pages across two angles are required before the writer can run,
    which keeps a search outage from turning into invented research.
    """
    topic = " ".join((topic or "").split())
    focus = " ".join((focus or "").split())
    source_context = " ".join((source_context or "").split())[:6000]
    if not topic:
        raise BreakoutResearchError("Breakout research requires a topic.")

    def enough(sources, angles):
        return len(sources) >= 2 and len(angles) >= 2

    sections, sources, represented_angles = [], [], set()
    if _uses_web_plugin(llm):
        sections, sources, represented_angles = await _research_with_web_plugin(
            llm, topic, focus, check_cancelled
        )

    result_count = None
    if not enough(sources, represented_angles):
        if sources:
            print(f"[Breakout] web plugin found only {len(sources)} pages; falling back to page fetching")
        sections, sources, represented_angles, result_count = await _research_with_page_fetches(
            search, topic, focus, check_cancelled
        )

    if not enough(sources, represented_angles):
        detail = ""
        if result_count == 0:
            detail = (
                " Web search returned no results at all, which usually means the "
                "search backend is unavailable or blocking automated requests."
            )
        raise BreakoutResearchError(
            f"Breakout research found only {len(sources)} usable pages across "
            f"{len(represented_angles)} angles; at least 2 usable pages from "
            f"different angles are required.{detail} Try again, or use a broader topic or focus."
        )

    context_section = ""
    if source_context:
        context_section = (
            "=== SOURCE EPISODE CONTEXT (listener-selected context, not web evidence) ===\n"
            f"{source_context}\n\n"
        )
    content = (
        f"BREAKOUT TOPIC: {topic}\n"
        f"REQUESTED FOCUS: {focus or 'No narrower focus supplied'}\n\n"
        f"{context_section}"
        + "\n\n".join(sections)
    )
    return BreakoutResearch(content=content, sources=sources)
