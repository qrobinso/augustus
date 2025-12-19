"""Cast schemas for API validation."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CastMemberBase(BaseModel):
    """Base cast member schema."""
    name: str = Field(..., description="Name of the cast member")
    voice_id: str = Field(..., description="Voice ID from TTS provider")
    personality: str = Field(..., description="Personality type")
    order: int = Field(..., ge=0, le=2, description="Position in cast (0, 1, or 2)")


class CastMemberResponse(CastMemberBase):
    """Cast member response schema."""
    id: str
    cast_id: str
    created_at: datetime
    
    model_config = {
        "from_attributes": True,
    }


class CastBase(BaseModel):
    """Base cast schema."""
    name: str = Field(..., description="Name of the cast")


class CastCreate(BaseModel):
    """Schema for creating a cast."""
    name: str = Field(..., description="Name of the cast")
    members: list[CastMemberBase] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="List of cast members (1-3 members)"
    )


class CastUpdate(BaseModel):
    """Schema for updating a cast."""
    name: Optional[str] = Field(None, description="Name of the cast")
    members: Optional[list[CastMemberBase]] = Field(
        None,
        min_length=1,
        max_length=3,
        description="List of cast members (1-3 members)"
    )


class CastResponse(CastBase):
    """Schema for cast response."""
    id: str
    user_id: str
    is_default: bool
    members: list[CastMemberResponse]
    created_at: datetime
    updated_at: datetime
    
    model_config = {
        "from_attributes": True,
    }


class CastListResponse(BaseModel):
    """Schema for listing casts."""
    casts: list[CastResponse]


