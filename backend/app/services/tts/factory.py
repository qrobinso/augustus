"""TTS provider factory."""

from typing import Optional
from pathlib import Path

from app.config import get_settings
from app.services.tts.base import TTSProvider, TTSResult
from app.services.tts.piper import PiperProvider
from app.services.tts.elevenlabs import ElevenLabsProvider
from app.services.tts.gemini import GeminiProvider


class TTSFactory:
    """Factory for creating TTS providers."""
    
    @classmethod
    def get_provider(cls, provider_name: Optional[str] = None) -> TTSProvider:
        """Get a TTS provider by name.
        
        Args:
            provider_name: 'piper' or 'elevenlabs'. Defaults to settings.
            
        Returns:
            TTSProvider instance
        """
        settings = get_settings()
        provider_name = provider_name or settings.tts_provider
        
        if provider_name == "piper":
            return PiperProvider()
        elif provider_name == "elevenlabs":
            if not settings.elevenlabs_api_key:
                raise ValueError("ElevenLabs API key required")
            return ElevenLabsProvider()
        elif provider_name == "gemini":
            if not settings.gemini_api_key:
                raise ValueError("Gemini API key required")
            return GeminiProvider()
        else:
            raise ValueError(f"Unknown TTS provider: {provider_name}")
    
    @classmethod
    async def synthesize(
        cls,
        text: str,
        voice_id: str,
        output_path: Path,
        provider_name: Optional[str] = None,
    ) -> TTSResult:
        """Synthesize text to speech using the chosen provider.
        
        Args:
            text: Text to synthesize
            voice_id: Voice identifier
            output_path: Path to save audio file
            provider_name: Optional provider name. Defaults to settings.tts_provider.
            
        Returns:
            TTSResult with audio path and metadata
        """
        provider_name = provider_name or get_settings().tts_provider
        print(f"[TTS] Using {provider_name} provider")
        provider = cls.get_provider(provider_name)
        try:
            result = await provider.synthesize(text, voice_id, output_path)
            return result
        finally:
            await provider.close()
    
    @classmethod
    async def synthesize_conversation(
        cls,
        script: list[dict],
        output_path: Path,
        voice_map: Optional[dict[str, str]] = None,
        provider_name: Optional[str] = None,
    ) -> TTSResult:
        """Synthesize conversation using the chosen provider.
        
        Args:
            script: List of dicts with 'speaker' and 'text' keys
            output_path: Path to save combined audio
            voice_map: Optional mapping of speaker names to voice IDs
            provider_name: Optional provider name. Defaults to settings.tts_provider.
            
        Returns:
            TTSResult with combined audio
        """
        provider_name = provider_name or get_settings().tts_provider
        print(f"[TTS] Using {provider_name} provider for conversation")
        provider = cls.get_provider(provider_name)
        try:
            result = await provider.synthesize_conversation(script, output_path, voice_map)
            return result
        finally:
            await provider.close()


# Convenience function
def get_tts_provider(provider_name: Optional[str] = None) -> TTSProvider:
    """Get TTS provider instance."""
    return TTSFactory.get_provider(provider_name)

