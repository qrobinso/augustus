"""Station service for topic subscriptions."""

import hashlib
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.config import get_settings
from app.models.station import Station, Episode
from app.services.llm.openrouter import get_llm_provider
from app.services.llm.prompts import format_station_update_prompt
from app.services.tts.factory import TTSFactory
from app.services.search import get_search_service

settings = get_settings()


class StationService:
    """Service for managing topic subscription stations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = get_llm_provider()
        self.search = get_search_service()
    
    async def create_station(
        self,
        user_id: str,
        topic: str,
        description: Optional[str] = None,
        update_frequency_hours: int = 6,
        settings: Optional[dict] = None,
    ) -> Station:
        """Create a new station subscription."""
        station = Station(
            id=str(uuid.uuid4()),
            user_id=user_id,
            topic=topic,
            description=description,
            update_frequency_hours=update_frequency_hours,
            settings=settings or {},
            is_active=True,
        )
        
        self.db.add(station)
        await self.db.commit()
        await self.db.refresh(station)
        
        return station
    
    async def generate_episode(
        self,
        station_id: str,
        force: bool = False,
    ) -> Optional[Episode]:
        """Generate a new episode for a station if there's new content."""
        # Get station
        result = await self.db.execute(
            select(Station).where(Station.id == station_id)
        )
        station = result.scalar_one_or_none()
        
        if not station:
            raise ValueError(f"Station {station_id} not found")
        
        if not station.is_active:
            return None
        
        try:
            # Research the topic - scale sources based on duration
            current_settings = get_settings()
            station_duration = current_settings.station_update_duration_minutes
            # Roughly 1-2 sources per minute of content
            num_sources = max(3, min(10, station_duration * 2))
            print(f"[Station] Using {num_sources} sources for {station_duration} minute update")
            research, sources = await self.search.research_topic(
                station.topic,
                num_sources=num_sources,
            )
            
            # Check if content has changed
            content_hash = hashlib.sha256(research.encode()).hexdigest()[:16]
            
            if not force and station.last_content_hash == content_hash:
                # No new content
                return None
            
            # Get previous episode summary for context
            previous_summary = "This is the first episode."
            episodes_result = await self.db.execute(
                select(Episode)
                .where(Episode.station_id == station_id)
                .order_by(Episode.created_at.desc())
                .limit(1)
            )
            last_episode = episodes_result.scalar_one_or_none()
            
            if last_episode and last_episode.summary:
                previous_summary = last_episode.summary
            
            # Create episode record
            episode = Episode(
                id=str(uuid.uuid4()),
                station_id=station_id,
                title=f"{station.topic} Update - {datetime.utcnow().strftime('%B %d, %Y')}",
                status="generating",
                sources=[s.to_dict() for s in sources],
            )
            
            self.db.add(episode)
            await self.db.commit()
            
            # Generate script - use configured duration from settings
            user_name = current_settings.user_name
            print(f"[Station] Target duration: {station_duration} minutes")
            system_prompt, user_prompt = format_station_update_prompt(
                topic=station.topic,
                new_content=research,
                previous_summary=previous_summary,
                duration=station_duration,
                user_name=user_name,
            )
            
            response = await self.llm.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=3000,
                temperature=0.7,
            )
            
            script = response.content
            episode.transcript = script
            episode.summary = self._extract_summary(script)
            
            # Parse script into segments
            segments = self._parse_script(script)
            
            # Generate audio
            audio_filename = f"episode_{episode.id}.mp3"
            audio_path = Path(settings.audio_storage_path) / audio_filename
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            
            tts_result = await TTSFactory.synthesize_conversation_with_fallback(
                script=segments,
                output_path=audio_path,
                voice_map=None,  # Use configured voices from settings
            )
            
            # Update episode
            episode.audio_filename = audio_filename
            episode.duration_seconds = tts_result.duration_seconds
            episode.status = "completed"
            episode.extra_data = {
                "model": response.model,
                "usage": response.usage,
            }
            
            # Update station
            station.last_update = datetime.utcnow()
            station.last_content_hash = content_hash
            
            await self.db.commit()
            await self.db.refresh(episode)
            
            return episode
            
        except Exception as e:
            # Mark episode as failed if it exists
            if 'episode' in locals():
                episode.status = "failed"
                await self.db.commit()
            raise
    
    def _parse_script(self, script: str) -> list[dict]:
        """Parse podcast script into speaker segments."""
        segments = []
        
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
            segments.append({
                "speaker": "HOST1",
                "text": script,
            })
        
        return segments
    
    def _extract_summary(self, script: str) -> str:
        """Extract a brief summary from the script."""
        # Take first few sentences
        sentences = re.split(r'[.!?]+', script)
        summary_sentences = []
        char_count = 0
        
        for sentence in sentences:
            # Skip speaker labels
            clean = re.sub(r'^HOST[12]:\s*', '', sentence.strip())
            if clean and len(clean) > 20:
                summary_sentences.append(clean)
                char_count += len(clean)
                if char_count > 300:
                    break
        
        return '. '.join(summary_sentences)[:500]
    
    async def get_station(self, station_id: str) -> Optional[Station]:
        """Get a station by ID."""
        result = await self.db.execute(
            select(Station).where(Station.id == station_id)
        )
        return result.scalar_one_or_none()
    
    async def list_stations(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[list[Station], int]:
        """List stations for a user."""
        # Get total count
        count_result = await self.db.execute(
            select(func.count()).select_from(Station).where(Station.user_id == user_id)
        )
        total = count_result.scalar() or 0
        
        # Get paginated results
        result = await self.db.execute(
            select(Station)
            .where(Station.user_id == user_id)
            .order_by(Station.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        stations = result.scalars().all()
        
        return list(stations), total
    
    async def get_episodes(
        self,
        station_id: str,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[list[Episode], int]:
        """Get episodes for a station."""
        # Get total count
        count_result = await self.db.execute(
            select(func.count()).select_from(Episode).where(Episode.station_id == station_id)
        )
        total = count_result.scalar() or 0
        
        # Get paginated results
        result = await self.db.execute(
            select(Episode)
            .where(Episode.station_id == station_id)
            .order_by(Episode.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        episodes = result.scalars().all()
        
        return list(episodes), total
    
    async def update_station(
        self,
        station_id: str,
        topic: Optional[str] = None,
        description: Optional[str] = None,
        update_frequency_hours: Optional[int] = None,
        settings: Optional[dict] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[Station]:
        """Update a station."""
        result = await self.db.execute(
            select(Station).where(Station.id == station_id)
        )
        station = result.scalar_one_or_none()
        
        if not station:
            return None
        
        if topic is not None:
            station.topic = topic
        if description is not None:
            station.description = description
        if update_frequency_hours is not None:
            station.update_frequency_hours = update_frequency_hours
        if settings is not None:
            station.settings = settings
        if is_active is not None:
            station.is_active = is_active
        
        await self.db.commit()
        await self.db.refresh(station)
        
        return station
    
    async def delete_station(self, station_id: str) -> bool:
        """Delete a station and all its episodes."""
        result = await self.db.execute(
            select(Station).where(Station.id == station_id)
        )
        station = result.scalar_one_or_none()
        
        if not station:
            return False
        
        # Delete audio files for all episodes
        episodes_result = await self.db.execute(
            select(Episode).where(Episode.station_id == station_id)
        )
        episodes = episodes_result.scalars().all()
        
        for episode in episodes:
            if episode.audio_filename:
                audio_path = Path(settings.audio_storage_path) / episode.audio_filename
                if audio_path.exists():
                    audio_path.unlink()
        
        await self.db.delete(station)
        await self.db.commit()
        
        return True

