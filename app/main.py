from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import time
import uuid

from app.database import db_health_check, init_database, close_database, db_manager
from app.api.auth import router as auth_router
from app.api.proxy_optimized import router as proxy_optimized_router
from app.api.health import router as health_router
from app.services.auth import get_auth_performance_stats
from app.config import get_settings
from app.utils.logger import get_logger
from app.middleware.error_handling import ErrorHandlingMiddleware, RequestLoggingMiddleware
from app.middleware.security import SecurityHeadersMiddleware, RateLimitingMiddleware
from app.middleware.request_size import RequestSizeLimitMiddleware, MultipartSizeLimitMiddleware
from app.api.openapi_docs import get_custom_openapi_schema
from app.monitoring.metrics import get_metrics, get_metrics_content_type, record_request
from app.monitoring.tracing import tracing_service
from app.monitoring.apm import apm_service, SystemMonitor
import asyncio

settings = get_settings()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events"""
    # Startup
    logger.info("Starting API Lens backend...")
    try:
        # Initialize database
        await init_database()
        logger.info("Database connections initialized")
        
        # Initialize monitoring services
        if settings.TRACING_ENABLED:
            tracing_service.initialize(app)
            logger.info("Tracing service initialized")
        
        if settings.APM_ENABLED:
            apm_service.initialize(app)
            logger.info("APM service initialized")
        
        # Start background tasks
        if settings.METRICS_ENABLED:
            asyncio.create_task(SystemMonitor.monitor_system_health())
            logger.info("System monitoring started")
            
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down API Lens backend...")
    try:
        await close_database()
        logger.info("Database connections closed successfully")
        
        # Shutdown monitoring services
        if tracing_service.initialized:
            tracing_service.shutdown()
            
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

app = FastAPI(
    title="API Lens",
    description="""
    ## API Lens - Enterprise AI API Gateway

    API Lens is a comprehensive AI API gateway that provides multi-company isolation, 
    cost tracking, analytics, and vendor management for AI services.

    ### Features

    * **Multi-Company Isolation**: Complete data isolation with company-specific schemas
    * **Cost Tracking**: Real-time cost calculation and analytics for all AI API calls
    * **Vendor Management**: Support for OpenAI, Anthropic, Google, and more
    * **Analytics & Reporting**: Comprehensive usage analytics and cost optimization
    * **BYOK Support**: Bring Your Own Keys with enterprise-grade encryption
    * **Rate Limiting**: Intelligent rate limiting and quota management
    * **Admin Tools**: Comprehensive admin APIs for system management

    ### Authentication

    API Lens uses API key authentication. Include your API key in the Authorization header:

    ```
    Authorization: Bearer als_your_api_key_here
    ```

    ### Getting Started

    1. **Get an API Key**: Contact your administrator to obtain an API key
    2. **Test Authentication**: Use the `/auth/verify` endpoint to verify your key
    3. **Start Making Requests**: Use the proxy endpoints to route AI API calls
    4. **Monitor Usage**: Check analytics to track usage and costs

    ### Rate Limits

    Rate limits are applied per company and tier:
    - **Free Tier**: 100 requests/minute, 1,000 requests/hour  
    - **Basic Tier**: 500 requests/minute, 10,000 requests/hour
    - **Premium Tier**: 2,000 requests/minute, 50,000 requests/hour
    - **Enterprise Tier**: Custom limits available

    ### Support

    For technical support or questions, contact your API Lens administrator.
    """,
    version=settings.VERSION,
    contact={
        "name": "API Lens Support",
        "email": "support@apilens.dev",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    terms_of_service="https://apilens.dev/terms",
    lifespan=lifespan,
    docs_url=None,  # We'll create custom docs
    redoc_url=None,  # We'll create custom redoc
    openapi_url="/openapi.json"
)

# Add middleware in proper order (outermost first)

# 1. Trusted Host Middleware (prevent host header attacks)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.apilens.dev"] if settings.ENVIRONMENT == "production" else ["*"]
)

# 2. CORS Middleware (handle cross-origin requests)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
    expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]
)

# 3. GZip Middleware (compress responses)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 4. Request Size Limiting - Simple content-length check
@app.middleware("http")
async def request_size_limit_middleware(request: Request, call_next):
    # Check content length header
    content_length = request.headers.get("content-length")
    
    if content_length:
        content_length = int(content_length)
        
        # Check against max request size
        if content_length > settings.MAX_REQUEST_SIZE:
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "type": "request_too_large",
                        "code": 413,
                        "message": f"Request body too large. Max size: {settings.MAX_REQUEST_SIZE} bytes",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
    
    return await call_next(request)

# 5. Security Headers - Using middleware decorator to avoid BaseHTTPMiddleware issues
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    if settings.SECURITY_HEADERS_ENABLED:
        # HSTS
        if settings.SECURITY_HSTS_ENABLED:
            hsts_value = f"max-age={settings.SECURITY_HSTS_MAX_AGE}"
            hsts_value += "; includeSubDomains; preload"
            response.headers["Strict-Transport-Security"] = hsts_value
        
        # Other security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = settings.SECURITY_FRAME_OPTIONS
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Remove server header if it exists
        if "Server" in response.headers:
            del response.headers["Server"]
    
    return response

# 6. Rate Limiting - Simple in-memory rate limiting
from collections import defaultdict
from datetime import datetime, timedelta

rate_limit_store = defaultdict(list)

@app.middleware("http")
async def rate_limiting_middleware(request: Request, call_next):
    if settings.RATE_LIMIT_ENABLED:
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Clean old entries
        current_time = datetime.now()
        rate_limit_store[client_ip] = [
            timestamp for timestamp in rate_limit_store[client_ip] 
            if current_time - timestamp < timedelta(minutes=1)
        ]
        
        # Check rate limit
        if len(rate_limit_store[client_ip]) >= settings.RATE_LIMIT_DEFAULT_PER_MINUTE:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded"},
                headers={
                    "X-RateLimit-Limit": str(settings.RATE_LIMIT_DEFAULT_PER_MINUTE),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int((current_time + timedelta(minutes=1)).timestamp()))
                }
            )
        
        # Record request
        rate_limit_store[client_ip].append(current_time)
    
    response = await call_next(request)
    
    # Add rate limit headers
    if settings.RATE_LIMIT_ENABLED:
        remaining = settings.RATE_LIMIT_DEFAULT_PER_MINUTE - len(rate_limit_store[client_ip])
        response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_DEFAULT_PER_MINUTE)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
    
    return response

# 7. Request Logging and ID assignment
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    # Generate request ID
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    
    # Log request start
    start_time = time.time()
    if settings.LOG_STRUCTURED:
        logger.info(f"Request started: {request.method} {request.url.path}")
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Log request completion
    if settings.LOG_STRUCTURED:
        logger.info(
            f"Request completed: {response.status_code} in {duration*1000:.2f}ms",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2)
            }
        )
    
    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id
    
    return response

# 8. Monitoring Middleware - commented out due to middleware conflict
# @app.middleware("http")
# async def monitoring_middleware(request: Request, call_next):
#     start_time = time.time()
#     
#     # Process request
#     response = await call_next(request)
#     
#     # Record metrics
#     if settings.METRICS_ENABLED:
#         duration = time.time() - start_time
#         record_request(
#             method=request.method,
#             path=request.url.path,
#             status_code=response.status_code,
#             duration=duration,
#             company_id=getattr(request.state, 'company_id', 'unknown')
#         )
#     
#     return response

# 9. Error Handling - Using exception handler instead of middleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import traceback

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": "http_error",
                "code": exc.status_code,
                "message": exc.detail,
                "request_id": getattr(request.state, "request_id", "unknown"),
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "type": "validation_error",
                "code": 422,
                "message": "Validation error",
                "details": exc.errors(),
                "request_id": getattr(request.state, "request_id", "unknown"),
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "type": "internal_error",
                "code": 500,
                "message": "An internal server error occurred",
                "request_id": getattr(request.state, "request_id", "unknown"),
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    )

# Include routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(proxy_optimized_router)

# Metrics endpoint
@app.get("/metrics", tags=["Monitoring"], include_in_schema=False)
async def get_prometheus_metrics(request: Request):
    """Prometheus metrics endpoint"""
    # Check if metrics are enabled
    if not settings.METRICS_ENABLED:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Metrics not enabled"}
        )
    
    # Optional: Add IP whitelist for metrics endpoint
    client_ip = request.client.host if request.client else "unknown"
    allowed_ips = getattr(settings, 'METRICS_ALLOWED_IPS', ['127.0.0.1', '::1'])
    
    if settings.ENVIRONMENT == "production" and client_ip not in allowed_ips:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "Access denied"}
        )
    
    # Return metrics in Prometheus format
    metrics_data = get_metrics()
    return PlainTextResponse(
        content=metrics_data,
        media_type=get_metrics_content_type()
    )

# Legacy health endpoints (keeping for backward compatibility)
@app.get("/health/db", tags=["Health", "Legacy"])
async def database_health_check():
    """Legacy database health check endpoint"""
    health_status = await db_health_check()
    
    if health_status["status"] == "healthy":
        return JSONResponse(content=health_status, status_code=status.HTTP_200_OK)
    elif health_status["status"] == "degraded":
        return JSONResponse(content=health_status, status_code=status.HTTP_200_OK)
    else:
        return JSONResponse(content=health_status, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

@app.get("/health/connections", tags=["Health", "Legacy"])
async def connection_stats():
    """Legacy database connection statistics"""
    if not db_manager._is_initialized:
        return JSONResponse(
            content={"error": "Database not initialized"}, 
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    stats = db_manager.get_connection_stats()
    return {"connection_stats": stats}

@app.get("/health/auth", tags=["Health", "Legacy"])
async def auth_performance_stats():
    """Legacy authentication service performance statistics"""
    stats = get_auth_performance_stats()
    return {"auth_performance": stats}

# ============================================================================
# CUSTOM OPENAPI AND DOCUMENTATION
# ============================================================================

def custom_openapi():
    """Generate custom OpenAPI schema with enhanced security definitions"""
    if app.openapi_schema:
        return app.openapi_schema
    
    # Use our comprehensive OpenAPI documentation
    openapi_schema = get_custom_openapi_schema(app)
    
    # Merge with FastAPI's auto-generated schema
    auto_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        contact=app.contact,
        license_info=app.license_info,
        terms_of_service=app.terms_of_service,
    )
    
    # Merge paths (keep our documented endpoints, add any auto-generated ones)
    for path, methods in auto_schema.get("paths", {}).items():
        if path not in openapi_schema["paths"]:
            openapi_schema["paths"][path] = methods
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "API Key",
            "description": "API Key authentication. Use your API key as the bearer token."
        },
        "AdminAuth": {
            "type": "http", 
            "scheme": "bearer",
            "bearerFormat": "Admin Token",
            "description": "Admin authentication token for administrative endpoints."
        }
    }
    
    # Add global security requirement for company endpoints
    for path_item in openapi_schema["paths"].values():
        for operation in path_item.values():
            if isinstance(operation, dict) and "tags" in operation:
                tags = operation.get("tags", [])
                if any(tag in ["Company Self-Service", "Analytics & Reporting"] for tag in tags):
                    operation["security"] = [{"BearerAuth": []}]
                elif "Admin" in tags:
                    operation["security"] = [{"AdminAuth": []}]
    
    # Add custom examples
    _add_custom_examples(openapi_schema)
    
    # Add servers information
    openapi_schema["servers"] = [
        {
            "url": "https://api.apilens.dev",
            "description": "Production API"
        },
        {
            "url": "https://staging-api.apilens.dev", 
            "description": "Staging API"
        },
        {
            "url": "http://localhost:8000",
            "description": "Local Development"
        }
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

def _add_custom_examples(openapi_schema):
    """Add custom examples to API operations"""
    paths = openapi_schema.get("paths", {})
    
    # Add example for company profile
    if "/companies/me" in paths and "get" in paths["/companies/me"]:
        paths["/companies/me"]["get"]["responses"]["200"]["content"]["application/json"]["example"] = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "name": "Acme Corporation",
            "description": "AI-powered solutions company",
            "contact_email": "admin@acme.com",
            "billing_email": "billing@acme.com", 
            "tier": "premium",
            "schema_name": "company_123e4567_e89b_12d3_a456_426614174000",
            "is_active": True,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-15T10:30:00Z",
            "webhook_url": "https://acme.com/api/webhooks/apilens",
            "current_month_requests": 15420,
            "current_month_cost": 234.56,
            "total_requests": 89234,
            "total_cost": 1456.78,
            "last_request_at": "2024-01-15T14:25:30Z"
        }
    
    # Add example for analytics usage
    if "/companies/me/analytics/usage" in paths and "get" in paths["/companies/me/analytics/usage"]:
        paths["/companies/me/analytics/usage"]["get"]["responses"]["200"]["content"]["application/json"]["example"] = {
            "period": "30d",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-01-31T23:59:59Z",
            "total_requests": 15420,
            "total_tokens": 2456789,
            "unique_models_used": 4,
            "unique_vendors_used": 2,
            "peak_requests_per_hour": 145,
            "average_requests_per_day": 497.4,
            "vendor_breakdown": [
                {
                    "vendor": "openai",
                    "requests": 12340,
                    "tokens": 1987654,
                    "cost": 189.23,
                    "models_used": 3,
                    "avg_cost_per_request": 0.0153,
                    "percentage_of_total": 80.0
                },
                {
                    "vendor": "anthropic", 
                    "requests": 3080,
                    "tokens": 469135,
                    "cost": 45.33,
                    "models_used": 1,
                    "avg_cost_per_request": 0.0147,
                    "percentage_of_total": 20.0
                }
            ]
        }

app.openapi = custom_openapi

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Custom Swagger UI with enhanced styling"""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - API Documentation",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui.css",
        swagger_ui_parameters={
            "deepLinking": True,
            "displayRequestDuration": True,
            "docExpansion": "none",
            "operationsSorter": "alpha",
            "filter": True,
            "tagsSorter": "alpha",
            "tryItOutEnabled": True,
            "displayOperationId": False,
            "defaultModelsExpandDepth": 2,
            "defaultModelExpandDepth": 2,
        }
    )

@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    """Custom ReDoc documentation"""
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - API Reference",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js",
    ) 