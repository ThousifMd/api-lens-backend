from fastapi import APIRouter, HTTPException, Depends, Request, Header, status
from fastapi.responses import StreamingResponse
import json
import os
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from datetime import datetime
import uuid

from app.clients.openai_client import OpenAIClient
from app.clients.anthropic_client import AnthropicClient
from app.clients.gemini_client import GeminiClient
from app.services.auth import validate_api_key
from app.utils.logger import get_logger
from app.database import get_db_session
from app.config import get_settings

router = APIRouter(prefix="/proxy", tags=["Proxy"])
logger = get_logger(__name__)
settings = get_settings()

async def get_database_connection():
    """Get the appropriate database connection (test or production)"""
    if settings.ENVIRONMENT == "testing" or "test" in settings.DATABASE_URL.lower():
        return test_db_manager.get_connection()
    else:
        return get_db_connection()

async def verify_api_key(authorization: Optional[str] = Header(None)) -> dict:
    """Dependency to verify API key from Authorization header"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    # Extract API key from Authorization header (Bearer or API key format)
    api_key = None
    if authorization.startswith("Bearer "):
        api_key = authorization[7:]
    elif authorization.startswith("als_"):
        api_key = authorization
    else:
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    # Validate the API key
    company = await validate_api_key(api_key)
    if not company:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return {
        "company_id": str(company.id),
        "company_name": company.name,
        "schema_name": company.schema_name
    }

class ChatRequest(BaseModel):
    messages: list
    model: str
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False

@router.post("/openai/chat")
async def proxy_openai_chat(
    request: ChatRequest,
    auth_data: dict = Depends(verify_api_key)
):
    """Proxy OpenAI chat completions"""
    try:
        company_id = auth_data["company_id"]
        
        # Initialize OpenAI client
        openai_client = OpenAIClient()
        
        # Make the request to OpenAI
        response = await openai_client.chat_completion(
            messages=request.messages,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=request.stream
        )
        
        return response
        
    except Exception as e:
        logger.error(f"OpenAI proxy error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OpenAI proxy error: {str(e)}")

@router.post("/claude/chat")
async def proxy_claude_chat(
    request: ChatRequest,
    auth_data: dict = Depends(verify_api_key)
):
    """Proxy Claude chat completions"""
    try:
        company_id = auth_data["company_id"]
        
        # Initialize Anthropic client
        anthropic_client = AnthropicClient()
        
        # Make the request to Claude
        response = await anthropic_client.chat_completion(
            messages=request.messages,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=request.stream
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Claude proxy error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Claude proxy error: {str(e)}")

@router.post("/gemini/chat")
async def proxy_gemini_chat(
    request: ChatRequest,
    auth_data: dict = Depends(verify_api_key)
):
    """Proxy Gemini chat completions"""
    try:
        company_id = auth_data["company_id"]
        
        # Initialize Gemini client
        gemini_client = GeminiClient()
        
        # Make the request to Gemini
        response = await gemini_client.chat_completion(
            messages=request.messages,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=request.stream
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Gemini proxy error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Gemini proxy error: {str(e)}")

# ============================================================================
# LOGGING ENDPOINTS FOR WORKERS PROXY
# ============================================================================

class RequestMetadata(BaseModel):
    requestId: str
    timestamp: int
    method: str
    url: str
    userAgent: Optional[str] = None
    origin: Optional[str] = None
    referer: Optional[str] = None
    ip: Optional[str] = None
    headers: Dict[str, str] = {}
    contentLength: Optional[int] = None
    contentType: Optional[str] = None
    vendor: str
    model: Optional[str] = None
    endpoint: str
    companyId: Optional[str] = None
    apiKeyId: Optional[str] = None
    userId: Optional[str] = None
    requestBody: Optional[Any] = None
    bodyHash: Optional[str] = None
    bodySize: int = 0
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    timezone: Optional[str] = None

class ResponseMetadata(BaseModel):
    requestId: str
    timestamp: int
    statusCode: int
    statusText: str
    headers: Dict[str, str] = {}
    contentLength: Optional[int] = None
    contentType: Optional[str] = None
    responseBody: Optional[Any] = None
    bodyHash: Optional[str] = None
    bodySize: int = 0
    totalLatency: int
    vendorLatency: Optional[int] = None
    processingLatency: int
    success: bool
    errorCode: Optional[str] = None
    errorMessage: Optional[str] = None
    errorType: Optional[str] = None
    inputTokens: Optional[int] = None
    outputTokens: Optional[int] = None
    totalTokens: Optional[int] = None
    cacheHit: Optional[bool] = None
    cacheKey: Optional[str] = None

class PerformanceMetrics(BaseModel):
    requestId: str
    companyId: str
    timestamp: int
    totalLatency: int
    vendorLatency: int = 0
    authLatency: int = 0
    ratelimitLatency: int = 0
    costLatency: int = 0
    loggingLatency: int = 0
    success: bool
    errorType: Optional[str] = None
    retryCount: Optional[int] = None
    bytesIn: int = 0
    bytesOut: int = 0
    cacheHitRate: Optional[float] = None
    rateLimitRemaining: Optional[int] = None
    queueDepth: Optional[int] = None

class LogEntry(BaseModel):
    requestId: str
    companyId: str
    timestamp: int
    request: RequestMetadata
    response: ResponseMetadata
    performance: PerformanceMetrics
    cost: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

class LogBatch(BaseModel):
    events: List[LogEntry]

class EventLog(BaseModel):
    requestId: str
    companyId: Optional[str] = None
    timestamp: str
    event: str
    success: Optional[bool] = None
    details: Optional[Dict[str, Any]] = None
    ipAddress: Optional[str] = None
    userAgent: Optional[str] = None
    path: Optional[str] = None

async def verify_worker_token(authorization: Optional[str] = Header(None)) -> bool:
    """Verify that the request is coming from an authorized worker"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    # Extract token from Authorization header
    token = None
    if authorization.startswith("Bearer "):
        token = authorization[7:]
    else:
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    if not token:
        raise HTTPException(status_code=401, detail="Missing worker token")
    
    # Get valid worker tokens from environment
    valid_tokens = []
    
    # Production worker token
    if hasattr(settings, 'WORKER_TOKEN') and settings.WORKER_TOKEN:
        valid_tokens.append(settings.WORKER_TOKEN)
    
    # Test worker token for testing
    test_token = os.getenv('TEST_WORKER_TOKEN', 'test-worker-token-123')
    if settings.ENVIRONMENT in ['testing', 'development']:
        valid_tokens.append(test_token)
    
    # Fallback tokens from environment
    env_token = os.getenv('API_LENS_WORKER_TOKEN')
    if env_token:
        valid_tokens.append(env_token)
    
    # Additional tokens for multi-worker environments
    for i in range(1, 6):  # Support up to 5 worker tokens
        env_token = os.getenv(f'API_LENS_WORKER_TOKEN_{i}')
        if env_token:
            valid_tokens.append(env_token)
    
    if not valid_tokens:
        logger.error("No worker tokens configured")
        raise HTTPException(status_code=500, detail="Worker authentication not configured")
    
    # Validate token
    if token in valid_tokens:
        logger.debug(f"Worker token validated successfully")
        return True
    else:
        logger.warning(f"Invalid worker token provided")
        raise HTTPException(status_code=401, detail="Invalid worker token")

