"""Persistent editorial memory; generation and listening are distinct facts."""
import uuid
import json
from datetime import datetime

from sqlalchemy import select, func
from app.models.briefing import Briefing
from app.models.story import Story, StoryDevelopment
from app.services.listening import ListeningService


def _normal(text):
    return ' '.join(str(text or '').casefold().split()).strip(' .')


def select_story_updates(ranked, items, memory, max_stories):
    """Validate editor choices, coalesce events, and exclude known rehashes.

    Semantic matching is the editor's job. Never accept an arbitrary database ID
    from model output, and never treat generated-but-unheard material as known.
    memory=None preserves the legacy caller contract; [] enables the new contract.
    """
    if not isinstance(ranked, list):
        raise ValueError('Editor rankings must be a list')
    known = {s['id']: s for s in memory or []}
    by_title = {_normal(s['title']): s for s in memory or []}
    selected, seen_keys, seen_articles = [], set(), set()
    for entry in ranked:
        if not isinstance(entry, dict) or type(entry.get('article_num')) is not int:
            raise ValueError('Editor must identify each selected article by number')
        idx = entry['article_num'] - 1
        if idx < 0 or idx >= len(items):
            raise ValueError('Editor selected an unknown article')
        if idx in seen_articles:
            continue
        key = entry.get('story_key')
        development = entry.get('development')
        change = entry.get('change_type')
        if memory is not None:
            if not isinstance(key, str) or not key.strip() or len(key) > 500:
                raise ValueError('Editor must identify a story with a short event label or known ID')
            if not isinstance(development, str) or not development.strip() or len(development) > 2000:
                raise ValueError('Editor must describe the factual development')
            if change not in ('new', 'update', 'unchanged'):
                raise ValueError('Editor returned an invalid change type')
        else:
            key = key or items[idx].title
            development = development or items[idx].summary or items[idx].title
            change = change or 'new'
        key = key.strip()
        prior = known.get(key) or by_title.get(_normal(key))
        if not prior:
            try:
                uuid.UUID(key)
            except ValueError:
                pass
            else:
                # An ID that is not in this profile's context cannot attach to it.
                continue
        canonical = prior['id'] if prior else _normal(key)
        if canonical in seen_keys:
            continue
        developments = prior.get('developments', []) if prior else []
        heard = [d['summary'] for d in developments if d.get('heard')]
        if any(_normal(development) == _normal(summary) for summary in heard):
            continue
        if change == 'unchanged' and developments and developments[0].get('heard'):
            continue
        news = items[idx]
        news.priority = entry.get('priority')
        news.editor_note = entry.get('reason')
        news.story_key = prior['id'] if prior else key
        news.development = development.strip()
        news.change_type = change if prior else 'new'
        news.heard_context = heard[:3]
        selected.append(news)
        seen_keys.add(canonical)
        seen_articles.add(idx)
        if len(selected) >= max_stories:
            break
    return selected


