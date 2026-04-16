#!/usr/bin/env python
"""
Augustus Testing CLI

A command-line interface for testing core features of the Augustus app,
including TTS integrations, news fetching, LLM generation, briefing generation,
and email notifications.

Usage:
    python cli.py --help
    python cli.py tts --help
    python cli.py news --help
    python cli.py llm --help
    python cli.py briefing --help
    python cli.py email --help

Email Commands:
    python cli.py email preview          # Preview email templates in browser
    python cli.py email send-test -r email@example.com  # Send test email
    python cli.py email list-schedules   # List scheduled briefings
    python cli.py email trigger-schedule # Trigger a scheduled briefing
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click


# Add app to path for imports
sys.path.insert(0, str(Path(__file__).parent))


def async_command(f):
    """Decorator to run async functions in click commands."""
    import functools
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


@click.group()
@click.version_option(version="1.0.0", prog_name="Augustus CLI")
def cli():
    """Augustus Testing CLI - Test core app features."""
    pass


# =============================================================================
# TTS Commands
# =============================================================================

@cli.group()
def tts():
    """Test Text-to-Speech integrations."""
    pass


@tts.command("list-providers")
def tts_list_providers():
    """List available TTS providers and their configuration."""
    from app.config import get_settings
    
    settings = get_settings()
    
    click.echo("\n" + "=" * 60)
    click.echo("  TTS Provider Configuration")
    click.echo("=" * 60)
    
    click.echo(f"\nCurrent Provider: {click.style(settings.tts_provider, fg='green', bold=True)}")
    
    click.echo("\n--- Piper ---")
    click.echo(f"  Model Path: {settings.piper_model_path}")
    click.echo(f"  URL: {settings.piper_url or '(not configured)'}")
    
    click.echo("\n--- ElevenLabs ---")
    click.echo(f"  API Key: {'[OK] configured' if settings.elevenlabs_api_key else '[--] not configured'}")
    click.echo(f"  Model: {settings.elevenlabs_model}")
    
    click.echo("\n--- Gemini ---")
    click.echo(f"  API Key: {'[OK] configured' if settings.gemini_api_key else '[!!] not configured'}")
    click.echo(f"  Model: {settings.gemini_model}")
    
    click.echo("")


@tts.command("list-voices")
@click.option("--provider", "-p", type=click.Choice(["piper", "elevenlabs", "gemini"]), 
              help="Filter by provider (default: current provider)")
@async_command
async def tts_list_voices(provider: Optional[str]):
    """List available voices for TTS providers."""
    from app.config import get_settings
    from app.services.tts.factory import TTSFactory
    
    settings = get_settings()
    provider = provider or settings.tts_provider
    
    click.echo(f"\nListing voices for {click.style(provider, fg='green', bold=True)}...\n")
    
    try:
        tts_provider = TTSFactory.get_provider(provider)
        voices = tts_provider.list_voices()
        
        click.echo(f"{'ID':<25} {'Name':<20} {'Description':<30} {'Language':<10}")
        click.echo("-" * 85)
        
        for voice in voices:
            click.echo(f"{voice.id:<25} {voice.name:<20} {(voice.description or ''):<30} {voice.language:<10}")
        
        click.echo(f"\nTotal: {len(voices)} voices")
        await tts_provider.close()
        
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg="red"))


@tts.command("test")
@click.option("--provider", "-p", type=click.Choice(["piper", "elevenlabs", "gemini"]),
              help="TTS provider to test (default: current provider)")
@click.option("--voice", "-v", help="Voice ID to use")
@click.option("--text", "-t", default="Hello! This is a test of the Augustus text-to-speech system. How does it sound?",
              help="Text to synthesize")
@click.option("--output", "-o", type=click.Path(), help="Output file path (default: test_output.mp3)")
@async_command
async def tts_test(provider: Optional[str], voice: Optional[str], text: str, output: Optional[str]):
    """Test TTS synthesis with a sample text."""
    from app.config import get_settings
    from app.services.tts.factory import TTSFactory
    
    settings = get_settings()
    provider = provider or settings.tts_provider
    
    # Default voices per provider
    default_voices = {
        "piper": "en_US-lessac-medium",
        "elevenlabs": "21m00Tcm4TlvDq8ikWAM",  # Rachel
        "gemini": "Kore",
    }
    voice = voice or default_voices.get(provider, "default")
    
    output_path = Path(output) if output else Path(f"test_output_{provider}.mp3")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    click.echo(f"\n{'=' * 60}")
    click.echo(f"  TTS Test - {provider.upper()}")
    click.echo(f"{'=' * 60}")
    click.echo(f"\nProvider: {provider}")
    click.echo(f"Voice: {voice}")
    click.echo(f"Text: {text[:100]}{'...' if len(text) > 100 else ''}")
    click.echo(f"Output: {output_path}")
    click.echo("")
    
    try:
        with click.progressbar(length=3, label="Synthesizing") as bar:
            bar.update(1)
            result = await TTSFactory.synthesize(
                text=text,
                voice_id=voice,
                output_path=output_path,
                provider_name=provider,
            )
            bar.update(2)
        
        click.echo(f"\n{click.style('[OK] Success!', fg='green', bold=True)}")
        click.echo(f"  Audio saved to: {result.audio_path}")
        click.echo(f"  Duration: {result.duration_seconds:.2f} seconds")
        click.echo(f"  Format: {result.format}")
        
    except Exception as e:
        click.echo(click.style(f"\n[!!] Error: {e}", fg="red"))
        raise click.Abort()


@tts.command("test-conversation")
@click.option("--provider", "-p", type=click.Choice(["piper", "elevenlabs", "gemini"]),
              help="TTS provider to test (default: current provider)")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@async_command
async def tts_test_conversation(provider: Optional[str], output: Optional[str]):
    """Test multi-speaker conversation synthesis."""
    from app.config import get_settings
    from app.services.tts.factory import TTSFactory
    
    settings = get_settings()
    provider = provider or settings.tts_provider
    
    # Sample conversation script
    script = [
        {"speaker": "HOST1", "text": "Welcome to today's tech news briefing! I'm excited to share some interesting developments with you."},
        {"speaker": "HOST2", "text": "Thanks for having me! There's been a lot happening in the AI space lately."},
        {"speaker": "HOST1", "text": "Absolutely! Let's dive right into our first story about the latest advancements in language models."},
        {"speaker": "HOST2", "text": "This is a really fascinating area. The progress we've seen in just the past year is remarkable."},
    ]
    
    # Voice maps per provider
    voice_maps = {
        "piper": {"HOST1": "en_US-lessac-medium", "HOST2": "en_US-amy-medium"},
        "elevenlabs": {"HOST1": "21m00Tcm4TlvDq8ikWAM", "HOST2": "AZnzlk1XvdvUeBnXmlld"},
        "gemini": {"HOST1": "Zephyr", "HOST2": "Sadachbia"},
    }
    
    voice_map = voice_maps.get(provider, voice_maps["piper"])
    output_path = Path(output) if output else Path(f"test_conversation_{provider}.mp3")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    click.echo(f"\n{'=' * 60}")
    click.echo(f"  Conversation Test - {provider.upper()}")
    click.echo(f"{'=' * 60}")
    click.echo(f"\nProvider: {provider}")
    click.echo(f"Segments: {len(script)}")
    click.echo(f"Voice Map: {voice_map}")
    click.echo(f"Output: {output_path}")
    click.echo("\nScript Preview:")
    for seg in script[:2]:
        click.echo(f"  {seg['speaker']}: {seg['text'][:50]}...")
    click.echo("")
    
    try:
        with click.progressbar(length=len(script) + 1, label="Generating segments") as bar:
            result = await TTSFactory.synthesize_conversation(
                script=script,
                output_path=output_path,
                voice_map=voice_map,
                provider_name=provider,
            )
            bar.update(len(script) + 1)
        
        click.echo(f"\n{click.style('[OK] Success!', fg='green', bold=True)}")
        click.echo(f"  Audio saved to: {result.audio_path}")
        click.echo(f"  Duration: {result.duration_seconds:.2f} seconds")
        click.echo(f"  Segments: {len(result.segment_timings) if result.segment_timings else 0}")
        
        if result.segment_timings:
            click.echo("\n  Segment Timings:")
            for seg in result.segment_timings:
                click.echo(f"    [{seg.start_seconds:.1f}s - {seg.end_seconds:.1f}s] {seg.speaker}: {seg.text[:40]}...")
        
    except Exception as e:
        click.echo(click.style(f"\n[!!] Error: {e}", fg="red"))
        import traceback
        traceback.print_exc()
        raise click.Abort()


# =============================================================================
# News Commands
# =============================================================================

@cli.group()
def news():
    """Test news fetching capabilities."""
    pass


@news.command("fetch-rss")
@click.option("--url", "-u", help="RSS feed URL (uses defaults if not provided)")
@click.option("--limit", "-l", default=5, help="Max items to display")
@async_command
async def news_fetch_rss(url: Optional[str], limit: int):
    """Fetch and display RSS feed items."""
    from app.services.news import get_news_service
    from app.config import get_settings
    
    settings = get_settings()
    news_service = get_news_service()
    
    click.echo(f"\n{'=' * 60}")
    click.echo("  RSS Feed Test")
    click.echo(f"{'=' * 60}")
    
    if url:
        urls = [url]
    else:
        urls = settings.rss_feed_list
        click.echo(f"\nUsing configured feeds: {len(urls)} feeds")
    
    try:
        items = await news_service.fetch_all_feeds(feed_urls=urls)
        
        click.echo(f"\nFetched {len(items)} items total\n")
        
        for i, item in enumerate(items[:limit], 1):
            click.echo(f"{click.style(f'[{i}]', fg='cyan', bold=True)} {item.title}")
            click.echo(f"    Source: {item.source}")
            click.echo(f"    Published: {item.published or 'Unknown'}")
            click.echo(f"    URL: {item.url[:60]}...")
            if item.summary:
                click.echo(f"    Summary: {item.summary[:100]}...")
            click.echo("")
        
        if len(items) > limit:
            click.echo(f"  ... and {len(items) - limit} more items")
        
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg="red"))
    finally:
        await news_service.close()


@news.command("fetch-newsapi")
@click.option("--topic", "-t", multiple=True, help="Topics to search (can specify multiple)")
@click.option("--limit", "-l", default=5, help="Max items to display")
@async_command
async def news_fetch_newsapi(topic: tuple, limit: int):
    """Fetch news from NewsAPI."""
    from app.services.news import get_news_service
    from app.config import get_settings
    
    settings = get_settings()
    news_service = get_news_service()
    
    if not settings.news_api_key:
        click.echo(click.style("Error: NEWS_API_KEY not configured", fg="red"))
        return
    
    topics = list(topic) if topic else ["technology", "business"]
    
    click.echo(f"\n{'=' * 60}")
    click.echo("  NewsAPI Test")
    click.echo(f"{'=' * 60}")
    click.echo(f"\nTopics: {', '.join(topics)}")
    
    try:
        items = await news_service.fetch_newsapi(topics=topics)
        
        click.echo(f"\nFetched {len(items)} items\n")
        
        for i, item in enumerate(items[:limit], 1):
            click.echo(f"{click.style(f'[{i}]', fg='cyan', bold=True)} {item.title}")
            click.echo(f"    Source: {item.source}")
            click.echo(f"    Category: {item.category}")
            click.echo(f"    Published: {item.published or 'Unknown'}")
            if item.summary:
                click.echo(f"    Summary: {item.summary[:100]}...")
            click.echo("")
        
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg="red"))
    finally:
        await news_service.close()


@news.command("fetch-reddit")
@click.option("--subreddit", "-s", default="technology", help="Subreddit to fetch from")
@click.option("--limit", "-l", default=5, help="Max items to display")
@async_command
async def news_fetch_reddit(subreddit: str, limit: int):
    """Fetch top posts from a Reddit subreddit."""
    from app.services.news import get_news_service
    
    news_service = get_news_service()
    
    click.echo(f"\n{'=' * 60}")
    click.echo(f"  Reddit Test - r/{subreddit}")
    click.echo(f"{'=' * 60}")
    
    try:
        items = await news_service.fetch_reddit_subreddit(subreddit=subreddit, limit=limit * 2)
        
        click.echo(f"\nFetched {len(items)} posts\n")
        
        for i, item in enumerate(items[:limit], 1):
            click.echo(f"{click.style(f'[{i}]', fg='cyan', bold=True)} {item.title}")
            click.echo(f"    Source: {item.source}")
            click.echo(f"    Author: {item.author or 'Unknown'}")
            click.echo(f"    Published: {item.published or 'Unknown'}")
            if item.summary:
                click.echo(f"    Preview: {item.summary[:100]}...")
            click.echo("")
        
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg="red"))
    finally:
        await news_service.close()


# =============================================================================
# LLM Commands
# =============================================================================

@cli.group()
def llm():
    """Test LLM (OpenRouter) integration."""
    pass


@llm.command("config")
def llm_config():
    """Show current LLM configuration."""
    from app.config import get_settings
    
    settings = get_settings()
    
    click.echo(f"\n{'=' * 60}")
    click.echo("  LLM Configuration")
    click.echo(f"{'=' * 60}")
    click.echo(f"\nProvider: OpenRouter")
    click.echo(f"API Key: {'[OK] configured' if settings.openrouter_api_key else '[!!] not configured'}")
    click.echo(f"Model: {settings.openrouter_model}")
    click.echo(f"Base URL: {settings.openrouter_base_url}")
    click.echo("")


@llm.command("test")
@click.option("--prompt", "-p", default="Write a one-paragraph summary about the benefits of AI assistants.",
              help="Prompt to send to the LLM")
@click.option("--system", "-s", help="System prompt (optional)")
@click.option("--max-tokens", default=500, help="Maximum tokens in response")
@async_command
async def llm_test(prompt: str, system: Optional[str], max_tokens: int):
    """Test LLM generation with a prompt."""
    from app.services.llm.openrouter import get_llm_provider
    
    llm = get_llm_provider()
    
    click.echo(f"\n{'=' * 60}")
    click.echo("  LLM Test")
    click.echo(f"{'=' * 60}")
    click.echo(f"\nModel: {llm.model}")
    click.echo(f"Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
    if system:
        click.echo(f"System: {system[:50]}...")
    click.echo(f"Max Tokens: {max_tokens}")
    click.echo("\nGenerating...")
    
    try:
        response = await llm.generate(
            prompt=prompt,
            system_prompt=system,
            max_tokens=max_tokens,
        )
        
        click.echo(f"\n{click.style('[OK] Response:', fg='green', bold=True)}")
        click.echo("-" * 40)
        click.echo(response.content)
        click.echo("-" * 40)
        click.echo(f"\nModel used: {response.model}")
        click.echo(f"Usage: {response.usage}")
        
    except Exception as e:
        click.echo(click.style(f"\n[!!] Error: {e}", fg="red"))
    finally:
        await llm.close()


@llm.command("list-personalities")
def llm_list_personalities():
    """List available podcast host personalities."""
    from app.services.llm.personalities import get_all_personalities
    
    personalities = get_all_personalities()
    
    click.echo(f"\n{'=' * 60}")
    click.echo("  Available Personalities")
    click.echo(f"{'=' * 60}")
    
    click.echo(f"\n{'ID':<15} {'Name':<20} {'Description':<40}")
    click.echo("-" * 75)
    
    for pid, personality in personalities.items():
        desc = personality.description[:37] + "..." if len(personality.description) > 40 else personality.description
        click.echo(f"{pid:<15} {personality.name:<20} {desc:<40}")
    
    click.echo(f"\nTotal: {len(personalities)} personalities")


# =============================================================================
# Briefing Commands
# =============================================================================

@cli.group()
def briefing():
    """Test briefing generation pipeline."""
    pass


@briefing.command("config")
def briefing_config():
    """Show current briefing configuration."""
    from app.config import get_settings
    
    settings = get_settings()
    
    click.echo(f"\n{'=' * 60}")
    click.echo("  Briefing Configuration")
    click.echo(f"{'=' * 60}")
    click.echo(f"\nDuration: {settings.briefing_duration_minutes} minutes")
    click.echo(f"Complexity: {settings.conversation_complexity}/5")
    click.echo(f"User Name: {settings.user_name or '(not set)'}")
    click.echo(f"Timezone: {settings.timezone}")
    click.echo(f"TTS Provider: {settings.tts_provider}")
    click.echo(f"Non-speech Sounds: {'[OK] enabled' if settings.enable_non_speech_sounds else '[--] disabled'}")
    click.echo(f"LLM Model: {settings.openrouter_model}")
    click.echo("")


@briefing.command("generate-script")
@click.option("--topic", "-t", multiple=True, help="Topics to include")
@click.option("--duration", "-d", default=5, help="Target duration in minutes")
@click.option("--non-speech-sounds", is_flag=True, help="Enable non-speech sounds markup (for Gemini TTS)")
@async_command
async def briefing_generate_script(topic: tuple, duration: int, non_speech_sounds: bool):
    """Generate a podcast script (without audio)."""
    from app.config import get_settings
    from app.services.news import get_news_service
    from app.services.llm.openrouter import get_llm_provider
    from app.services.llm.agents.orchestrator import BriefingOrchestrator
    
    settings = get_settings()
    topics = list(topic) if topic else ["technology"]
    # Use flag if provided, otherwise use settings
    enable_non_speech_sounds = non_speech_sounds or settings.enable_non_speech_sounds
    
    click.echo(f"\n{'=' * 60}")
    click.echo("  Script Generation Test")
    click.echo(f"{'=' * 60}")
    click.echo(f"\nTopics: {', '.join(topics)}")
    click.echo(f"Duration: {duration} minutes")
    click.echo(f"Non-speech Sounds: {'enabled' if enable_non_speech_sounds else 'disabled'}")
    
    news_service = get_news_service()
    llm = get_llm_provider()
    orchestrator = BriefingOrchestrator(llm)
    
    try:
        # Step 1: Fetch news
        click.echo("\n[1/3] Fetching news...")
        all_items = []
        
        rss_items = await news_service.fetch_all_feeds()
        all_items.extend(rss_items)
        click.echo(f"  - RSS feeds: {len(rss_items)} items")
        
        newsapi_items = await news_service.fetch_newsapi(topics=topics)
        all_items.extend(newsapi_items)
        click.echo(f"  - NewsAPI: {len(newsapi_items)} items")
        
        # Dedupe
        seen = set()
        unique_items = []
        for item in all_items:
            key = item.title.lower()[:50]
            if key not in seen:
                seen.add(key)
                unique_items.append(item)
        
        click.echo(f"  - Total unique: {len(unique_items)} items")
        
        # Step 2: Format content
        click.echo("\n[2/3] Formatting content...")
        news_content = news_service.format_news_for_briefing(unique_items[:10])
        
        # Step 3: Generate script
        click.echo("\n[3/3] Generating script...")
        
        # Simple cast for testing
        cast_members = [
            {"name": "Alex", "personality": "professional", "voice_id": "host1", "order": 1},
            {"name": "Jordan", "personality": "friendly", "voice_id": "host2", "order": 2},
        ]
        
        response = await orchestrator.write_briefing_script(
            content=news_content,
            topics=topics,
            cast_members=cast_members,
            duration=duration,
            user_name=None,
            complexity=3,
            enable_non_speech_sounds=enable_non_speech_sounds,
        )
        
        click.echo(f"\n{click.style('[OK] Script Generated!', fg='green', bold=True)}")
        click.echo("-" * 60)
        
        # Display script preview
        script = response.content
        lines = script.split('\n')
        preview_lines = lines[:30]
        click.echo('\n'.join(preview_lines))
        
        if len(lines) > 30:
            click.echo(f"\n... ({len(lines) - 30} more lines)")
        
        click.echo("-" * 60)
        click.echo(f"\nTotal length: {len(script)} characters")
        click.echo(f"Model: {response.model}")
        click.echo(f"Usage: {response.usage}")
        
    except Exception as e:
        click.echo(click.style(f"\n[!!] Error: {e}", fg="red"))
        import traceback
        traceback.print_exc()
    finally:
        await news_service.close()
        await llm.close()


@briefing.command("full-test")
@click.option("--topic", "-t", multiple=True, help="Topics to include")
@click.option("--duration", "-d", default=2, help="Target duration in minutes (keep short for testing)")
@click.option("--provider", "-p", type=click.Choice(["piper", "elevenlabs", "gemini"]),
              help="TTS provider to use")
@click.option("--output", "-o", type=click.Path(), help="Output audio file path")
@click.option("--non-speech-sounds", is_flag=True, help="Enable non-speech sounds markup (for Gemini TTS)")
@async_command
async def briefing_full_test(topic: tuple, duration: int, provider: Optional[str], output: Optional[str], non_speech_sounds: bool):
    """Run a full briefing generation test (news + script + audio)."""
    from app.config import get_settings
    from app.services.news import get_news_service
    from app.services.llm.openrouter import get_llm_provider
    from app.services.llm.agents.orchestrator import BriefingOrchestrator
    from app.services.tts.factory import TTSFactory
    
    settings = get_settings()
    topics = list(topic) if topic else ["technology"]
    provider = provider or settings.tts_provider
    # Use flag if provided, otherwise use settings
    enable_non_speech_sounds = non_speech_sounds or settings.enable_non_speech_sounds
    output_path = Path(output) if output else Path(f"test_briefing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3")
    
    click.echo(f"\n{'=' * 60}")
    click.echo("  Full Briefing Generation Test")
    click.echo(f"{'=' * 60}")
    click.echo(f"\nTopics: {', '.join(topics)}")
    click.echo(f"Duration: {duration} minutes")
    click.echo(f"TTS Provider: {provider}")
    click.echo(f"Non-speech Sounds: {'enabled' if enable_non_speech_sounds else 'disabled'}")
    click.echo(f"Output: {output_path}")
    
    news_service = get_news_service()
    llm = get_llm_provider()
    orchestrator = BriefingOrchestrator(llm)
    
    try:
        # Step 1: Fetch news
        click.echo("\n[1/4] Fetching news...")
        all_items = []
        
        rss_items = await news_service.fetch_all_feeds()
        all_items.extend(rss_items)
        
        newsapi_items = await news_service.fetch_newsapi(topics=topics)
        all_items.extend(newsapi_items)
        
        # Dedupe
        seen = set()
        unique_items = []
        for item in all_items:
            key = item.title.lower()[:50]
            if key not in seen:
                seen.add(key)
                unique_items.append(item)
        
        click.echo(f"  Fetched {len(unique_items)} unique items")
        
        # Step 2: Format content
        click.echo("\n[2/4] Formatting content...")
        news_content = news_service.format_news_for_briefing(unique_items[:5])  # Limit for short test
        
        # Step 3: Generate script
        click.echo("\n[3/4] Generating script...")
        
        cast_members = [
            {"name": "Alex", "personality": "professional", "voice_id": "host1", "order": 1},
            {"name": "Jordan", "personality": "friendly", "voice_id": "host2", "order": 2},
        ]
        
        response = await orchestrator.write_briefing_script(
            content=news_content,
            topics=topics,
            cast_members=cast_members,
            duration=duration,
            user_name=None,
            complexity=3,
            enable_non_speech_sounds=enable_non_speech_sounds,
        )
        
        script_text = response.content
        click.echo(f"  Generated script: {len(script_text)} characters")
        
        # Parse script into segments
        import re
        segments = []
        pattern = r'^(Alex|Jordan):\s*(.+?)(?=^(Alex|Jordan):|\Z)'
        matches = re.findall(pattern, script_text, re.MULTILINE | re.DOTALL)
        
        name_to_host = {"Alex": "HOST1", "Jordan": "HOST2"}
        for match in matches:
            speaker = match[0]
            text = match[1].strip()
            if text:
                segments.append({
                    "speaker": name_to_host.get(speaker, "HOST1"),
                    "text": text,
                })
        
        if not segments:
            # Fallback: treat whole script as one speaker
            segments = [{"speaker": "HOST1", "text": script_text}]
        
        click.echo(f"  Parsed {len(segments)} segments")
        
        # Step 4: Generate audio
        click.echo("\n[4/4] Generating audio...")
        
        # Voice maps per provider
        voice_maps = {
            "piper": {"HOST1": "en_US-lessac-medium", "HOST2": "en_US-amy-medium"},
            "elevenlabs": {"HOST1": "21m00Tcm4TlvDq8ikWAM", "HOST2": "AZnzlk1XvdvUeBnXmlld"},
            "gemini": {"HOST1": "Kore", "HOST2": "Sadachbia"},
        }
        voice_map = voice_maps.get(provider, voice_maps["piper"])
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        result = await TTSFactory.synthesize_conversation(
            script=segments,
            output_path=output_path,
            voice_map=voice_map,
            provider_name=provider,
        )
        
        click.echo(f"\n{click.style('[OK] Briefing Generated Successfully!', fg='green', bold=True)}")
        click.echo("-" * 60)
        click.echo(f"Audio file: {result.audio_path}")
        click.echo(f"Duration: {result.duration_seconds:.2f} seconds ({result.duration_seconds/60:.1f} minutes)")
        click.echo(f"Segments: {len(result.segment_timings) if result.segment_timings else len(segments)}")
        click.echo("-" * 60)
        
    except Exception as e:
        click.echo(click.style(f"\n[!!] Error: {e}", fg="red"))
        import traceback
        traceback.print_exc()
    finally:
        await news_service.close()
        await llm.close()


# =============================================================================
# Email Commands
# =============================================================================

@cli.group()
def email():
    """Test email notifications and templates."""
    pass


@email.command("preview")
@click.option("--port", "-p", default=8099, help="Port to serve the preview on")
@click.option("--type", "-t", "email_type", type=click.Choice(["single", "batched", "all"]), default="all",
              help="Type of email template to preview")
def email_preview(port: int, email_type: str):
    """Serve email templates as a webpage for visual testing.
    
    Opens a local web server displaying email templates with sample data.
    """
    import http.server
    import socketserver
    from datetime import datetime
    
    # Generate test data
    test_briefings = [
        {
            "id": "test-briefing-1",
            "title": "Morning Tech News Roundup",
            "summary": "Today's briefing covers major developments in AI and machine learning, including new language model capabilities and their real-world applications. We also discuss the latest tech industry trends and what they mean for businesses and consumers.",
            "audio_url": "/audio/test-briefing-1.mp3",
            "duration_seconds": 320.5,
            "created_at": datetime.now(),
        },
        {
            "id": "test-briefing-2",
            "title": "Business & Finance Update",
            "summary": "Market movements in the tech sector take center stage as several major companies announce quarterly earnings. We analyze the financial implications and what investors should watch for in the coming weeks.",
            "audio_url": "/audio/test-briefing-2.mp3",
            "duration_seconds": 245.0,
            "created_at": datetime.now(),
        },
        {
            "id": "test-briefing-3",
            "title": "Science & Innovation Spotlight",
            "summary": "Researchers announce a breakthrough in renewable energy technology that could transform how we power our homes and businesses. We explore the implications for the energy sector and climate goals.",
            "audio_url": "/audio/test-briefing-3.mp3",
            "duration_seconds": 180.0,
            "created_at": datetime.now(),
        },
    ]
    
    def generate_single_email_html(briefing: dict) -> str:
        """Generate single briefing email HTML."""
        summary = briefing.get("summary", "")
        if summary:
            summary = summary[:500] + "..." if len(summary) > 500 else summary
        
        briefing_url = f"http://localhost:3000/briefing/{briefing['id']}?autoplay=true"
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin: 0; padding: 0; background-color: #f5f5f5; font-family: Arial, Helvetica, sans-serif;">
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f5f5f5;">
                <tr>
                    <td align="center" style="padding: 20px 0;">
                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="max-width: 600px; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <!-- Header -->
                            <tr>
                                <td style="background-color: #e85d04; padding: 32px 24px; text-align: center;">
                                    <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 600; font-family: Arial, Helvetica, sans-serif;">Augustus Today</h1>
                                </td>
                            </tr>
                            <!-- Content -->
                            <tr>
                                <td style="padding: 24px; background-color: #ffffff;">
                                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                        <tr>
                                            <td style="background-color: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 6px; padding: 20px;">
                                                <h2 style="margin: 0 0 16px 0; color: #333333; font-size: 20px; font-weight: 600; font-family: Arial, Helvetica, sans-serif;">{briefing['title']}</h2>
                                                {f'<p style="margin: 0 0 20px 0; color: #666666; font-size: 14px; line-height: 1.6; font-family: Arial, Helvetica, sans-serif;">{summary}</p>' if summary else ''}
                                                {f'<table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr><td><a href="{briefing_url}" style="display: inline-block; padding: 12px 24px; background-color: #e85d04; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 14px; font-family: Arial, Helvetica, sans-serif;">▶ Play Now</a></td></tr></table>' if briefing_url else ''}
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
    
    def generate_batched_email_html(briefings: list) -> str:
        """Generate batched briefings email HTML."""
        briefing_items_html = ""
        for briefing in briefings:
            summary = briefing.get("summary", "")
            if summary:
                summary = summary[:300] + "..." if len(summary) > 300 else summary
            
            briefing_url = f"http://localhost:3000/briefing/{briefing['id']}?autoplay=true"
            
            duration_str = ""
            if briefing.get("duration_seconds"):
                mins = int(briefing["duration_seconds"] // 60)
                secs = int(briefing["duration_seconds"] % 60)
                duration_str = f"{mins}:{secs:02d}"
            
            briefing_items_html += f"""
                            <tr>
                                <td style="padding-bottom: 16px;">
                                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 6px; padding: 20px;">
                                        <tr>
                                            <td>
                                                <h3 style="margin: 0 0 12px 0; color: #333333; font-size: 18px; font-weight: 600; font-family: Arial, Helvetica, sans-serif;">{briefing['title']}</h3>
                                                {f'<p style="margin: 0 0 16px 0; color: #666666; font-size: 14px; line-height: 1.6; font-family: Arial, Helvetica, sans-serif;">{summary}</p>' if summary else ''}
                                                <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                                                    <tr>
                                                        <td>
                                                            <a href="{briefing_url}" style="display: inline-block; padding: 10px 20px; background-color: #e85d04; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 13px; font-family: Arial, Helvetica, sans-serif;">▶ Play Now</a>
                                                            {f'<span style="color: #999999; font-size: 13px; font-family: monospace; margin-left: 12px;">{duration_str}</span>' if duration_str else ''}
                                                        </td>
                                                    </tr>
                                                </table>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
            """
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin: 0; padding: 0; background-color: #f5f5f5; font-family: Arial, Helvetica, sans-serif;">
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f5f5f5;">
                <tr>
                    <td align="center" style="padding: 20px 0;">
                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="max-width: 600px; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <!-- Header -->
                            <tr>
                                <td style="background-color: #e85d04; padding: 32px 24px; text-align: center;">
                                    <h1 style="margin: 0 0 8px 0; color: #ffffff; font-size: 24px; font-weight: 600; font-family: Arial, Helvetica, sans-serif;">Augustus Today</h1>
                                    <p style="margin: 0; color: #ffffff; font-size: 14px; font-family: Arial, Helvetica, sans-serif;">You have {len(briefings)} new briefing{'' if len(briefings) == 1 else 's'}</p>
                                </td>
                            </tr>
                            <!-- Content -->
                            <tr>
                                <td style="padding: 24px; background-color: #ffffff;">
                                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                        {briefing_items_html}
                                    </table>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
    
    def generate_index_html() -> str:
        """Generate index page with links to all email templates."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Augustus Email Preview</title>
            <style>
                * {{ box-sizing: border-box; }}
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; 
                    line-height: 1.6; 
                    color: #eeeef0; 
                    background-color: #0f0f12;
                    margin: 0;
                    padding: 40px 20px;
                }}
                .container {{ 
                    max-width: 800px; 
                    margin: 0 auto;
                }}
                h1 {{
                    color: #e85d04;
                    margin-bottom: 8px;
                }}
                .subtitle {{
                    color: #747484;
                    margin-bottom: 32px;
                }}
                .card {{
                    background-color: rgba(58, 58, 65, 0.5);
                    border: 1px solid rgba(66, 66, 75, 0.5);
                    padding: 24px;
                    border-radius: 12px;
                    margin-bottom: 16px;
                }}
                .card h3 {{
                    margin-top: 0;
                    margin-bottom: 8px;
                    color: #ffffff;
                }}
                .card p {{
                    color: #b8b8c1;
                    margin-bottom: 16px;
                }}
                .card a {{
                    display: inline-block;
                    background-color: #e85d04;
                    color: white;
                    padding: 10px 20px;
                    border-radius: 8px;
                    text-decoration: none;
                    font-weight: 500;
                }}
                .card a:hover {{
                    background-color: #d14e00;
                }}
                .info {{
                    background-color: rgba(232, 93, 4, 0.1);
                    border: 1px solid rgba(232, 93, 4, 0.3);
                    padding: 16px;
                    border-radius: 8px;
                    margin-top: 24px;
                    color: #e85d04;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Augustus Email Preview</h1>
                <p class="subtitle">Preview email templates with sample data</p>
                
                <div class="card">
                    <h3>Single Briefing Email</h3>
                    <p>The email sent when a single briefing is ready</p>
                    <a href="/single">View Template</a>
                </div>
                
                <div class="card">
                    <h3>Batched Briefings Email</h3>
                    <p>The email sent when multiple briefings are batched together</p>
                    <a href="/batched">View Template</a>
                </div>
                
                <div class="info">
                    <strong>Tip:</strong> These templates use test data. To test with real data, use the 
                    <code>email send-test</code> command.
                </div>
            </div>
        </body>
        </html>
        """
    
    class EmailPreviewHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/" or self.path == "/index.html":
                content = generate_index_html()
            elif self.path == "/single":
                content = generate_single_email_html(test_briefings[0])
            elif self.path == "/batched":
                content = generate_batched_email_html(test_briefings)
            else:
                self.send_error(404, "Not Found")
                return
            
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
        
        def log_message(self, format, *args):
            # Suppress default logging
            pass
    
    click.echo(f"\n{'=' * 60}")
    click.echo("  Email Template Preview Server")
    click.echo(f"{'=' * 60}")
    click.echo(f"\nServing email templates at: {click.style(f'http://localhost:{port}', fg='cyan', bold=True)}")
    click.echo("\nAvailable routes:")
    click.echo(f"  /         - Index page with all templates")
    click.echo(f"  /single   - Single briefing email")
    click.echo(f"  /batched  - Batched briefings email")
    click.echo(f"\nPress Ctrl+C to stop the server")
    
    try:
        with socketserver.TCPServer(("", port), EmailPreviewHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        click.echo("\n\nServer stopped.")


@email.command("send-test")
@click.option("--recipient", "-r", required=True, help="Email address to send test email to")
@click.option("--type", "-t", "email_type", type=click.Choice(["single", "batched"]), default="single",
              help="Type of email to send")
@click.option("--api-key", "-k", help="Resend API key (uses global config if not provided)")
@async_command
async def email_send_test(recipient: str, email_type: str, api_key: Optional[str]):
    """Send a test email with sample briefing data.
    
    This sends a real email using the Resend API to verify email delivery.
    Uses sample briefing data for testing.
    """
    from app.config import get_settings
    from app.services.email import send_briefing_email, send_batched_briefings_email
    from app.models.briefing import Briefing
    
    settings = get_settings()
    api_key = api_key or getattr(settings, 'resend_api_key', None)
    
    if not api_key:
        click.echo(click.style("[!!] Error: No Resend API key configured", fg="red"))
        click.echo("    Set RESEND_API_KEY environment variable or use --api-key option")
        return
    
    click.echo(f"\n{'=' * 60}")
    click.echo("  Test Email Sender")
    click.echo(f"{'=' * 60}")
    click.echo(f"\nRecipient: {recipient}")
    click.echo(f"Type: {email_type}")
    
    if email_type == "single":
        click.echo("\nSending single briefing test email...")
        
        success = await send_briefing_email(
            briefing_title="Morning Tech News Roundup",
            briefing_summary="Today's briefing covers major developments in AI and machine learning, including new language model capabilities and their real-world applications. We also discuss the latest tech industry trends and what they mean for businesses and consumers.",
            audio_url=None,
            recipients=[recipient],
            briefing_id="test-briefing-123",
            api_key=api_key,
        )
        
        if success:
            click.echo(click.style("\n[OK] Test email sent successfully!", fg="green", bold=True))
        else:
            click.echo(click.style("\n[!!] Failed to send test email", fg="red"))
    
    else:  # batched
        click.echo("\nSending batched briefings test email...")
        
        # Create sample Briefing objects
        class SampleBriefing:
            def __init__(self, id, title, summary, duration_seconds):
                self.id = id
                self.title = title
                self.duration_seconds = duration_seconds
                self.extra_data = {'story_analysis': summary}
        
        sample_briefings = [
            SampleBriefing(
                id="test-1",
                title="Morning Tech News Roundup",
                summary="Today's briefing covers major developments in AI and machine learning, including new language model capabilities and their real-world applications.",
                duration_seconds=320.5,
            ),
            SampleBriefing(
                id="test-2",
                title="Business & Finance Update",
                summary="Market movements in the tech sector take center stage as several major companies announce quarterly earnings. We analyze the financial implications and what investors should watch for.",
                duration_seconds=245.0,
            ),
        ]
        
        success = await send_batched_briefings_email(
            briefings=sample_briefings,
            recipients=[recipient],
            api_key=api_key,
        )
        
        if success:
            click.echo(click.style(f"\n[OK] Test batched email sent successfully with {len(sample_briefings)} briefings!", fg="green", bold=True))
        else:
            click.echo(click.style("\n[!!] Failed to send test batched email", fg="red"))


@email.command("trigger-schedule")
@click.option("--schedule-id", "-s", help="Scheduled briefing ID to trigger (optional)")
@click.option("--user-id", "-u", default="default", help="User ID to use (default: 'default')")
@click.option("--force", "-f", is_flag=True, help="Force trigger even if already generated today")
@async_command
async def email_trigger_schedule(schedule_id: Optional[str], user_id: str, force: bool):
    """Trigger scheduled briefing email notifications for testing.
    
    This will:
    1. List all active scheduled briefings (if no schedule-id provided)
    2. Generate briefings and send email notifications
    
    Use this to test the full scheduled briefing + email pipeline.
    """
    from app.config import get_settings
    from app.database import get_db, init_db
    from app.services.scheduled_briefing import ScheduledBriefingService
    from sqlalchemy import select
    from app.models.scheduled_briefing import ScheduledBriefing
    
    settings = get_settings()
    
    click.echo(f"\n{'=' * 60}")
    click.echo("  Scheduled Briefing Email Trigger")
    click.echo(f"{'=' * 60}")
    
    # Initialize database
    await init_db()
    
    from app.database import async_session
    async with async_session() as db:
        service = ScheduledBriefingService(db)
        
        if schedule_id:
            # Trigger specific schedule
            schedule = await service.get_scheduled_briefing(schedule_id)
            if not schedule:
                click.echo(click.style(f"\n[!!] Schedule {schedule_id} not found", fg="red"))
                return
            
            schedules = [schedule]
        else:
            # List all active schedules
            result = await db.execute(
                select(ScheduledBriefing)
                .where(ScheduledBriefing.is_active == True)
            )
            schedules = list(result.scalars().all())
        
        if not schedules:
            click.echo("\nNo active scheduled briefings found.")
            click.echo("Create a scheduled briefing first using the web interface.")
            return
        
        click.echo(f"\nFound {len(schedules)} active scheduled briefing(s):\n")
        
        for i, sched in enumerate(schedules, 1):
            click.echo(f"  [{i}] {click.style(sched.name, fg='cyan', bold=True)}")
            click.echo(f"      ID: {sched.id}")
            click.echo(f"      Schedule: {sched.schedule_time} on days {sched.schedule_days}")
            click.echo(f"      Topics: {len(sched.topic_ids or [])} topics")
            click.echo(f"      Notifications: {sched.notification_methods}")
            if 'email' in (sched.notification_methods or []):
                click.echo(f"      Email recipients: {sched.email_recipients}")
            click.echo(f"      Last generated: {sched.last_generated_at or 'Never'}")
            click.echo("")
        
        if not schedule_id:
            # Ask which one to trigger
            choice = click.prompt(
                "Enter schedule number to trigger (or 'q' to quit)",
                default="q"
            )
            
            if choice.lower() == 'q':
                click.echo("Cancelled.")
                return
            
            try:
                idx = int(choice) - 1
                if idx < 0 or idx >= len(schedules):
                    raise ValueError()
                selected_schedule = schedules[idx]
            except (ValueError, IndexError):
                click.echo(click.style("Invalid selection", fg="red"))
                return
        else:
            selected_schedule = schedules[0]
        
        click.echo(f"\nTriggering: {click.style(selected_schedule.name, fg='cyan', bold=True)}")
        
        # Check if email notifications are configured
        if 'email' not in (selected_schedule.notification_methods or []):
            click.echo(click.style("\n[!!] Warning: Email notifications not enabled for this schedule", fg="yellow"))
            if not click.confirm("Continue anyway?"):
                return
        
        if not selected_schedule.email_recipients:
            click.echo(click.style("\n[!!] Warning: No email recipients configured", fg="yellow"))
            if not click.confirm("Continue anyway?"):
                return
        
        # Trigger the briefing generation
        click.echo("\n[1/3] Triggering briefing generation...")
        
        try:
            briefing = await service.trigger_scheduled_briefing(
                schedule_id=selected_schedule.id,
                db_url=settings.database_url,
            )
            
            if briefing:
                click.echo(f"\n{click.style('[OK] Briefing generated!', fg='green', bold=True)}")
                click.echo(f"  ID: {briefing.id}")
                click.echo(f"  Title: {briefing.title}")
                click.echo(f"  Status: {briefing.status}")
                
                if 'email' in (selected_schedule.notification_methods or []):
                    click.echo("\n[2/3] Email notification scheduled...")
                    click.echo("  Note: Batched emails are sent after a 90-second delay")
                    click.echo("  to allow multiple briefings to be combined.")
                else:
                    click.echo("\n[2/3] Skipping email (not configured)")
                
                click.echo("\n[3/3] Done!")
            else:
                click.echo(click.style("\n[!!] Briefing generation failed or was skipped", fg="red"))
                click.echo("  Check the logs for more details.")
        
        except Exception as e:
            click.echo(click.style(f"\n[!!] Error: {e}", fg="red"))
            import traceback
            traceback.print_exc()


@email.command("list-schedules")
@async_command
async def email_list_schedules():
    """List all scheduled briefings with their email configuration."""
    from app.database import init_db, async_session
    from sqlalchemy import select
    from app.models.scheduled_briefing import ScheduledBriefing
    
    click.echo(f"\n{'=' * 60}")
    click.echo("  Scheduled Briefings")
    click.echo(f"{'=' * 60}")
    
    # Initialize database
    await init_db()
    
    async with async_session() as db:
        result = await db.execute(
            select(ScheduledBriefing).order_by(ScheduledBriefing.created_at.desc())
        )
        schedules = list(result.scalars().all())
    
    if not schedules:
        click.echo("\nNo scheduled briefings found.")
        return
    
    click.echo(f"\nFound {len(schedules)} scheduled briefing(s):\n")
    
    for sched in schedules:
        status_color = "green" if sched.is_active else "red"
        status_text = "[ON]" if sched.is_active else "[OFF]"
        
        click.echo(f"  {click.style(status_text, fg=status_color)} {click.style(sched.name, bold=True)}")
        click.echo(f"      ID: {sched.id}")
        click.echo(f"      Time: {sched.schedule_time} | Days: {sched.schedule_days}")
        click.echo(f"      Duration: {sched.max_duration_minutes} min")
        
        # Notification info
        notifs = sched.notification_methods or []
        if 'email' in notifs:
            recipients = sched.email_recipients or []
            click.echo(f"      Email: {click.style('enabled', fg='green')} -> {recipients}")
        else:
            click.echo(f"      Email: {click.style('disabled', fg='white')}")
        
        if 'webhook' in notifs:
            click.echo(f"      Webhook: {click.style('enabled', fg='green')} -> {sched.webhook_url}")
        
        click.echo(f"      Last run: {sched.last_generated_at or 'Never'}")
        click.echo("")


# =============================================================================
# Status Commands
# =============================================================================

@cli.command("status")
def status():
    """Show overall system status and configuration."""
    from app.config import get_settings
    
    settings = get_settings()
    
    click.echo(f"\n{'=' * 60}")
    click.echo(f"  {click.style('Augustus System Status', fg='cyan', bold=True)}")
    click.echo(f"{'=' * 60}")
    
    # App Info
    click.echo(f"\n{click.style('Application', fg='yellow', bold=True)}")
    click.echo(f"  Name: {settings.app_name}")
    click.echo(f"  Version: {settings.app_version}")
    click.echo(f"  Debug: {settings.debug}")
    
    # Database
    click.echo(f"\n{click.style('Database', fg='yellow', bold=True)}")
    db_url = settings.database_url
    if "sqlite" in db_url:
        db_path = db_url.split("///")[-1]
        db_exists = Path(db_path).exists() if not db_path.startswith(":") else True
        click.echo(f"  Type: SQLite")
        click.echo(f"  Path: {db_path}")
        click.echo(f"  Status: {'[OK] exists' if db_exists else '[!!] not found'}")
    else:
        click.echo(f"  URL: {db_url[:50]}...")
    
    # TTS
    click.echo(f"\n{click.style('Text-to-Speech', fg='yellow', bold=True)}")
    click.echo(f"  Provider: {settings.tts_provider}")
    
    tts_status = []
    if settings.piper_url or Path(settings.piper_model_path).exists():
        tts_status.append(("Piper", "[OK]"))
    else:
        tts_status.append(("Piper", "[--]"))
    
    if settings.elevenlabs_api_key:
        tts_status.append(("ElevenLabs", "[OK]"))
    else:
        tts_status.append(("ElevenLabs", "[--]"))
    
    if settings.gemini_api_key:
        tts_status.append(("Gemini", "[OK]"))
    else:
        tts_status.append(("Gemini", "[--]"))
    
    for name, status in tts_status:
        color = "green" if "[OK]" in status else "white"
        click.echo(f"  {name}: {click.style(status, fg=color)}")
    
    # LLM
    click.echo(f"\n{click.style('LLM (OpenRouter)', fg='yellow', bold=True)}")
    click.echo(f"  API Key: {'[OK] configured' if settings.openrouter_api_key else '[!!] not configured'}")
    click.echo(f"  Model: {settings.openrouter_model}")
    
    # News Sources
    click.echo(f"\n{click.style('News Sources', fg='yellow', bold=True)}")
    click.echo(f"  NewsAPI: {'[OK] configured' if settings.news_api_key else '[--] not configured'}")
    click.echo(f"  RSS Feeds: {len(settings.rss_feed_list)} configured")
    
    # Content Settings
    click.echo(f"\n{click.style('Content Settings', fg='yellow', bold=True)}")
    click.echo(f"  Duration: {settings.briefing_duration_minutes} minutes")
    click.echo(f"  Complexity: {settings.conversation_complexity}/5")
    click.echo(f"  Non-speech Sounds: {'[OK] enabled' if settings.enable_non_speech_sounds else '[--] disabled'}")
    click.echo(f"  Timezone: {settings.timezone}")
    click.echo(f"  User Name: {settings.user_name or '(not set)'}")
    
    click.echo("\n" + "=" * 60)
    click.echo("Use 'python cli.py --help' to see available commands")
    click.echo("")


if __name__ == "__main__":
    cli()

