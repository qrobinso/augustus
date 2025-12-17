"""DeepCast schemas for API validation."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ChapterSchema(BaseModel):
    """Schema for podcast chapters."""
    title: str
    start_time: float
    end_time: Optional[float] = None


class SourceSchema(BaseModel):
    """Schema for content sources."""
    url: str
    title: str
    snippet: Optional[str] = None


class DeepCastCreate(BaseModel):
    """Schema for creating a DeepCast."""
    query: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="The topic or question to research and generate a podcast about",
    )
    target_duration_minutes: Optional[int] = Field(
        default=None,
        ge=1,
        le=60,
        description="Target duration in minutes (uses configured default if not specified)",
    )
    num_sources: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of sources to research",
    )


class DeepCastResponse(BaseModel):
    """Schema for DeepCast response."""
    id: str
    user_id: str
    query: str
    title: Optional[str] = None
    transcript: Optional[str] = None
    chapters: list[ChapterSchema] = []
    audio_url: Optional[str] = None
    audio_filename: Optional[str] = None
    duration_seconds: Optional[float] = None
    sources: list[SourceSchema] = []
    extra_data: dict = Field(default={})
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    model_config = {
        "from_attributes": True,
    }


class DeepCastListResponse(BaseModel):
    """Schema for listing DeepCasts."""
    deepcasts: list[DeepCastResponse]
    total: int
