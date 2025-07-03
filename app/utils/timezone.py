"""
Timezone utilities for API Lens
Detects and handles caller timezone for accurate timestamp logging
"""

import pytz
from datetime import datetime, timezone
from typing import Optional
from fastapi import Request
import requests
import json

def detect_timezone_from_request(request: Request) -> str:
    """
    Detect timezone from various request sources
    
    Priority order:
    1. X-Timezone header (if client provides it)
    2. IP-based geolocation
    3. Fallback to UTC
    
    Args:
        request: FastAPI Request object
        
    Returns:
        Timezone string (e.g., 'America/New_York', 'Europe/London')
    """
    
    # 1. Check for explicit timezone header
    timezone_header = request.headers.get("X-Timezone")
    if timezone_header:
        try:
            # Validate the timezone
            pytz.timezone(timezone_header)
            return timezone_header
        except pytz.UnknownTimeZoneError:
            pass
    
    # 2. Try to detect from IP address
    client_ip = get_client_ip(request)
    if client_ip and client_ip not in ["127.0.0.1", "localhost"]:
        timezone_from_ip = get_timezone_from_ip(client_ip)
        if timezone_from_ip:
            return timezone_from_ip
    else:
        # For localhost/development, use actual public IP for testing
        import requests
        try:
            public_ip_response = requests.get("https://ipv4.icanhazip.com/", timeout=2)
            if public_ip_response.status_code == 200:
                public_ip = public_ip_response.text.strip()
                timezone_from_public_ip = get_timezone_from_ip(public_ip)
                if timezone_from_public_ip:
                    return timezone_from_public_ip
        except:
            pass
    
    # 3. Fallback to UTC
    return "UTC"

def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from request headers"""
    
    # Check common proxy headers first
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first (original client)
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Cloudflare specific header
    cf_connecting_ip = request.headers.get("CF-Connecting-IP")
    if cf_connecting_ip:
        return cf_connecting_ip
    
    # Fallback to direct client IP
    if hasattr(request, 'client') and request.client:
        return request.client.host
    
    return None

def get_timezone_from_ip(ip_address: str) -> Optional[str]:
    """
    Get timezone from IP address using a geolocation service
    
    Args:
        ip_address: IP address to lookup
        
    Returns:
        Timezone string or None if lookup fails
    """
    try:
        # Using ip-api.com (free service, no API key required)
        # In production, you might want to use a paid service for better reliability
        response = requests.get(
            f"http://ip-api.com/json/{ip_address}?fields=timezone",
            timeout=2  # Quick timeout to avoid delays
        )
        
        if response.status_code == 200:
            data = response.json()
            timezone_str = data.get("timezone")
            
            if timezone_str:
                try:
                    # Validate the timezone
                    pytz.timezone(timezone_str)
                    return timezone_str
                except pytz.UnknownTimeZoneError:
                    pass
                    
    except Exception as e:
        # Don't let timezone detection break the API call
        print(f"Timezone detection error: {e}")
        pass
    
    return None

def get_localized_timestamp(timezone_str: str = "UTC") -> datetime:
    """
    Get current timestamp in the specified timezone
    
    Args:
        timezone_str: Timezone string (e.g., 'America/New_York')
        
    Returns:
        Datetime object in the specified timezone
    """
    try:
        tz = pytz.timezone(timezone_str)
        return datetime.now(tz)
    except pytz.UnknownTimeZoneError:
        # Fallback to UTC
        return datetime.now(timezone.utc)

def get_client_local_timestamp(timezone_str: str = "UTC") -> datetime:
    """
    Get current timestamp as naive datetime in the client's local time
    This prevents PostgreSQL from converting to UTC
    
    Args:
        timezone_str: Timezone string (e.g., 'America/New_York')
        
    Returns:
        Naive datetime object showing client's local time
    """
    try:
        tz = pytz.timezone(timezone_str)
        local_time = datetime.now(tz)
        # Return as naive datetime to prevent timezone conversion
        return local_time.replace(tzinfo=None)
    except pytz.UnknownTimeZoneError:
        # Fallback to UTC
        return datetime.now(timezone.utc).replace(tzinfo=None)

def format_timestamp_for_display(dt: datetime, timezone_str: str = None) -> str:
    """
    Format timestamp for user-friendly display
    
    Args:
        dt: Datetime object
        timezone_str: Target timezone for display
        
    Returns:
        Formatted timestamp string
    """
    if timezone_str:
        try:
            tz = pytz.timezone(timezone_str)
            if dt.tzinfo is None:
                dt = pytz.utc.localize(dt)
            dt = dt.astimezone(tz)
        except (pytz.UnknownTimeZoneError, AttributeError):
            pass
    
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")

def get_timezone_info(timezone_str: str) -> dict:
    """
    Get detailed timezone information
    
    Args:
        timezone_str: Timezone string
        
    Returns:
        Dictionary with timezone details
    """
    try:
        tz = pytz.timezone(timezone_str)
        now = datetime.now(tz)
        
        return {
            "timezone": timezone_str,
            "offset": now.strftime("%z"),
            "name": now.tzname(),
            "is_dst": bool(now.dst()),
            "utc_offset_hours": now.utcoffset().total_seconds() / 3600
        }
    except pytz.UnknownTimeZoneError:
        return {
            "timezone": "UTC",
            "offset": "+0000",
            "name": "UTC",
            "is_dst": False,
            "utc_offset_hours": 0
        }

# Common timezone mappings for quick reference
COMMON_TIMEZONES = {
    "US/Eastern": "America/New_York",
    "US/Central": "America/Chicago", 
    "US/Mountain": "America/Denver",
    "US/Pacific": "America/Los_Angeles",
    "Europe/London": "Europe/London",
    "Europe/Paris": "Europe/Paris",
    "Asia/Tokyo": "Asia/Tokyo",
    "Asia/Shanghai": "Asia/Shanghai",
    "Australia/Sydney": "Australia/Sydney",
    "UTC": "UTC"
}

def normalize_timezone(timezone_str: str) -> str:
    """Normalize timezone string to standard format"""
    return COMMON_TIMEZONES.get(timezone_str, timezone_str)