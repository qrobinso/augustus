"""Application configuration using pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


def find_env_file() -> Optional[str]:
    """Find the .env file location, checking common locations."""
    # Check common locations relative to where the backend runs
    locations = [
        Path.cwd() / ".env",  # backend/.env when running from backend dir
        Path.cwd().parent / ".env",  # project root .env
        Path(__file__).parent.parent.parent / ".env",  # relative to this file -> backend/.env
        Path(__file__).parent.parent.parent.parent / ".env",  # relative to this file -> project/.env
    ]
    
    for loc in locations:
        if loc.exists():
            return str(loc.resolve())
    
    # Return None to let pydantic-settings use its default behavior
    return None


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=find_env_file(),  # Can be None, pydantic-settings will handle it
        env_file_encoding="utf-8-sig",  # utf-8-sig handles BOM automatically
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields (like BOM-prefixed keys)
    )
    
    # Application
    app_name: str = "Augustus"
    app_version: str = "0.1.0"
    debug: bool = False
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./augustus.db"
    
    # Audio Storage
    audio_storage_path: str = "./audio"
    
    # OpenRouter LLM
    openrouter_api_key: Optional[str] = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "anthropic/claude-3.5-sonnet"
    
    # TTS Providers
    tts_provider: str = "piper"  # "piper", "elevenlabs", or "gemini"
    
    # Piper TTS
    piper_model_path: str = "./models/en_US-lessac-medium.onnx"
    piper_config_path: Optional[str] = None
    
    # ElevenLabs TTS
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_model: str = "eleven_turbo_v2_5"  # TTS model to use
    
    # Gemini TTS
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash-preview-tts"
    
    # Voice settings (used by ElevenLabs, Piper, and Gemini)
    # For ElevenLabs: use voice IDs like "21m00Tcm4TlvDq8ikWAM" (Rachel) or voice names
    # For Piper: use voice names like "en_US-lessac-medium"
    # For Gemini: use voice names like "Kore", "Puck", etc.
    tts_voice_host1: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel (ElevenLabs) / en_US-lessac-medium (Piper) / Kore (Gemini)
    tts_voice_host2: str = "AZnzlk1XvdvUeBnXmlld"  # Domi (ElevenLabs) / en_US-amy-medium (Piper) / Puck (Gemini)
    
    # Content Duration Settings (in minutes)
    briefing_duration_minutes: int = 5  # Daily briefing duration
    deepcast_duration_minutes: int = 10  # DeepCast duration
    station_update_duration_minutes: int = 3  # Station update duration
    
    # Conversation Complexity (1-5 scale)
    # 1 = Casual/High School - simple language, everyday analogies
    # 2 = Accessible - clear explanations, minimal jargon
    # 3 = Standard/Early College - balanced depth and accessibility (default)
    # 4 = Advanced - technical language, assumes background knowledge
    # 5 = Expert/PhD - academic depth, specialized terminology
    conversation_complexity: int = 3
    
    # Timezone setting (IANA timezone name, e.g., "America/New_York", "Europe/London")
    timezone: str = "UTC"
    
    # User Personalization
    user_name: Optional[str] = None  # User's name for personalized introductions
    
    # News Sources
    news_api_key: Optional[str] = None
    rss_feeds: str = "https://feeds.bbci.co.uk/news/technology/rss.xml,https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml"
    
    # Resend Email
    resend_api_key: Optional[str] = None
    
    # Scheduler
    briefing_schedule_hour: int = 7
    briefing_schedule_minute: int = 0
    station_update_interval_hours: int = 6
    
    @property
    def rss_feed_list(self) -> list[str]:
        """Parse RSS feeds from comma-separated string."""
        return [feed.strip() for feed in self.rss_feeds.split(",") if feed.strip()]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