async def _store_log_entry_sqlite(log_entry: LogEntry):
    """Store log entry in SQLite test database"""
    async with test_db_manager.get_connection() as db:
        # Store main log entry
        await db.execute("""
            INSERT OR REPLACE INTO worker_request_logs (
                id, request_id, company_id, timestamp, method, url, vendor, model,
                status_code, success, total_latency, vendor_latency, 
                input_tokens, output_tokens, total_tokens, cost,
                ip_address, country, region, user_agent, error_message,
                endpoint, processing_latency, error_code, error_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), log_entry.requestId, log_entry.companyId,
            datetime.fromtimestamp(log_entry.timestamp / 1000),
            log_entry.request.method, log_entry.request.url,
            log_entry.request.vendor, log_entry.request.model,
            log_entry.response.statusCode, log_entry.response.success,
            log_entry.response.totalLatency, log_entry.response.vendorLatency,
            log_entry.response.inputTokens, log_entry.response.outputTokens,
            log_entry.response.totalTokens, log_entry.cost,
            log_entry.request.ip, log_entry.request.country,
            log_entry.request.region, log_entry.request.userAgent,
            log_entry.response.errorMessage, log_entry.request.endpoint,
            log_entry.response.processingLatency, log_entry.response.errorCode,
            log_entry.response.errorType
        ))
        
        # Store performance metrics if available
        if log_entry.performance:
            await db.execute("""
                INSERT OR REPLACE INTO worker_performance_metrics (
                    id, request_id, company_id, timestamp, total_latency, vendor_latency,
                    auth_latency, ratelimit_latency, cost_latency, logging_latency,
                    success, error_type, retry_count, bytes_in, bytes_out,
                    cache_hit_rate, rate_limit_remaining, queue_depth
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()), log_entry.performance.requestId,
                log_entry.performance.companyId,
                datetime.fromtimestamp(log_entry.performance.timestamp / 1000),
                log_entry.performance.totalLatency, log_entry.performance.vendorLatency,
                log_entry.performance.authLatency, log_entry.performance.ratelimitLatency,
                log_entry.performance.costLatency, log_entry.performance.loggingLatency,
                log_entry.performance.success, log_entry.performance.errorType,
                log_entry.performance.retryCount, log_entry.performance.bytesIn,
                log_entry.performance.bytesOut, log_entry.performance.cacheHitRate,
                log_entry.performance.rateLimitRemaining, log_entry.performance.queueDepth
            ))
        
        await db.commit()