class StoryMemoryService:
    def __init__(self, db):
        self.db = db

    async def context(self, user_id, profile_id):
        """Bounded cross-topic memory for the exact owner; no historical inference."""
        stories = (await self.db.execute(
            select(Story).where(Story.user_id == user_id, Story.profile_id == profile_id)
            .order_by((Story.preference == 'follow').desc(), Story.updated_at.desc()).limit(60)
        )).scalars().all()
        if not stories:
            return []
        # Limit in SQL as well as in the prompt: long-running installations can
        # accumulate many appearances of a followed story.
        recent = (select(StoryDevelopment.id.label("development_id"),
            func.row_number().over(partition_by=StoryDevelopment.story_id,
                order_by=(StoryDevelopment.created_at.desc(), StoryDevelopment.id.desc())).label("position"))
            .join(Briefing, StoryDevelopment.briefing_id == Briefing.id)
            .where(StoryDevelopment.story_id.in_([s.id for s in stories]),
                   Briefing.user_id == user_id, Briefing.profile_id == profile_id,
                   Briefing.status == 'completed').subquery())
        rows = (await self.db.execute(
            select(StoryDevelopment, Briefing)
            .join(recent, recent.c.development_id == StoryDevelopment.id)
            .join(Briefing, StoryDevelopment.briefing_id == Briefing.id)
            .where(recent.c.position <= 5)
            .order_by(StoryDevelopment.created_at.desc(), StoryDevelopment.id.desc())
        )).all()
        grouped = {s.id: [] for s in stories}
        coverage_cache = {}
        listening = ListeningService(self.db)
        for development, briefing in rows:
            if len(grouped[development.story_id]) >= 5:
                continue
            if briefing.id not in coverage_cache:
                coverage_cache[briefing.id] = await listening.coverage(briefing)
            coverage = coverage_cache[briefing.id].get('chapter_coverage', {})
            heard = (development.chapter_index is not None and
                     coverage.get(str(development.chapter_index), 0) >= 0.8)
            grouped[development.story_id].append({
                'id': development.id, 'summary': development.summary[:600],
                'date': development.created_at.isoformat(), 'heard': heard,
                'evidence': [{'text': c.get('text', '')[:300], 'sources': [
                    {'url': source.get('url', '')[:500], 'excerpt': source.get('excerpt', '')[:300]}
                    for source in c.get('sources', [])[:1]]}
                    for c in (development.claims or []) if c.get('sources')][:1],
            })
        context = []
        budget = 32000  # Keep room for candidates and writer instructions in modest contexts.
        for story in stories:
            if not grouped[story.id]:
                continue
            entry = {'id': story.id, 'title': story.title, 'preference': story.preference,
                     'developments': grouped[story.id]}
            size = len(json.dumps(entry, ensure_ascii=False)) + 2
            if size > budget:
                continue
            context.append(entry)
            budget -= size
        return context

    async def save(self, briefing, items, chapters, claims):
        """Stage memory alongside the successful briefing transaction; caller commits."""
        if briefing.status != 'completed':
            return {}
        stories = (await self.db.execute(select(Story).where(
            Story.user_id == briefing.user_id, Story.profile_id == briefing.profile_id
        ))).scalars().all()
        by_id = {s.id: s for s in stories}
        by_title = {_normal(s.title): s for s in stories}
        existing = (await self.db.execute(select(StoryDevelopment).where(
            StoryDevelopment.briefing_id == briefing.id
        ))).scalars().all()
        by_article = {d.article_index: d for d in existing}
        chapter_map = {}
        for idx, news in enumerate(items):
            key = getattr(news, 'story_key', None) or news.title
            story = by_id.get(key) or by_title.get(_normal(key))
            if not story:
                # IDs outside the owning scope are never used as references.
                try:
                    uuid.UUID(key)
                except ValueError:
                    pass
                else:
                    continue
                story = Story(user_id=briefing.user_id, profile_id=briefing.profile_id, title=key[:500])
                self.db.add(story)
                await self.db.flush()
                by_id[story.id] = story
                by_title[_normal(story.title)] = story
            matches = [ci for ci, ch in enumerate(chapters) if ch.get('article_index') == idx
                       and ch.get('end_time') is not None and ch['end_time'] > ch.get('start_time', 0)]
            # Ambiguous associations do not create knowledge.
            ci = matches[0] if len(matches) == 1 else None
            development = by_article.get(idx)
            if development is None:
                development = StoryDevelopment(
                    story_id=story.id, briefing_id=briefing.id, article_index=idx, chapter_index=ci,
                    summary=getattr(news, 'development', None) or news.summary or news.title,
                    change_type=getattr(news, 'change_type', None) or 'new', claims=claims.get(idx, []),
                )
                self.db.add(development)
                story.updated_at = datetime.utcnow()
            if ci is not None:
                chapter_map[str(ci)] = {
                    'story_id': story.id, 'title': story.title, 'development': development.summary,
                    'change_type': development.change_type, 'preference': story.preference,
                    'claims': development.claims,
                }
        await self.db.flush()
        return chapter_map

    async def set_preference(self, user_id, profile_id, story_id, preference):
        if preference not in ('normal', 'follow', 'less'):
            raise ValueError('Unknown story preference')
        story = (await self.db.execute(select(Story).where(
            Story.id == story_id, Story.user_id == user_id, Story.profile_id == profile_id
        ))).scalar_one_or_none()
        if story is None:
            return None
        story.preference = preference
        await self.db.commit()
        return preference
