"""Briefing schemas for API validation."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, computed_field


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
    extra_data: dict = Field(default={})
    sources: list = []
    status: str
    error_message: Optional[str] = None
    generated_at: Optional[datetime] = None
    created_at: datetime
    listened: bool = False
    listened_at: Optional[datetime] = None
    
    model_config = {
        "from_attributes": True,
    }


class BriefingListenedUpdate(BaseModel):
    """Request to update listened state."""
    listened: bool


class BriefingListResponse(BaseModel):
    """Schema for listing briefings."""
    briefings: list[BriefingResponse]
    total: int
