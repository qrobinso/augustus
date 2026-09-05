"""Briefing service for generating daily audio briefings."""

import asyncio
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.briefing import Briefing
from app.models.custom_site import CustomSite
from app.models.topic import Topic
from app.models.user import User
from app.models.cast import Cast
from app.models.article import Article
from app.services.cast import CastService
from app.services.llm.openrouter import get_llm_provider
from app.services.llm.agents.orchestrator import BriefingOrchestrator
from app.services.tts.factory import TTSFactory
from app.services.tts.style import build_delivery_style, strip_inert_tags
from app.services.news import get_news_service, filter_stale_items
from app.services.scraper import get_scraper_service
from app.services.search import get_search_service
from app.utils.timezone import utc_now, local_now, format_local_datetime
from app.utils.audio import embed_chapters_in_mp3
from app.services.cancellation import (
    BriefingCancelledException,
    BriefingTimeoutException,
    register as cancel_register,
    unregister as cancel_unregister,
    is_cancelled as cancel_is_cancelled,
)
from app.services.search import SearchService
from app.services.web_research import select_stories_for_research, merge_sources
from app.services.story_memory import StoryMemoryService, select_story_updates
from app.services.evidence import attribute_claims, collect_claims
from app.services.breakout import research_breakout

settings = get_settings()


# Re-export exceptions for backward compatibility
__all__ = ["BriefingService", "BriefingCancelledException", "BriefingTimeoutException"]


