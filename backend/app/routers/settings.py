"""Settings router for managing application configuration."""

import os
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# Cache for models list
_models_cache: Optional[list] = None
_models_cache_time: float = 0


class SettingsResponse(BaseModel):
    """Current settings response."""
    # OpenRouter
    openrouter_api_key: Optional[str] = None
    openrouter_model: str = "anthropic/claude-3.5-sonnet"
    
    # TTS
    tts_provider: str = "piper"
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_model: str = "eleven_turbo_v2_5"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash-preview-tts"
    # Content Durations (minutes)
    briefing_duration_minutes: int = 5
    deepcast_duration_minutes: int = 10
    station_update_duration_minutes: int = 3
    
    # Conversation Complexity (1-5 scale)
    conversation_complexity: int = 3
    
    # Timezone (IANA timezone name)
    timezone: str = "UTC"
    
    # News
    news_api_key: Optional[str] = None
    rss_feeds: str = ""
    
    # Resend Email
    resend_api_key: Optional[str] = None
    
    # User Personalization
    user_name: Optional[str] = None
    
    # Status
    openrouter_configured: bool = False
    elevenlabs_configured: bool = False
    news_api_configured: bool = False
    resend_configured: bool = False
    gemini_configured: bool = False


class SettingsUpdate(BaseModel):
    """Settings update request."""
    openrouter_api_key: Optional[str] = None
    openrouter_model: Optional[str] = None
    tts_provider: Optional[str] = None
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_model: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    briefing_duration_minutes: Optional[int] = None
    deepcast_duration_minutes: Optional[int] = None
    station_update_duration_minutes: Optional[int] = None
    conversation_complexity: Optional[int] = None
    timezone: Optional[str] = None
    news_api_key: Optional[str] = None
    rss_feeds: Optional[str] = None
    resend_api_key: Optional[str] = None
    user_name: Optional[str] = None


def mask_api_key(key: Optional[str]) -> Optional[str]:
    """Mask API key for display, showing only first/last 4 chars."""
    if not key or len(key) < 12:
        return None
    return f"{key[:4]}...{key[-4:]}"


def find_env_file() -> Path:
    """Find the .env file location."""
    # Check common locations relative to where the backend runs
    locations = [
        Path.cwd() / ".env",  # backend/.env when running from backend dir
        Path.cwd().parent / ".env",  # project root .env
        Path(__file__).parent.parent.parent / ".env",  # relative to this file -> backend/.env
        Path(__file__).parent.parent.parent.parent / ".env",  # relative to this file -> project/.env
    ]
    
    for loc in locations:
        if loc.exists():
            return loc.resolve()
    
    # Default to project root (parent of backend)
    return (Path.cwd().parent / ".env").resolve()


def read_env_file() -> dict[str, str]:
    """Read current .env file contents directly."""
    env_file = find_env_file()
    env_vars = {}
    
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    env_vars[key.strip()] = value.strip()
    
    return env_vars


def write_env_file(updates: dict[str, str]):
    """Update .env file with new values."""
    env_file = find_env_file()
    
    # Read existing content
    existing_lines = []
    existing_keys = set()
    
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith('#') and '=' in stripped:
                    key = stripped.split('=')[0].strip()
                    existing_keys.add(key)
                    
                    # Update if we have a new value
                    if key in updates:
                        value = updates[key]
                        if value is not None:
                            existing_lines.append(f"{key}={value}\n")
                        else:
                            existing_lines.append(line if line.endswith('\n') else line + '\n')
                    else:
                        existing_lines.append(line if line.endswith('\n') else line + '\n')
                else:
                    existing_lines.append(line if line.endswith('\n') else line + '\n')
    
    # Add new keys that weren't in the file
    for key, value in updates.items():
        if key not in existing_keys and value is not None:
            existing_lines.append(f"{key}={value}\n")
    
    # Ensure parent directory exists
    env_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Write back
    with open(env_file, 'w', encoding='utf-8') as f:
        f.writelines(existing_lines)


