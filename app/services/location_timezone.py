"""
Location-Based Timezone Service
Handles IP geolocation and timezone detection for local timestamp conversion
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Tuple
import re

from ..database import DatabaseUtils
from ..utils.logger import get_logger
from .geolocation import get_geolocation_service

logger = get_logger(__name__)

class LocationTimezoneService:
    """Service for handling location-based timezone detection and conversion"""
    
    # Common timezone mappings for countries (fallback when detailed location unavailable)
    COUNTRY_TIMEZONE_MAP = {
        'US': 'America/New_York',    # Default to Eastern (most population)
        'CA': 'America/Toronto',     # Default to Eastern
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
    
    @staticmethod
    def is_valid_ip(ip_address) -> bool:
        """Check if IP address is valid and not private/local"""
        if not ip_address:
            return False
        
        # Convert to string if it's an IP address object
        ip_str = str(ip_address)
        
        # Skip localhost, private ranges, etc.
        private_patterns = [
            r'^127\.',           # Localhost
            r'^192\.168\.',      # Private
            r'^10\.',            # Private
            r'^172\.(1[6-9]|2[0-9]|3[01])\.',  # Private
            r'^169\.254\.',      # Link-local
            r'^::1$',            # IPv6 localhost
            r'^fe80:',           # IPv6 link-local
        ]
        
        for pattern in private_patterns:
            if re.match(pattern, ip_str):
                return False
        
        return True
    
    @staticmethod
    def detect_timezone_from_country(country_code: str) -> Optional[str]:
        """Get default timezone for a country"""
        if not country_code or len(country_code) != 2:
            return None
        
        return LocationTimezoneService.COUNTRY_TIMEZONE_MAP.get(country_code.upper())
    
    @staticmethod
    def convert_utc_to_timezone(utc_timestamp: datetime, timezone_name: str) -> Optional[datetime]:
        """Convert UTC timestamp to specified timezone"""
        if not utc_timestamp or not timezone_name:
            return None
        
        try:
            # For this basic implementation, we'll use the database function
            # In production, you might want to use Python's zoneinfo or pytz
            return utc_timestamp  # Placeholder - will use DB function
        except Exception as e:
            logger.warning(f"Failed to convert timezone {timezone_name}: {e}")
            return None
    
    @staticmethod
    async def populate_location_data_for_requests() -> Dict[str, int]:
        """Populate location-based timezone data for existing requests using MaxMind GeoLite2"""
        
        logger.info("Starting to populate location data for requests using MaxMind GeoLite2...")
        
        try:
            # Get geolocation service
            geo_service = get_geolocation_service()
            
            # First, get requests that need location data populated
            query = """
            SELECT id, ip_address, country, timestamp_utc, created_at
            FROM requests 
            WHERE detected_timezone IS NULL 
            AND ip_address IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1000
            """
            
            requests = await DatabaseUtils.execute_query(query, [], fetch_all=True)
            
            if not requests:
                logger.info("No requests need location data population")
                return {"processed": 0, "updated": 0, "errors": 0}
            
            logger.info(f"Processing {len(requests)} requests for location data...")
            
            updated_count = 0
            error_count = 0
            
            for request in requests:
                try:
                    # Extract data
                    request_id = request['id']
                    ip_address = str(request['ip_address'])  # Convert to string
                    timestamp_utc = request['timestamp_utc']
                    created_at = request['created_at']
                    
                    # Use MaxMind GeoLite2 to detect timezone and country
                    detected_timezone, country_code = geo_service.detect_timezone_from_ip(ip_address)
                    
                    # Fallback if no detection possible
                    if not detected_timezone or not country_code:
                        # For private IPs or unknown locations, use hash-based assignment for demo
                        if geo_service.is_private_ip(ip_address):
                            # Use the original hash-based method for private IPs (development/testing)
                            hash_val = hash(ip_address) % 10
                            timezone_map = [
                                ('America/New_York', 'US'),
                                ('Europe/London', 'GB'),
                                ('Asia/Tokyo', 'JP'),
                                ('Australia/Sydney', 'AU'),
                                ('America/Los_Angeles', 'US'),
                                ('Europe/Berlin', 'DE'),
                                ('Asia/Singapore', 'SG'),
                                ('America/Toronto', 'CA'),
                                ('Europe/Paris', 'FR'),
                                ('Asia/Seoul', 'KR')
                            ]
                            detected_timezone, country_code = timezone_map[hash_val]
                        else:
                            # Unknown public IP, default to UTC
                            detected_timezone = 'UTC'
                            country_code = 'XX'  # Unknown country
                    
                    # Update the request with location data (cast to correct types)
                    update_query = """
                    UPDATE requests SET
                        detected_timezone = $1::varchar,
                        detected_country_code = $2::char(2),
                        timestamp_local_detected = convert_to_detected_timezone($3, $1::varchar),
                        created_at_local_detected = convert_to_detected_timezone($4, $1::varchar)
                    WHERE id = $5
                    """
                    
                    await DatabaseUtils.execute_query(
                        update_query, 
                        [detected_timezone, country_code, timestamp_utc, created_at, request_id],
                        fetch_all=False
                    )
                    
                    updated_count += 1
                    
                    if updated_count % 100 == 0:
                        logger.info(f"Updated {updated_count} requests...")
                        
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error processing request {request.get('id', 'unknown')}: {e}")
                    if error_count <= 5:  # Only log first 5 errors
                        continue
            
            logger.info(f"Completed location data population: {updated_count} updated, {error_count} errors")
            
            return {
                "processed": len(requests),
                "updated": updated_count, 
                "errors": error_count
            }
            
        except Exception as e:
            logger.error(f"Failed to populate location data: {e}")
            return {"processed": 0, "updated": 0, "errors": 1, "error": str(e)}
    
    @staticmethod
    async def populate_location_data_for_users() -> Dict[str, int]:
        """Populate location data for client users based on their requests"""
        
        logger.info("Starting to populate location data for users...")
        
        try:
            # Get users and their most common location from requests
            query = """
            WITH user_locations AS (
                SELECT 
                    client_user_id,
                    detected_country_code,
                    detected_timezone,
                    COUNT(*) as request_count,
                    MIN(timestamp_utc) as first_seen,
                    MAX(timestamp_utc) as last_seen,
                    MIN(created_at) as created_at,
                    MAX(created_at) as updated_at
                FROM requests 
                WHERE client_user_id IS NOT NULL 
                AND detected_timezone IS NOT NULL
                GROUP BY client_user_id, detected_country_code, detected_timezone
            ),
            primary_locations AS (
                SELECT DISTINCT ON (client_user_id)
                    client_user_id,
                    detected_country_code,
                    detected_timezone,
                    first_seen,
                    last_seen,
                    created_at,
                    updated_at
                FROM user_locations
                ORDER BY client_user_id, request_count DESC
            )
            UPDATE client_users cu SET
                detected_timezone = pl.detected_timezone,
                detected_country_code = pl.detected_country_code,
                first_seen_local_detected = convert_to_detected_timezone(pl.first_seen, pl.detected_timezone),
                last_seen_local_detected = convert_to_detected_timezone(pl.last_seen, pl.detected_timezone),
                created_at_local_detected = convert_to_detected_timezone(pl.created_at, pl.detected_timezone),
                updated_at_local_detected = convert_to_detected_timezone(pl.updated_at, pl.detected_timezone)
            FROM primary_locations pl
            WHERE cu.id = pl.client_user_id
            AND cu.detected_timezone IS NULL
            """
            
            result = await DatabaseUtils.execute_query(query, [], fetch_all=False)
            updated_count = result.get('updated_count', 0) if result else 0
            
            logger.info(f"Updated location data for {updated_count} users")
            
            return {"updated": updated_count, "errors": 0}
            
        except Exception as e:
            logger.error(f"Failed to populate user location data: {e}")
            return {"updated": 0, "errors": 1, "error": str(e)}
    
    @staticmethod
    async def populate_location_data_for_sessions() -> Dict[str, int]:
        """Populate location data for user sessions"""
        
        logger.info("Starting to populate location data for sessions...")
        
        try:
            query = """
            WITH session_locations AS (
                SELECT 
                    us.client_user_id,
                    us.session_id,
                    cu.detected_timezone,
                    cu.detected_country_code,
                    us.started_at_utc,
                    us.ended_at_utc,
                    us.last_activity_at_utc
                FROM user_sessions us
                JOIN client_users cu ON us.client_user_id = cu.id
                WHERE us.detected_timezone IS NULL
                AND cu.detected_timezone IS NOT NULL
            )
            UPDATE user_sessions us SET
                detected_timezone = sl.detected_timezone,
                detected_country_code = sl.detected_country_code,
                started_at_local_detected = convert_to_detected_timezone(sl.started_at_utc, sl.detected_timezone),
                ended_at_local_detected = convert_to_detected_timezone(sl.ended_at_utc, sl.detected_timezone),
                last_activity_local_detected = convert_to_detected_timezone(sl.last_activity_at_utc, sl.detected_timezone)
            FROM session_locations sl
            WHERE us.client_user_id = sl.client_user_id 
            AND us.session_id = sl.session_id
            """
            
            result = await DatabaseUtils.execute_query(query, [], fetch_all=False)
            updated_count = result.get('updated_count', 0) if result else 0
            
            logger.info(f"Updated location data for {updated_count} sessions")
            
            return {"updated": updated_count, "errors": 0}
            
        except Exception as e:
            logger.error(f"Failed to populate session location data: {e}")
            return {"updated": 0, "errors": 1, "error": str(e)}


# Background functions for location data management

async def populate_all_location_data() -> Dict[str, Dict[str, int]]:
    """Populate location data for all relevant tables"""
    
    logger.info("Starting comprehensive location data population...")
    
    results = {}
    
    # Populate requests first (has the raw IP data)
    results['requests'] = await LocationTimezoneService.populate_location_data_for_requests()
    
    # Then populate users (derived from requests)
    results['users'] = await LocationTimezoneService.populate_location_data_for_users()
    
    # Finally populate sessions (derived from users)
    results['sessions'] = await LocationTimezoneService.populate_location_data_for_sessions()
    
    # Summary
    total_updated = sum(r.get('updated', 0) for r in results.values())
    total_errors = sum(r.get('errors', 0) for r in results.values())
    
    logger.info(f"Location data population complete: {total_updated} records updated, {total_errors} errors")
    
    results['summary'] = {
        'total_updated': total_updated,
        'total_errors': total_errors
    }
    
    return results

async def get_location_data_summary() -> Dict[str, int]:
    """Get summary of location data coverage"""
    
    try:
        query = """
        SELECT 
            'requests' as table_name,
            COUNT(*) as total_records,
            COUNT(detected_timezone) as with_location_data,
            COUNT(detected_timezone) * 100.0 / COUNT(*) as coverage_percentage
        FROM requests
        WHERE ip_address IS NOT NULL
        
        UNION ALL
        
        SELECT 
            'client_users' as table_name,
            COUNT(*) as total_records,
            COUNT(detected_timezone) as with_location_data,
            COUNT(detected_timezone) * 100.0 / COUNT(*) as coverage_percentage
        FROM client_users
        
        UNION ALL
        
        SELECT 
            'user_sessions' as table_name,
            COUNT(*) as total_records,
            COUNT(detected_timezone) as with_location_data,
            COUNT(detected_timezone) * 100.0 / COUNT(*) as coverage_percentage
        FROM user_sessions
        """
        
        results = await DatabaseUtils.execute_query(query, [], fetch_all=True)
        
        summary = {}
        for row in results:
            summary[row['table_name']] = {
                'total_records': row['total_records'],
                'with_location_data': row['with_location_data'],
                'coverage_percentage': round(float(row['coverage_percentage'] or 0), 1)
            }
        
        return summary
        
    except Exception as e:
        logger.error(f"Failed to get location data summary: {e}")
        return {}