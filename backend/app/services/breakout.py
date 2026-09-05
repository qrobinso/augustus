"""Focused, source-backed research for on-demand breakout episodes."""

from dataclasses import dataclass
from typing import Awaitable, Callable, Optional
from urllib.parse import urlparse

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


async def research_breakout(
    search: SearchService,
    topic: str,
    focus: str = "",
    source_context: str = "",
    check_cancelled: Optional[Callable[[], Awaitable[None]]] = None,
) -> BreakoutResearch:
    """Retrieve real page content for several complementary angles on one topic.

    Search snippets help discover pages but are never treated as fetched article
    content. At least two pages across two angles are required before the writer
    can run, which keeps a search outage from turning into invented research.
    """
    topic = " ".join((topic or "").split())
    focus = " ".join((focus or "").split())
    source_context = " ".join((source_context or "").split())[:6000]
    if not topic:
        raise BreakoutResearchError("Breakout research requires a topic.")

    focus_clause = f" Focus: {focus}." if focus else ""
    sources: list[dict] = []
    sections: list[str] = []
    seen_urls: set[str] = set()
    represented_angles: set[str] = set()

    for angle, angle_query in _ANGLES:
        if check_cancelled:
            await check_cancelled()
        query = f"{topic}.{focus_clause} {angle_query} reliable sources"
        results = await search.search(query, num_results=5)
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

    if len(sources) < 2 or len(represented_angles) < 2:
        raise BreakoutResearchError(
            f"Breakout research found only {len(sources)} usable pages across "
            f"{len(represented_angles)} angles; at least 2 usable pages from "
            "different angles are required. Try a broader topic or focus."
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
