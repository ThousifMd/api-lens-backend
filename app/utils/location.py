"""
Location and Timezone Detection Utilities
Provides real location detection based on IP address and timezone conversion
"""
import asyncio
import httpx
import pytz
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from ..utils.logger import get_logger

logger = get_logger(__name__)

class LocationService:
    """Service for detecting location and timezone from IP addresses"""
    
    @staticmethod
    async def get_location_from_ip(ip_address: Optional[str]) -> Dict[str, Any]:
        """
        Get location information from IP address using ipapi.co
        
        Args:
            ip_address: Client IP address
            
        Returns:
            Dictionary with location information
        """
        if not ip_address or ip_address in ['127.0.0.1', 'localhost', '::1']:
            return LocationService._get_default_location()
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"https://ipapi.co/{ip_address}/json/")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check if the response contains error
                    if data.get('error'):
                        logger.warning(f"IP geolocation error: {data.get('reason', 'Unknown error')}")
                        return LocationService._get_default_location()
                    
                    return {
                        'country': data.get('country_code', 'US'),
                        'country_name': data.get('country_name', 'United States'),
                        'region': data.get('region', 'California'),
                        'city': data.get('city', 'San Francisco'),
                        'timezone': data.get('timezone', 'America/Los_Angeles'),
                        'latitude': float(data.get('latitude', 37.7749)),
                        'longitude': float(data.get('longitude', -122.4194)),
                        'utc_offset': data.get('utc_offset', '-0800'),
                        'source': 'ipapi'
                    }
                else:
                    logger.warning(f"IP geolocation API returned status {response.status_code}")
                    return LocationService._get_default_location()
                    
        except asyncio.TimeoutError:
            logger.warning("IP geolocation request timed out")
            return LocationService._get_default_location()
        except Exception as e:
            logger.warning(f"Error getting location from IP {ip_address}: {e}")
            return LocationService._get_default_location()
    
    @staticmethod
    def _get_default_location() -> Dict[str, Any]:
        """Get default location when IP detection fails"""
        return {
            'country': 'US',
            'country_name': 'United States', 
            'region': 'California',
            'city': 'San Francisco',
            'timezone': 'America/Los_Angeles',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'utc_offset': '-0800',
            'source': 'default'
        }
    
    @staticmethod
    def calculate_local_time(utc_timestamp: datetime, timezone_name: str) -> Tuple[datetime, int]:
        """
        Calculate local time and UTC offset for a given timezone
        
        Args:
            utc_timestamp: UTC timestamp
            timezone_name: IANA timezone name (e.g., 'America/Los_Angeles')
            
        Returns:
            Tuple of (local_datetime, utc_offset_minutes)
        """
        try:
            if timezone_name == 'UTC':
                return utc_timestamp, 0
            
            # Get timezone object
            target_tz = pytz.timezone(timezone_name)
            
            # Convert UTC to local time
            local_time = utc_timestamp.astimezone(target_tz)
            
            # Calculate UTC offset in minutes
            utc_offset_seconds = local_time.utcoffset().total_seconds()
            utc_offset_minutes = int(utc_offset_seconds / 60)
            
            return local_time, utc_offset_minutes
            
        except Exception as e:
            logger.error(f"Error calculating local time for timezone {timezone_name}: {e}")
            # Return UTC time with 0 offset as fallback
            return utc_timestamp, 0
    
    @staticmethod
    def get_timezone_from_coordinates(latitude: float, longitude: float) -> str:
        """
        Get timezone from coordinates using a basic lookup
        This is a fallback method when timezone is not provided by IP service
        """
        try:
            # Basic timezone mapping based on longitude
            # This is a simplified approach - in production you might want to use a more sophisticated library
            if longitude >= -180 and longitude < -150:
                return 'Pacific/Honolulu'  # Hawaii
            elif longitude >= -150 and longitude < -120:
                return 'America/Anchorage'  # Alaska
            elif longitude >= -120 and longitude < -105:
                return 'America/Los_Angeles'  # Pacific
            elif longitude >= -105 and longitude < -90:
                return 'America/Denver'  # Mountain
            elif longitude >= -90 and longitude < -75:
                return 'America/Chicago'  # Central
            elif longitude >= -75 and longitude < -60:
                return 'America/New_York'  # Eastern
            elif longitude >= -60 and longitude < 0:
                return 'America/Sao_Paulo'  # South America
            elif longitude >= 0 and longitude < 30:
                return 'Europe/London'  # Western Europe
            elif longitude >= 30 and longitude < 60:
                return 'Europe/Moscow'  # Eastern Europe
            elif longitude >= 60 and longitude < 120:
                return 'Asia/Kolkata'  # India/Central Asia
            elif longitude >= 120 and longitude < 150:
                return 'Asia/Shanghai'  # China/East Asia
            elif longitude >= 150 and longitude <= 180:
                return 'Asia/Tokyo'  # Japan/Far East
            else:
                return 'UTC'
                
        except Exception as e:
            logger.error(f"Error determining timezone from coordinates ({latitude}, {longitude}): {e}")
            return 'UTC'

class TimezoneUtils:
    """Utilities for timezone handling and conversion"""
    
    @staticmethod
    def get_current_utc_offset(timezone_name: str) -> int:
        """
        Get current UTC offset in minutes for a timezone
        
        Args:
            timezone_name: IANA timezone name
            
        Returns:
            UTC offset in minutes (positive for east of UTC, negative for west)
        """
        try:
            if timezone_name == 'UTC':
                return 0
            
            tz = pytz.timezone(timezone_name)
            now_utc = datetime.now(timezone.utc)
            now_local = now_utc.astimezone(tz)
            
            # Calculate offset in minutes
            offset_seconds = now_local.utcoffset().total_seconds()
            return int(offset_seconds / 60)
            
        except Exception as e:
            logger.error(f"Error getting UTC offset for {timezone_name}: {e}")
            return 0
    
    @staticmethod
    def validate_timezone(timezone_name: str) -> bool:
        """
        Validate if a timezone name is valid
        
        Args:
            timezone_name: IANA timezone name to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            pytz.timezone(timezone_name)
            return True
        except pytz.exceptions.UnknownTimeZoneError:
            return False
        except Exception:
            return False
    
    @staticmethod
    def normalize_timezone_name(timezone_name: str) -> str:
        """
        Normalize timezone name to standard IANA format
        
        Args:
            timezone_name: Input timezone name
            
        Returns:
            Normalized IANA timezone name
        """
        if not timezone_name:
            return 'UTC'
        
        # Handle common aliases and abbreviations
        timezone_aliases = {
            'PST': 'America/Los_Angeles',
            'PDT': 'America/Los_Angeles',
            'EST': 'America/New_York',
            'EDT': 'America/New_York',
            'CST': 'America/Chicago',
            'CDT': 'America/Chicago',
            'MST': 'America/Denver',
            'MDT': 'America/Denver',
            'GMT': 'UTC',
            'BST': 'Europe/London',
            'CET': 'Europe/Berlin',
            'JST': 'Asia/Tokyo',
            'IST': 'Asia/Kolkata',
            'AEST': 'Australia/Sydney',
        }
        
        # Check if it's an alias
        if timezone_name.upper() in timezone_aliases:
            return timezone_aliases[timezone_name.upper()]
        
        # Check if it's already a valid IANA name
        if TimezoneUtils.validate_timezone(timezone_name):
            return timezone_name
        
        # Return UTC as fallback
        logger.warning(f"Unknown timezone '{timezone_name}', using UTC")
        return 'UTC'