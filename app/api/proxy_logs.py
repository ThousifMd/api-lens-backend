"""
Optimized Proxy API using the new normalized schema
Clean, efficient, and timezone-aware
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Header, status
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid
import json
import re
from uuid import UUID

from app.database import DatabaseUtils
from app.utils.logger import get_logger
from app.config import get_settings
from app.utils.location import LocationService, TimezoneUtils
from app.services.pricing import FixedPricingService as PricingService
from app.middleware.request_middleware import get_client_info, authenticate_api_key
from app.utils.validation import InputValidator, RequestValidator, ValidationError
from app.services.token_calculator import TokenCalculator

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
    
    # Image generation fields (optional)
    imageCount: Optional[int] = None
    imageUrls: Optional[List[str]] = None
    imageDimensions: Optional[str] = None
    imageQuality: Optional[str] = None
    imageStyle: Optional[str] = None
    prompt: Optional[str] = None
    negativePrompt: Optional[str] = None
    seed: Optional[int] = None
    generationSteps: Optional[int] = None
    guidanceScale: Optional[float] = None
    
    # Request and response samples (already exist in DB schema)
    requestSample: Optional[Dict[str, Any]] = None
    responseSample: Optional[Dict[str, Any]] = None
    
    # Alternative field names from Cloudflare Worker
    request_body: Optional[Dict[str, Any]] = None
    response_body: Optional[Dict[str, Any]] = None

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
        # First try to get existing vendor model (case-insensitive)
        result = await DatabaseUtils.execute_query("""
            SELECT vm.id 
            FROM vendor_models vm
            JOIN vendors v ON vm.vendor_id = v.id
            WHERE LOWER(v.name) = LOWER($1) AND vm.name = $2 AND vm.is_active = true
        """, [vendor_name, model_name], fetch_all=True)
        
        if result:
            return str(result[0]['id'])
        
        # If not found, create vendor first, then model
        vendor_result = await DatabaseUtils.execute_query("""
            INSERT INTO vendors (id, name, slug, is_active, is_supported)
            VALUES (gen_random_uuid(), $1, $2, true, true)
            ON CONFLICT (name) DO NOTHING
            RETURNING id
        """, [vendor_name, vendor_name], fetch_all=True)
        
        if vendor_result:
            vendor_id = vendor_result[0]['id']
        else:
            # Vendor already exists, get its ID (case-insensitive)
            vendor_query = await DatabaseUtils.execute_query("""
                SELECT id FROM vendors WHERE LOWER(name) = LOWER($1)
            """, [vendor_name], fetch_all=True)
            
            if not vendor_query:
                logger.error(f"Failed to create or find vendor: {vendor_name}")
                return None
            vendor_id = vendor_query[0]['id']
        
        # Create model
        model_result = await DatabaseUtils.execute_query("""
            INSERT INTO vendor_models (
                id, vendor_id, name, slug, model_type
            )
            VALUES (
                gen_random_uuid(), $1, $2, $3, 'chat'
            ) 
            RETURNING id
        """, [vendor_id, model_name, model_name.lower().replace('.', '-')], fetch_all=True)
        
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
        logger.info(f"Getting/creating user session for company {company_id}, user {user_id}")
        
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
            WHERE client_user_id = $1 AND ended_at IS NULL
            ORDER BY started_at DESC
            LIMIT 1
        """, [client_user_uuid], fetch_all=True)
        
        if session_result:
            # Update request count
            await DatabaseUtils.execute_query("""
                UPDATE user_sessions 
                SET request_count = request_count + 1
                WHERE id = $1
            """, [session_result[0]['id']], fetch_all=False)
            return str(session_result[0]['id'])
        
        # Create new session
        new_session_result = await DatabaseUtils.execute_query("""
            INSERT INTO user_sessions (client_user_id, session_id) 
            VALUES ($1, $2) 
            RETURNING id
        """, [client_user_uuid, session_id], fetch_all=True)
        
        if new_session_result:
            session_id = str(new_session_result[0]['id'])
            logger.info(f"Created new session: {session_id}")
            return session_id
        else:
            logger.error(f"Failed to create user session for: {user_id}")
            return None
        
    except Exception as e:
        logger.error(f"Error with user session {user_id}: {e}", exc_info=True)
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
    request: Request,
    client_info: Dict[str, Any] = Depends(get_client_info)
):
    """
    Receive log entry and store in optimized normalized schema
    Clean, efficient, timezone-aware
    """
    
    # Get raw request body
    try:
        body = await request.body()
        body_str = body.decode('utf-8')
        logger.info("=== INCOMING METADATA FROM CLOUDFLARE WORKER ===")
        logger.info(f"Raw request body: {body_str}")
        logger.info("==============================================")
        
        # Parse the body
        import json
        body_json = json.loads(body_str)
        
        # Try to create OptimizedLogEntry from the data
        log_entry = OptimizedLogEntry(**body_json)
        
    except Exception as e:
        logger.error(f"Failed to parse request body: {str(e)}")
        logger.error(f"Body was: {body_str if 'body_str' in locals() else 'Could not read body'}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid request format: {str(e)}"
        )
    
    # No authentication - trust the data from Cloudflare Workers
    auth_info = {
        'company_id': log_entry.companyId,
        'api_key_id': None,  # Not provided by Cloudflare Workers
        'is_admin': True
    }
    logger.info(f"Processing log entry {log_entry.requestId} without authentication")
    
    try:
        logger.info(f"Processing optimized log entry {log_entry.requestId}")
        
        # Handle alternative field names from Cloudflare Worker
        if not log_entry.requestSample and log_entry.request_body:
            log_entry.requestSample = log_entry.request_body
        if not log_entry.responseSample and log_entry.response_body:
            log_entry.responseSample = log_entry.response_body
            
        # Extract prompt from request if not provided directly
        if not log_entry.prompt and log_entry.requestSample:
            if isinstance(log_entry.requestSample, dict):
                # Try to extract from messages array (OpenAI format)
                messages = log_entry.requestSample.get("messages", [])
                if messages and isinstance(messages, list) and len(messages) > 0:
                    first_message = messages[0]
                    if isinstance(first_message, dict) and first_message.get("role") == "user":
                        log_entry.prompt = first_message.get("content")
                # Try direct prompt field (some APIs)
                if not log_entry.prompt:
                    log_entry.prompt = log_entry.requestSample.get("prompt")
        
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
        
        # Validate image generation fields
        if log_entry.imageCount is not None:
            logger.info(f"Validating imageCount: {log_entry.imageCount}")
            if not 0 <= log_entry.imageCount <= 10:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="image_count must be between 0 and 10"
                )
        
        if log_entry.imageDimensions:
            # Validate format WIDTHxHEIGHT
            if not re.match(r'^\d+x\d+$', log_entry.imageDimensions):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="image_dimensions must be in format WIDTHxHEIGHT (e.g., 1024x768)"
                )
        
        if log_entry.generationSteps is not None:
            if not 1 <= log_entry.generationSteps <= 150:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="generation_steps must be between 1 and 150"
                )
        
        if log_entry.guidanceScale is not None:
            if not 1.0 <= log_entry.guidanceScale <= 20.0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="guidance_scale must be between 1.0 and 20.0"
                )
        
        # Get authenticated company and API key info
        company_id = str(auth_info['company_id'])
        api_key_id = auth_info.get('api_key_id')
        
        # Validate user_id if provided
        user_id = None
        if log_entry.userId:
            try:
                user_id = validate_uuid(log_entry.userId, "userId")
                logger.info(f"Validated user_id: {user_id}")
            except Exception as e:
                logger.error(f"Failed to validate userId: {log_entry.userId} - {str(e)}")
                user_id = log_entry.userId  # Use the raw value if it's not a valid UUID
        
        # Get real client IP and location
        client_ip = client_info.get('ip_address')
        location_info = await LocationService.get_location_from_ip(client_ip)
        
        # Ensure location data is always populated (use defaults if missing)
        if not location_info or location_info.get('source') == 'default':
            logger.warning(f"Using default location for IP {client_ip}")
            # Use the provided country/region if available, otherwise defaults
            location_info = {
                'country': log_entry.country or 'US',
                'country_name': 'United States',
                'region': log_entry.region or 'California',
                'city': 'San Francisco',
                'timezone': 'America/Los_Angeles',
                'latitude': 37.7749,
                'longitude': -122.4194,
                'utc_offset': '-0800',
                'source': 'fallback'
            }
        
        # 1. Get or create vendor model
        model_id = await get_or_create_vendor_model(
            log_entry.vendor, 
            log_entry.model
        )
        
        if not model_id:
            raise ValueError(f"Failed to get/create vendor model {log_entry.vendor}/{log_entry.model}")
        
        # Get the vendor_id from the vendor_models table
        vendor_result = await DatabaseUtils.execute_query("""
            SELECT vendor_id FROM vendor_models WHERE id = $1
        """, [model_id], fetch_all=True)
        
        if not vendor_result:
            raise ValueError(f"Failed to get vendor_id for model {model_id}")
        
        vendor_id = vendor_result[0]['vendor_id']
        
        # 2. Get or create user session (if user provided)
        user_session_id = None
        client_user_id = None
        if user_id:
            logger.info(f"Creating session for user: {user_id}")
            user_session_id = await get_or_create_user_session(company_id, user_id)
            logger.info(f"Session creation returned: {user_session_id}")
            if user_session_id:
                # Get client_user_id from session
                session_result = await DatabaseUtils.execute_query("""
                    SELECT client_user_id FROM user_sessions WHERE id = $1
                """, [user_session_id], fetch_all=True)
                if session_result:
                    client_user_id = session_result[0]['client_user_id']
        
        # 3. Calculate/estimate tokens if needed
        calculated_input_tokens, calculated_output_tokens = TokenCalculator.calculate_tokens(
            vendor=log_entry.vendor,
            model=log_entry.model,
            input_tokens=log_entry.inputTokens,
            output_tokens=log_entry.outputTokens,
            endpoint=log_entry.endpoint,
            request_data=None,  # Could be passed if available
            response_data=None  # Could be passed if available
        )
        
        # Use calculated tokens for cost calculation
        cost_result = await PricingService.calculate_cost(
            vendor=log_entry.vendor,
            model=log_entry.model, 
            input_tokens=calculated_input_tokens,
            output_tokens=calculated_output_tokens,
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
                request_sample, response_sample,
                image_count, image_urls, image_dimensions, image_quality, image_style,
                prompt, negative_prompt, seed, generation_steps, guidance_scale
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32, $33, $34, $35, $36, $37, $38, $39, $40, $41, $42, $43, $44, $45, $46, $47, $48)
            RETURNING id, created_at
        """, [
            log_entry.requestId,  # request_id
            company_id,
            client_user_id,  # client_user_id 
            user_session_id,  # user_session_id
            vendor_id,
            model_id,  # model_id
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
            calculated_input_tokens,  # input_tokens - using calculated/estimated values
            calculated_output_tokens,  # output_tokens - using calculated/estimated values
            input_cost,  # input_cost - calculated from pricing service
            output_cost,  # output_cost - calculated from pricing service
            log_entry.totalLatency,  # total_latency_ms
            log_entry.vendorLatency,  # vendor_latency_ms
            log_entry.statusCode,  # status_code
            None,  # error_type
            log_entry.errorMessage,  # error_message
            log_entry.errorCode,  # error_code
            json.dumps(log_entry.requestSample) if log_entry.requestSample else None,  # request_sample
            json.dumps(log_entry.responseSample) if log_entry.responseSample else None,   # response_sample
            log_entry.imageCount,  # image_count
            log_entry.imageUrls,  # image_urls
            log_entry.imageDimensions,  # image_dimensions
            log_entry.imageQuality,  # image_quality
            log_entry.imageStyle,  # image_style
            log_entry.prompt,  # prompt
            log_entry.negativePrompt,  # negative_prompt
            log_entry.seed,  # seed
            log_entry.generationSteps,  # generation_steps
            log_entry.guidanceScale   # guidance_scale
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
            "model_id": model_id,
            "user_session_id": user_session_id
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions (like validation errors)
        raise
    except Exception as e:
        logger.error(f"Error processing optimized log entry: {str(e)}", exc_info=True)
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
                AVG(r.response_time_ms) as avg_latency,
                -- Image generation stats
                COUNT(CASE WHEN r.image_count > 0 THEN 1 END) as image_requests,
                SUM(COALESCE(r.image_count, 0)) as total_images_generated,
                AVG(CASE WHEN r.image_count > 0 THEN r.image_count END) as avg_images_per_request,
                MODE() WITHIN GROUP (ORDER BY r.image_dimensions) FILTER (WHERE r.image_dimensions IS NOT NULL) as most_common_dimensions
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
                AVG(r.response_time_ms) as avg_latency,
                -- Image generation summary
                COUNT(CASE WHEN r.image_count > 0 THEN 1 END) as total_image_requests,
                SUM(COALESCE(r.image_count, 0)) as total_images_generated,
                COUNT(DISTINCT CASE WHEN r.image_count > 0 THEN r.vendor_id END) as image_vendors,
                COUNT(DISTINCT CASE WHEN r.image_count > 0 THEN r.model_id END) as image_models
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

@router.get("/requests", tags=["Analytics"])
async def get_all_requests(
    api_key_data: Dict[str, Any] = Depends(authenticate_api_key),
    limit: int = 1000
):
    """
    Get all API call requests for the authenticated company.
    Returns an array of all individual API calls with complete details.
    """
    try:
        company_id = api_key_data['company_id']
        
        # Get all requests for this company
        query = """
            SELECT 
                r.*,
                v.name as vendor_name,
                vm.name as model_name
            FROM requests r
            LEFT JOIN vendor_models vm ON r.model_id = vm.id
            LEFT JOIN vendors v ON vm.vendor_id = v.id
            WHERE r.company_id = $1
            ORDER BY r.created_at DESC
            LIMIT $2
        """
        
        requests = await DatabaseUtils.execute_query(
            query, 
            [company_id, limit], 
            fetch_all=True
        )
        
        # Convert to list of dictionaries with all fields
        result = []
        for req in requests:
            result.append({
                "id": str(req.get('id', '')),
                "request_id": req.get('request_id'),
                "company_id": str(req.get('company_id', '')),
                "timestamp": req.get('created_at').isoformat() if req.get('created_at') else None,
                "method": req.get('method'),
                "endpoint": req.get('endpoint'),
                "url": req.get('url'),
                "headers": req.get('headers'),
                "body": req.get('body'),
                "response": req.get('response'),
                "status_code": req.get('status_code'),
                "success": req.get('success'),
                "error_message": req.get('error_message'),
                "vendor": req.get('vendor_name'),
                "model": req.get('model_name'),
                "model_id": str(req.get('model_id')) if req.get('model_id') else None,
                "input_tokens": req.get('input_tokens'),
                "output_tokens": req.get('output_tokens'),
                "total_tokens": req.get('total_tokens'),
                "cost": float(req.get('cost')) if req.get('cost') else 0.0,
                "total_latency": req.get('total_latency'),
                "vendor_latency": req.get('vendor_latency'),
                "user_id": str(req.get('user_id')) if req.get('user_id') else None,
                "session_id": str(req.get('session_id')) if req.get('session_id') else None,
                "ip_address": req.get('ip_address'),
                "user_agent": req.get('user_agent'),
                "country": req.get('country'),
                "region": req.get('region'),
                "city": req.get('city'),
                "timezone": req.get('timezone'),
                "metadata": req.get('metadata'),
                "created_at": req.get('created_at').isoformat() if req.get('created_at') else None,
                "updated_at": req.get('updated_at').isoformat() if req.get('updated_at') else None,
                # Image generation fields
                "image_count": req.get('image_count'),
                "image_urls": req.get('image_urls'),
                "image_dimensions": req.get('image_dimensions'),
                "image_quality": req.get('image_quality'),
                "image_style": req.get('image_style'),
                "prompt": req.get('prompt'),
                "negative_prompt": req.get('negative_prompt'),
                "seed": req.get('seed'),
                "generation_steps": req.get('generation_steps'),
                "guidance_scale": req.get('guidance_scale')
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving requests: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve requests: {str(e)}"
        )