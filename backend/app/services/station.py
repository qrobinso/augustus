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
from app.models.cast import Cast
from app.services.cast import CastService
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
            
            # Load cast for this station
            cast_service = CastService(self.db)
            if station.cast_id:
                cast = await cast_service.get_cast(station.cast_id, station.user_id)
                if not cast:
                    print(f"[Station] Cast {station.cast_id} not found, using default")
                    cast = await cast_service.get_default_cast(station.user_id)
            else:
                cast = await cast_service.get_default_cast(station.user_id)
            
            # Prepare cast members for prompt
            cast_members = []
            for member in sorted(cast.members, key=lambda m: m.order):
                cast_members.append({
                    "name": member.name,
                    "personality": member.personality,
                    "voice_id": member.voice_id,
                    "order": member.order,
                })
            
            print(f"[Station] Using cast '{cast.name}' with {len(cast_members)} member(s)")
            
            # Generate script - use configured duration from settings
            user_name = current_settings.user_name
            print(f"[Station] Target duration: {station_duration} minutes")
            system_prompt, user_prompt = format_station_update_prompt(
                topic=station.topic,
                new_content=research,
                previous_summary=previous_summary,
                duration=station_duration,
                user_name=user_name,
                cast_members=cast_members,
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
            
            # Parse script into segments using cast member names
            segments = self._parse_script(script, cast_members)
            
            # Build voice_map from cast members
            voice_map = {}
            for i, member in enumerate(cast_members):
                host_key = f"HOST{i+1}"
                voice_map[host_key] = member["voice_id"]
                voice_map[member["name"]] = member["voice_id"]  # Also map by name
            
            print(f"[Station] Voice map: {voice_map}")
            
            # Generate audio
            audio_filename = f"episode_{episode.id}.mp3"
            audio_path = Path(settings.audio_storage_path) / audio_filename
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            
            tts_result = await TTSFactory.synthesize_conversation(
                script=segments,
                output_path=audio_path,
                voice_map=voice_map,  # Use cast voice IDs
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
    
    def _parse_script(self, script: str, cast_members: list[dict] | None = None) -> list[dict]:
        """Parse podcast script into speaker segments.
        
        Args:
            script: The script text to parse
            cast_members: List of cast members with 'name' and 'order' keys
            
        Returns:
            List of segments with 'speaker' and 'text' keys
        """
        segments = []
        
        if cast_members:
            # Build pattern from cast member names
            cast_names = [m["name"] for m in sorted(cast_members, key=lambda x: x["order"])]
            # Escape names for regex
            escaped_names = [re.escape(name) for name in cast_names]
            # Create pattern: NAME: or NAME: (case-insensitive)
            pattern_parts = "|".join(escaped_names)
            pattern = rf'^({pattern_parts}):\s*(.+?)(?=^({pattern_parts}):|\Z)'
            
            matches = re.findall(pattern, script, re.MULTILINE | re.DOTALL | re.IGNORECASE)
            
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
                        host_id = name_to_host.get(speaker_name, "HOST1")
                        segments.append({
                            "speaker": host_id,
                            "text": text,
                        })
            else:
                # Fallback: treat entire script as first host
                segments.append({
                    "speaker": "HOST1",
                    "text": script,
                })
        else:
            # Legacy parsing for backward compatibility
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

