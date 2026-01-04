"""Profile schemas for API validation."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.base import UTCDatetime


class ProfileBase(BaseModel):
    """Base profile schema."""
    name: str = Field(..., min_length=1, max_length=50, description="Name used for personalization in briefings (max 50 characters)")
    color: str = Field(default="#e85d04", pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex color for avatar (app accent color)")


class ProfileCreate(ProfileBase):
    """Schema for creating a profile."""
    pass


class ProfileUpdate(BaseModel):
    """Schema for updating a profile."""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="Name used for personalization in briefings (max 50 characters)")
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")


class ProfileResponse(ProfileBase):
    """Schema for profile response."""
    id: str
    user_id: str
    is_admin: bool
    created_at: UTCDatetime
    updated_at: UTCDatetime
    
    class Config:
        from_attributes = True


class ProfileListResponse(BaseModel):
    """Schema for profile list response."""
    profiles: list[ProfileResponse]
    total: int

