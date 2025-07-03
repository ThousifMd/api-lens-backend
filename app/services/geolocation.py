"""
Production-Ready Geolocation Service
Uses MaxMind GeoLite2 for real IP geolocation and timezone detection
"""
import os
import logging
import ipaddress
from typing import Optional, Dict, Tuple
from pathlib import Path

try:
    import geoip2.database
    import geoip2.errors
    GEOIP2_AVAILABLE = True
except ImportError:
    GEOIP2_AVAILABLE = False

from ..utils.logger import get_logger

logger = get_logger(__name__)

class GeolocationService:
    """Production geolocation service using MaxMind GeoLite2"""
    
    def __init__(self):
        self.reader = None
        self._init_geoip_reader()
    
    def _init_geoip_reader(self):
        """Initialize the MaxMind GeoIP2 reader"""
        if not GEOIP2_AVAILABLE:
            logger.warning("geoip2 library not available. Install with: pip install geoip2")
            return
        
        # Look for GeoLite2 database in common locations
        possible_paths = [
            "data/geoip/GeoLite2-City.mmdb",
            "/usr/share/GeoIP/GeoLite2-City.mmdb",
            "/var/lib/GeoIP/GeoLite2-City.mmdb",
            os.path.expanduser("~/GeoLite2-City.mmdb")
        ]
        
        db_path = None
        for path in possible_paths:
            if os.path.exists(path):
                db_path = path
                break
        
        if not db_path:
            logger.warning(f"GeoLite2 database not found in any of: {possible_paths}")
            logger.info("Download from: https://dev.maxmind.com/geoip/geolite2-free-geolocation-data")
            return
        
        try:
            self.reader = geoip2.database.Reader(db_path)
            logger.info(f"GeoLite2 database loaded from: {db_path}")
        except Exception as e:
            logger.error(f"Failed to load GeoLite2 database: {e}")
    
    def is_private_ip(self, ip_str: str) -> bool:
        """Check if IP address is private/local"""
        try:
            ip = ipaddress.ip_address(ip_str)
            return ip.is_private or ip.is_loopback or ip.is_link_local
        except ValueError:
            return True  # Invalid IP, treat as private
    
    def get_real_client_ip(self, headers: Dict[str, str], remote_addr: str = None) -> str:
        """Extract real client IP from request headers"""
        # Check common forwarded headers (in order of preference)
        forwarded_headers = [
            'X-Forwarded-For',
            'X-Real-IP', 
            'X-Client-IP',
            'CF-Connecting-IP',  # Cloudflare
            'True-Client-IP',    # Akamai
            'X-Forwarded',
            'Forwarded-For',
            'Forwarded'
        ]
        
        for header in forwarded_headers:
            ip_list = headers.get(header, '').strip()
            if ip_list:
                # X-Forwarded-For can contain multiple IPs
                first_ip = ip_list.split(',')[0].strip()
                if first_ip and not self.is_private_ip(first_ip):
                    return first_ip
        
        # Fallback to direct connection IP
        if remote_addr and not self.is_private_ip(remote_addr):
            return remote_addr
        
        return None
    
    def detect_location(self, ip_address: str) -> Optional[Dict[str, str]]:
        """Detect location from IP address using MaxMind GeoLite2"""
        if not self.reader:
            return None
        
        if not ip_address or self.is_private_ip(ip_address):
            return None
        
        try:
            response = self.reader.city(ip_address)
            
            # Extract location data
            country_code = response.country.iso_code
            country_name = response.country.name
            city = response.city.name
            latitude = float(response.location.latitude) if response.location.latitude else None
            longitude = float(response.location.longitude) if response.location.longitude else None
            
            # Get timezone from MaxMind data
            timezone = response.location.time_zone
            
            return {
                'country_code': country_code,
                'country_name': country_name,
                'city': city,
                'latitude': latitude,
                'longitude': longitude,
                'timezone': timezone,
                'source': 'maxmind_geolite2'
            }
            
        except geoip2.errors.AddressNotFoundError:
            logger.debug(f"IP address not found in GeoLite2 database: {ip_address}")
            return None
        except Exception as e:
            logger.error(f"Error looking up IP {ip_address}: {e}")
            return None
    
    def get_timezone_for_country(self, country_code: str) -> Optional[str]:
        """Fallback timezone mapping for countries (when MaxMind doesn't have timezone)"""
        country_timezone_map = {
            'US': 'America/New_York',    # Default to Eastern (most populated)
            'CA': 'America/Toronto',     # Default to Eastern Canada
            'GB': 'Europe/London',
            'DE': 'Europe/Berlin',
            'FR': 'Europe/Paris',
            'JP': 'Asia/Tokyo',
            'AU': 'Australia/Sydney',    # Default to Eastern Australia
            'IN': 'Asia/Kolkata',
            'CN': 'Asia/Shanghai',       # Default to Beijing time
            'BR': 'America/Sao_Paulo',   # Default to most populated timezone
            'MX': 'America/Mexico_City',
            'RU': 'Europe/Moscow',       # Default to Moscow time
            'ZA': 'Africa/Johannesburg',
            'EG': 'Africa/Cairo',
            'NG': 'Africa/Lagos',
            'SG': 'Asia/Singapore',
            'KR': 'Asia/Seoul',
            'TH': 'Asia/Bangkok',
            'ID': 'Asia/Jakarta',        # Default to Western Indonesia
            'PH': 'Asia/Manila',
            'VN': 'Asia/Ho_Chi_Minh',
            'MY': 'Asia/Kuala_Lumpur',
            'NZ': 'Pacific/Auckland',
            'AR': 'America/Argentina/Buenos_Aires',
            'CL': 'America/Santiago',
            'CO': 'America/Bogota',
            'PE': 'America/Lima',
            'VE': 'America/Caracas',
            'AE': 'Asia/Dubai',
            'SA': 'Asia/Riyadh',
            'IL': 'Asia/Jerusalem',
            'TR': 'Europe/Istanbul',
            'IT': 'Europe/Rome',
            'ES': 'Europe/Madrid',
            'NL': 'Europe/Amsterdam',
            'CH': 'Europe/Zurich',
            'SE': 'Europe/Stockholm',
            'NO': 'Europe/Oslo',
            'DK': 'Europe/Copenhagen',
            'FI': 'Europe/Helsinki',
            'PL': 'Europe/Warsaw',
            'AT': 'Europe/Vienna',
            'BE': 'Europe/Brussels',
            'PT': 'Europe/Lisbon',
            'GR': 'Europe/Athens',
            'IE': 'Europe/Dublin',
        }
        
        return country_timezone_map.get(country_code.upper()) if country_code else None
    
    def detect_timezone_from_ip(self, ip_address: str, headers: Dict[str, str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Detect timezone from IP address
        Returns: (timezone, country_code)
        """
        # Try to get real client IP if headers provided
        if headers:
            real_ip = self.get_real_client_ip(headers, ip_address)
            if real_ip:
                ip_address = real_ip
        
        # Get location data from MaxMind
        location_data = self.detect_location(ip_address)
        
        if location_data:
            timezone = location_data.get('timezone')
            country_code = location_data.get('country_code')
            
            # If MaxMind doesn't provide timezone, use country fallback
            if not timezone and country_code:
                timezone = self.get_timezone_for_country(country_code)
            
            return timezone, country_code
        
        # Complete fallback for private/unknown IPs
        return None, None
    
    def __del__(self):
        """Cleanup GeoIP2 reader"""
        if hasattr(self, 'reader') and self.reader:
            try:
                self.reader.close()
            except:
                pass

# Global instance
_geolocation_service = None

def get_geolocation_service() -> GeolocationService:
    """Get global geolocation service instance"""
    global _geolocation_service
    if _geolocation_service is None:
        _geolocation_service = GeolocationService()
    return _geolocation_service