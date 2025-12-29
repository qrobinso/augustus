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
            env_path = str(loc.resolve())
            print(f"[Config] Found .env file at: {env_path}")
            return env_path
    
    # Return None to let pydantic-settings use its default behavior
    print(f"[Config] No .env file found in standard locations")
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
    openrouter_writer_model: Optional[str] = None  # Optional separate model for briefing writing (uses openrouter_model if not set)
    
    # TTS Providers
    tts_provider: str = "piper"  # "piper", "elevenlabs", or "gemini"
    
    # Piper TTS
    piper_model_path: str = "./models/en_US-lessac-medium.onnx"
    piper_config_path: Optional[str] = None
    piper_url: Optional[str] = None  # URL for remote Piper TTS API (e.g., http://localhost:5000)
    piper_model: Optional[str] = None  # Model name to use with remote Piper API
    
    # ElevenLabs TTS
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_model: str = "eleven_turbo_v2_5"  # TTS model to use
    
    # Gemini TTS
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash-preview-tts"
    
    # Non-speech sounds (for Gemini TTS - adds sighs, laughs, pauses, etc.)
    enable_non_speech_sounds: bool = False
    
    # Content Duration Settings (in minutes)
    briefing_duration_minutes: int = 5  # Daily briefing duration
    
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
    resend_from_email: Optional[str] = None  # From email address (defaults to onboarding@resend.dev if not set)
    
    # Frontend URL (for email links)
    frontend_url: str = "http://localhost:3000"
    
    # Scheduler
    briefing_schedule_hour: int = 7
    briefing_schedule_minute: int = 0
    
    # Briefing Generation Timeout
    briefing_timeout_minutes: int = 15  # Timeout in minutes for briefing generation
    
    @property
    def rss_feed_list(self) -> list[str]:
        """Parse RSS feeds from comma-separated string."""
        return [feed.strip() for feed in self.rss_feeds.split(",") if feed.strip()]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    # Log TTS provider on startup to verify it's loaded correctly
    print(f"[Config] TTS Provider loaded: {settings.tts_provider}")
    if settings.piper_url:
        print(f"[Config] Piper URL loaded: {settings.piper_url}")
    if settings.piper_model:
        print(f"[Config] Piper Model loaded: {settings.piper_model}")
    return settings
