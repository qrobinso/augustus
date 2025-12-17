"""ScheduledBriefing schemas for API validation."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class ScheduledBriefingCreate(BaseModel):
    """Schema for creating a scheduled briefing."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="User-friendly name for this schedule",
    )
    topic_ids: list[str] = Field(
        default=[],
        description="List of topic IDs to include in the briefing",
    )
    schedule_time: str = Field(
        ...,
        pattern=r"^([0-1][0-9]|2[0-3]):[0-5][0-9]$",
        description="Time to generate briefing (HH:MM format in user's timezone)",
    )
    schedule_days: list[int] = Field(
        ...,
        min_length=1,
        description="Days of week to run (0=Monday, 6=Sunday)",
    )
    notification_methods: list[str] = Field(
        default=[],
        description="Notification methods: ['email', 'webhook']. Leave empty to generate briefing without notifications.",
    )
    email_recipients: list[str] = Field(
        default=[],
        description="List of email addresses to notify",
    )
    webhook_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Webhook URL for notifications",
    )
    is_active: bool = Field(
        default=True,
        description="Whether this schedule is enabled",
    )
    max_duration_minutes: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Target duration in minutes",
    )
    resend_api_key: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Resend API key (optional, uses global if not set)",
    )
    
    @field_validator('schedule_days')
    @classmethod
    def validate_schedule_days(cls, v):
        """Validate schedule days are in range 0-6."""
        if not all(0 <= day <= 6 for day in v):
            raise ValueError("Schedule days must be between 0 (Monday) and 6 (Sunday)")
        return v
    
    @field_validator('notification_methods')
    @classmethod
    def validate_notification_methods(cls, v):
        """Validate notification methods."""
        valid_methods = {'email', 'webhook'}
        if not all(method in valid_methods for method in v):
            raise ValueError(f"Notification methods must be one of: {valid_methods}")
        return v
    
    @model_validator(mode='after')
    def validate_notification_config(self):
        """Validate notification configuration."""
        import re
        
        # Only validate if notification methods are specified
        if 'email' in self.notification_methods:
            if not self.email_recipients:
                raise ValueError("Email recipients required when email notification is enabled")
            # Basic email validation
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            for email in self.email_recipients:
                if not re.match(email_pattern, email):
                    raise ValueError(f"Invalid email address: {email}")
        
        if 'webhook' in self.notification_methods:
            if not self.webhook_url:
                raise ValueError("Webhook URL required when webhook notification is enabled")
            # Basic URL validation
            if not self.webhook_url.startswith(('http://', 'https://')):
                raise ValueError("Webhook URL must start with http:// or https://")
        
        # If no notification methods, that's fine - briefing will just be generated without notifications
        return self


class ScheduledBriefingUpdate(BaseModel):
    """Schema for updating a scheduled briefing."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=500)
    topic_ids: Optional[list[str]] = None
    schedule_time: Optional[str] = Field(default=None, pattern=r"^([0-1][0-9]|2[0-3]):[0-5][0-9]$")
    schedule_days: Optional[list[int]] = None
    notification_methods: Optional[list[str]] = None
    email_recipients: Optional[list[str]] = None
    webhook_url: Optional[str] = Field(default=None, max_length=500)
    is_active: Optional[bool] = None
    max_duration_minutes: Optional[int] = Field(default=None, ge=1, le=60)
    resend_api_key: Optional[str] = Field(default=None, max_length=255)


class ScheduledBriefingResponse(BaseModel):
    """Schema for scheduled briefing response."""
    id: str
    user_id: str
    name: str
    topic_ids: list[str] = []
    schedule_time: str
    schedule_days: list[int] = []
    notification_methods: list[str] = []
    email_recipients: list[str] = []
    webhook_url: Optional[str] = None
    is_active: bool
    max_duration_minutes: int
    resend_api_key: Optional[str] = None
    last_generated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = {
        "from_attributes": True,
    }


class ScheduledBriefingListResponse(BaseModel):
    """Schema for listing scheduled briefings."""
    scheduled_briefings: list[ScheduledBriefingResponse]
    total: int