def get_current_settings() -> dict:
    """Get current settings from both environment and .env file."""
    # Read directly from .env file first
    env_vars = read_env_file()
    
    # Helper to get int with default
    def get_int(env_key: str, default: int) -> int:
        val = os.environ.get(env_key) or env_vars.get(env_key)
        if val:
            try:
                return int(val)
            except ValueError:
                pass
        return default
    
    # Merge with current environment (env takes precedence for runtime changes)
    settings = {
        "openrouter_api_key": os.environ.get("OPENROUTER_API_KEY") or env_vars.get("OPENROUTER_API_KEY"),
        "openrouter_model": os.environ.get("OPENROUTER_MODEL") or env_vars.get("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet"),
        "tts_provider": os.environ.get("TTS_PROVIDER") or env_vars.get("TTS_PROVIDER", "piper"),
        "elevenlabs_api_key": os.environ.get("ELEVENLABS_API_KEY") or env_vars.get("ELEVENLABS_API_KEY"),
        "elevenlabs_model": os.environ.get("ELEVENLABS_MODEL") or env_vars.get("ELEVENLABS_MODEL", "eleven_turbo_v2_5"),
        "gemini_api_key": os.environ.get("GEMINI_API_KEY") or env_vars.get("GEMINI_API_KEY"),
        "gemini_model": os.environ.get("GEMINI_MODEL") or env_vars.get("GEMINI_MODEL", "gemini-2.5-flash-preview-tts"),
        "briefing_duration_minutes": get_int("BRIEFING_DURATION_MINUTES", 5),
        "deepcast_duration_minutes": get_int("DEEPCAST_DURATION_MINUTES", 10),
        "station_update_duration_minutes": get_int("STATION_UPDATE_DURATION_MINUTES", 3),
        "conversation_complexity": get_int("CONVERSATION_COMPLEXITY", 3),
        "timezone": os.environ.get("TIMEZONE") or env_vars.get("TIMEZONE", "UTC"),
        "news_api_key": os.environ.get("NEWS_API_KEY") or env_vars.get("NEWS_API_KEY"),
        "rss_feeds": os.environ.get("RSS_FEEDS") or env_vars.get("RSS_FEEDS", ""),
        "resend_api_key": os.environ.get("RESEND_API_KEY") or env_vars.get("RESEND_API_KEY"),
        "user_name": os.environ.get("USER_NAME") or env_vars.get("USER_NAME"),
    }
    
    return settings


@router.get("", response_model=SettingsResponse)
async def get_settings_endpoint():
    """Get current application settings."""
    settings = get_current_settings()
    
    return SettingsResponse(
        openrouter_api_key=mask_api_key(settings["openrouter_api_key"]),
        openrouter_model=settings["openrouter_model"],
        tts_provider=settings["tts_provider"],
        elevenlabs_api_key=mask_api_key(settings["elevenlabs_api_key"]),
        elevenlabs_model=settings["elevenlabs_model"],
        gemini_api_key=mask_api_key(settings["gemini_api_key"]),
        gemini_model=settings["gemini_model"],
        briefing_duration_minutes=settings["briefing_duration_minutes"],
        deepcast_duration_minutes=settings["deepcast_duration_minutes"],
        station_update_duration_minutes=settings["station_update_duration_minutes"],
        conversation_complexity=settings["conversation_complexity"],
        timezone=settings["timezone"],
        news_api_key=mask_api_key(settings["news_api_key"]),
        rss_feeds=settings["rss_feeds"],
        resend_api_key=mask_api_key(settings["resend_api_key"]),
        user_name=settings["user_name"],
        openrouter_configured=bool(settings["openrouter_api_key"]),
        elevenlabs_configured=bool(settings["elevenlabs_api_key"]),
        news_api_configured=bool(settings["news_api_key"]),
        resend_configured=bool(settings["resend_api_key"]),
        gemini_configured=bool(settings["gemini_api_key"]),
    )


