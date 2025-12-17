"""Briefing service for generating daily audio briefings."""

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.models.briefing import Briefing
from app.models.user import User
from app.services.llm.openrouter import get_llm_provider
from app.services.llm.prompts import format_briefing_prompt
from app.services.tts.factory import TTSFactory
from app.services.news import get_news_service
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
        topics: Optional[list[str]] = None,
        max_duration_minutes: int = 10,
    ) -> Briefing:
        """Create a new briefing record."""
        # Use local time for the title display
        local_date = local_now()
        briefing = Briefing(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=f"Daily Briefing - {local_date.strftime('%B %d, %Y')}",
            status="pending",
            extra_data={
                "topics": topics or [],
                "target_duration": max_duration_minutes,
            },
        )
        
        self.db.add(briefing)
        await self.db.commit()
        await self.db.refresh(briefing)
        
        return briefing
    
    async def generate_briefing(
        self,
        briefing_id: str,
        topics: Optional[list[str]] = None,
        max_duration_minutes: Optional[int] = None,
    ) -> Briefing:
        """Generate audio content for a briefing."""
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
        
        print(f"[Briefing] Target duration: {max_duration_minutes} minutes")
        
        try:
            # Update status
            briefing.status = "generating"
            await self.db.commit()
            
            # Fetch news from multiple sources
            print("[Briefing] Fetching news from RSS feeds...")
            rss_items = await self.news.fetch_all_feeds()
            
            print("[Briefing] Fetching news from NewsAPI...")
            newsapi_items = await self.news.fetch_newsapi(
                categories=topics or ["technology", "business", "science", "health"]
            )
            
            # Combine and deduplicate
            all_items = newsapi_items + rss_items
            seen_titles = set()
            news_items = []
            for item in all_items:
                # Simple dedup by title similarity
                title_key = item.title.lower()[:50]
                if title_key not in seen_titles:
                    seen_titles.add(title_key)
                    news_items.append(item)
            
            print(f"[Briefing] Total unique news items: {len(news_items)}")
            
            # Calculate max stories based on duration
            # Roughly 2-3 stories per minute of content gives good depth
            max_stories = max(5, min(30, max_duration_minutes * 3))
            print(f"[Briefing] Using {max_stories} stories for {max_duration_minutes} minute briefing")
            
            news_content = self.news.format_news_for_briefing(news_items, max_stories=max_stories)
            
            # Store sources (same limit as what was passed to LLM)
            briefing.sources = [item.to_dict() for item in news_items[:max_stories]]
            
            # Generate script with LLM
            user_name = get_settings().user_name
            system_prompt, user_prompt = format_briefing_prompt(
                content=news_content,
                topics=topics or ["technology", "business", "science"],
                duration=max_duration_minutes,
                user_name=user_name,
            )
            
            response = await self.llm.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=4096,
                temperature=0.7,
            )
            
            script = response.content
            briefing.transcript = script
            
            # Parse script into segments
            segments = self._parse_script(script)
            
            # Generate audio
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
    ) -> tuple[list[Briefing], int]:
        """List briefings for a user."""
        # Get total count
        count_result = await self.db.execute(
            select(Briefing).where(Briefing.user_id == user_id)
        )
        total = len(count_result.scalars().all())
        
        # Get paginated results
        result = await self.db.execute(
            select(Briefing)
            .where(Briefing.user_id == user_id)
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

