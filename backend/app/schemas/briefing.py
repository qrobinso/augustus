"""Briefing schemas for API validation."""

import math
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.base import UTCDatetime, UTCDatetimeOptional


class ChapterSchema(BaseModel):
    """Schema for podcast chapters."""
    title: str
    start_time: float
    end_time: Optional[float] = None


class BriefingBase(BaseModel):
    """Base briefing schema."""
    title: str = "Daily Briefing"


class BriefingGenerateRequest(BaseModel):
    """Request to generate a new briefing."""
    topic_ids: Optional[list[str]] = Field(
        default=None,
        description="Optional list of topic IDs to include in the briefing",
    )
    include_calendar: bool = Field(
        default=False,
        description="Include calendar events (requires OAuth)",
    )
    include_email: bool = Field(
        default=False,
        description="Include email summaries (requires OAuth)",
    )
    max_duration_minutes: Optional[int] = Field(
        default=None,
        ge=1,
        le=60,
        description="Target duration in minutes (uses configured default if not specified)",
    )
    cast_id: Optional[str] = Field(
        default=None,
        description="Optional cast ID to use (uses default if not specified)",
    )


class BreakoutGenerateRequest(BaseModel):
    """Exactly one subject selector for a focused standalone podcast."""
    model_config = {"extra": "forbid", "str_strip_whitespace": True}
    topic: Optional[str] = Field(default=None, min_length=1, max_length=300)
    topic_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    source_briefing_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    chapter_index: Optional[int] = Field(default=None, ge=0, strict=True)
    focus: str = Field(default="", max_length=1000)
    max_duration_minutes: int = Field(default=10, ge=3, le=30, strict=True)
    cast_id: Optional[str] = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def one_target(self):
        if sum(value is not None for value in (self.topic, self.topic_id, self.source_briefing_id)) != 1:
            raise ValueError("Select one topic, saved topic, or source chapter")
        if (self.source_briefing_id is None) != (self.chapter_index is None):
            raise ValueError("source_briefing_id and chapter_index must be supplied together")
        return self


class BriefingCreate(BriefingBase):
    """Schema for creating a briefing record."""
    user_id: str


class BriefingResponse(BriefingBase):
    """Schema for briefing response."""
    id: str
    user_id: str
    transcript: Optional[str] = None
    audio_url: Optional[str] = None
    audio_filename: Optional[str] = None
    duration_seconds: Optional[float] = None
    cast_id: Optional[str] = None
    extra_data: dict = Field(default={})
    sources: list = []
    status: str
    error_message: Optional[str] = None
    generated_at: UTCDatetimeOptional = None
    created_at: UTCDatetime
    listened: bool = False
    listened_at: UTCDatetimeOptional = None
    playback_position: Optional[float] = None
    favorite: bool = False
    chapters: list[ChapterSchema] = Field(default_factory=list)
    
    model_config = {
        "from_attributes": True,
    }
    
    @model_validator(mode='after')
    def extract_chapters(self):
        """Extract chapters from extra_data."""
        chapters_data = self.extra_data.get("chapters", [])
        if isinstance(chapters_data, list) and chapters_data:
            try:
                self.chapters = [
                    ChapterSchema(**ch) if isinstance(ch, dict) else ch 
                    for ch in chapters_data
                ]
            except Exception as e:
                # If validation fails, log and use empty list
                print(f"[BriefingSchema] Error extracting chapters: {e}")
                self.chapters = []
        else:
            self.chapters = []
        return self


class BriefingListenedUpdate(BaseModel):
    """Request to update listened state."""
    listened: bool


class BriefingPlaybackPositionUpdate(BaseModel):
    """Request to update playback position."""
    position: float = Field(ge=0, description="Playback position in seconds")


class BriefingFavoriteUpdate(BaseModel):
    """Request to update favorite state."""
    favorite: bool


class ListeningRangesRequest(BaseModel):
    """Continuous audio-time intervals observed by the player."""
    ranges: list[tuple[float, float]] = Field(min_length=1, max_length=1000)

    @field_validator("ranges")
    @classmethod
    def validate_ranges(cls, ranges: list[tuple[float, float]]):
        for start, end in ranges:
            if not math.isfinite(start) or not math.isfinite(end):
                raise ValueError("Listening ranges must be finite")
            if start < 0 or end <= start:
                raise ValueError("Range end must be greater than its non-negative start")
        return ranges


class ListeningCoverageResponse(BaseModel):
    """Canonical persisted listening coverage."""
    ranges: list[tuple[float, float]]
    chapter_coverage: dict[str, float]
    episode_coverage: float


class BriefingListResponse(BaseModel):
    """Schema for listing briefings."""
    briefings: list[BriefingResponse]
    total: int
