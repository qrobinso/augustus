"""Base TTS provider interface."""

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SegmentTiming:
    """Timing information for a transcript segment."""
    index: int
    speaker: str
    text: str
    start_seconds: float
    end_seconds: float
    duration_seconds: float


@dataclass
class TTSResult:
    """Result from TTS generation."""
    audio_path: Path
    duration_seconds: float
    voice_id: str
    format: str = "mp3"
    segment_timings: Optional[list[SegmentTiming]] = None


@dataclass
class Voice:
    """Voice configuration."""
    id: str
    name: str
    description: Optional[str] = None
    language: str = "en"


class TTSProvider(ABC):
    """Abstract base class for TTS providers."""
    
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
    ) -> TTSResult:
        """Synthesize text to speech.
        
        Args:
            text: Text to synthesize
            voice_id: Voice identifier
            output_path: Path to save audio file
            
        Returns:
            TTSResult with audio path and metadata
        """
        pass
    
    @abstractmethod
    async def synthesize_conversation(
        self,
        script: list[dict],
        output_path: Path,
        voice_map: Optional[dict[str, str]] = None,
    ) -> TTSResult:
        """Synthesize a multi-speaker conversation.
        
        Args:
            script: List of dicts with 'speaker' and 'text' keys
            output_path: Path to save combined audio
            voice_map: Optional mapping of speaker names to voice IDs
            
        Returns:
            TTSResult with combined audio
        """
        pass
    
    @abstractmethod
    def list_voices(self) -> list[Voice]:
        """List available voices."""
        pass
    
    @abstractmethod
    async def close(self):
        """Close any open connections."""
        pass

