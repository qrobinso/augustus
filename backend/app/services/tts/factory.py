"""TTS provider factory with fallback support."""

from typing import Optional
from pathlib import Path

from app.config import get_settings
from app.services.tts.base import TTSProvider, TTSResult
from app.services.tts.piper import PiperProvider
from app.services.tts.elevenlabs import ElevenLabsProvider


class TTSFactory:
    """Factory for creating TTS providers with fallback support."""
    
    _primary: Optional[TTSProvider] = None
    _fallback: Optional[TTSProvider] = None
    
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
        else:
            raise ValueError(f"Unknown TTS provider: {provider_name}")
    
    @classmethod
    def _get_primary_and_fallback(cls) -> tuple[str, str]:
        """Get primary and fallback provider names based on settings."""
        settings = get_settings()
        primary = settings.tts_provider
        
        # Set fallback to the other provider
        if primary == "elevenlabs":
            fallback = "piper"
        else:
            fallback = "elevenlabs"
        
        return primary, fallback
    
    @classmethod
    async def synthesize_with_fallback(
        cls,
        text: str,
        voice_id: str,
        output_path: Path,
        primary: Optional[str] = None,
        fallback: Optional[str] = None,
    ) -> TTSResult:
        """Synthesize with automatic fallback.
        
        Tries primary provider first, falls back to secondary on failure.
        Uses settings.tts_provider as primary if not specified.
        """
        # Get primary/fallback from settings if not provided
        if primary is None or fallback is None:
            settings_primary, settings_fallback = cls._get_primary_and_fallback()
            primary = primary or settings_primary
            fallback = fallback or settings_fallback
        
        primary_error_msg = None
        
        # Try primary
        try:
            print(f"[TTS] Using {primary} as primary provider")
            provider = cls.get_provider(primary)
            result = await provider.synthesize(text, voice_id, output_path)
            await provider.close()
            return result
        except Exception as e:
            primary_error_msg = str(e)
            print(f"[TTS] Primary ({primary}) failed: {primary_error_msg}")
        
        # Try fallback
        try:
            print(f"[TTS] Trying fallback provider: {fallback}")
            provider = cls.get_provider(fallback)
            result = await provider.synthesize(text, voice_id, output_path)
            await provider.close()
            return result
        except Exception as fallback_error:
            raise RuntimeError(
                f"All TTS providers failed. Primary ({primary}): {primary_error_msg}, "
                f"Fallback ({fallback}): {fallback_error}"
            )
    
    @classmethod
    async def synthesize_conversation_with_fallback(
        cls,
        script: list[dict],
        output_path: Path,
        voice_map: Optional[dict[str, str]] = None,
        primary: Optional[str] = None,
        fallback: Optional[str] = None,
    ) -> TTSResult:
        """Synthesize conversation with automatic fallback.
        
        Uses settings.tts_provider as primary if not specified.
        """
        # Get primary/fallback from settings if not provided
        if primary is None or fallback is None:
            settings_primary, settings_fallback = cls._get_primary_and_fallback()
            primary = primary or settings_primary
            fallback = fallback or settings_fallback
        
        primary_error_msg = None
        
        # Try primary
        try:
            print(f"[TTS] Using {primary} as primary provider for conversation")
            provider = cls.get_provider(primary)
            result = await provider.synthesize_conversation(script, output_path, voice_map)
            await provider.close()
            return result
        except Exception as e:
            primary_error_msg = str(e)
            print(f"[TTS] Primary ({primary}) failed: {primary_error_msg}")
        
        # Try fallback
        try:
            print(f"[TTS] Trying fallback provider: {fallback}")
            provider = cls.get_provider(fallback)
            result = await provider.synthesize_conversation(script, output_path, voice_map)
            await provider.close()
            return result
        except Exception as fallback_error:
            raise RuntimeError(
                f"All TTS providers failed. Primary ({primary}): {primary_error_msg}, "
                f"Fallback ({fallback}): {fallback_error}"
            )


# Convenience function
def get_tts_provider(provider_name: Optional[str] = None) -> TTSProvider:
    """Get TTS provider instance."""
    return TTSFactory.get_provider(provider_name)

