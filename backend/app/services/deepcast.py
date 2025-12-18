"""DeepCast service for on-demand topic podcasts."""

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.models.deepcast import DeepCast
from app.models.cast import Cast
from app.services.cast import CastService
from app.services.llm.openrouter import get_llm_provider
from app.services.llm.prompts import format_deepcast_prompt
from app.services.tts.factory import TTSFactory
from app.services.search import get_search_service

settings = get_settings()


class DeepCastService:
    """Service for generating on-demand topic podcasts."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = get_llm_provider()
        self.search = get_search_service()
    
    async def create_deepcast(
        self,
        user_id: str,
        query: str,
        target_duration_minutes: int = 10,
        num_sources: int = 5,
    ) -> DeepCast:
        """Create a new DeepCast record and start generation."""
        deepcast = DeepCast(
            id=str(uuid.uuid4()),
            user_id=user_id,
            query=query,
            status="pending",
            extra_data={
                "target_duration": target_duration_minutes,
                "num_sources": num_sources,
            },
        )
        
        self.db.add(deepcast)
        await self.db.commit()
        await self.db.refresh(deepcast)
        
        return deepcast
    
    async def generate_deepcast(
        self,
        deepcast_id: str,
    ) -> DeepCast:
        """Generate audio content for a DeepCast."""
        # Get DeepCast record
        result = await self.db.execute(
            select(DeepCast).where(DeepCast.id == deepcast_id)
        )
        deepcast = result.scalar_one_or_none()
        
        if not deepcast:
            raise ValueError(f"DeepCast {deepcast_id} not found")
        
        try:
            # Update status
            deepcast.status = "researching"
            await self.db.commit()
            
            # Research the topic - scale sources based on duration
            target_duration = deepcast.extra_data.get("target_duration") or get_settings().deepcast_duration_minutes
            # Roughly 1-2 sources per minute of content
            num_sources = deepcast.extra_data.get("num_sources") or max(3, min(15, target_duration * 2))
            print(f"[DeepCast] Using {num_sources} sources for {target_duration} minute deepcast")
            research, sources = await self.search.research_topic(
                deepcast.query,
                num_sources=num_sources,
            )
            
            # Store sources
            deepcast.sources = [s.to_dict() for s in sources]
            
            # Update status
            deepcast.status = "generating"
            await self.db.commit()
            
            # Load cast for this DeepCast
            cast_service = CastService(self.db)
            if deepcast.cast_id:
                cast = await cast_service.get_cast(deepcast.cast_id, deepcast.user_id)
                if not cast:
                    print(f"[DeepCast] Cast {deepcast.cast_id} not found, using default")
                    cast = await cast_service.get_default_cast(deepcast.user_id)
            else:
                cast = await cast_service.get_default_cast(deepcast.user_id)
            
            # Prepare cast members for prompt
            cast_members = []
            for member in sorted(cast.members, key=lambda m: m.order):
                cast_members.append({
                    "name": member.name,
                    "personality": member.personality,
                    "voice_id": member.voice_id,
                    "order": member.order,
                })
            
            print(f"[DeepCast] Using cast '{cast.name}' with {len(cast_members)} member(s)")
            
            # Generate script with LLM - use stored duration or configured default
            from app.config import get_settings
            current_settings = get_settings()
            target_duration = deepcast.extra_data.get("target_duration") or current_settings.deepcast_duration_minutes
            user_name = current_settings.user_name
            print(f"[DeepCast] Target duration: {target_duration} minutes")
            system_prompt, user_prompt = format_deepcast_prompt(
                query=deepcast.query,
                research=research,
                sources=[s.to_dict() for s in sources],
                duration=target_duration,
                user_name=user_name,
                cast_members=cast_members,
            )
            
            response = await self.llm.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=6000,
                temperature=0.7,
            )
            
            script = response.content
            deepcast.transcript = script
            
            # Generate title from script
            deepcast.title = self._extract_title(script, deepcast.query)
            
            # Parse script into segments and chapters using cast member names
            segments = self._parse_script(script, cast_members)
            deepcast.chapters = self._extract_chapters(script)
            
            # Build voice_map from cast members
            voice_map = {}
            for i, member in enumerate(cast_members):
                host_key = f"HOST{i+1}"
                voice_map[host_key] = member["voice_id"]
                voice_map[member["name"]] = member["voice_id"]  # Also map by name
            
            print(f"[DeepCast] Voice map: {voice_map}")
            
            # Generate audio
            audio_filename = f"deepcast_{deepcast.id}.mp3"
            audio_path = Path(settings.audio_storage_path) / audio_filename
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            
            tts_result = await TTSFactory.synthesize_conversation(
                script=segments,
                output_path=audio_path,
                voice_map=voice_map,  # Use cast voice IDs
            )
            
            # Update deepcast
            deepcast.audio_filename = audio_filename
            deepcast.duration_seconds = tts_result.duration_seconds
            deepcast.status = "completed"
            deepcast.completed_at = datetime.utcnow()
            deepcast.extra_data.update({
                "model": response.model,
                "usage": response.usage,
                "tts_voice": tts_result.voice_id,
            })
            
            await self.db.commit()
            await self.db.refresh(deepcast)
            
            return deepcast
            
        except Exception as e:
            deepcast.status = "failed"
            deepcast.error_message = str(e)
            await self.db.commit()
            raise
    
    def _extract_title(self, script: str, fallback: str) -> str:
        """Extract or generate a title from the script."""
        # Look for title in script
        title_match = re.search(r'\[CHAPTER:\s*Introduction\].*?about\s+(.+?)[\.\n]', script, re.IGNORECASE | re.DOTALL)
        if title_match:
            return title_match.group(1).strip()[:100]
        
        # Use first line if it looks like a title
        first_line = script.split('\n')[0].strip()
        if len(first_line) < 100 and not first_line.startswith('HOST'):
            return first_line
        
        # Fallback to query
        return f"DeepCast: {fallback[:80]}"
    
    def _parse_script(self, script: str, cast_members: list[dict] | None = None) -> list[dict]:
        """Parse podcast script into speaker segments.
        
        Args:
            script: The script text to parse
            cast_members: List of cast members with 'name' and 'order' keys
            
        Returns:
            List of segments with 'speaker' and 'text' keys
        """
        segments = []
        
        # Remove chapter markers for TTS
        clean_script = re.sub(r'\[CHAPTER:.*?\]', '', script)
        
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
                        host_id = name_to_host.get(speaker_name, "HOST1")
                        segments.append({
                            "speaker": host_id,
                            "text": text,
                        })
            else:
                # Fallback: treat entire script as first host
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
        """Extract chapter markers from script."""
        chapters = []
        
        # Find all chapter markers
        pattern = r'\[CHAPTER:\s*(.+?)\]'
        matches = re.finditer(pattern, script)
        
        for i, match in enumerate(matches):
            chapters.append({
                "title": match.group(1).strip(),
                "start_time": 0.0,  # Will be updated after audio generation
                "end_time": None,
            })
        
        if not chapters:
            # Default chapters
            chapters = [
                {"title": "Introduction", "start_time": 0.0, "end_time": None},
            ]
        
        return chapters
    
    async def get_deepcast(self, deepcast_id: str) -> Optional[DeepCast]:
        """Get a DeepCast by ID."""
        result = await self.db.execute(
            select(DeepCast).where(DeepCast.id == deepcast_id)
        )
        return result.scalar_one_or_none()
    
    async def list_deepcasts(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[list[DeepCast], int]:
        """List DeepCasts for a user."""
        # Get total count
        count_result = await self.db.execute(
            select(DeepCast).where(DeepCast.user_id == user_id)
        )
        total = len(count_result.scalars().all())
        
        # Get paginated results
        result = await self.db.execute(
            select(DeepCast)
            .where(DeepCast.user_id == user_id)
            .order_by(DeepCast.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        deepcasts = result.scalars().all()
        
        return list(deepcasts), total
    
    async def delete_deepcast(self, deepcast_id: str) -> bool:
        """Delete a DeepCast."""
        result = await self.db.execute(
            select(DeepCast).where(DeepCast.id == deepcast_id)
        )
        deepcast = result.scalar_one_or_none()
        
        if not deepcast:
            return False
        
        # Delete audio file if exists
        if deepcast.audio_filename:
            audio_path = Path(settings.audio_storage_path) / deepcast.audio_filename
            if audio_path.exists():
                audio_path.unlink()
        
        await self.db.delete(deepcast)
        await self.db.commit()
        
        return True

