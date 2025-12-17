"""Topic schemas for API validation."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class TopicCreate(BaseModel):
    """Schema for creating a topic."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Display name for the topic",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional description of the topic",
    )
    color: Optional[str] = Field(
        default=None,
        pattern=r'^#[0-9A-Fa-f]{6}$',
        description="Hex color for UI (e.g., '#3B82F6')",
    )


class TopicUpdate(BaseModel):
    """Schema for updating a topic."""
    name: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    color: Optional[str] = Field(
        default=None,
        pattern=r'^#[0-9A-Fa-f]{6}$',
    )
    is_active: Optional[bool] = None


class TopicResponse(BaseModel):
    """Schema for topic response."""
    id: str
    user_id: str
    name: str
    slug: str
    description: Optional[str] = None
    color: Optional[str] = None
    is_active: bool
    created_at: datetime
    site_count: int = 0  # Count of linked custom sites
    
    model_config = {
        "from_attributes": True,
    }


class TopicListResponse(BaseModel):
    """Schema for listing topics."""
    topics: list[TopicResponse]
    total: int

