from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.staticfiles import StaticFiles

from app.database import db_health_check, init_database, close_database, db_manager
from app.api.auth import router as auth_router
from app.api.proxy import router as proxy_router
from app.api.admin import admin_router
from app.api.company import company_router
from app.api.analytics import analytics_router
from app.services.auth import get_auth_performance_stats
from app.config import get_settings
from app.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events"""
    # Startup
    logger.info("Starting API Lens backend...")
    try:
        await init_database()
        logger.info("Database connections initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down API Lens backend...")
    try:
        await close_database()
        logger.info("Database connections closed successfully")
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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(proxy_router)
app.include_router(admin_router)
app.include_router(company_router)
app.include_router(analytics_router)

@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy", 
        "version": settings.VERSION,
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT
    }

@app.get("/health/db", tags=["Health"])
async def database_health_check():
    """Comprehensive database health check endpoint"""
    health_status = await db_health_check()
    
    if health_status["status"] == "healthy":
        return JSONResponse(content=health_status, status_code=status.HTTP_200_OK)
    elif health_status["status"] == "degraded":
        return JSONResponse(content=health_status, status_code=status.HTTP_200_OK)
    else:
        return JSONResponse(content=health_status, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

@app.get("/health/connections", tags=["Health"])
async def connection_stats():
    """Get database connection statistics"""
    if not db_manager._is_initialized:
        return JSONResponse(
            content={"error": "Database not initialized"}, 
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    stats = db_manager.get_connection_stats()
    return {"connection_stats": stats}

@app.get("/health/auth", tags=["Health"])
async def auth_performance_stats():
    """Get authentication service performance statistics"""
    stats = get_auth_performance_stats()
    return {"auth_performance": stats}

# ============================================================================
# CUSTOM OPENAPI AND DOCUMENTATION
# ============================================================================

def custom_openapi():
    """Generate custom OpenAPI schema with enhanced security definitions"""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        contact=app.contact,
        license_info=app.license_info,
        terms_of_service=app.terms_of_service,
    )
    
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