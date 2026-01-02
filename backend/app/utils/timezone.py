"""Timezone utilities for date/time handling."""

from datetime import datetime, timezone as tz
from typing import Optional
from zoneinfo import ZoneInfo


def get_user_timezone() -> ZoneInfo:
    """Get the user's configured timezone."""
    from app.config import get_settings
    settings = get_settings()
    try:
        return ZoneInfo(settings.timezone)
    except Exception:
        return ZoneInfo("UTC")


def utc_now() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(tz.utc)


def local_now() -> datetime:
    """Get current time in user's timezone."""
    return datetime.now(get_user_timezone())


def to_utc(dt: datetime, from_tz: Optional[ZoneInfo] = None) -> datetime:
    """Convert a datetime to UTC.
    
    Args:
        dt: The datetime to convert
        from_tz: Source timezone (defaults to user's timezone if dt is naive)
    
    Returns:
        UTC datetime with tzinfo
    """
    if dt.tzinfo is None:
        # Naive datetime - assume it's in the specified timezone or user's timezone
        from_tz = from_tz or get_user_timezone()
        dt = dt.replace(tzinfo=from_tz)
    
    return dt.astimezone(tz.utc)


def to_local(dt: datetime, to_tz: Optional[ZoneInfo] = None) -> datetime:
    """Convert a datetime to local timezone.
    
    Args:
        dt: The datetime to convert (should be UTC or have tzinfo)
        to_tz: Target timezone (defaults to user's timezone)
    
    Returns:
        Local datetime with tzinfo
    """
    to_tz = to_tz or get_user_timezone()
    
    if dt.tzinfo is None:
        # Assume naive datetime is UTC
        dt = dt.replace(tzinfo=tz.utc)
    
    return dt.astimezone(to_tz)


def format_local_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
    """Format a datetime in the user's local timezone.
    
    Args:
        dt: The datetime to format (should be UTC or have tzinfo)
        format_str: strftime format string
    
    Returns:
        Formatted datetime string in local timezone
    """
    local_dt = to_local(dt)
    return local_dt.strftime(format_str)


def get_timezone_offset_str(tz_name: Optional[str] = None) -> str:
    """Get the current UTC offset string for a timezone.
    
    Args:
        tz_name: Timezone name (defaults to user's timezone)
    
    Returns:
        Offset string like "UTC-05:00" or "UTC+01:00"
    """
    try:
        zone = ZoneInfo(tz_name) if tz_name else get_user_timezone()
        now = datetime.now(zone)
        offset = now.utcoffset()
        if offset is None:
            return "UTC+00:00"
        
        total_seconds = int(offset.total_seconds())
        hours, remainder = divmod(abs(total_seconds), 3600)
        minutes = remainder // 60
        sign = "+" if total_seconds >= 0 else "-"
        
        return f"UTC{sign}{hours:02d}:{minutes:02d}"
    except Exception:
        return "UTC+00:00"


def get_time_of_day(tz_name: Optional[str] = None) -> str:
    """Get the time of day period based on the current hour in the user's timezone.
    
    Args:
        tz_name: Timezone name (defaults to user's timezone)
    
    Returns:
        Time of day string: "Morning", "Afternoon", "Evening", or "Night"
    """
    try:
        zone = ZoneInfo(tz_name) if tz_name else get_user_timezone()
        now = datetime.now(zone)
        hour = now.hour
        
        if 5 <= hour < 12:
            return "Morning"
        elif 12 <= hour < 17:
            return "Afternoon"
        elif 17 <= hour < 22:
            return "Evening"
        else:
            return "Night"
    except Exception:
        # Default to Morning if there's an error
        return "Morning"























