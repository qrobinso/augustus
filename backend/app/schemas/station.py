"""Station and Episode schemas for API validation."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class StationCreate(BaseModel):
    """Schema for creating a station subscription."""
    topic: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="The topic to subscribe to",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional description of the station",
    )
    update_frequency_hours: int = Field(
        default=6,
        ge=1,
        le=168,
        description="How often to check for updates (in hours)",
    )
    settings: dict = Field(
        default={},
        description="Additional station settings",
    )
    cast_id: Optional[str] = Field(
        default=None,
        description="Optional cast ID to use (uses default if not specified)",
    )


class StationUpdate(BaseModel):
    """Schema for updating a station."""
    topic: Optional[str] = None
    description: Optional[str] = None
    update_frequency_hours: Optional[int] = Field(default=None, ge=1, le=168)
    settings: Optional[dict] = None
    is_active: Optional[bool] = None


class EpisodeResponse(BaseModel):
    """Schema for episode response."""
    id: str
    station_id: str
    title: str
    summary: Optional[str] = None
    transcript: Optional[str] = None
    audio_url: Optional[str] = None
    audio_filename: Optional[str] = None
    duration_seconds: Optional[float] = None
    sources: list = []
    extra_data: dict = Field(default={})
    status: str
    created_at: datetime
    
    model_config = {
        "from_attributes": True,
    }


class StationResponse(BaseModel):
    """Schema for station response."""
    id: str
    user_id: str
    topic: str
    description: Optional[str] = None
    update_frequency_hours: int
    settings: dict = {}
    is_active: bool
    cast_id: Optional[str] = None
    last_update: Optional[datetime] = None
    created_at: datetime
    episodes: list[EpisodeResponse] = []
    episode_count: int = 0
    
    model_config = {
        "from_attributes": True,
    }
    
    @classmethod
    def from_orm_with_count(cls, station, episode_count: int = 0):
        """Create response with episode count."""
        return cls(
            id=station.id,
            user_id=station.user_id,
            topic=station.topic,
            description=station.description,
            update_frequency_hours=station.update_frequency_hours,
            settings=station.settings,
            is_active=station.is_active,
            cast_id=getattr(station, 'cast_id', None),
            last_update=station.last_update,
            created_at=station.created_at,
            episodes=[],
            episode_count=episode_count,
        )


class StationListResponse(BaseModel):
    """Schema for listing stations."""
    stations: list[StationResponse]
    total: int
