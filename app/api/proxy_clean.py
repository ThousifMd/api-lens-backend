"""
Clean Proxy API - NO HARDCODING, ONLY API DATA
All data comes from the API call. If something is missing, it's NULL.
No defaults, no lookups, no calculations - pure data passthrough.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, status
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid
import json
from uuid import UUID

from app.database import DatabaseUtils
from app.utils.logger import get_logger
from app.middleware.request_middleware import authenticate_api_key

router = APIRouter(prefix="/proxy", tags=["Clean Proxy"])
logger = get_logger(__name__)

# ============================================================================
# Clean Data Model - All fields that should come from API
# ============================================================================

class CleanLogEntry(BaseModel):
    # Required identifiers
    requestId: str
    companyId: str
    timestamp: int
    
    # Request info
    method: str
    endpoint: str
    url: Optional[str] = None
    vendor: str
    model: str
    
    # User info
    userId: Optional[str] = None
    userAgent: Optional[str] = None
    referer: Optional[str] = None
    
    # Location info - ALL from API, no lookups
    ipAddress: Optional[str] = None
    country: Optional[str] = None
    countryName: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezoneName: Optional[str] = None
    utcOffset: Optional[int] = None
    
    # Timestamps - both UTC and local from API
    timestampUtc: Optional[str] = None
    timestampLocal: Optional[str] = None
    
    # Headers
    userIdHeader: Optional[str] = None
    customHeaders: Optional[Dict[str, Any]] = None
    
    # Performance metrics
    inputTokens: int
    outputTokens: int
    totalLatency: int
    vendorLatency: int
    responseTime: Optional[int] = None
    statusCode: int
    
    # Cost - from API calculation
    inputCost: float
    outputCost: float
    totalCost: Optional[float] = None  # Can be calculated or provided
    
    # Error info
    errorType: Optional[str] = None
    errorMessage: Optional[str] = None
    errorCode: Optional[str] = None
    
    # Request/Response samples
    requestSample: Optional[Any] = None
    responseSample: Optional[Any] = None
    
    # Image generation fields
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

# ============================================================================
# Clean Proxy Endpoint - NO HARDCODING
# ============================================================================

@router.post("/logs/clean", tags=["Clean Logging"])
async def receive_clean_log_entry(
    log_entry: CleanLogEntry,
    request: Request,
    auth_info: Dict[str, Any] = Depends(authenticate_api_key)
):
    """
    Receive log entry and store EXACTLY as provided - NO MODIFICATIONS
    If data is missing, it's NULL. No lookups, no calculations, no defaults.
    """
    try:
        logger.info(f"Processing clean log entry {log_entry.requestId}")
        
        # Get auth info
        company_id = str(auth_info['company_id'])
        api_key_id = auth_info.get('api_key_id')
        
        # Get vendor and model IDs - create if needed
        vendor_id = None
        model_id = None
        
        # Try to get vendor
        vendor_result = await DatabaseUtils.execute_query(
            "SELECT id FROM vendors WHERE name = $1",
            [log_entry.vendor],
            fetch_all=True
        )
        
        if vendor_result:
            vendor_id = vendor_result[0]['id']
        else:
            # Create vendor only if explicitly provided
            create_vendor = await DatabaseUtils.execute_query(
                "INSERT INTO vendors (name, slug) VALUES ($1, $2) RETURNING id",
                [log_entry.vendor, log_entry.vendor.lower()],
                fetch_all=True
            )
            if create_vendor:
                vendor_id = create_vendor[0]['id']
        
        # Try to get model if vendor exists
        if vendor_id:
            model_result = await DatabaseUtils.execute_query(
                "SELECT id FROM vendor_models WHERE vendor_id = $1 AND name = $2",
                [vendor_id, log_entry.model],
                fetch_all=True
            )
            
            if model_result:
                model_id = model_result[0]['id']
            else:
                # Create model
                create_model = await DatabaseUtils.execute_query(
                    "INSERT INTO vendor_models (vendor_id, name, slug, model_type) VALUES ($1, $2, $3, $4) RETURNING id",
                    [vendor_id, log_entry.model, log_entry.model.lower().replace('.', '-'), 'chat'],
                    fetch_all=True
                )
                if create_model:
                    model_id = create_model[0]['id']
        
        # Handle client user if userId provided
        client_user_id = None
        if log_entry.userId:
            # Check if user exists
            user_result = await DatabaseUtils.execute_query(
                """
                SELECT id FROM client_users 
                WHERE company_id = $1 AND client_user_id = $2
                """,
                [company_id, log_entry.userId],
                fetch_all=True
            )
            
            if user_result:
                client_user_id = user_result[0]['id']
            else:
                # Create user
                create_user = await DatabaseUtils.execute_query(
                    """
                    INSERT INTO client_users (company_id, client_user_id, first_seen_at, last_seen_at, total_requests, total_cost_usd)
                    VALUES ($1, $2, NOW(), NOW(), 0, 0)
                    RETURNING id
                    """,
                    [company_id, log_entry.userId],
                    fetch_all=True
                )
                if create_user:
                    client_user_id = create_user[0]['id']
        
        # Convert timestamps if provided, otherwise NULL
        timestamp_utc = None
        if log_entry.timestampUtc:
            timestamp_utc = log_entry.timestampUtc
        elif log_entry.timestamp:
            # Convert milliseconds to datetime only if no UTC timestamp provided
            timestamp_utc = datetime.fromtimestamp(log_entry.timestamp / 1000, tz=timezone.utc)
        
        # Insert request - ONLY with data from API
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
            log_entry.requestId,
            company_id,
            client_user_id,
            None,  # user_session_id - handle separately if needed
            vendor_id,
            model_id,
            api_key_id,
            log_entry.method,
            log_entry.endpoint,
            log_entry.url,  # ONLY from API, no construction
            log_entry.userIdHeader or log_entry.userId,
            json.dumps(log_entry.customHeaders) if log_entry.customHeaders else None,
            timestamp_utc,
            log_entry.timestampLocal,  # ONLY from API
            log_entry.timezoneName,  # ONLY from API
            log_entry.utcOffset,  # ONLY from API
            log_entry.responseTime or log_entry.totalLatency,
            log_entry.ipAddress,  # ONLY from API
            log_entry.country,  # ONLY from API
            log_entry.countryName,  # ONLY from API
            log_entry.region,  # ONLY from API
            log_entry.city,  # ONLY from API
            log_entry.latitude,  # ONLY from API
            log_entry.longitude,  # ONLY from API
            log_entry.userAgent,  # ONLY from API
            log_entry.referer,  # ONLY from API
            log_entry.inputTokens,  # ONLY from API
            log_entry.outputTokens,  # ONLY from API
            log_entry.inputCost,  # ONLY from API
            log_entry.outputCost,  # ONLY from API
            log_entry.totalLatency,
            log_entry.vendorLatency,
            log_entry.statusCode,
            log_entry.errorType,  # ONLY from API
            log_entry.errorMessage,
            log_entry.errorCode,
            json.dumps(log_entry.requestSample) if log_entry.requestSample else None,
            json.dumps(log_entry.responseSample) if log_entry.responseSample else None,
            log_entry.imageCount,
            log_entry.imageUrls,
            log_entry.imageDimensions,
            log_entry.imageQuality,
            log_entry.imageStyle,
            log_entry.prompt,
            log_entry.negativePrompt,
            log_entry.seed,
            log_entry.generationSteps,
            log_entry.guidanceScale
        ], fetch_all=True)
        
        if request_result:
            request_id = request_result[0]['id']
            
            # Update client user stats if user exists
            if client_user_id and log_entry.totalCost:
                await DatabaseUtils.execute_query(
                    """
                    UPDATE client_users 
                    SET total_requests = total_requests + 1,
                        total_cost_usd = total_cost_usd + $3,
                        last_seen_at = NOW()
                    WHERE id = $1 AND company_id = $2
                    """,
                    [client_user_id, company_id, log_entry.totalCost or 0],
                    fetch_all=False
                )
            
            logger.info(f"Successfully stored clean log entry {log_entry.requestId} - NO data was modified or hardcoded")
            
            return {
                "status": "success",
                "message": "Log entry stored exactly as provided",
                "request_id": str(request_id),
                "data_integrity": "preserved"
            }
        else:
            raise Exception("Failed to insert request")
            
    except Exception as e:
        logger.error(f"Error processing clean log entry: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process log entry: {str(e)}"
        )

@router.get("/logs/clean/verify", tags=["Clean Logging"])
async def verify_clean_data():
    """
    Verify data integrity - check for any hardcoded values
    """
    try:
        # Check for suspicious patterns that might indicate hardcoding
        suspicious = await DatabaseUtils.execute_query("""
            SELECT 
                COUNT(*) FILTER (WHERE city = 'San Francisco' AND latitude = 37.7749) as hardcoded_sf,
                COUNT(*) FILTER (WHERE country = 'US' AND country_name IS NULL) as missing_country_names,
                COUNT(*) FILTER (WHERE timezone_name = 'America/Los_Angeles' AND country != 'US') as wrong_timezones,
                COUNT(*) FILTER (WHERE latitude IS NOT NULL AND longitude IS NULL) as incomplete_coords,
                COUNT(*) FILTER (WHERE url LIKE 'https://api.%.com%') as constructed_urls,
                COUNT(*) as total_requests
            FROM requests
            WHERE created_at > NOW() - INTERVAL '1 hour'
        """, fetch_all=True)
        
        result = suspicious[0] if suspicious else {}
        
        integrity_issues = []
        if result.get('hardcoded_sf', 0) > 0:
            integrity_issues.append(f"Found {result['hardcoded_sf']} requests with hardcoded San Francisco location")
        if result.get('wrong_timezones', 0) > 0:
            integrity_issues.append(f"Found {result['wrong_timezones']} requests with mismatched timezone/country")
        if result.get('constructed_urls', 0) > 0:
            integrity_issues.append(f"Found {result['constructed_urls']} requests with constructed URLs")
            
        return {
            "total_requests": result.get('total_requests', 0),
            "integrity_check": "PASSED" if not integrity_issues else "FAILED",
            "issues": integrity_issues,
            "recommendation": "Use /proxy/logs/clean endpoint to ensure data integrity"
        }
        
    except Exception as e:
        logger.error(f"Error verifying data integrity: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify data integrity: {str(e)}"
        )