@router.put("", response_model=SettingsResponse)
async def update_settings(updates: SettingsUpdate):
    """Update application settings and save to .env file."""
    print(f"[Settings] Received updates: {updates.model_dump(exclude_unset=True)}")
    try:
        env_updates = {}
        
        # Only update non-None values
        if updates.openrouter_api_key is not None:
            env_updates["OPENROUTER_API_KEY"] = updates.openrouter_api_key
            os.environ["OPENROUTER_API_KEY"] = updates.openrouter_api_key
        
        if updates.openrouter_model is not None:
            env_updates["OPENROUTER_MODEL"] = updates.openrouter_model
            os.environ["OPENROUTER_MODEL"] = updates.openrouter_model
        
        if updates.tts_provider is not None:
            env_updates["TTS_PROVIDER"] = updates.tts_provider
            os.environ["TTS_PROVIDER"] = updates.tts_provider
        
        if updates.elevenlabs_api_key is not None:
            env_updates["ELEVENLABS_API_KEY"] = updates.elevenlabs_api_key
            os.environ["ELEVENLABS_API_KEY"] = updates.elevenlabs_api_key
        
        if updates.elevenlabs_model is not None:
            env_updates["ELEVENLABS_MODEL"] = updates.elevenlabs_model
            os.environ["ELEVENLABS_MODEL"] = updates.elevenlabs_model
        
        if updates.gemini_api_key is not None:
            env_updates["GEMINI_API_KEY"] = updates.gemini_api_key
            os.environ["GEMINI_API_KEY"] = updates.gemini_api_key
        
        if updates.gemini_model is not None:
            env_updates["GEMINI_MODEL"] = updates.gemini_model
            os.environ["GEMINI_MODEL"] = updates.gemini_model
        
        if updates.briefing_duration_minutes is not None:
            env_updates["BRIEFING_DURATION_MINUTES"] = str(updates.briefing_duration_minutes)
            os.environ["BRIEFING_DURATION_MINUTES"] = str(updates.briefing_duration_minutes)
        
        if updates.deepcast_duration_minutes is not None:
            env_updates["DEEPCAST_DURATION_MINUTES"] = str(updates.deepcast_duration_minutes)
            os.environ["DEEPCAST_DURATION_MINUTES"] = str(updates.deepcast_duration_minutes)
        
        if updates.station_update_duration_minutes is not None:
            env_updates["STATION_UPDATE_DURATION_MINUTES"] = str(updates.station_update_duration_minutes)
            os.environ["STATION_UPDATE_DURATION_MINUTES"] = str(updates.station_update_duration_minutes)
        
        if updates.conversation_complexity is not None:
            # Clamp to valid range 1-5
            complexity = max(1, min(5, updates.conversation_complexity))
            env_updates["CONVERSATION_COMPLEXITY"] = str(complexity)
            os.environ["CONVERSATION_COMPLEXITY"] = str(complexity)
        
        if updates.timezone is not None:
            env_updates["TIMEZONE"] = updates.timezone
            os.environ["TIMEZONE"] = updates.timezone
        
        if updates.news_api_key is not None:
            env_updates["NEWS_API_KEY"] = updates.news_api_key
            os.environ["NEWS_API_KEY"] = updates.news_api_key
        
        if updates.rss_feeds is not None:
            env_updates["RSS_FEEDS"] = updates.rss_feeds
            os.environ["RSS_FEEDS"] = updates.rss_feeds
        
        if updates.resend_api_key is not None:
            env_updates["RESEND_API_KEY"] = updates.resend_api_key
            os.environ["RESEND_API_KEY"] = updates.resend_api_key
        
        if updates.user_name is not None:
            env_updates["USER_NAME"] = updates.user_name
            os.environ["USER_NAME"] = updates.user_name
        
        # Write to .env file
        if env_updates:
            write_env_file(env_updates)
        
        # Clear the cached settings in app.config
        from app.config import get_settings
        get_settings.cache_clear()
        
        # Reset LLM provider if model or API key changed
        if updates.openrouter_model is not None or updates.openrouter_api_key is not None:
            from app.services.llm.openrouter import reset_llm_provider
            reset_llm_provider()
        
        # Return updated settings
        return await get_settings_endpoint()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")


