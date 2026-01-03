"""CustomSite schemas for API validation."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.base import UTCDatetime, UTCDatetimeOptional


class CustomSiteCreate(BaseModel):
    """Schema for creating a custom site."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Display name for the site",
    )
    url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="URL of the website/blog",
    )
    topic_id: str = Field(
        ...,
        description="ID of the topic this site belongs to",
    )


class CustomSiteUpdate(BaseModel):
    """Schema for updating a custom site."""
    name: Optional[str] = Field(default=None, max_length=255)
    url: Optional[str] = Field(default=None, max_length=2048)
    topic_id: Optional[str] = None
    is_active: Optional[bool] = None


class CustomSiteResponse(BaseModel):
    """Schema for custom site response."""
    id: str
    user_id: str
    name: str
    url: str
    topic_id: str
    topic_name: Optional[str] = None  # Populated from relationship
    topic_color: Optional[str] = None  # Populated from relationship
    is_active: bool
    last_fetched: UTCDatetimeOptional = None
    last_error: Optional[str] = None
    created_at: UTCDatetime
    
    model_config = {
        "from_attributes": True,
    }


class CustomSiteListResponse(BaseModel):
    """Schema for listing custom sites."""
    sites: list[CustomSiteResponse]
    total: int