async def _store_log_entry_postgres(log_entry: LogEntry):
    """Store log entry in PostgreSQL production database"""
    async with get_db_connection() as connection:
        # Store the log entry in the database
        query = """
        INSERT INTO worker_request_logs (
            request_id, company_id, timestamp, method, url, vendor, model,
            status_code, success, total_latency, vendor_latency, 
            input_tokens, output_tokens, total_tokens, cost,
            ip_address, country, region, user_agent, error_message,
            endpoint, processing_latency, error_code, error_type,
            created_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
            $16, $17, $18, $19, $20, $21, $22, $23, $24, $25
        )
        ON CONFLICT (request_id) DO UPDATE SET
            total_latency = EXCLUDED.total_latency,
            vendor_latency = EXCLUDED.vendor_latency,
            processing_latency = EXCLUDED.processing_latency,
            success = EXCLUDED.success,
            status_code = EXCLUDED.status_code,
            cost = EXCLUDED.cost,
            error_message = EXCLUDED.error_message,
            error_code = EXCLUDED.error_code,
            error_type = EXCLUDED.error_type,
            updated_at = NOW()
        """
        
        await connection.execute(
            query,
            log_entry.requestId,
            log_entry.companyId,
            datetime.fromtimestamp(log_entry.timestamp / 1000),
            log_entry.request.method,
            log_entry.request.url,
            log_entry.request.vendor,
            log_entry.request.model,
            log_entry.response.statusCode,
            log_entry.response.success,
            log_entry.response.totalLatency,
            log_entry.response.vendorLatency,
            log_entry.response.inputTokens,
            log_entry.response.outputTokens,
            log_entry.response.totalTokens,
            log_entry.cost,
            log_entry.request.ip,
            log_entry.request.country,
            log_entry.request.region,
            log_entry.request.userAgent,
            log_entry.response.errorMessage,
            log_entry.request.endpoint,
            log_entry.response.processingLatency,
            log_entry.response.errorCode,
            log_entry.response.errorType,
            datetime.utcnow()
        )
        
        # Also store performance metrics if needed
        if log_entry.performance:
            perf_query = """
            INSERT INTO worker_performance_metrics (
                request_id, company_id, timestamp, total_latency, vendor_latency,
                auth_latency, ratelimit_latency, cost_latency, logging_latency,
                success, error_type, retry_count, bytes_in, bytes_out,
                cache_hit_rate, rate_limit_remaining, queue_depth, created_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
                $15, $16, $17, $18
            )
            ON CONFLICT (request_id) DO NOTHING
            """
            
            await connection.execute(
                perf_query,
                log_entry.performance.requestId,
                log_entry.performance.companyId,
                datetime.fromtimestamp(log_entry.performance.timestamp / 1000),
                log_entry.performance.totalLatency,
                log_entry.performance.vendorLatency,
                log_entry.performance.authLatency,
                log_entry.performance.ratelimitLatency,
                log_entry.performance.costLatency,
                log_entry.performance.loggingLatency,
                log_entry.performance.success,
                log_entry.performance.errorType,
                log_entry.performance.retryCount,
                log_entry.performance.bytesIn,
                log_entry.performance.bytesOut,
                log_entry.performance.cacheHitRate,
                log_entry.performance.rateLimitRemaining,
                log_entry.performance.queueDepth,
                datetime.utcnow()
            )

@router.post("/logs/requests", tags=["Logging"])
async def receive_log_entry(
    log_entry: LogEntry,
    authorized: bool = Depends(verify_worker_token)
):
    """
    Receive a single log entry from the Workers proxy
    
    This endpoint receives structured log data from Cloudflare Workers
    and stores it in the database for analytics and monitoring.
    """
    try:
        # Use test database for testing, regular database for production
        if settings.ENVIRONMENT == "testing" or "test" in getattr(settings, 'DATABASE_URL', '').lower():
            await _store_log_entry_sqlite(log_entry)
        else:
            await _store_log_entry_postgres(log_entry)
        
        logger.info(f"Successfully stored log entry for request {log_entry.requestId}")
        return {"status": "success", "message": "Log entry stored successfully"}
        
    except Exception as e:
        logger.error(f"Error storing log entry: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store log entry: {str(e)}"
        )