@router.get("/models")
async def get_available_models():
    """Get list of available OpenRouter models from their API."""
    import time
    global _models_cache, _models_cache_time
    
    # Return cached models if less than 5 minutes old
    if _models_cache and (time.time() - _models_cache_time) < 300:
        return {"models": _models_cache}
    
    settings = get_current_settings()
    api_key = settings.get("openrouter_api_key")
    
    # Fallback models if API call fails or no API key
    fallback_models = [
        {"id": "anthropic/claude-sonnet-4", "name": "Claude Sonnet 4", "provider": "Anthropic", "context_length": 200000},
        {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "provider": "Anthropic", "context_length": 200000},
        {"id": "anthropic/claude-3-haiku", "name": "Claude 3 Haiku", "provider": "Anthropic", "context_length": 200000},
        {"id": "openai/gpt-4o", "name": "GPT-4o", "provider": "OpenAI", "context_length": 128000},
        {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "provider": "OpenAI", "context_length": 128000},
        {"id": "google/gemini-pro-1.5", "name": "Gemini Pro 1.5", "provider": "Google", "context_length": 1000000},
        {"id": "meta-llama/llama-3.1-70b-instruct", "name": "Llama 3.1 70B", "provider": "Meta", "context_length": 131072},
    ]
    
    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        
        # Parse and format the models
        models = []
        for model in data.get("data", []):
            model_id = model.get("id", "")
            name = model.get("name", model_id)
            
            # Extract provider from model ID (e.g., "anthropic/claude-3" -> "Anthropic")
            provider = model_id.split("/")[0].title() if "/" in model_id else "Unknown"
            
            # Get context length
            context_length = model.get("context_length", 0)
            
            # Get pricing info
            pricing = model.get("pricing", {})
            prompt_price = float(pricing.get("prompt", 0)) * 1000000  # Convert to per million tokens
            completion_price = float(pricing.get("completion", 0)) * 1000000
            
            models.append({
                "id": model_id,
                "name": name,
                "provider": provider,
                "context_length": context_length,
                "pricing": {
                    "prompt": prompt_price,
                    "completion": completion_price,
                },
                "description": model.get("description", ""),
            })
        
        # Sort by provider, then by name
        models.sort(key=lambda x: (x["provider"], x["name"]))
        
        # Cache the results
        _models_cache = models
        _models_cache_time = time.time()
        
        return {"models": models}
        
    except Exception as e:
        print(f"[Settings] Failed to fetch models from OpenRouter: {e}")
        # Return fallback models
        return {"models": fallback_models}


