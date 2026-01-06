"""Base schemas with common functionality."""

from datetime import datetime
from typing import Annotated, Any
from pydantic import BaseModel, PlainSerializer


def serialize_datetime_as_utc(dt: datetime | None) -> str | None:
    """
    Serialize datetime to ISO format with UTC timezone indicator.
    
    Naive datetimes (stored as UTC in the database) need the 'Z' suffix
    so that JavaScript's Date() constructor interprets them correctly as UTC
    instead of local time.
    """
    if dt is None:
        return None
    # If the datetime is naive (no timezone), assume UTC and add Z
    if dt.tzinfo is None:
        return dt.isoformat() + 'Z'
    # If timezone-aware, use isoformat which includes timezone
    return dt.isoformat()


# Custom type for UTC datetime that serializes with 'Z' suffix
UTCDatetime = Annotated[datetime, PlainSerializer(serialize_datetime_as_utc)]
UTCDatetimeOptional = Annotated[datetime | None, PlainSerializer(serialize_datetime_as_utc)]





