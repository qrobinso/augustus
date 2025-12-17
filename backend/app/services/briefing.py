"""Briefing service for generating daily audio briefings."""

import asyncio
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.briefing import Briefing
from app.models.custom_site import CustomSite
from app.models.topic import Topic
from app.models.user import User
from app.services.llm.openrouter import get_llm_provider
from app.services.llm.prompts import format_briefing_prompt, format_story_analysis_prompt
from app.services.tts.factory import TTSFactory
from app.services.news import get_news_service
from app.services.scraper import get_scraper_service
from app.utils.timezone import utc_now, local_now, format_local_datetime

settings = get_settings()


class BriefingService:
    """Service for generating daily audio briefings."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = get_llm_provider()
        self.news = get_news_service()
    
    async def create_briefing(
        self,
        user_id: str,
        topic_ids: Optional[list[str]] = None,
        max_duration_minutes: int = 10,
    ) -> Briefing:
        """Create a new briefing record.
        
        Args:
            user_id: The user ID creating the briefing
            topic_ids: List of topic IDs to include in the briefing
            max_duration_minutes: Target duration in minutes
        """
        # Use local time for the title display
        local_date = local_now()
        date_str = local_date.strftime('%B %d, %Y')
        
        # Generate a descriptive title based on topics
        title = await self._generate_briefing_title(user_id, topic_ids, date_str)
        
        briefing = Briefing(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title,
            status="pending",
            extra_data={
                "topic_ids": topic_ids or [],
                "target_duration": max_duration_minutes,
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
    ) -> Briefing:
        """Generate audio content for a briefing.
        
        Args:
            briefing_id: The briefing record ID
            topic_ids: List of topic IDs to include (uses stored topic_ids if not provided)
            max_duration_minutes: Target duration in minutes
        """
        # Get briefing record
        result = await self.db.execute(
            select(Briefing).where(Briefing.id == briefing_id)
        )
        briefing = result.scalar_one_or_none()
        
        if not briefing:
            raise ValueError(f"Briefing {briefing_id} not found")
        
        # Use duration from extra_data if not provided, then fall back to settings
        if max_duration_minutes is None:
            max_duration_minutes = briefing.extra_data.get("target_duration")
        if max_duration_minutes is None:
            max_duration_minutes = get_settings().briefing_duration_minutes
        
        # Get topic_ids from extra_data if not provided
        if topic_ids is None:
            topic_ids = briefing.extra_data.get("topic_ids", [])
        
        print(f"[Briefing] Target duration: {max_duration_minutes} minutes")
        
        try:
            # Update status and initialize progress
            briefing.status = "generating"
            briefing.extra_data = {
                **briefing.extra_data,
                "progress": {
                    "step": 1,
                    "total_steps": 6,
                    "step_name": "Fetching news sources",
                    "percent": 0,
                },
            }
            await self.db.commit()
            
            # Helper to update progress
            async def update_progress(step: int, step_name: str, percent: int = None):
                # Check if cancelled
                result = await self.db.execute(
                    select(Briefing).where(Briefing.id == briefing_id)
                )
                current = result.scalar_one_or_none()
                if current and current.status == "cancelled":
                    raise Exception("Briefing was cancelled")
                
                # Calculate percent based on step if not provided
                if percent is None:
                    percent = int((step - 1) / 6 * 100)
                
                briefing.extra_data = {
                    **briefing.extra_data,
                    "progress": {
                        "step": step,
                        "total_steps": 6,
                        "step_name": step_name,
                        "percent": percent,
                    },
                }
                await self.db.commit()
            
            # Look up topic names from IDs and check use_newsapi settings
            topics_data = await self._get_topics_data(briefing.user_id, topic_ids)
            topic_names = [t.name for t in topics_data]
            # Only include topic names for topics that have use_newsapi=True
            newsapi_topic_names = [t.name for t in topics_data if t.use_newsapi]
            # Check if any topic has use_newsapi enabled
            any_use_newsapi = any(t.use_newsapi for t in topics_data) if topics_data else True
            print(f"[Briefing] Topics: {topic_names}")
            print(f"[Briefing] Topics with NewsAPI enabled: {newsapi_topic_names}")
            
            # Step 1: Fetch news from RSS feeds (only if at least one topic has use_newsapi=True)
            # RSS feeds are external sources like NewsAPI, so they should be excluded when user wants only custom sites
            rss_items = []
            if any_use_newsapi:
                await update_progress(1, "Fetching RSS feeds", 5)
                print("[Briefing] Fetching news from RSS feeds...")
                rss_items = await self.news.fetch_all_feeds()
            else:
                await update_progress(1, "Skipping RSS feeds (only using custom sites)", 5)
                print("[Briefing] Skipping RSS feeds - all topics have use_newsapi=False (using custom sites only)")
            
            # Step 2: Fetch from NewsAPI (only if at least one topic has use_newsapi=True)
            newsapi_items = []
            if newsapi_topic_names:
                await update_progress(2, "Fetching news from NewsAPI", 20)
                print("[Briefing] Fetching news from NewsAPI...")
                fetched_newsapi_items = await self.news.fetch_newsapi(topics=newsapi_topic_names)
                
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
            await update_progress(3, "Fetching custom sites", 35)
            print("[Briefing] Fetching from custom sites...")
            custom_site_items = await self._fetch_custom_site_articles(
                briefing.user_id,
                topic_ids,
            )
            print(f"[Briefing] Found {len(custom_site_items)} articles from custom sites")
            
            # Combine articles from all sources
            # Note: 
            # - custom_site_items: Already filtered by topic_ids (only includes sites for selected topics)
            # - newsapi_items: Filtered to only include topics with use_newsapi=True (empty if all topics have use_newsapi=False)
            # - rss_items: Global RSS feeds (only included if at least one topic has use_newsapi=True)
            all_items = custom_site_items + newsapi_items + rss_items
            seen_titles = set()
            news_items = []
            for item in all_items:
                # Simple dedup by title similarity
                title_key = item.title.lower()[:50]
                if title_key not in seen_titles:
                    seen_titles.add(title_key)
                    news_items.append(item)
            
            print(f"[Briefing] Total unique news items: {len(news_items)}")
            
            # News editor should narrow down to 3-5 articles, stack-ranked in priority order
            # Weather stories are always top priority
            target_story_count = 5  # Aim for 5, but allow 3-5 range
            print(f"[Briefing] Target: 3-5 stories (stack-ranked in priority order, weather stories top priority)")
            
            # Step 4: Analyze and rank stories with LLM to narrow down to 3-5 top stories
            await update_progress(4, "Analyzing and ranking stories", 50)
            if len(news_items) > 3:
                # Always use story analysis when we have more than 3 articles to narrow down to 3-5
                print(f"[Briefing] Analyzing {len(news_items)} stories to narrow down to 3-5 top stories...")
                ranked_items, analysis_summary = await self._analyze_and_rank_stories(
                    news_items=news_items,
                    topics=topic_names if topic_names else ["technology", "business", "science"],
                    max_stories=target_story_count,
                )
                # Ensure we have 3-5 stories (take top 5 max)
                ranked_items = ranked_items[:5]
                print(f"[Briefing] Selected {len(ranked_items)} top stories (stack-ranked in priority order)")
                if analysis_summary:
                    print(f"[Briefing] Analysis: {analysis_summary}")
            else:
                # If 3 or fewer stories, use them all (no need to narrow down)
                ranked_items = news_items
                analysis_summary = None
                print(f"[Briefing] Using all {len(ranked_items)} stories (no narrowing needed)")
            
            # Format the prioritized stories for the podcast prompt
            # Use all ranked items (should be 3-5 stories)
            news_content = self.news.format_news_for_briefing(ranked_items, max_stories=len(ranked_items))
            
            # Store sources (the ranked/prioritized stories - should be 3-5)
            briefing.sources = [item.to_dict() for item in ranked_items]
            
            # Step 5: Generate podcast script with LLM
            await update_progress(5, "Writing podcast script", 65)
            user_name = get_settings().user_name
            system_prompt, user_prompt = format_briefing_prompt(
                content=news_content,
                topics=topic_names if topic_names else ["technology", "business", "science"],
                duration=max_duration_minutes,
                user_name=user_name,
            )
            
            response = await self.llm.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=4096,
                temperature=0.7,
            )
            
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
            
            briefing.transcript = script
            
            # Parse script into segments
            segments = self._parse_script(script)
            
            # Step 6: Generate audio
            await update_progress(6, "Generating audio", 80)
            audio_filename = f"briefing_{briefing.id}.mp3"
            audio_path = Path(settings.audio_storage_path) / audio_filename
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            
            tts_result = await TTSFactory.synthesize_conversation_with_fallback(
                script=segments,
                output_path=audio_path,
                voice_map=None,  # Use configured voices from settings
            )
            
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
            
            # Update briefing
            briefing.audio_filename = audio_filename
            briefing.duration_seconds = tts_result.duration_seconds
            briefing.status = "completed"
            briefing.generated_at = utc_now()
            
            # Reassign extra_data to ensure SQLAlchemy detects the change
            # (in-place mutations like .update() aren't detected on JSON fields)
            new_extra_data = dict(briefing.extra_data) if briefing.extra_data else {}
            new_extra_data.update({
                "model": response.model,
                "usage": response.usage,
                "tts_voice": tts_result.voice_id,
                "segment_timings": segment_timings,
                "story_analysis": analysis_summary,
                "stories_analyzed": len(news_items),
                "stories_selected": len(ranked_items),
            })
            briefing.extra_data = new_extra_data
            
            await self.db.commit()
            await self.db.refresh(briefing)
            
            return briefing
            
        except Exception as e:
            briefing.status = "failed"
            briefing.error_message = str(e)
            await self.db.commit()
            raise
    
    def _parse_script(self, script: str) -> list[dict]:
        """Parse podcast script into speaker segments."""
        segments = []
        
        # Pattern to match HOST1: or HOST2: at the start of lines
        pattern = r'^(HOST[12]):\s*(.+?)(?=^HOST[12]:|\Z)'
        matches = re.findall(pattern, script, re.MULTILINE | re.DOTALL)
        
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
                "text": script,
            })
        
        return segments
    
    async def get_briefing(self, briefing_id: str) -> Optional[Briefing]:
        """Get a briefing by ID."""
        result = await self.db.execute(
            select(Briefing).where(Briefing.id == briefing_id)
        )
        return result.scalar_one_or_none()
    
    async def list_briefings(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0,
        listened: Optional[bool] = None,
    ) -> tuple[list[Briefing], int]:
        """List briefings for a user.
        
        Args:
            user_id: User ID
            limit: Maximum number of results
            offset: Number of results to skip
            listened: Optional filter by listened status
        """
        # Build query
        query = select(Briefing).where(Briefing.user_id == user_id)
        
        # Apply listened filter if provided
        if listened is not None:
            query = query.where(Briefing.listened == listened)
        
        # Get total count
        count_result = await self.db.execute(query)
        total = len(count_result.scalars().all())
        
        # Get paginated results
        result = await self.db.execute(
            query
            .order_by(Briefing.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        briefings = result.scalars().all()
        
        return list(briefings), total
    
    async def delete_briefing(self, briefing_id: str) -> bool:
        """Delete a briefing."""
        result = await self.db.execute(
            select(Briefing).where(Briefing.id == briefing_id)
        )
        briefing = result.scalar_one_or_none()
        
        if not briefing:
            return False
        
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
    
    async def has_briefing_in_progress(self, user_id: str) -> Optional[Briefing]:
        """Check if user has a briefing currently being generated.
        
        Args:
            user_id: The user ID to check
            
        Returns:
            The in-progress briefing if one exists, None otherwise
        """
        result = await self.db.execute(
            select(Briefing)
            .where(Briefing.user_id == user_id)
            .where(Briefing.status.in_(["pending", "generating"]))
            .order_by(Briefing.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
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
        
        if briefing.status not in ["pending", "generating"]:
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
    ) -> list:
        """Fetch articles from user's custom sites matching the given topic IDs.
        
        Args:
            user_id: The user ID to fetch custom sites for
            topic_ids: List of topic IDs to filter by
            
        Returns:
            List of NewsItem objects from custom sites
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
            return []
        
        scraper = get_scraper_service()
        all_articles = []
        
        # Fetch from all custom sites concurrently
        async def fetch_site(site: CustomSite):
            try:
                print(f"[Briefing] Fetching from custom site: {site.name} ({site.url})")
                # Use topic name as category for the scraper
                topic_name = site.topic.name.lower() if site.topic else "general"
                articles = await scraper.fetch_site_articles(
                    url=site.url,
                    site_name=site.name,
                    category=topic_name,
                    max_articles=3,  # Limit per site
                )
                print(f"[Briefing] Got {len(articles)} articles from {site.name}")
                # Update last_fetched timestamp
                site.last_fetched = datetime.utcnow()
                site.last_error = None
                return articles
            except Exception as e:
                print(f"[Briefing] Error fetching from {site.name}: {e}")
                site.last_error = str(e)[:500]
                return []
        
        # Run all fetches concurrently
        tasks = [fetch_site(site) for site in custom_sites]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect results
        for result in results:
            if isinstance(result, list):
                all_articles.extend(result)
        
        # Commit the last_fetched updates
        await self.db.commit()
        
        return all_articles
    
    async def _analyze_and_rank_stories(
        self,
        news_items: list,
        topics: list[str],
        max_stories: int,
    ) -> tuple[list, str | None]:
        """Use LLM to analyze and rank news stories by importance.
        
        Args:
            news_items: List of NewsItem objects to analyze
            topics: Topics of interest for ranking relevance
            max_stories: Maximum number of top stories to select
            
        Returns:
            Tuple of (ranked_items, analysis_summary)
        """
        import json
        
        # Convert news items to dictionaries for the prompt
        articles_for_analysis = [
            {
                "title": item.title,
                "summary": item.summary,
                "source": item.source,
                "category": item.category or "general",
            }
            for item in news_items
        ]
        
        # Get the analysis prompt
        system_prompt, user_prompt = format_story_analysis_prompt(
            articles=articles_for_analysis,
            topics=topics,
            max_stories=max_stories,
        )
        
        try:
            # Call LLM to analyze and rank stories
            response = await self.llm.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=2048,
                temperature=0.3,  # Lower temperature for more consistent analysis
            )
            
            # Parse the JSON response
            content = response.content.strip()
            
            # Extract JSON from the response (handle markdown code blocks)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            analysis = json.loads(content)
            ranked_stories = analysis.get("ranked_stories", [])
            summary = analysis.get("summary", None)
            
            # Reorder news items based on the ranking
            ranked_items = []
            used_indices = set()
            
            for story in ranked_stories:
                article_num = story.get("article_num", 0)
                # Convert to 0-based index
                idx = article_num - 1
                
                if 0 <= idx < len(news_items) and idx not in used_indices:
                    ranked_items.append(news_items[idx])
                    used_indices.add(idx)
                    print(f"[Briefing]   #{len(ranked_items)}: {news_items[idx].title[:60]}... (priority: {story.get('priority', '?')})")
            
            # If we didn't get enough ranked items, fall back to original order
            if len(ranked_items) < max_stories:
                print(f"[Briefing] Warning: Only got {len(ranked_items)} ranked items, padding with remaining stories")
                for i, item in enumerate(news_items):
                    if i not in used_indices and len(ranked_items) < max_stories:
                        ranked_items.append(item)
            
            return ranked_items[:max_stories], summary
            
        except json.JSONDecodeError as e:
            print(f"[Briefing] Warning: Failed to parse story analysis JSON: {e}")
            print(f"[Briefing] Falling back to original order")
            return news_items[:max_stories], None
        except Exception as e:
            print(f"[Briefing] Warning: Story analysis failed: {e}")
            print(f"[Briefing] Falling back to original order")
            return news_items[:max_stories], None