class BriefingService:
    """Service for generating daily audio briefings."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = get_llm_provider()
        self.orchestrator = BriefingOrchestrator(self.llm)
        self.news = get_news_service()
        self.search = get_search_service()
    
    async def _check_cancelled(self, briefing_id: str) -> None:
        """Check if briefing has been cancelled and raise exception if so.

        Uses the in-memory cancellation event for a fast path before
        falling back to a database check.

        Args:
            briefing_id: The briefing ID to check

        Raises:
            BriefingCancelledException: If the briefing has been cancelled
        """
        # Fast path: check in-memory event first (no DB query)
        if cancel_is_cancelled(briefing_id):
            raise BriefingCancelledException("Briefing was cancelled by user")

        status = await self.db.scalar(
            select(Briefing.status).where(Briefing.id == briefing_id)
        )
        if status == "cancelled":
            raise BriefingCancelledException("Briefing was cancelled by user")
    
    async def create_briefing(
        self,
        user_id: str,
        profile_id: Optional[str] = None,
        topic_ids: Optional[list[str]] = None,
        max_duration_minutes: int = 10,
        name: Optional[str] = None,
        initial_status: str = "pending",
        cast_id: Optional[str] = None,
        profile_name: Optional[str] = None,
    ) -> Briefing:
        """Create a new briefing record.
        
        Args:
            user_id: The user ID creating the briefing
            profile_id: The profile ID creating the briefing
            topic_ids: List of topic IDs to include in the briefing
            max_duration_minutes: Target duration in minutes
            name: Optional name for the briefing (used for scheduled briefings)
            initial_status: Initial status for the briefing (pending, queued)
        """
        # Use local time for the title display
        local_date = local_now()
        date_str = local_date.strftime('%B %d, %Y')
        
        # Use provided name if available, otherwise generate a descriptive title based on topics
        if name:
            title = name
        else:
            title = await self._generate_briefing_title(user_id, topic_ids, date_str)
        
        briefing = Briefing(
            id=str(uuid.uuid4()),
            user_id=user_id,
            profile_id=profile_id,
            title=title,
            status=initial_status,
            cast_id=cast_id,
            extra_data={
                "topic_ids": topic_ids or [],
                "target_duration": max_duration_minutes,
                "max_duration": max_duration_minutes,
                "profile_name": profile_name,
            },
        )
        
        self.db.add(briefing)
        await self.db.commit()
        await self.db.refresh(briefing)
        
        return briefing
    
    async def _generate_briefing_title(
        self,
        user_id: str,
        topic_ids: Optional[list[str]],
        date_str: str,
    ) -> str:
        """Generate a descriptive title for the briefing based on topics.
        
        Args:
            user_id: The user ID
            topic_ids: List of topic IDs to include
            date_str: Formatted date string
            
        Returns:
            A descriptive title string
        """
        if not topic_ids:
            return f"Daily Briefing - {date_str}"
        
        # Fetch topic names from the database
        result = await self.db.execute(
            select(Topic)
            .where(Topic.id.in_(topic_ids))
            .where(Topic.user_id == user_id)
        )
        topics = result.scalars().all()
        
        if not topics:
            return f"Daily Briefing - {date_str}"
        
        topic_names = [t.name for t in topics]
        
        # Format title based on number of topics
        if len(topic_names) == 1:
            return f"{topic_names[0]} Briefing - {date_str}"
        elif len(topic_names) == 2:
            return f"{topic_names[0]} & {topic_names[1]} Briefing - {date_str}"
        elif len(topic_names) <= 4:
            # Join with commas and "& " for the last one
            return f"{', '.join(topic_names[:-1])} & {topic_names[-1]} - {date_str}"
        else:
            # Too many topics, just show count
            return f"{len(topic_names)}-Topic Briefing - {date_str}"
    
    async def generate_briefing(
        self,
        briefing_id: str,
        topic_ids: Optional[list[str]] = None,
        max_duration_minutes: Optional[int] = None,
        profile_name: Optional[str] = None,
    ) -> Briefing:
        """Run in the single execution slot shared by queued and scheduled work."""
        from app.services.briefing_queue import briefing_queue

        async with briefing_queue.generation_lock:
            return await self._generate_briefing_serialized(
                briefing_id, topic_ids, max_duration_minutes, profile_name,
            )

    async def _generate_briefing_serialized(
        self,
        briefing_id: str,
        topic_ids: Optional[list[str]] = None,
        max_duration_minutes: Optional[int] = None,
        profile_name: Optional[str] = None,
    ) -> Briefing:
        """Generate audio content for a briefing.
        
        Args:
            briefing_id: The briefing record ID
            topic_ids: List of topic IDs to include (uses stored topic_ids if not provided)
            max_duration_minutes: Target duration in minutes
            profile_name: Profile name for personalized greetings (overrides settings.user_name)
        """
        # Get briefing record with profile relationship loaded
        from sqlalchemy.orm import selectinload
        from app.models.profile import Profile
        result = await self.db.execute(
            select(Briefing)
            .options(selectinload(Briefing.profile))
            .where(Briefing.id == briefing_id)
            .execution_options(populate_existing=True)
        )
        briefing = result.scalar_one_or_none()
        
        if not briefing:
            raise ValueError(f"Briefing {briefing_id} not found")
        if briefing.status == "cancelled":
            raise BriefingCancelledException("Briefing was cancelled by user")
        if briefing.status not in ("pending", "queued"):
            return briefing
        
        # Use duration from extra_data if not provided, then fall back to settings
        if max_duration_minutes is None:
            max_duration_minutes = briefing.extra_data.get("target_duration")
        if max_duration_minutes is None:
            max_duration_minutes = get_settings().briefing_duration_minutes
        
        # Get topic_ids from extra_data if not provided
        if topic_ids is None:
            topic_ids = briefing.extra_data.get("topic_ids", [])
        
        print(f"[Briefing] Target duration: {max_duration_minutes} minutes")
        
        # Get timeout from settings
        timeout_minutes = get_settings().briefing_timeout_minutes
        timeout_seconds = timeout_minutes * 60
        
        try:
            # Wrap the entire generation in a timeout
            return await asyncio.wait_for(
                self._generate_briefing_internal(
                    briefing_id=briefing_id,
                    briefing=briefing,
                    topic_ids=topic_ids,
                    max_duration_minutes=max_duration_minutes,
                    profile_name=profile_name,
                ),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            # Timeout exceeded - mark briefing as failed
            # Note: We do NOT clear the queue here - other queued briefings should continue processing
            print(f"[Briefing] Generation timeout exceeded ({timeout_minutes} minutes) for briefing {briefing_id}")
            
            # Refresh briefing to get latest state
            await self.db.refresh(briefing)
            
            # Mark as failed with timeout error
            briefing.status = "failed"
            briefing.error_message = f"Briefing generation exceeded the app timeout ({timeout_minutes} minutes)"
            
            # Clear progress
            if briefing.extra_data:
                briefing.extra_data = {
                    **briefing.extra_data,
                    "progress": None,
                }
            
            await self.db.commit()
            
            # Don't clear the queue - let other queued briefings continue processing
            print(f"[Briefing] Marked briefing {briefing_id} as failed due to timeout (queue continues processing)")
            
            raise BriefingTimeoutException(f"Briefing generation exceeded timeout of {timeout_minutes} minutes")
    
    async def _generate_briefing_internal(
        self,
        briefing_id: str,
        briefing: Briefing,
        topic_ids: Optional[list[str]],
        max_duration_minutes: int,
        profile_name: Optional[str] = None,
    ) -> Briefing:
        """Internal method that performs the actual briefing generation.
        
        This is separated from generate_briefing to allow timeout wrapping.
        
        Args:
            briefing_id: The briefing record ID
            briefing: The briefing record
            topic_ids: List of topic IDs to include
            max_duration_minutes: Target duration in minutes
            profile_name: Profile name for personalized greetings
        """
        # Register cancellation event for this briefing
        cancel_register(briefing_id)
        try:
            requested_breakout = briefing.extra_data.get("kind") == "breakout"
            breakout_metadata = briefing.extra_data.get("breakout")
            if requested_breakout and not isinstance(breakout_metadata, dict):
                raise ValueError("Breakout is missing breakout metadata; refusing to run the daily pipeline.")
            is_breakout = requested_breakout

            # Update status and initialize progress
            # Cancellation may arrive after selection but before this update.
            claimed = await self.db.execute(
                update(Briefing).where(
                    Briefing.id == briefing_id,
                    Briefing.status.in_(["pending", "queued"]),
                ).values(status="generating")
            )
            await self.db.commit()
            await self.db.refresh(briefing)
            if not claimed.rowcount:
                if briefing.status == "cancelled":
                    raise BriefingCancelledException("Briefing was cancelled by user")
                return briefing
            await self._check_cancelled(briefing_id)
            total_steps = 8
            briefing.extra_data = {
                **briefing.extra_data,
                "progress": {
                    "step": 1,
                    "total_steps": total_steps,
                    "step_name": "Preparing breakout topic" if is_breakout else "Fetching news sources",
                    "percent": 0,
                },
            }
            await self.db.commit()
            
            # Helper to update progress
            async def update_progress(step: int, step_name: str, percent: int = None):
                # Check if cancelled
                await self._check_cancelled(briefing_id)
                
                # Calculate percent based on step if not provided
                if percent is None:
                    percent = int((step - 1) / total_steps * 100)
                
                briefing.extra_data = {
                    **briefing.extra_data,
                    "progress": {
                        "step": step,
                        "total_steps": total_steps,
                        "step_name": step_name,
                        "percent": percent,
                    },
                }
                await self.db.commit()

            # Look up topic names from IDs and check use_newsapi settings
            topics_data = (
                []
                if is_breakout
                else await self._get_topics_data(briefing.user_id, topic_ids)
            )
            topic_names = (
                [str(breakout_metadata.get("topic") or "").strip()]
                if is_breakout
                else [t.name for t in topics_data]
            )
            topic_names = [name for name in topic_names if name]
            # Only include topic names for topics that have use_newsapi=True
            newsapi_topic_names = [t.name for t in topics_data if t.use_newsapi]
            # Check if any topic has use_newsapi enabled
            any_use_newsapi = (
                False
                if is_breakout
                else (any(t.use_newsapi for t in topics_data) if topics_data else True)
            )
            print(f"[Briefing] Topics: {topic_names}")
            print(f"[Briefing] Topics with NewsAPI enabled: {newsapi_topic_names}")
            
            # Step 1: Fetch news from RSS feeds (only if at least one topic has use_newsapi=True)
            # RSS feeds are external sources like NewsAPI, so they should be excluded when user wants only custom sites
            rss_items = []
            if is_breakout:
                await update_progress(1, "Preparing breakout topic", 5)
            elif any_use_newsapi:
                await update_progress(1, "Fetching RSS feeds", 5)
                await self._check_cancelled(briefing_id)
                print("[Briefing] Fetching news from RSS feeds...")
                rss_items = await self.news.fetch_all_feeds()
                await self._check_cancelled(briefing_id)
            else:
                await update_progress(1, "Skipping RSS feeds (only using custom sites)", 5)
                print("[Briefing] Skipping RSS feeds - all topics have use_newsapi=False (using custom sites only)")
            
            # Step 2: Fetch from NewsAPI (only if at least one topic has use_newsapi=True)
            newsapi_items = []
            if is_breakout:
                await update_progress(2, "Planning the deep dive", 20)
            elif newsapi_topic_names:
                await update_progress(2, "Fetching news from NewsAPI", 20)
                await self._check_cancelled(briefing_id)
                print("[Briefing] Fetching news from NewsAPI...")
                fetched_newsapi_items = await self.news.fetch_newsapi(topics=newsapi_topic_names)
                await self._check_cancelled(briefing_id)
                
                # Filter NewsAPI items to ensure they only match topics with use_newsapi=True
                # NewsAPI items have category set to topic name (lowercase)
                allowed_categories = {t.name.lower() for t in topics_data if t.use_newsapi}
                newsapi_items = [
                    item for item in fetched_newsapi_items
                    if item.category and item.category.lower() in allowed_categories
                ]
                print(f"[Briefing] Filtered NewsAPI items: {len(fetched_newsapi_items)} fetched, {len(newsapi_items)} allowed")
            else:
                await update_progress(2, "Skipping NewsAPI (disabled for all topics)", 20)
                print("[Briefing] Skipping NewsAPI - all topics have use_newsapi=False")
            
            # Step 3: Fetch from custom sites
            if is_breakout:
                custom_site_items, custom_site_url_to_topic_id = [], {}
            else:
                await update_progress(3, "Fetching custom sites", 35)
                await self._check_cancelled(briefing_id)
                print("[Briefing] Fetching from custom sites...")
                custom_site_items, custom_site_url_to_topic_id = await self._fetch_custom_site_articles(
                    briefing.user_id,
                    topic_ids,
                    briefing_id=briefing_id,
                )
                await self._check_cancelled(briefing_id)
                print(f"[Briefing] Found {len(custom_site_items)} articles from custom sites")
            
            # Combine articles from all sources
            # Note: 
            # - custom_site_items: Already filtered by topic_ids (only includes sites for selected topics)
            # - newsapi_items: Filtered to only include topics with use_newsapi=True (empty if all topics have use_newsapi=False)
            # - rss_items: Global RSS feeds (only included if at least one topic has use_newsapi=True)
            all_items = custom_site_items + newsapi_items + rss_items
            
            # Build URL to topic_id mapping for later use when saving ranked articles
            # This allows us to save only articles that were actually used in the podcast script
            url_to_topic_id = {}
            url_to_topic_id.update(custom_site_url_to_topic_id)  # Add custom site mappings
            
            topic_name_to_id = {t.name.lower(): t.id for t in topics_data}
            
            # Map NewsAPI items by category (category is set to topic name lowercase)
            for item in newsapi_items:
                if item.url and item.category:
                    topic_id = topic_name_to_id.get(item.category.lower())
                    if topic_id:
                        url_to_topic_id[item.url] = topic_id
            
            # Map RSS items to first topic (if available)
            default_topic_id = topics_data[0].id if topics_data else None
            for item in rss_items:
                if item.url and default_topic_id:
                    url_to_topic_id[item.url] = default_topic_id
            
            # Drop clearly stale items before the editor sees them (undated items are kept but flagged)
            before_stale = len(all_items)
            all_items = filter_stale_items(all_items, max_age_days=settings.article_max_age_days)
            if before_stale != len(all_items):
                print(f"[Briefing] Dropped {before_stale - len(all_items)} items older than {settings.article_max_age_days} days")

            # The article cache is shared ingestion state, not a listener's memory.
            # Remove only exact duplicate URLs within this fetch; the editor groups events.
            seen_urls = set()
            news_items = []
            for item in all_items:
                if item.url and item.url not in seen_urls:
                    seen_urls.add(item.url)
                    news_items.append(item)

            # The editor selects at most N stories, stack-ranked; fewer is fine.
            target_story_count = settings.briefing_story_count
            topic_descriptions = {t.name: t.description for t in topics_data if t.description}
            print(f"[Briefing] Target: up to {target_story_count} stories (stack-ranked in priority order)")

            memory_service = None if is_breakout else StoryMemoryService(self.db)
            story_memory = (
                []
                if is_breakout
                else await memory_service.context(briefing.user_id, briefing.profile_id)
            )
            # Personal context replaces the old exact-topic/generated-episode lookup.
            recent_articles, last_script, prior_titles = [], None, []
            if is_breakout:
                await update_progress(4, "Researching breakout topic", 50)
                breakout_research = await research_breakout(
                    search=self.search,
                    topic=breakout_metadata.get("topic", ""),
                    focus=breakout_metadata.get("focus", ""),
                    source_context=breakout_metadata.get("source_context", ""),
                    check_cancelled=lambda: self._check_cancelled(briefing_id),
                )
                ranked_items = []
                analysis_summary, raw_analysis, story_analysis_usage = None, "", {}
                news_content = breakout_research.content
                briefing.sources = breakout_research.sources
            elif news_items:
                await update_progress(4, "Selecting new developments", 50)
                ranked_items, analysis_summary, raw_analysis, story_analysis_usage = await self._analyze_and_rank_stories(
                    briefing_id=briefing_id, news_items=news_items,
                    topics=topic_names or ["technology", "business", "science"],
                    max_stories=target_story_count, topic_descriptions=topic_descriptions,
                    story_memory=story_memory,
                )
            else:
                ranked_items, analysis_summary, raw_analysis, story_analysis_usage = [], None, "", {}
            if not ranked_items and not is_breakout:
                briefing.title = "No new developments"
                briefing.transcript = "No qualifying developments were found in the available sources for your selected topics."
                briefing.status = "completed"
                briefing.generated_at = utc_now()
                briefing.sources = []
                briefing.extra_data = {**briefing.extra_data, "empty_reason": "no_qualifying_developments",
                    "stories_selected": 0, "stories_analyzed": len(news_items), "chapters": [],
                    "chapter_stories": {}, "progress": {"step": 8, "total_steps": 8, "percent": 100,
                    "step_name": "No qualifying developments"}}
                await self.db.commit()
                await self.db.refresh(briefing)
                return briefing
            # A quiet day earns a shorter episode, not padding to the full budget.
            if not is_breakout:
                requested_duration = max_duration_minutes
                max_duration_minutes = min(requested_duration, max(1, round(
                    requested_duration * len(ranked_items) / max(1, target_story_count))))

            # Format the prioritized stories for the podcast prompt
            # Use all ranked items (should be 3-5 stories)
            if not is_breakout:
                news_content = self.news.format_news_for_briefing(ranked_items, max_stories=len(ranked_items))
            
            # Store sources (the ranked/prioritized stories - should be 3-5)
            if not is_breakout:
                briefing.sources = [item.to_dict() for item in ranked_items]

            # NOTE: web-research sources are merged in AFTER _generate_additional_facts runs
            # (see the merge block below, after Step 5 returns)

            # Save ONLY the articles that were used in the podcast script (ranked_items)
            # Group by topic_id to save efficiently
            articles_by_topic = {}
            for item in ranked_items:
                if item.url:
                    topic_id = url_to_topic_id.get(item.url)
                    # Use None as key if topic_id not found (for articles without topic mapping)
                    if topic_id not in articles_by_topic:
                        articles_by_topic[topic_id] = []
                    articles_by_topic[topic_id].append(item)
            
            # Save articles grouped by topic_id
            for topic_id, items in articles_by_topic.items():
                await self._save_articles(items, topic_id=topic_id)
            
            saved_count = sum(len(items) for items in articles_by_topic.values())
            print(f"[Briefing] Saved {saved_count} articles that were used in the podcast script")
            
            # Step 5: Load cast for this briefing (needed by per-host research below)
            await update_progress(5, "Loading cast configuration", 60)
            cast_service = CastService(self.db)
            if briefing.cast_id:
                cast = await cast_service.get_cast(briefing.cast_id, briefing.user_id, briefing.profile_id)
                if not cast:
                    print(f"[Briefing] Cast {briefing.cast_id} not found, using default")
                    cast = await cast_service.get_default_cast(briefing.user_id, briefing.profile_id)
            else:
                cast = await cast_service.get_default_cast(briefing.user_id, briefing.profile_id)

            # Save the cast_id to the briefing so it can be looked up later
            if cast and not briefing.cast_id:
                briefing.cast_id = cast.id

            # Prepare cast members for prompt
            cast_members = []
            for member in sorted(cast.members, key=lambda m: m.order):
                cast_members.append({
                    "name": member.name,
                    "personality": member.personality,
                    "voice_id": member.voice_id,
                    "order": member.order,
                })

            print(f"[Briefing] Using cast '{cast.name}' with {len(cast_members)} member(s)")

            # Step 6: Gather additional facts for each article (or per-host research if enabled)
            await update_progress(6, "Gathering additional facts", 65)
            await self._check_cancelled(briefing_id)

            host_research = None
            raw_facts_response = ""
            facts_usage = {}
            if is_breakout:
                additional_facts = {}
                print("[Briefing] Breakout research is complete; skipping daily fact gathering")
            elif get_settings().host_research_enabled and len(cast_members) >= 1:
                print("[Briefing] Per-host research enabled — gathering host-specific research...")
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
                print("[Briefing] Generating additional facts for articles...")
                additional_facts, raw_facts_response, facts_usage = await self._generate_additional_facts(
                    briefing_id=briefing_id,
                    ranked_items=ranked_items,
                    topics=topic_names if topic_names else ["technology", "business", "science"],
                )
                await self._check_cancelled(briefing_id)
                print(f"[Briefing] Generated facts for {len(additional_facts)} articles")

                # Merge any web-research sources gathered during gap-fill into briefing.sources
                _research_sources = []
                for _item in ranked_items:
                    for _s in getattr(_item, "research_sources", []) or []:
                        _research_sources.append(_s)
                if _research_sources:
                    briefing.sources = merge_sources(briefing.sources, _research_sources)
                    print(f"[Briefing] Merged {len(_research_sources)} web-research source(s) into briefing.sources")

            story_claims = collect_claims(host_research)
            for index, item in enumerate(ranked_items):
                # Preserve the original reported summary alongside host evidence.
                baseline = attribute_claims([{"answer": item.summary, "evidence": [
                    {"url": item.url, "excerpt": (item.summary or "")[:1500]}]}],
                    [{"url": item.url, "title": item.source, "content": item.summary or ""}], "Source article")
                story_claims[index] = baseline + story_claims.get(index, [])
                if not host_research:
                    story_claims[index].extend(attribute_claims(
                        [{"answer": fact} for fact in additional_facts.get(index, [])], [], "Research"))

            # Step 7: Generate podcast script with LLM
            await update_progress(7, "Writing podcast script", 70)
            await self._check_cancelled(briefing_id)
            
            # Get profile name from profile if not provided
            # Always use profile name from the briefing's profile (never use settings.user_name)
            if not profile_name and briefing.profile:
                profile_name = briefing.profile.name
            
            # Use profile name for personalization (never fall back to settings.user_name)
            # If no profile name is available, use None (will result in generic greeting)
            user_name = profile_name if profile_name else None
            complexity = get_settings().conversation_complexity
            enable_non_speech_sounds = get_settings().enable_non_speech_sounds
            
            # Use orchestrator to write the briefing script
            response = await self.orchestrator.write_briefing_script(
                content=news_content,
                topics=topic_names if topic_names else ["technology", "business", "science"],
                cast_members=cast_members,
                duration=max_duration_minutes,
                user_name=user_name,
                complexity=complexity,
                additional_facts=additional_facts,
                ranked_items=ranked_items,
                cast_name=cast.name,
                cast_description=cast.description,
                briefing_title=briefing.title,
                recent_articles=recent_articles,
                last_script=last_script,
                prior_titles=prior_titles,
                enable_non_speech_sounds=enable_non_speech_sounds,
                briefing_id=briefing_id,
                host_research=host_research,
                breakout=breakout_metadata if is_breakout else None,
            )
            await self._check_cancelled(briefing_id)
            
            # Extract title and script from response
            content = response.content.strip()
            script = content
            title_match = None
            
            # Look for title in format "TITLE: [title]" (case-insensitive)
            # Try multiple patterns to be robust
            title_patterns = [
                r"^TITLE:\s*(.+?)(?:\n|$)",  # At start of content
                r"TITLE:\s*(.+?)(?:\n|$)",   # Anywhere in content
            ]
            
            for pattern in title_patterns:
                match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
                if match:
                    title_match = match.group(1).strip()
                    # Remove title line from script
                    script = re.sub(pattern, "", content, flags=re.IGNORECASE | re.MULTILINE).strip()
                    break
            
            # Update briefing title if found, otherwise keep the existing one
            if title_match and len(title_match) > 0:
                # Ensure title is not too long (max 60 chars for glanceability)
                title = title_match[:60] if len(title_match) > 60 else title_match
                briefing.title = title
                print(f"[Briefing] Updated title from LLM: {title}")
            else:
                print(f"[Briefing] No valid title found in LLM response, keeping existing title: {briefing.title}")
            
            # Extract chapters from script, or derive from stories if none found
            chapters = self._extract_chapters(script)
            
            # Drop markup no provider can voice (pause tags always; sound tags unless enabled)
            script = strip_inert_tags(script, keep_sounds=enable_non_speech_sounds)

            # Remove chapter markers from transcript before storing (keep clean transcript for display)
            clean_transcript = re.sub(r'\[CHAPTER:\s*.+?\]', '', script).strip()
            briefing.transcript = clean_transcript
            
            # If no chapters found in script, derive them from the stories
            if not chapters and ranked_items:
                chapters = self._derive_chapters_from_stories(ranked_items)
                print(f"[Briefing] Derived {len(chapters)} chapters from stories")
            
            # Parse script into segments using cast member names
            segments = self._parse_script(script, cast_members)
            
            # Build voice_map from cast members
            voice_map = {}
            host_mapping = {}  # Map cast member names to HOST1/HOST2/HOST3
            host_to_name = {}  # Map HOST1/HOST2/HOST3 to cast member names
            for i, member in enumerate(cast_members):
                host_key = f"HOST{i+1}"
                voice_map[host_key] = member["voice_id"]
                voice_map[member["name"]] = member["voice_id"]  # Also map by name
                host_mapping[member["name"]] = host_key
                host_to_name[host_key] = member["name"]
            
            print(f"[Briefing] Voice map: {voice_map}")
            
            # Step 8: Generate audio
            await update_progress(8, "Generating audio", 85)
            await self._check_cancelled(briefing_id)
            audio_filename = f"briefing_{briefing.id}.mp3"
            audio_path = Path(settings.audio_storage_path) / audio_filename
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                tts_result = await TTSFactory.synthesize_conversation(
                    script=segments,
                    output_path=audio_path,
                    voice_map=voice_map,  # Use cast voice IDs
                    briefing_id=briefing_id,
                    style_prompt=build_delivery_style(cast_members, cast.description),
                )
                await self._check_cancelled(briefing_id)
            except BriefingCancelledException:
                # Clean up partial audio file if cancelled
                if audio_path.exists():
                    try:
                        audio_path.unlink()
                        print(f"[Briefing] Cleaned up partial audio file: {audio_path}")
                    except Exception as e:
                        print(f"[Briefing] Failed to clean up audio file: {e}")
                raise
            
            # Build segment timings for the transcript
            segment_timings = []
            if tts_result.segment_timings:
                print(f"[Briefing] Building {len(tts_result.segment_timings)} segment timings...")
                for timing in tts_result.segment_timings:
                    segment_timings.append({
                        "index": timing.index,
                        "speaker": timing.speaker,
                        "text": timing.text,
                        "start_seconds": timing.start_seconds,
                        "end_seconds": timing.end_seconds,
                        "duration_seconds": timing.duration_seconds,
                    })
                print(f"[Briefing] Segment timings: {len(segment_timings)} segments saved")
            else:
                print("[Briefing] WARNING: No segment timings returned from TTS")
            
            # Map chapters to audio timestamps using segment timings
            if chapters and segment_timings:
                chapters = self._map_chapters_to_timestamps(chapters, script, segment_timings, tts_result.duration_seconds)
                print(f"[Briefing] Mapped {len(chapters)} chapters to timestamps")
            elif chapters:
                print(f"[Briefing] WARNING: Found {len(chapters)} chapters but no segment timings to map them")
            
            # Update briefing
            briefing.audio_filename = audio_filename
            # Embed ID3 chapters so external podcast players show them (new briefings only).
            try:
                if chapters:
                    embed_chapters_in_mp3(audio_path, chapters, title=briefing.title)
            except Exception as e:
                print(f"[Briefing] Chapter embedding skipped: {e}")
            briefing.duration_seconds = tts_result.duration_seconds
            briefing.status = "completed"
            briefing.generated_at = utc_now()
            
            # Calculate TTS cost
            tts_cost = self._calculate_tts_cost(
                tts_provider=settings.tts_provider,
                script=segments,
                duration_seconds=tts_result.duration_seconds,
            )
            
            # Calculate total costs
            costs = {
                "story_analysis": self._extract_cost(story_analysis_usage),
                "facts_gathering": self._extract_cost(facts_usage),
                "script_writing": self._extract_cost(response.usage),
                "tts_generation": tts_cost,
            }
            
            # Calculate total cost
            total_cost = sum(
                cost.get("cost", 0) if isinstance(cost, dict) else 0
                for cost in costs.values()
            )
            costs["total"] = total_cost
            
            chapter_sources = {}
            if is_breakout:
                for ci, _chapter in enumerate(chapters):
                    chapter_sources[str(ci)] = list(briefing.sources)
            else:
                for ci, chapter in enumerate(chapters):
                    si = chapter.get("article_index")
                    if type(si) is not int or not 0 <= si < len(ranked_items):
                        continue
                    item = ranked_items[si]
                    sources = [{"name": item.source or item.title, "url": item.url}]
                    for research in host_research or []:
                        sources.extend(source for source in research.sources if source.get("story_index") == si)
                    sources.extend(getattr(item, "research_sources", []) or [])
                    chapter_sources[str(ci)] = merge_sources([], sources)

            # Reassign extra_data to ensure SQLAlchemy detects the change
            # (in-place mutations like .update() aren't detected on JSON fields)
            new_extra_data = dict(briefing.extra_data) if briefing.extra_data else {}
            # Preserve topic_ids - use existing ones if present, otherwise use the ones passed in
            if "topic_ids" not in new_extra_data or not new_extra_data.get("topic_ids"):
                new_extra_data["topic_ids"] = topic_ids or []
            new_extra_data.update({
                "model": response.model,
                "usage": response.usage,
                "tts_voice": tts_result.voice_id,
                "segment_timings": segment_timings,
                "chapters": chapters,  # Store chapters with timestamps
                "chapter_sources": chapter_sources,  # Per-chapter source links for frontend
                "story_analysis": analysis_summary,
                "story_analysis_raw": raw_analysis,
                "story_analysis_usage": story_analysis_usage,
                "facts_analysis_raw": raw_facts_response,
                "facts_usage": facts_usage,
                "stories_analyzed": len(news_items),
                "stories_selected": len(ranked_items),
                "cast_member_names": host_to_name,  # Map HOST1/HOST2 to actual names
                "topic_ids": new_extra_data.get("topic_ids", topic_ids or []),  # Explicitly preserve topic_ids
                "costs": costs,  # Store all costs breakdown
            })
            new_extra_data["chapter_stories"] = (
                {}
                if is_breakout
                else await memory_service.save(briefing, ranked_items, chapters, story_claims)
            )
            new_extra_data["claim_evidence"] = {str(i): c for i, c in story_claims.items()}
            new_extra_data["editorial_duration_minutes"] = max_duration_minutes
            new_extra_data["progress"] = {"step": 8, "total_steps": 8, "percent": 100, "step_name": "Ready"}
            briefing.extra_data = new_extra_data

            await self.db.commit()
            await self.db.refresh(briefing)
            
            return briefing
        except BriefingCancelledException:
            # Briefing was cancelled - status already set to cancelled
            briefing.error_message = "Cancelled by user"
            await self.db.commit()
            raise
        except BriefingTimeoutException:
            # Timeout exception - already handled in generate_briefing
            raise
        except Exception as e:
            # Check if cancelled during exception handling
            result = await self.db.execute(
                select(Briefing).where(Briefing.id == briefing_id)
            )
            current = result.scalar_one_or_none()
            if current and current.status == "cancelled":
                briefing.error_message = "Cancelled by user"
                briefing.status = "cancelled"
            else:
                briefing.status = "failed"
                briefing.error_message = str(e)
            await self.db.commit()
            raise
        finally:
            # Always unregister the cancellation event to prevent memory leaks
            cancel_unregister(briefing_id)

    def _parse_script(self, script: str, cast_members: list[dict] | None = None) -> list[dict]:
        """Parse podcast script into speaker segments.
        
        Args:
            script: The script text to parse
            cast_members: List of cast members with 'name' and 'order' keys
            
        Returns:
            List of segments with 'speaker' and 'text' keys
        """
        # Remove chapter markers from script for parsing (they're extracted separately)
        clean_script = re.sub(r'\[CHAPTER:\s*.+?\]', '', script)
        segments = []
        
        if cast_members:
            # Build pattern from cast member names
            cast_names = [m["name"] for m in sorted(cast_members, key=lambda x: x["order"])]
            # Escape names for regex
            escaped_names = [re.escape(name) for name in cast_names]
            # Create pattern: NAME: or NAME: (case-insensitive)
            pattern_parts = "|".join(escaped_names)
            pattern = rf'^({pattern_parts}):\s*(.+?)(?=^({pattern_parts}):|\Z)'
            
            matches = re.findall(pattern, clean_script, re.MULTILINE | re.DOTALL | re.IGNORECASE)
            
            # Map cast member names to HOST identifiers
            name_to_host = {}
            for i, member in enumerate(sorted(cast_members, key=lambda x: x["order"])):
                name_to_host[member["name"]] = f"HOST{i+1}"
            
            if matches:
                for match in matches:
                    # match is a tuple: (speaker_name, text, next_speaker_or_empty)
                    speaker_name = match[0]
                    text = match[1].strip()
                    if text:
                        # Map cast member name to HOST identifier for TTS
                        # Case-insensitive match back to the canonical cast name
                        canonical = next((n for n in name_to_host if n.lower() == speaker_name.lower()), speaker_name)
                        host_id = name_to_host.get(canonical, "HOST1")
                        segments.append({
                            "speaker": host_id,
                            "name": canonical,
                            "text": text,
                        })
            else:
                # Fallback: treat entire script as first host
                if cast_members:
                    segments.append({
                        "speaker": "HOST1",
                        "text": clean_script,
                    })
                else:
                    segments.append({
                        "speaker": "HOST1",
                        "text": clean_script,
                    })
        else:
            # Legacy parsing for backward compatibility
            pattern = r'^(HOST[12]):\s*(.+?)(?=^HOST[12]:|\Z)'
            matches = re.findall(pattern, clean_script, re.MULTILINE | re.DOTALL)
            
            if matches:
                for speaker, text in matches:
                    text = text.strip()
                    if text:
                        segments.append({
                            "speaker": speaker,
                            "text": text,
                        })
            else:
                # Fallback: treat entire script as single speaker
                segments.append({
                    "speaker": "HOST1",
                    "text": clean_script,
                })
        
        return segments
    
    def _extract_chapters(self, script: str) -> list[dict]:
        """Extract chapter markers from script.
        
        Args:
            script: The script text to parse
            
        Returns:
            List of chapters with title and start_time (will be mapped to timestamps later)
        """
        chapters = []
        
        # Find all chapter markers
        pattern = r'\[CHAPTER:\s*(.+?)\]'
        matches = re.finditer(pattern, script)
        
        for match in matches:
            label = match.group(1).strip()
            numbered = re.match(r"^(\d+)\s*\|\s*(.+)$", label)
            chapter = {"title": numbered.group(2).strip() if numbered else label,
                       "start_time": 0.0, "end_time": None}
            if numbered and int(numbered.group(1)) > 0:
                chapter["article_index"] = int(numbered.group(1)) - 1
            chapters.append(chapter)
        
        return chapters
    
    def _derive_chapters_from_stories(self, ranked_items: list) -> list[dict]:
        """Derive chapters from the stories included in the briefing.
        
        Args:
            ranked_items: List of NewsItem objects that were included in the briefing
            
        Returns:
            List of chapters with titles derived from story titles
        """
        chapters = []
        
        for item in ranked_items:
            # Use the story title as the chapter title (truncate if too long)
            title = item.title
            if len(title) > 60:
                title = title[:57] + "..."
            
            chapters.append({
                "title": title,
                "start_time": 0.0,  # Will be mapped to timestamps later
                "end_time": None,
            })
        
        return chapters
    
    def _map_chapters_to_timestamps(
        self, 
        chapters: list[dict], 
        script: str, 
        segment_timings: list[dict],
        duration_seconds: float
    ) -> list[dict]:
        """Map chapter markers to actual audio timestamps using segment timings.
        
        Args:
            chapters: List of chapters with title and start_time=0.0
            script: The original script text
            segment_timings: List of segment timing dicts with start_seconds, end_seconds, text
            duration_seconds: Total duration of the audio
            
        Returns:
            List of chapters with updated start_time and end_time
        """
        if not chapters or not segment_timings:
            return chapters
        pattern = r'\[CHAPTER:\s*(.+?)\]'
        normalize = lambda text: re.sub(r"\s+", " ", text).strip()
        clean_script = normalize(re.sub(pattern, '', script))
        spans, cursor = [], 0
        for segment in segment_timings:
            text = normalize(segment.get("text", ""))
            pos = clean_script.find(text, cursor) if text else -1
            if pos >= 0:
                spans.append((pos, pos + len(text), segment))
                cursor = pos + len(text)
        markers = list(re.finditer(pattern, script))
        mapped = []
        measured_starts = []
        for index, original in enumerate(chapters):
            chapter = dict(original)
            if index < len(markers):
                prefix = re.sub(pattern, '', script[:markers[index].start()])
                target = len(normalize(prefix))
                span = next(((start, end, seg) for start, end, seg in spans if end > target), None)
                # A marker embedded within one TTS turn has no measured boundary.
                # Do not count the pre-marker portion as exposure to this story.
                segment = span[2] if span and span[0] >= target else None
            else:
                segment = None
            measured_starts.append(segment is not None)
            if segment is None:
                # Navigation remains available, but estimated identity never earns exposure.
                chapter.pop("article_index", None)
                chapter["start_time"] = duration_seconds * index / len(chapters)
            else:
                chapter["start_time"] = segment.get("start_seconds", 0.0)
            mapped.append(chapter)
        for index, chapter in enumerate(mapped):
            chapter["end_time"] = mapped[index + 1]["start_time"] if index + 1 < len(mapped) else duration_seconds
            if index + 1 < len(mapped) and not measured_starts[index + 1]:
                # A story needs measured boundaries at both ends before its
                # playback interval can establish listener knowledge.
                chapter.pop("article_index", None)
        return mapped

    async def get_briefing(self, briefing_id: str) -> Optional[Briefing]:
        """Get a briefing by ID."""
        result = await self.db.execute(
            select(Briefing).where(Briefing.id == briefing_id)
        )
        return result.scalar_one_or_none()
    
    async def _get_last_matching_briefing(
        self,
        user_id: str,
        topic_ids: Optional[list[str]],
        exclude_briefing_id: Optional[str] = None,
    ) -> Optional[Briefing]:
        """Find the most recent completed briefing whose topics exactly match topic_ids."""
        if not topic_ids or len(topic_ids) == 0:
            return None

        # Get all completed briefings for this user with transcripts
        query = select(Briefing).where(
            Briefing.user_id == user_id,
            Briefing.status == "completed",
            Briefing.transcript.isnot(None),
        )

        # Exclude current briefing if provided
        if exclude_briefing_id:
            query = query.where(Briefing.id != exclude_briefing_id)

        # Order by generated_at descending (most recent first)
        query = query.order_by(Briefing.generated_at.desc())

        result = await self.db.execute(query)
        all_briefings = result.scalars().all()

        # Filter to exact topic_ids match
        topic_set = set(topic_ids)
        for briefing in all_briefings:
            briefing_topic_ids = briefing.extra_data.get("topic_ids", [])
            if not isinstance(briefing_topic_ids, list):
                briefing_topic_ids = []

            # Check for exact match (same set of topics)
            if set(briefing_topic_ids) == topic_set and briefing.transcript:
                return briefing

        return None

    async def get_last_script_for_topics(
        self,
        user_id: str,
        topic_ids: Optional[list[str]],
        exclude_briefing_id: Optional[str] = None,
    ) -> Optional[str]:
        """Get the transcript from the most recent completed briefing with matching topic_ids.

        Args:
            user_id: The user ID
            topic_ids: List of topic IDs to match (must match exactly)
            exclude_briefing_id: Optional briefing ID to exclude from results

        Returns:
            The transcript text, or None if no matching briefing found
        """
        briefing = await self._get_last_matching_briefing(user_id, topic_ids, exclude_briefing_id)
        return briefing.transcript if briefing else None

    async def get_last_story_titles_for_topics(
        self,
        user_id: str,
        topic_ids: Optional[list[str]],
        exclude_briefing_id: Optional[str] = None,
    ) -> list[str]:
        """Get the story titles covered by the most recent matching briefing.

        Returns a precise list of what the previous briefing discussed (from its
        saved sources), used to tell the writer what NOT to repeat. Preferred over
        feeding back the raw transcript tail.
        """
        briefing = await self._get_last_matching_briefing(user_id, topic_ids, exclude_briefing_id)
        if not briefing or not briefing.sources:
            return []
        return [
            s["title"]
            for s in briefing.sources
            if isinstance(s, dict) and s.get("title")
        ]
    
    async def list_briefings(
        self,
        user_id: str,
        profile_id: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
        listened: Optional[bool] = None,
        cast_id: Optional[str] = None,
        topic_ids: Optional[list[str]] = None,
        favorite: Optional[bool] = None,
        q: Optional[str] = None,
    ) -> tuple[list[Briefing], int]:
        """List briefings for a user/profile.
        
        Args:
            user_id: User ID
            profile_id: Profile ID (if provided, filters by profile)
            limit: Maximum number of results
            offset: Number of results to skip
            listened: Optional filter by listened status
            cast_id: Optional filter by cast ID
            topic_ids: Optional filter by topic IDs (briefings must contain at least one of these topics)
            favorite: Optional filter by favorite status
            q: Optional text search across title and transcript (case-insensitive)
        """
        # Build query
        query = select(Briefing).where(Briefing.user_id == user_id)
        
        if profile_id:
            # Include briefings for this profile OR briefings with NULL profile_id (legacy)
            from sqlalchemy import or_
            query = query.where(
                or_(
                    Briefing.profile_id == profile_id,
                    Briefing.profile_id.is_(None)
                )
            )
        
        # Apply listened filter if provided
        if listened is not None:
            query = query.where(Briefing.listened == listened)
        
        # Apply cast_id filter if provided
        if cast_id is not None:
            query = query.where(Briefing.cast_id == cast_id)
        
        # Apply favorite filter if provided
        if favorite is not None:
            query = query.where(Briefing.favorite == favorite)
        
        # Get all matching briefings (before topic_ids filter)
        result = await self.db.execute(
            query.order_by(Briefing.created_at.desc())
        )
        all_briefings = result.scalars().all()
        
        # Apply topic_ids filter if provided (filter in Python since topic_ids is in JSON)
        if topic_ids and len(topic_ids) > 0:
            filtered_briefings = []
            for briefing in all_briefings:
                briefing_topic_ids = briefing.extra_data.get("topic_ids", [])
                # Ensure briefing_topic_ids is a list
                if not isinstance(briefing_topic_ids, list):
                    briefing_topic_ids = []
                # Convert to sets for easier comparison
                briefing_topic_set = set(briefing_topic_ids)
                filter_topic_set = set(topic_ids)
                # Only include briefings that have at least one matching topic
                # Exclude briefings with no topics when filtering
                if briefing_topic_set and briefing_topic_set.intersection(filter_topic_set):
                    filtered_briefings.append(briefing)
            all_briefings = filtered_briefings
        
        # Apply text search across title + transcript if provided
        if q and q.strip():
            search_term = q.strip().lower()
            filtered_by_q = []
            for briefing in all_briefings:
                title_match = search_term in (briefing.title or "").lower()
                transcript_match = search_term in (briefing.transcript or "").lower()
                if title_match or transcript_match:
                    filtered_by_q.append(briefing)
            all_briefings = filtered_by_q

        # Get total count
        total = len(all_briefings)

        # Apply pagination
        briefings = all_briefings[offset:offset + limit]
        
        return list(briefings), total
    
    async def delete_briefing(self, briefing_id: str) -> bool:
        """Delete a briefing and its associated articles."""
        result = await self.db.execute(
            select(Briefing).where(Briefing.id == briefing_id)
        )
        briefing = result.scalar_one_or_none()
        
        if not briefing:
            return False
        
        # Delete associated articles by URL from briefing sources
        if briefing.sources and isinstance(briefing.sources, list):
            # Extract URLs from sources
            urls = []
            for source in briefing.sources:
                if isinstance(source, dict) and 'url' in source:
                    urls.append(source['url'])
                elif hasattr(source, 'url'):
                    urls.append(source.url)
            
            if urls:
                # Delete articles with matching URLs
                articles_result = await self.db.execute(
                    select(Article).where(Article.url.in_(urls))
                )
                articles_to_delete = articles_result.scalars().all()
                
                for article in articles_to_delete:
                    await self.db.delete(article)
                
                if articles_to_delete:
                    print(f"[Briefing] Deleted {len(articles_to_delete)} articles associated with briefing {briefing_id}")
        
        # Delete audio file if exists
        if briefing.audio_filename:
            audio_path = Path(settings.audio_storage_path) / briefing.audio_filename
            if audio_path.exists():
                audio_path.unlink()
        
        await self.db.delete(briefing)
        await self.db.commit()
        
        return True
    
    async def update_listened_status(
        self,
        briefing_id: str,
        listened: bool,
    ) -> Optional[Briefing]:
        """Update the listened status of a briefing."""
        result = await self.db.execute(
            select(Briefing).where(Briefing.id == briefing_id)
        )
        briefing = result.scalar_one_or_none()
        
        if not briefing:
            return None
        
        briefing.listened = listened
        briefing.listened_at = datetime.utcnow() if listened else None
        
        await self.db.commit()
        await self.db.refresh(briefing)
        
        return briefing
    
    async def update_playback_position(
        self,
        briefing_id: str,
        position: float,
    ) -> Optional[Briefing]:
        """Update the playback position of a briefing.
        
        Args:
            briefing_id: The briefing ID
            position: Playback position in seconds
            
        Returns:
            Updated briefing or None if not found
        """
        result = await self.db.execute(
            select(Briefing).where(Briefing.id == briefing_id)
        )
        briefing = result.scalar_one_or_none()
        
        if not briefing:
            return None
        
        briefing.playback_position = position
        
        await self.db.commit()
        await self.db.refresh(briefing)
        
        return briefing
    
    async def update_favorite_status(
        self,
        briefing_id: str,
        favorite: bool,
    ) -> Optional[Briefing]:
        """Update the favorite status of a briefing."""
        result = await self.db.execute(
            select(Briefing).where(Briefing.id == briefing_id)
        )
        briefing = result.scalar_one_or_none()
        
        if not briefing:
            return None
        
        briefing.favorite = favorite
        
        await self.db.commit()
        await self.db.refresh(briefing)
        
        return briefing
    
    async def has_briefing_in_progress(self, user_id: str, profile_id: Optional[str] = None) -> Optional[Briefing]:
        """Check if user/profile has a briefing currently being generated or queued.
        
        Args:
            user_id: The user ID to check
            profile_id: The profile ID to check (optional)
            
        Returns:
            The in-progress or queued briefing if one exists, None otherwise
        """
        query = select(Briefing).where(Briefing.user_id == user_id)
        
        if profile_id:
            query = query.where(Briefing.profile_id == profile_id)
        
        result = await self.db.execute(
            query
            .where(Briefing.status.in_(["pending", "generating", "queued"]))
            .order_by(Briefing.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def has_any_active_briefing(self) -> bool:
        """Check if any briefing globally is currently pending or generating.
        
        Returns:
            True if any briefing is currently being generated
        """
        result = await self.db.execute(
            select(Briefing)
            .where(Briefing.status.in_(["pending", "generating"]))
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
    
    async def get_next_queued_briefing(self) -> Optional[Briefing]:
        """Get the oldest queued briefing.
        
        Returns:
            The oldest queued briefing, or None if no queued briefings
        """
        result = await self.db.execute(
            select(Briefing)
            .where(Briefing.status == "queued")
            .order_by(Briefing.created_at.asc(), Briefing.id.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_active_briefings(self, user_id: str, profile_id: str) -> list[Briefing]:
        """Return this profile's complete generation queue, independent of history paging."""
        result = await self.db.scalars(
            select(Briefing).where(
                Briefing.user_id == user_id, Briefing.profile_id == profile_id,
                Briefing.status.in_(["queued", "pending", "generating"]),
            ).order_by(Briefing.created_at.asc(), Briefing.id.asc())
        )
        return list(result.all())

    async def cancel_briefing(self, briefing_id: str) -> Optional[Briefing]:
        """Cancel a briefing that is pending or generating.
        
        Args:
            briefing_id: The briefing ID to cancel
            
        Returns:
            The cancelled briefing if successful, None if not found
        """
        result = await self.db.execute(
            select(Briefing).where(Briefing.id == briefing_id)
        )
        briefing = result.scalar_one_or_none()
        
        if not briefing:
            return None
        
        if briefing.status not in ["pending", "generating", "queued"]:
            return briefing  # Already completed/failed/cancelled
        
        briefing.status = "cancelled"
        briefing.error_message = "Cancelled by user"
        
        # Clear progress
        if briefing.extra_data:
            briefing.extra_data = {
                **briefing.extra_data,
                "progress": None,
            }
        
        await self.db.commit()
        await self.db.refresh(briefing)
        
        return briefing
    
    async def _get_topics_data(
        self,
        user_id: str,
        topic_ids: list[str],
    ) -> list[Topic]:
        """Look up topic data from topic IDs.
        
        Args:
            user_id: The user ID
            topic_ids: List of topic IDs
            
        Returns:
            List of Topic objects
        """
        if not topic_ids:
            # If no topic IDs provided, get all active topics for the user
            result = await self.db.execute(
                select(Topic).where(
                    Topic.user_id == user_id,
                    Topic.is_active == True,
                )
            )
            topics = result.scalars().all()
            return list(topics)
        
        result = await self.db.execute(
            select(Topic).where(
                Topic.id.in_(topic_ids),
                Topic.user_id == user_id,
            )
        )
        topics = result.scalars().all()
        return list(topics)
    
    async def _get_topic_names(
        self,
        user_id: str,
        topic_ids: list[str],
    ) -> list[str]:
        """Look up topic names from topic IDs.
        
        Args:
            user_id: The user ID
            topic_ids: List of topic IDs
            
        Returns:
            List of topic names
        """
        topics = await self._get_topics_data(user_id, topic_ids)
        return [t.name for t in topics]
    
    async def _fetch_custom_site_articles(
        self,
        user_id: str,
        topic_ids: list[str],
        briefing_id: Optional[str] = None,
    ) -> tuple[list, dict[str, str]]:
        """Fetch articles from user's custom sites matching the given topic IDs.
        
        Args:
            user_id: The user ID to fetch custom sites for
            topic_ids: List of topic IDs to filter by
            
        Returns:
            Tuple of (list of NewsItem objects, dict mapping URL to topic_id)
        """
        # Build query for active custom sites
        query = (
            select(CustomSite)
            .options(selectinload(CustomSite.topic))
            .where(
                CustomSite.user_id == user_id,
                CustomSite.is_active == True,
            )
        )
        
        # Filter by topic_ids if provided
        if topic_ids:
            query = query.where(CustomSite.topic_id.in_(topic_ids))
        
        result = await self.db.execute(query)
        custom_sites = result.scalars().all()
        
        print(f"[Briefing] Found {len(custom_sites)} custom sites for topic_ids: {topic_ids}")
        
        if not custom_sites:
            return [], {}
        
        scraper = get_scraper_service()
        all_articles = []
        url_to_topic_id = {}  # Map URLs to topic_ids for custom site articles
        
        # Store site updates to apply after concurrent operations complete
        site_updates = {}  # site_id -> {last_fetched, last_error}
        
        # Fetch from all custom sites concurrently
        async def fetch_site(site: CustomSite):
            try:
                # Check for cancellation before fetching
                if briefing_id:
                    await self._check_cancelled(briefing_id)
                print(f"[Briefing] Fetching from custom site: {site.name} ({site.url})")
                
                # Check if this is a Reddit URL
                if self.news.is_reddit_url(site.url):
                    # Extract subreddit name and fetch using Reddit API
                    subreddit = self.news.extract_subreddit_name(site.url)
                    if subreddit:
                        print(f"[Briefing] Detected Reddit subreddit: r/{subreddit}, using Reddit API")
                        articles = await self.news.fetch_reddit_subreddit(
                            subreddit=subreddit,
                            max_age_days=3,
                            limit=25,
                        )
                        # Limit to 3 articles per site (same as scraper)
                        articles = articles[:3]
                    else:
                        print(f"[Briefing] Could not extract subreddit name from {site.url}, skipping")
                        articles = []
                else:
                    # Use topic name as category for the scraper
                    topic_name = site.topic.name.lower() if site.topic else "general"
                    articles = await scraper.fetch_site_articles(
                        url=site.url,
                        site_name=site.name,
                        category=topic_name,
                        max_articles=3,  # Limit per site
                    )
                
                # Check for cancellation after fetching
                if briefing_id:
                    await self._check_cancelled(briefing_id)
                print(f"[Briefing] Got {len(articles)} articles from {site.name}")
                
                # Map article URLs to topic_id for later saving
                site_url_mapping = {}
                if articles and site.topic_id:
                    for article in articles:
                        if article.url:
                            url_to_topic_id[article.url] = site.topic_id
                            site_url_mapping[article.url] = site.topic_id
                
                # Store update to apply later (avoid SQLAlchemy session conflicts)
                site_updates[site.id] = {
                    "last_fetched": datetime.utcnow(),
                    "last_error": None,
                }
                return articles, site_url_mapping
            except BriefingCancelledException:
                # Re-raise cancellation exceptions
                raise
            except Exception as e:
                print(f"[Briefing] Error fetching from {site.name}: {e}")
                # Store error update to apply later
                site_updates[site.id] = {
                    "last_fetched": datetime.utcnow(),
                    "last_error": str(e)[:500],
                }
                return [], {}
        
        # Run all fetches concurrently
        # Use return_exceptions=False so cancellation exceptions propagate immediately
        tasks = [fetch_site(site) for site in custom_sites]
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except BriefingCancelledException:
            # Re-raise cancellation exceptions immediately
            raise
        
        # Check if any task returned a cancellation exception
        if briefing_id:
            for result in results:
                if isinstance(result, BriefingCancelledException):
                    raise result
        
        # Collect results and merge URL-to-topic_id mappings
        merged_url_to_topic_id = {}
        for result in results:
            if isinstance(result, tuple) and len(result) == 2:
                articles, url_mapping = result
                if isinstance(articles, list):
                    all_articles.extend(articles)
                if isinstance(url_mapping, dict):
                    merged_url_to_topic_id.update(url_mapping)
            elif isinstance(result, list):
                # Fallback for old format (shouldn't happen, but be safe)
                all_articles.extend(result)
        
        # Apply site updates after all concurrent operations complete
        # This avoids SQLAlchemy session conflicts from modifying objects during concurrent operations
        if site_updates:
            for site_id, updates in site_updates.items():
                # Refresh the site object to ensure we have the latest state
                result = await self.db.execute(
                    select(CustomSite).where(CustomSite.id == site_id)
                )
                site = result.scalar_one_or_none()
                if site:
                    site.last_fetched = updates["last_fetched"]
                    site.last_error = updates["last_error"]
        
        # Commit the last_fetched updates
        await self.db.commit()
        
        return all_articles, merged_url_to_topic_id
    
    async def _analyze_and_rank_stories(
        self,
        briefing_id: str,
        news_items: list,
        topics: list[str],
        max_stories: int,
        topic_descriptions: Optional[dict[str, str]] = None,
        prior_titles: Optional[list[str]] = None,
        story_memory: Optional[list[dict]] = None,
    ) -> tuple[list, str | None, str, dict]:
        """Use the editor LLM to select and rank stories.

        The editor's selection is final: if it picks fewer than max_stories,
        that is the briefing. We never pad with articles it rejected. A
        malformed response is retried once, then raised so the failure is
        visible instead of silently producing an off-topic briefing.

        Returns:
            Tuple of (ranked_items, analysis_summary, raw_response, usage)
        """
        import json

        articles_for_analysis = [
            {
                "title": item.title,
                "summary": item.summary,
                "source": item.source,
                "category": item.category or "general",
                "url": item.url,
                "published": item.published.isoformat() if item.published else None,
            }
            for item in news_items
        ]

        last_error: Optional[Exception] = None
        for attempt in (1, 2):
            await self._check_cancelled(briefing_id)
            try:
                ranked_stories, summary, raw_response, usage = await self.orchestrator.analyze_and_rank_stories(
                    articles=articles_for_analysis,
                    topics=topics,
                    max_stories=max_stories,
                    briefing_id=briefing_id,
                    topic_descriptions=topic_descriptions,
                    prior_titles=prior_titles,
                    story_memory=story_memory,
                )
                ranked_items = select_story_updates(ranked_stories, news_items, story_memory, max_stories)
                break
            except (json.JSONDecodeError, ValueError) as e:
                last_error = e
                print(f"[Briefing] Story analysis attempt {attempt} returned unparseable output: {e}")
        else:
            raise ValueError(f"Story analysis failed twice; refusing to fall back to unfiltered articles: {last_error}")

        await self._check_cancelled(briefing_id)

        return ranked_items[:max_stories], summary, raw_response, usage
    
    async def _generate_additional_facts(
        self,
        briefing_id: str,
        ranked_items: list,
        topics: list[str],
    ) -> tuple[dict[int, list[str]], str, dict]:
        """Use LLM to generate additional quantifiable facts for each article.
        
        This method fetches the full article content from URLs to provide
        more interesting and detailed facts beyond what's in the summary.
        
        Args:
            ranked_items: List of ranked NewsItem objects
            topics: List of topic names (kept for compatibility, not used)
            
        Returns:
            Tuple of (facts_dict, raw_response, usage)
            facts_dict: Dictionary mapping article index (0-based) to lists of facts
            raw_response: Raw LLM response content
            usage: LLM usage data including cost information
        """
        import json
        
        # Fetch full article content for each article
        print(f"[Briefing] Fetching full article content for {len(ranked_items)} articles...")
        
        async def fetch_article_content(item, index: int):
            """Fetch full article content for a single article."""
            try:
                # Check for cancellation
                await self._check_cancelled(briefing_id)
                
                # Use existing content if available, otherwise fetch from URL
                article_content = None
                if hasattr(item, 'content') and item.content:
                    article_content = item.content
                elif item.url:
                    print(f"[Briefing] Fetching content for article {index + 1}: {item.title[:60]}...")
                    article_content = await self.search.fetch_page_content(item.url)
                    if article_content:
                        # Limit content length to avoid token limits (keep first 3000 chars)
                        article_content = article_content[:3000]
                
                return {
                    "title": item.title,
                    "summary": item.summary,
                    "source": item.source,
                    "category": item.category or "general",
                    "url": item.url,
                    "full_content": article_content,  # Full article text if available
                }
            except Exception as e:
                print(f"[Briefing] Warning: Could not fetch content for article {index + 1}: {e}")
                # Fallback to summary only
                return {
                    "title": item.title,
                    "summary": item.summary,
                    "source": item.source,
                    "category": item.category or "general",
                    "url": item.url,
                    "full_content": None,
                }
        
        # Fetch all articles concurrently (with cancellation checks)
        fetch_tasks = [fetch_article_content(item, i) for i, item in enumerate(ranked_items)]
        stories_for_analysis = await asyncio.gather(*fetch_tasks)
        
        try:
            # Check for cancellation before LLM call
            await self._check_cancelled(briefing_id)
            
            # Use orchestrator to gather facts
            facts_dict, raw_facts_response, facts_usage = await self.orchestrator.gather_additional_facts(
                stories=stories_for_analysis,
                briefing_id=briefing_id,
            )
            
            # Check for cancellation after LLM call
            await self._check_cancelled(briefing_id)
            
            # Log facts generated
            for idx, facts in facts_dict.items():
                if 0 <= idx < len(ranked_items):
                    print(f"[Briefing] Generated {len(facts)} facts for article {idx + 1}: {ranked_items[idx].title[:60]}...")

            # Gap-fill thin stories with live web research
            _settings = get_settings()
            if _settings.web_research_enabled:
                thin_indices = select_stories_for_research(
                    ranked_items,
                    facts_dict,
                    min_chars=_settings.web_research_min_content_chars,
                    min_facts=_settings.web_research_min_facts,
                    max_stories=_settings.web_research_max_stories,
                )
                if thin_indices:
                    print(f"[Briefing] {len(thin_indices)} thin story/stories identified for web research: {thin_indices}")
                    search = SearchService()
                    try:
                        for idx in thin_indices:
                            item = ranked_items[idx]
                            try:
                                research_text, sources = await search.research_topic(
                                    item.title, num_sources=3
                                )
                            except Exception as e:
                                print(
                                    f"[Briefing] Web research failed for '{getattr(item, 'title', '')}': {e}"
                                )
                                continue
                            if research_text:
                                item.content = (
                                    (getattr(item, "content", "") or "")
                                    + "\n\n[Web research]\n"
                                    + research_text
                                )
                            if sources:
                                item.research_sources = [
                                    {"name": s.title, "url": s.url} for s in sources
                                ]
                                print(
                                    f"[Briefing] Web research added {len(sources)} sources "
                                    f"for article {idx + 1}: {item.title[:60]}..."
                                )
                    finally:
                        await search.close()

            return facts_dict, raw_facts_response, facts_usage
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[Briefing] Warning: Failed to parse facts agent JSON: {e}")
            print(f"[Briefing] Falling back to empty facts")
            return {}, ""
        except Exception as e:
            print(f"[Briefing] Warning: Facts generation failed: {e}")
            print(f"[Briefing] Falling back to empty facts")
            return {}, ""
    
    async def _save_articles(
        self,
        news_items: list,
        topic_id: Optional[str] = None,
    ) -> None:
        """Save articles to the database.
        
        Args:
            news_items: List of NewsItem objects to save
            topic_id: Optional topic ID to associate articles with
        """
        if not news_items:
            return
        
        # Check for existing articles by URL to avoid duplicates
        urls = [item.url for item in news_items if item.url]
        if not urls:
            return
        
        result = await self.db.execute(
            select(Article).where(Article.url.in_(urls))
        )
        existing_articles = {article.url: article for article in result.scalars().all()}
        
        # Save new articles
        new_count = 0
        for item in news_items:
            if not item.url:
                continue
            
            # Skip if already exists
            if item.url in existing_articles:
                continue
            
            article = Article(
                id=str(uuid.uuid4()),
                title=item.title[:500],  # Ensure it fits in VARCHAR(500)
                summary=item.summary[:10000] if item.summary else None,  # Limit summary length
                url=item.url[:1000],  # Ensure it fits in VARCHAR(1000)
                source=item.source[:255] if item.source else "Unknown",
                author=item.author[:255] if item.author else None,
                content=item.content[:50000] if item.content else None,  # Limit content length
                image_url=item.image_url[:1000] if item.image_url else None,
                topic_id=topic_id,
                published=item.published,
                fetched_at=utc_now(),
            )
            self.db.add(article)
            new_count += 1
        
        if new_count > 0:
            await self.db.commit()
            print(f"[Briefing] Saved {new_count} new articles to database")
    
    async def _get_existing_article_urls(self, urls: list[str], since: Optional[datetime] = None) -> set[str]:
        """Return the subset of URLs already used in a briefing.

        Args:
            urls: URLs to check
            since: Only count articles fetched at or after this time. None = any time.
        """
        if not urls:
            return set()

        query = select(Article.url).where(Article.url.in_(urls))
        if since is not None:
            query = query.where(Article.fetched_at >= since)
        result = await self.db.execute(query)
        return {row[0] for row in result.fetchall()}
    
    async def _get_recent_articles_for_topics(
        self,
        topic_ids: list[str],
        limit: int = 5,
    ) -> list[dict]:
        """Get recent articles for the given topics for continuity context.
        
        Args:
            topic_ids: List of topic IDs to get articles for
            limit: Maximum number of articles to return per topic
            
        Returns:
            List of article dictionaries (for use in prompts)
        """
        if not topic_ids:
            return []
        
        # Get recent articles for each topic
        result = await self.db.execute(
            select(Article)
            .where(Article.topic_id.in_(topic_ids))
            .order_by(Article.fetched_at.desc())
            .limit(limit * len(topic_ids))  # Get more than needed, then dedupe
        )
        articles = result.scalars().all()
        
        # Convert to dict format for prompts
        recent_articles = []
        seen_urls = set()
        
        for article in articles:
            if article.url in seen_urls:
                continue
            seen_urls.add(article.url)
            
            recent_articles.append({
                "title": article.title,
                "summary": article.summary or "",
                "source": article.source,
                "url": article.url,
                "published": article.published.isoformat() if article.published else None,
                "fetched_at": article.fetched_at.isoformat() if article.fetched_at else None,
            })
            
            if len(recent_articles) >= limit:
                break
        
        return recent_articles
    
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

    def _extract_cost(self, usage: dict) -> dict:
        """Extract cost information from OpenRouter usage data.

        Args:
            usage: OpenRouter usage dict with cost information

        Returns:
            Dict with cost breakdown including cost, tokens, etc.
        """
        if not usage or not isinstance(usage, dict):
            return {"cost": 0.0, "tokens": 0, "details": {}}
        
        cost = usage.get("cost", 0.0)
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)
        cost_details = usage.get("cost_details", {})
        
        return {
            "cost": float(cost) if cost else 0.0,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_details": cost_details,
            "usage": usage,  # Store full usage for reference
        }
    
    def _calculate_tts_cost(
        self,
        tts_provider: str,
        script: list[dict],
        duration_seconds: float,
    ) -> dict:
        """Calculate TTS generation cost based on provider and usage.
        
        Args:
            tts_provider: TTS provider name ('piper', 'elevenlabs', 'gemini')
            script: List of script segments with 'text' keys
            duration_seconds: Audio duration in seconds
            
        Returns:
            Dict with cost information
        """
        total_chars = sum(len(seg.get("text", "")) for seg in script)
        
        if tts_provider == "piper":
            # Piper is free (local/self-hosted)
            return {
                "cost": 0.0,
                "provider": "piper",
                "characters": total_chars,
                "duration_seconds": duration_seconds,
            }
        elif tts_provider == "elevenlabs":
            # ElevenLabs pricing: varies by model
            # For eleven_turbo_v2_5: $0.18 per 1000 characters
            # For eleven_multilingual_v2: $0.30 per 1000 characters
            # For eleven_v3 (dialogue): $0.30 per 1000 characters
            # Using average/standard pricing - can be refined based on actual model used
            cost_per_1k_chars = 0.18  # Default for turbo model
            cost = (total_chars / 1000.0) * cost_per_1k_chars
            
            return {
                "cost": round(cost, 6),
                "provider": "elevenlabs",
                "characters": total_chars,
                "duration_seconds": duration_seconds,
                "cost_per_1k_chars": cost_per_1k_chars,
            }
        elif tts_provider == "gemini":
            # Gemini TTS pricing: typically free or very low cost
            # For now, assume free (can be updated with actual pricing if needed)
            return {
                "cost": 0.0,
                "provider": "gemini",
                "characters": total_chars,
                "duration_seconds": duration_seconds,
            }
        else:
            return {
                "cost": 0.0,
                "provider": tts_provider or "unknown",
                "characters": total_chars,
                "duration_seconds": duration_seconds,
            }
