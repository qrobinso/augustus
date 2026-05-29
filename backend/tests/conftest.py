"""Shared test fixtures."""
import os
import tempfile

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database import Base
# Import all models so Base.metadata is fully populated before create_all.
import app.models  # noqa: F401
from app.models import briefing, user, profile, cast, topic, custom_site, article, scheduled_briefing, api_key  # noqa


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """In-memory async SQLite session with all tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


def make_silent_mp3(path: str, frames: int = 40) -> None:
    """Write a minimal valid MPEG-1 Layer III MP3 (128kbps, 44.1kHz, mono).

    No ffmpeg needed. Each frame is 417 bytes: a 4-byte header + zero padding.
    """
    header = bytes([0xFF, 0xFB, 0x90, 0xC0])
    frame = header + bytes(417 - len(header))
    with open(path, "wb") as f:
        f.write(frame * frames)


@pytest.fixture
def silent_mp3(tmp_path):
    """Path to a freshly generated silent MP3 file."""
    p = str(tmp_path / "test.mp3")
    make_silent_mp3(p)
    return p


from app.services.llm.base import LLMProvider, LLMResponse


class FakeLLM(LLMProvider):
    """Recording fake provider. Captures call kwargs; returns canned content."""

    def __init__(self, response_content: str = "{}"):
        self.response_content = response_content
        self.calls: list[dict] = []

    async def generate(self, prompt, system_prompt=None, max_tokens=4096,
                       temperature=0.7, response_format=None, briefing_id=None):
        self.calls.append({
            "prompt": prompt, "system_prompt": system_prompt,
            "max_tokens": max_tokens, "temperature": temperature,
            "response_format": response_format,
        })
        return LLMResponse(content=self.response_content, model="fake", usage={})

    async def generate_conversation(self, messages, max_tokens=4096,
                                   temperature=0.7, response_format=None, briefing_id=None):
        self.calls.append({
            "messages": messages, "max_tokens": max_tokens,
            "temperature": temperature, "response_format": response_format,
        })
        return LLMResponse(content=self.response_content, model="fake", usage={})

    async def close(self):
        pass