@router.post("/logs/batch", tags=["Logging"])
async def receive_log_batch(
    log_batch: LogBatch,
    authorized: bool = Depends(verify_worker_token)
):
    """
    Receive a batch of log entries from the Workers proxy
    
    This endpoint receives multiple log entries in a single request
    for efficient bulk processing.
    """
    try:
        batch_id = str(uuid.uuid4())
        processed_count = 0
        failed_count = 0
        
        async with get_db_connection() as connection:
            async with connection.transaction():
                for log_entry in log_batch.events:
                    try:
                        # Store each log entry
                        query = """
                        INSERT INTO worker_request_logs (
                            request_id, company_id, timestamp, method, url, vendor, model,
                            status_code, success, total_latency, vendor_latency, 
                            input_tokens, output_tokens, total_tokens, cost,
                            ip_address, country, region, user_agent, error_message,
                            batch_id, endpoint, processing_latency, error_code, error_type,
                            created_at
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
                            $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26
                        )
                        ON CONFLICT (request_id) DO UPDATE SET
                            total_latency = EXCLUDED.total_latency,
                            vendor_latency = EXCLUDED.vendor_latency,
                            processing_latency = EXCLUDED.processing_latency,
                            success = EXCLUDED.success,
                            status_code = EXCLUDED.status_code,
                            cost = EXCLUDED.cost,
                            batch_id = EXCLUDED.batch_id,
                            error_message = EXCLUDED.error_message,
                            error_code = EXCLUDED.error_code,
                            error_type = EXCLUDED.error_type,
                            updated_at = NOW()
                        """
                        
                        await connection.execute(
                            query,
                            log_entry.requestId,
                            log_entry.companyId,
                            datetime.fromtimestamp(log_entry.timestamp / 1000),
                            log_entry.request.method,
                            log_entry.request.url,
                            log_entry.request.vendor,
                            log_entry.request.model,
                            log_entry.response.statusCode,
                            log_entry.response.success,
                            log_entry.response.totalLatency,
                            log_entry.response.vendorLatency,
                            log_entry.response.inputTokens,
                            log_entry.response.outputTokens,
                            log_entry.response.totalTokens,
                            log_entry.cost,
                            log_entry.request.ip,
                            log_entry.request.country,
                            log_entry.request.region,
                            log_entry.request.userAgent,
                            log_entry.response.errorMessage,
                            batch_id,
                            log_entry.request.endpoint,
                            log_entry.response.processingLatency,
                            log_entry.response.errorCode,
                            log_entry.response.errorType,
                            datetime.utcnow()
                        )
                        
                        processed_count += 1
                        
                    except Exception as entry_error:
                        logger.error(f"Error processing log entry {log_entry.requestId}: {str(entry_error)}")
                        failed_count += 1
        
        logger.info(f"Batch {batch_id}: processed {processed_count} entries, failed {failed_count}")
        return {
            "status": "success",
            "batch_id": batch_id,
            "processed_count": processed_count,
            "failed_count": failed_count,
            "message": f"Processed {processed_count} log entries successfully"
        }
        
    except Exception as e:
        logger.error(f"Error processing log batch: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process log batch: {str(e)}"
        )

@router.post("/events", tags=["Logging"])
async def receive_events(
    event: EventLog,
    authorized: bool = Depends(verify_worker_token)
):
    """
    Receive system events from the Workers proxy
    
    This endpoint receives various system events like rate limit
    violations, authentication failures, etc.
    """
    try:
        async with get_db_connection() as connection:
            query = """
            INSERT INTO worker_system_events (
                request_id, company_id, timestamp, event_type, success,
                details, ip_address, user_agent, path, created_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10
            )
            """
            
            await connection.execute(
                query,
                event.requestId,
                event.companyId,
                datetime.fromisoformat(event.timestamp.replace('Z', '+00:00')),
                event.event,
                event.success,
                json.dumps(event.details) if event.details else None,
                event.ipAddress,
                event.userAgent,
                event.path,
                datetime.utcnow()
            )
        
        logger.info(f"Successfully stored event {event.event} for request {event.requestId}")
        return {"status": "success", "message": "Event stored successfully"}
        
    except Exception as e:
        logger.error(f"Error storing event: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store event: {str(e)}"
        )