"""Pydantic schemas for API request/response validation."""

from app.schemas.user import UserCreate, UserResponse
from app.schemas.briefing import BriefingCreate, BriefingResponse, BriefingGenerateRequest
from app.schemas.topic import TopicCreate, TopicUpdate, TopicResponse, TopicListResponse
from app.schemas.custom_site import CustomSiteCreate, CustomSiteUpdate, CustomSiteResponse, CustomSiteListResponse
from app.schemas.scheduled_briefing import (
    ScheduledBriefingCreate,
    ScheduledBriefingUpdate,
    ScheduledBriefingResponse,
    ScheduledBriefingListResponse,
)

__all__ = [
    "UserCreate",
    "UserResponse",
    "BriefingCreate",
    "BriefingResponse",
    "BriefingGenerateRequest",
    "TopicCreate",
    "TopicUpdate",
    "TopicResponse",
    "TopicListResponse",
    "CustomSiteCreate",
    "CustomSiteUpdate",
    "CustomSiteResponse",
    "CustomSiteListResponse",
    "ScheduledBriefingCreate",
    "ScheduledBriefingUpdate",
    "ScheduledBriefingResponse",
    "ScheduledBriefingListResponse",
]

