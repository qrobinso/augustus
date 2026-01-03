"""User schemas for API validation."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr

from app.schemas.base import UTCDatetime


class UserBase(BaseModel):
    """Base user schema."""
    name: str = "Default User"
    email: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a user."""
    preferences: dict = {}


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    name: Optional[str] = None
    email: Optional[str] = None
    preferences: Optional[dict] = None


class UserResponse(UserBase):
    """Schema for user response."""
    id: str
    preferences: dict
    created_at: UTCDatetime
    updated_at: UTCDatetime
    
    class Config:
        from_attributes = True

