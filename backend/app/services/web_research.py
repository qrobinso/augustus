"""Helpers for deciding when to augment thin stories with live web research."""
from typing import Optional


def story_needs_research(item, facts: Optional[list], min_chars: int, min_facts: int) -> bool:
    """A story is 'thin' if its content is short OR it has too few usable facts."""
    content = getattr(item, "content", "") or ""
    facts = facts or []
    if len(content.strip()) < min_chars:
        return True
    if len(facts) < min_facts:
        return True
    return False


def select_stories_for_research(
    items: list,
    facts_by_index: dict,
    min_chars: int,
    min_facts: int,
    max_stories: int,
) -> list:
    """Return up to max_stories indices of thin stories, preserving rank order."""
    selected = []
    for i, item in enumerate(items):
        if story_needs_research(item, facts_by_index.get(i), min_chars, min_facts):
            selected.append(i)
        if len(selected) >= max_stories:
            break
    return selected


def merge_sources(existing: list, new: list) -> list:
    """Append new sources to existing, deduped by url, preserving order."""
    seen = {s.get("url") for s in existing if s.get("url")}
    merged = list(existing)
    for s in new:
        url = s.get("url")
        if url and url not in seen:
            seen.add(url)
            merged.append(s)
    return merged