@router.get("/timezones")
async def get_available_timezones():
    """Get list of common timezones grouped by region."""
    # Common timezones organized by region
    timezones = {
        "Americas": [
            {"id": "America/New_York", "name": "Eastern Time (US)", "offset": "UTC-5/-4"},
            {"id": "America/Chicago", "name": "Central Time (US)", "offset": "UTC-6/-5"},
            {"id": "America/Denver", "name": "Mountain Time (US)", "offset": "UTC-7/-6"},
            {"id": "America/Los_Angeles", "name": "Pacific Time (US)", "offset": "UTC-8/-7"},
            {"id": "America/Anchorage", "name": "Alaska Time", "offset": "UTC-9/-8"},
            {"id": "Pacific/Honolulu", "name": "Hawaii Time", "offset": "UTC-10"},
            {"id": "America/Toronto", "name": "Toronto", "offset": "UTC-5/-4"},
            {"id": "America/Vancouver", "name": "Vancouver", "offset": "UTC-8/-7"},
            {"id": "America/Mexico_City", "name": "Mexico City", "offset": "UTC-6/-5"},
            {"id": "America/Sao_Paulo", "name": "São Paulo", "offset": "UTC-3"},
            {"id": "America/Buenos_Aires", "name": "Buenos Aires", "offset": "UTC-3"},
        ],
        "Europe": [
            {"id": "Europe/London", "name": "London (GMT/BST)", "offset": "UTC+0/+1"},
            {"id": "Europe/Paris", "name": "Paris (CET)", "offset": "UTC+1/+2"},
            {"id": "Europe/Berlin", "name": "Berlin (CET)", "offset": "UTC+1/+2"},
            {"id": "Europe/Amsterdam", "name": "Amsterdam (CET)", "offset": "UTC+1/+2"},
            {"id": "Europe/Rome", "name": "Rome (CET)", "offset": "UTC+1/+2"},
            {"id": "Europe/Madrid", "name": "Madrid (CET)", "offset": "UTC+1/+2"},
            {"id": "Europe/Zurich", "name": "Zurich (CET)", "offset": "UTC+1/+2"},
            {"id": "Europe/Stockholm", "name": "Stockholm (CET)", "offset": "UTC+1/+2"},
            {"id": "Europe/Moscow", "name": "Moscow (MSK)", "offset": "UTC+3"},
            {"id": "Europe/Istanbul", "name": "Istanbul (TRT)", "offset": "UTC+3"},
        ],
        "Asia & Pacific": [
            {"id": "Asia/Dubai", "name": "Dubai (GST)", "offset": "UTC+4"},
            {"id": "Asia/Kolkata", "name": "India (IST)", "offset": "UTC+5:30"},
            {"id": "Asia/Bangkok", "name": "Bangkok (ICT)", "offset": "UTC+7"},
            {"id": "Asia/Singapore", "name": "Singapore (SGT)", "offset": "UTC+8"},
            {"id": "Asia/Hong_Kong", "name": "Hong Kong (HKT)", "offset": "UTC+8"},
            {"id": "Asia/Shanghai", "name": "Shanghai (CST)", "offset": "UTC+8"},
            {"id": "Asia/Tokyo", "name": "Tokyo (JST)", "offset": "UTC+9"},
            {"id": "Asia/Seoul", "name": "Seoul (KST)", "offset": "UTC+9"},
            {"id": "Australia/Sydney", "name": "Sydney (AEST)", "offset": "UTC+10/+11"},
            {"id": "Australia/Melbourne", "name": "Melbourne (AEST)", "offset": "UTC+10/+11"},
            {"id": "Pacific/Auckland", "name": "Auckland (NZST)", "offset": "UTC+12/+13"},
        ],
        "Other": [
            {"id": "UTC", "name": "UTC (Coordinated Universal Time)", "offset": "UTC+0"},
            {"id": "Africa/Cairo", "name": "Cairo (EET)", "offset": "UTC+2"},
            {"id": "Africa/Johannesburg", "name": "Johannesburg (SAST)", "offset": "UTC+2"},
            {"id": "Africa/Lagos", "name": "Lagos (WAT)", "offset": "UTC+1"},
        ],
    }
    
    return {"timezones": timezones}


@router.get("/debug")
async def debug_settings():
    """Debug endpoint to see where .env file is and what's in it."""
    env_file = find_env_file()
    env_vars = read_env_file()
    
    return {
        "env_file_path": str(env_file),
        "env_file_exists": env_file.exists(),
        "cwd": str(Path.cwd()),
        "env_vars_from_file": {k: mask_api_key(v) if "KEY" in k else v for k, v in env_vars.items()},
        "env_vars_from_os": {
            "OPENROUTER_API_KEY": mask_api_key(os.environ.get("OPENROUTER_API_KEY")),
            "OPENROUTER_MODEL": os.environ.get("OPENROUTER_MODEL"),
            "TTS_PROVIDER": os.environ.get("TTS_PROVIDER"),
        }
    }
