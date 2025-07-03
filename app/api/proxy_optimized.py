"""
Optimized Proxy API using the new normalized schema
Clean, efficient, and timezone-aware
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Header, status
from typing import Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid
import json
from uuid import UUID

from app.database import DatabaseUtils
from app.utils.logger import get_logger
from app.config import get_settings
from app.utils.location import LocationService, TimezoneUtils
from app.services.pricing import FixedPricingService as PricingService
from app.middleware.request_middleware import get_client_info, authenticate_api_key
from app.utils.validation import InputValidator, RequestValidator, ValidationError

router = APIRouter(prefix="/proxy", tags=["Proxy Optimized"])
logger = get_logger(__name__)
settings = get_settings()

# ============================================================================
# Optimized Data Models
# ============================================================================

class OptimizedLogEntry(BaseModel):
    requestId: str
    companyId: str
    timestamp: int
    
    # Request info
    method: str
    endpoint: str
    url: Optional[str] = None
    vendor: str
    model: str
    
    # User info (optional)
    userId: Optional[str] = None
    userAgent: Optional[str] = None
    
    # Location info for timezone
    country: Optional[str] = "US"
    region: Optional[str] = "Unknown"
    ipAddress: Optional[str] = None
    
    # Performance metrics
    inputTokens: int
    outputTokens: int
    totalLatency: int
    vendorLatency: int
    statusCode: int
    success: bool
    
    # Error info (optional)
    errorMessage: Optional[str] = None
    errorCode: Optional[str] = None
    
    # Cost
    cost: float

# ============================================================================
# Helper Functions
# ============================================================================

def get_timezone_from_location(country: str, region: str) -> str:
    """Enhanced timezone mapping"""
    location_timezone_map = {
        # United States
        ("US", "California"): "America/Los_Angeles",
        ("US", "New York"): "America/New_York",
        ("US", "Texas"): "America/Chicago",
        ("US", "Dallas"): "America/Chicago",
        ("US", "Florida"): "America/New_York",
        ("US", "Washington"): "America/Los_Angeles",
        ("US", "Illinois"): "America/Chicago",
        
        # Canada
        ("CA", "Ontario"): "America/Toronto",
        ("CA", "Quebec"): "America/Toronto",
        ("CA", "British Columbia"): "America/Vancouver",
        ("CA", "Alberta"): "America/Edmonton",
        
        # Europe
        ("UK", "London"): "Europe/London",
        ("DE", "Berlin"): "Europe/Berlin",
        ("FR", "Paris"): "Europe/Paris",
        ("IT", "Rome"): "Europe/Rome",
        ("ES", "Madrid"): "Europe/Madrid",
        
        # Asia Pacific
        ("JP", "Tokyo"): "Asia/Tokyo",
        ("SG", "Singapore"): "Asia/Singapore",
        ("AU", "Sydney"): "Australia/Sydney",
        ("AU", "Melbourne"): "Australia/Melbourne",
        ("IN", "Mumbai"): "Asia/Kolkata",
        ("CN", "Beijing"): "Asia/Shanghai",
    }
    
    timezone_str = location_timezone_map.get((country, region))
    if timezone_str:
        return timezone_str
    
    # Country defaults
    country_defaults = {
        "US": "America/New_York",
        "CA": "America/Toronto", 
        "UK": "Europe/London",
        "DE": "Europe/Berlin",
        "FR": "Europe/Paris",
        "JP": "Asia/Tokyo",
        "SG": "Asia/Singapore",
        "AU": "Australia/Sydney",
        "IN": "Asia/Kolkata",
        "CN": "Asia/Shanghai",
    }
    
    return country_defaults.get(country, "UTC")

def get_calculated_timestamp(timestamp_ms: int, timezone_name: str) -> str:
    """Calculate timezone-aware timestamp based on location and return as string"""
    from datetime import datetime, timezone
    import pytz
    
    try:
        # Convert millisecond timestamp to UTC datetime
        utc_time = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        
        # Convert to the target timezone
        if timezone_name != "UTC":
            target_tz = pytz.timezone(timezone_name)
            local_time = utc_time.astimezone(target_tz)
        else:
            local_time = utc_time
        
        # Return as formatted string with timezone info
        return local_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        
    except Exception as e:
        logger.error(f"Error calculating timestamp for {timezone_name}: {e}")
        # Fallback to UTC
        utc_time = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        return utc_time.strftime("%Y-%m-%d %H:%M:%S UTC")

async def get_or_create_vendor_model(vendor_name: str, model_name: str) -> Optional[str]:
    """Get or create vendor model, return model_id UUID"""
    try:
        # First try to get existing vendor model
        result = await DatabaseUtils.execute_query("""
            SELECT vm.id 
            FROM vendor_models vm
            JOIN vendors v ON vm.vendor_id = v.id
            WHERE v.name = $1 AND vm.name = $2 AND vm.is_active = true
        """, [vendor_name, model_name], fetch_all=True)
        
        if result:
            return str(result[0]['id'])
        
        # If not found, create vendor first, then model
        vendor_result = await DatabaseUtils.execute_query("""
            INSERT INTO vendors (name, display_name) 
            VALUES ($1, $2) 
            ON CONFLICT (name) DO UPDATE SET display_name = EXCLUDED.display_name
            RETURNING id
        """, [vendor_name, vendor_name.title()], fetch_all=True)
        
        if not vendor_result:
            logger.error(f"Failed to create vendor: {vendor_name}")
            return None
            
        vendor_id = vendor_result[0]['id']
        
        # Create model
        model_result = await DatabaseUtils.execute_query("""
            INSERT INTO vendor_models (vendor_id, name, display_name, model_type) 
            VALUES ($1, $2, $3, 'chat') 
            RETURNING id
        """, [vendor_id, model_name, model_name], fetch_all=True)
        
        if model_result:
            logger.info(f"Created new vendor model: {vendor_name}/{model_name}")
            return str(model_result[0]['id'])
        else:
            logger.error(f"Failed to create vendor model: {vendor_name}/{model_name}")
            return None
        
    except Exception as e:
        logger.error(f"Error with vendor {vendor_name}/{model_name}: {e}")
        return None

async def get_or_create_user_session(company_id: str, user_id: str) -> Optional[str]:
    """Get or create user session for Schema v2, return session_id UUID"""
    if not user_id:
        return None
        
    try:
        # First get or create client user
        client_user_result = await DatabaseUtils.execute_query("""
            INSERT INTO client_users (company_id, client_user_id, display_name)
            VALUES ($1, $2, $2)
            ON CONFLICT (company_id, client_user_id) 
            DO UPDATE SET last_seen_at = NOW()
            RETURNING id
        """, [company_id, user_id], fetch_all=True)
        
        if not client_user_result:
            logger.error(f"Failed to create/get client user: {user_id}")
            return None
            
        client_user_uuid = client_user_result[0]['id']
        session_id = f"{user_id}_session_{datetime.now().strftime('%Y%m%d')}"
        
        # Try to get existing active session
        session_result = await DatabaseUtils.execute_query("""
            SELECT id FROM user_sessions 
            WHERE client_user_id = $1 AND is_active = true
            ORDER BY last_activity_at_utc DESC
            LIMIT 1
        """, [client_user_uuid], fetch_all=True)
        
        if session_result:
            # Update last activity
            await DatabaseUtils.execute_query("""
                UPDATE user_sessions 
                SET last_activity_at_utc = NOW(), request_count = request_count + 1
                WHERE id = $1
            """, [session_result[0]['id']], fetch_all=False)
            return str(session_result[0]['id'])
        
        # Create new session
        new_session_result = await DatabaseUtils.execute_query("""
            INSERT INTO user_sessions (client_user_id, session_id, is_active) 
            VALUES ($1, $2, true) 
            RETURNING id
        """, [client_user_uuid, session_id], fetch_all=True)
        
        if new_session_result:
            return str(new_session_result[0]['id'])
        else:
            logger.error(f"Failed to create user session for: {user_id}")
            return None
        
    except Exception as e:
        logger.error(f"Error with user session {user_id}: {e}")
        return None

def validate_uuid(uuid_string: str, field_name: str = "UUID") -> str:
    try:
        return str(UUID(uuid_string))
    except Exception:
        raise HTTPException(status_code=422, detail=f"Invalid {field_name} format: {uuid_string}")

# ============================================================================
# Optimized Endpoints
# ============================================================================

@router.post("/logs/optimized", tags=["Logging"])
async def receive_optimized_log_entry(
    log_entry: OptimizedLogEntry,
    request: Request,
    client_info: Dict[str, Any] = Depends(get_client_info),
    auth_info: Dict[str, Any] = Depends(authenticate_api_key)
):
    """
    Receive log entry and store in optimized normalized schema
    Clean, efficient, timezone-aware
    """
    try:
        logger.info(f"Processing optimized log entry {log_entry.requestId}")
        
        # Validate input data using comprehensive validation
        try:
            validated_data = InputValidator.validate_log_entry(log_entry.dict())
            logger.debug(f"Input validation passed for request {log_entry.requestId}")
        except ValidationError as ve:
            logger.error(f"Input validation failed for request {log_entry.requestId}: {str(ve)}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Input validation failed: {str(ve)}"
            )
        
        # Get authenticated company and API key info
        company_id = str(auth_info['company_id'])
        api_key_id = auth_info.get('api_key_id')
        
        # Validate user_id if provided
        user_id = None
        if log_entry.userId:
            user_id = validate_uuid(log_entry.userId, "userId")
        
        # Get real client IP and location
        client_ip = client_info.get('ip_address')
        location_info = await LocationService.get_location_from_ip(client_ip)
        
        # 1. Get or create vendor model
        vendor_model_id = await get_or_create_vendor_model(
            log_entry.vendor, 
            log_entry.model
        )
        
        if not vendor_model_id:
            raise ValueError(f"Failed to get/create vendor model {log_entry.vendor}/{log_entry.model}")
        
        # Get the vendor_id from the vendor_models table
        vendor_result = await DatabaseUtils.execute_query("""
            SELECT vendor_id FROM vendor_models WHERE id = $1
        """, [vendor_model_id], fetch_all=True)
        
        if not vendor_result:
            raise ValueError(f"Failed to get vendor_id for model {vendor_model_id}")
        
        vendor_id = vendor_result[0]['vendor_id']
        
        # 2. Get or create user session (if user provided)
        user_session_id = None
        client_user_id = None
        if user_id:
            user_session_id = await get_or_create_user_session(company_id, user_id)
            if user_session_id:
                # Get client_user_id from session
                session_result = await DatabaseUtils.execute_query("""
                    SELECT client_user_id FROM user_sessions WHERE id = $1
                """, [user_session_id], fetch_all=True)
                if session_result:
                    client_user_id = session_result[0]['client_user_id']
        
        # 3. Get real pricing from database
        cost_result = await PricingService.calculate_cost(
            vendor=log_entry.vendor,
            model=log_entry.model, 
            input_tokens=log_entry.inputTokens,
            output_tokens=log_entry.outputTokens,
            company_id=UUID(company_id)
        )
        
        input_cost = cost_result.get('input_cost', 0)
        output_cost = cost_result.get('output_cost', 0)
        total_cost = cost_result.get('total_cost', 0)
        
        # 4. Use real location and timezone detection
        timezone_name = location_info.get('timezone', 'UTC')
        country = location_info.get('country', 'US')
        country_name = location_info.get('country_name', 'United States')
        region = location_info.get('region', 'Unknown')
        city = location_info.get('city', 'Unknown')
        latitude = location_info.get('latitude')
        longitude = location_info.get('longitude')
        
        # Calculate local time and UTC offset
        utc_timestamp = datetime.fromtimestamp(log_entry.timestamp / 1000, tz=timezone.utc)
        local_time, utc_offset_minutes = LocationService.calculate_local_time(utc_timestamp, timezone_name)
        
        # 5. Insert main request record (Schema v2 compliant) with real data
        request_result = await DatabaseUtils.execute_query("""
            INSERT INTO requests (
                request_id, company_id, client_user_id, user_session_id,
                vendor_id, model_id, api_key_id,
                method, endpoint, url,
                user_id_header, custom_headers,
                timestamp_utc, timestamp_local, timezone_name, utc_offset,
                response_time_ms,
                ip_address, country, country_name, region, city, latitude, longitude,
                user_agent, referer,
                input_tokens, output_tokens,
                input_cost, output_cost,
                total_latency_ms, vendor_latency_ms,
                status_code, error_type, error_message, error_code,
                request_sample, response_sample
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32, $33, $34, $35, $36, $37, $38)
            RETURNING id, created_at
        """, [
            log_entry.requestId,  # request_id
            company_id,
            client_user_id,  # client_user_id 
            user_session_id,  # user_session_id
            vendor_id,
            vendor_model_id,  # model_id
            api_key_id,  # api_key_id - from authentication middleware
            log_entry.method,
            log_entry.endpoint,
            log_entry.url or f"https://api.{log_entry.vendor}.com{log_entry.endpoint}",
            log_entry.userId,  # user_id_header
            json.dumps(client_info.get('custom_headers', {})),  # custom_headers
            utc_timestamp,  # timestamp_utc
            local_time,  # timestamp_local - calculated from timezone
            timezone_name,  # timezone_name - real timezone
            utc_offset_minutes,  # utc_offset - calculated offset
            log_entry.totalLatency,  # response_time_ms
            client_ip,  # ip_address - real client IP
            country,  # country - from location service
            country_name,  # country_name - from location service
            region,  # region - from location service
            city,  # city - from location service
            latitude,  # latitude - from location service
            longitude,  # longitude - from location service
            client_info.get('user_agent'),  # user_agent - real user agent
            client_info.get('referer'),  # referer - real referer
            log_entry.inputTokens,  # input_tokens
            log_entry.outputTokens,  # output_tokens
            input_cost,  # input_cost - calculated from pricing service
            output_cost,  # output_cost - calculated from pricing service
            log_entry.totalLatency,  # total_latency_ms
            log_entry.vendorLatency,  # vendor_latency_ms
            log_entry.statusCode,  # status_code
            None,  # error_type
            log_entry.errorMessage,  # error_message
            log_entry.errorCode,  # error_code
            None,  # request_sample
            None   # response_sample
        ], fetch_all=True)
        
        request_id = request_result[0]['id']
        request_created_at = request_result[0]['created_at']
        
        # Note: In Schema v2, cost and error information is stored directly in the requests table
        # No separate cost_calculations or request_errors tables needed
        
        logger.info(f"Successfully stored optimized log entry {log_entry.requestId} with real data - Location: {city}, {region}, {country} ({timezone_name}), Cost: ${total_cost:.6f}")
        
        return {
            "status": "success", 
            "message": "Optimized log entry processed with real location and pricing data",
            "location": f"{city}, {region}, {country}",
            "timezone": timezone_name,
            "cost": {
                "input_cost": input_cost,
                "output_cost": output_cost,
                "total_cost": total_cost,
                "source": cost_result.get('pricing_source', 'unknown')
            },
            "api_key_id": api_key_id,
            "vendor_model_id": vendor_model_id,
            "user_session_id": user_session_id
        }
        
    except Exception as e:
        logger.error(f"Error processing optimized log entry: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process optimized log entry: {str(e)}"
        )

@router.get("/stats/optimized", tags=["Analytics"])
async def get_optimized_stats():
    """Get analytics using Schema v2"""
    try:
        # Get stats from the requests table (Schema v2 compliant)
        stats = await DatabaseUtils.execute_query("""
            SELECT 
                c.name as company_name,
                v.name as vendor,
                vm.name as model,
                COUNT(*) as request_count,
                SUM(r.total_cost) as total_cost,
                AVG(r.total_cost) as avg_cost,
                SUM(r.input_tokens) as total_input_tokens,
                SUM(r.output_tokens) as total_output_tokens,
                AVG(r.response_time_ms) as avg_latency
            FROM requests r
            JOIN companies c ON r.company_id = c.id
            JOIN vendors v ON r.vendor_id = v.id
            JOIN vendor_models vm ON r.model_id = vm.id
            WHERE r.success = true
            GROUP BY c.name, v.name, vm.name
            ORDER BY request_count DESC
        """, fetch_all=True)
        
        # Summary stats (Schema v2 compliant)
        summary = await DatabaseUtils.execute_query("""
            SELECT 
                COUNT(*) as total_requests,
                COUNT(DISTINCT r.company_id) as unique_companies,
                COUNT(DISTINCT r.model_id) as unique_models,
                SUM(r.total_cost) as total_cost,
                AVG(r.response_time_ms) as avg_latency
            FROM requests r
            WHERE r.success = true
        """, fetch_all=True)
        
        return {
            "summary": summary[0] if summary else {},
            "breakdown": stats,
            "schema_info": {
                "optimized": True,
                "normalization": "Schema v2 (3NF)",
                "tables": 8,
                "foreign_keys": True
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting optimized stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get optimized stats: {str(e)}"
        )

@router.get("/health/optimized", tags=["Health"])
async def optimized_health_check():
    """Health check for Schema v2"""
    try:
        # Check all Schema v2 tables
        tables_status = {}
        current_tables = [
            'vendors', 'vendor_models', 'vendor_pricing', 'companies', 
            'api_keys', 'client_users', 'user_sessions', 'requests'
        ]
        
        for table in current_tables:
            try:
                result = await DatabaseUtils.execute_query(f"SELECT COUNT(*) as count FROM {table}", fetch_all=True)
                tables_status[table] = {
                    "status": "healthy",
                    "record_count": result[0]['count'] if result else 0
                }
            except Exception as e:
                tables_status[table] = {
                    "status": "error",
                    "error": str(e)
                }
        
        all_healthy = all(t["status"] == "healthy" for t in tables_status.values())
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "schema": "v2",
            "tables": tables_status,
            "normalization": "Third Normal Form (3NF)",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }