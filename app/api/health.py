"""
Enhanced Health Check Endpoints
Provides comprehensive system health monitoring and diagnostics
"""
import asyncio
import time
import platform
import psutil
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, status, HTTPException, Depends
from pydantic import BaseModel

from ..database import DatabaseUtils
from ..services.cache import cache_health_check, get_cache_stats
from ..config import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/health", tags=["Health"])

class HealthStatus(BaseModel):
    """Health status response model"""
    status: str  # healthy, degraded, unhealthy
    version: str
    timestamp: str
    uptime: Optional[str] = None
    request_id: Optional[str] = None

class DetailedHealthStatus(BaseModel):
    """Detailed health status response model"""
    overall_status: str
    version: str
    timestamp: str
    uptime: str
    services: Dict[str, Any]
    system: Dict[str, Any]
    metrics: Dict[str, Any]
    request_id: Optional[str] = None

class ServiceHealth(BaseModel):
    """Individual service health model"""
    status: str
    response_time_ms: Optional[float] = None
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

# Track application start time
app_start_time = time.time()

async def check_database_health() -> ServiceHealth:
    """Check database connectivity and performance"""
    start_time = time.time()
    
    try:
        # Test basic connectivity
        result = await DatabaseUtils.execute_query(
            "SELECT 1 as health_check, NOW() as db_time", 
            [], 
            fetch_all=False
        )
        
        if result and result.get('health_check') == 1:
            response_time = (time.time() - start_time) * 1000
            
            # Get additional database info
            db_info = await get_database_info()
            
            return ServiceHealth(
                status="healthy",
                response_time_ms=round(response_time, 2),
                message="Database connection successful",
                details=db_info
            )
        else:
            return ServiceHealth(
                status="unhealthy",
                message="Database query returned unexpected result"
            )
            
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return ServiceHealth(
            status="unhealthy",
            response_time_ms=round(response_time, 2),
            message=f"Database connection failed: {str(e)}"
        )

async def check_cache_health() -> ServiceHealth:
    """Check Redis cache connectivity and performance"""
    start_time = time.time()
    
    try:
        cache_healthy = await cache_health_check()
        response_time = (time.time() - start_time) * 1000
        
        if cache_healthy:
            cache_stats = await get_cache_stats()
            return ServiceHealth(
                status="healthy",
                response_time_ms=round(response_time, 2),
                message="Cache connection successful",
                details=cache_stats.get('health', {}) if isinstance(cache_stats, dict) else {}
            )
        else:
            return ServiceHealth(
                status="unhealthy",
                response_time_ms=round(response_time, 2),
                message="Cache health check failed"
            )
            
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return ServiceHealth(
            status="unhealthy",
            response_time_ms=round(response_time, 2),
            message=f"Cache connection failed: {str(e)}"
        )

async def check_external_services() -> Dict[str, ServiceHealth]:
    """Check external service connectivity"""
    services = {}
    
    # Check OpenAI API (if configured)
    if settings.OPENAI_API_KEY:
        services['openai'] = await check_openai_health()
    
    # Check Anthropic API (if configured)
    if settings.ANTHROPIC_API_KEY:
        services['anthropic'] = await check_anthropic_health()
    
    # Check Google/Gemini API (if configured)
    if settings.GEMINI_API_KEY:
        services['google'] = await check_google_health()
    
    return services

async def check_openai_health() -> ServiceHealth:
    """Check OpenAI API connectivity"""
    start_time = time.time()
    
    try:
        import httpx
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
            )
            
        response_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            return ServiceHealth(
                status="healthy",
                response_time_ms=round(response_time, 2),
                message="OpenAI API accessible"
            )
        else:
            return ServiceHealth(
                status="degraded",
                response_time_ms=round(response_time, 2),
                message=f"OpenAI API returned status {response.status_code}"
            )
            
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return ServiceHealth(
            status="unhealthy",
            response_time_ms=round(response_time, 2),
            message=f"OpenAI API check failed: {str(e)}"
        )

async def check_anthropic_health() -> ServiceHealth:
    """Check Anthropic API connectivity"""
    start_time = time.time()
    
    try:
        import httpx
        
        # Simple connectivity check - Anthropic doesn't have a public models endpoint
        # so we'll just check if the API is reachable
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.options("https://api.anthropic.com")
            
        response_time = (time.time() - start_time) * 1000
        
        return ServiceHealth(
            status="healthy",
            response_time_ms=round(response_time, 2),
            message="Anthropic API reachable"
        )
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return ServiceHealth(
            status="unhealthy",
            response_time_ms=round(response_time, 2),
            message=f"Anthropic API check failed: {str(e)}"
        )

async def check_google_health() -> ServiceHealth:
    """Check Google/Gemini API connectivity"""
    start_time = time.time()
    
    try:
        import httpx
        
        # Check Google AI API
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://generativelanguage.googleapis.com/v1/models",
                params={"key": settings.GEMINI_API_KEY}
            )
            
        response_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            return ServiceHealth(
                status="healthy",
                response_time_ms=round(response_time, 2),
                message="Google AI API accessible"
            )
        else:
            return ServiceHealth(
                status="degraded",
                response_time_ms=round(response_time, 2),
                message=f"Google AI API returned status {response.status_code}"
            )
            
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return ServiceHealth(
            status="unhealthy",
            response_time_ms=round(response_time, 2),
            message=f"Google AI API check failed: {str(e)}"
        )

async def get_database_info() -> Dict[str, Any]:
    """Get detailed database information"""
    try:
        # Get database version
        version_result = await DatabaseUtils.execute_query(
            "SELECT version() as version", [], fetch_all=False
        )
        
        # Get database size
        size_result = await DatabaseUtils.execute_query(
            "SELECT pg_size_pretty(pg_database_size(current_database())) as size",
            [], 
            fetch_all=False
        )
        
        # Get connection count
        connections_result = await DatabaseUtils.execute_query(
            "SELECT count(*) as connections FROM pg_stat_activity",
            [],
            fetch_all=False
        )
        
        return {
            "version": version_result.get('version', 'Unknown') if version_result else 'Unknown',
            "size": size_result.get('size', 'Unknown') if size_result else 'Unknown',
            "active_connections": connections_result.get('connections', 0) if connections_result else 0
        }
        
    except Exception as e:
        return {"error": str(e)}

def get_system_info() -> Dict[str, Any]:
    """Get system resource information"""
    try:
        # CPU information
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # Memory information
        memory = psutil.virtual_memory()
        memory_info = {
            "total_gb": round(memory.total / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "used_percent": memory.percent
        }
        
        # Disk information
        disk = psutil.disk_usage('/')
        disk_info = {
            "total_gb": round(disk.total / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "used_percent": round((disk.used / disk.total) * 100, 2)
        }
        
        # Process information
        process = psutil.Process()
        process_info = {
            "pid": process.pid,
            "memory_mb": round(process.memory_info().rss / (1024**2), 2),
            "cpu_percent": process.cpu_percent(),
            "threads": process.num_threads(),
            "open_files": len(process.open_files()) if hasattr(process, 'open_files') else 0
        }
        
        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu": {
                "count": cpu_count,
                "usage_percent": cpu_percent
            },
            "memory": memory_info,
            "disk": disk_info,
            "process": process_info
        }
        
    except Exception as e:
        return {"error": str(e)}

def get_application_metrics() -> Dict[str, Any]:
    """Get application-specific metrics"""
    uptime_seconds = time.time() - app_start_time
    uptime_str = format_uptime(uptime_seconds)
    
    return {
        "uptime_seconds": round(uptime_seconds, 2),
        "uptime_formatted": uptime_str,
        "start_time": datetime.fromtimestamp(app_start_time, tz=timezone.utc).isoformat(),
        "environment": settings.ENVIRONMENT,
        "debug_mode": settings.DEBUG,
        "version": settings.APP_VERSION
    }

def format_uptime(seconds: float) -> str:
    """Format uptime in human-readable format"""
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m {secs}s"
    elif hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"

def determine_overall_status(services: Dict[str, ServiceHealth]) -> str:
    """Determine overall system status based on individual services"""
    unhealthy_count = 0
    degraded_count = 0
    
    for service in services.values():
        if isinstance(service, ServiceHealth):
            if service.status == "unhealthy":
                unhealthy_count += 1
            elif service.status == "degraded":
                degraded_count += 1
        elif isinstance(service, dict):
            # Handle nested services (like external_services)
            for nested_service in service.values():
                if isinstance(nested_service, ServiceHealth):
                    if nested_service.status == "unhealthy":
                        unhealthy_count += 1
                    elif nested_service.status == "degraded":
                        degraded_count += 1
    
    # Core services (database, cache) are critical
    core_services = ['database', 'cache']
    core_unhealthy = any(
        services.get(service, ServiceHealth(status="unknown")).status == "unhealthy" 
        for service in core_services
    )
    
    if core_unhealthy or unhealthy_count > 2:
        return "unhealthy"
    elif degraded_count > 0 or unhealthy_count > 0:
        return "degraded"
    else:
        return "healthy"

@router.get("/", response_model=HealthStatus)
async def basic_health_check():
    """
    Basic health check endpoint - fast and lightweight
    Returns simple status for load balancers
    """
    try:
        # Quick database check
        result = await DatabaseUtils.execute_query("SELECT 1", [], fetch_all=False)
        
        if result:
            return HealthStatus(
                status="healthy",
                version=settings.APP_VERSION,
                timestamp=datetime.utcnow().isoformat(),
                uptime=format_uptime(time.time() - app_start_time)
            )
        else:
            return HealthStatus(
                status="unhealthy",
                version=settings.APP_VERSION,
                timestamp=datetime.utcnow().isoformat()
            )
            
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthStatus(
            status="unhealthy",
            version=settings.APP_VERSION,
            timestamp=datetime.utcnow().isoformat()
        )

@router.get("/detailed", response_model=DetailedHealthStatus)
async def detailed_health_check():
    """
    Comprehensive health check with detailed system information
    Includes all services, system metrics, and diagnostics
    """
    try:
        # Run all health checks concurrently
        database_task = check_database_health()
        cache_task = check_cache_health()
        external_task = check_external_services()
        
        database_health, cache_health, external_services = await asyncio.gather(
            database_task, cache_task, external_task,
            return_exceptions=True
        )
        
        # Handle exceptions from async tasks
        if isinstance(database_health, Exception):
            database_health = ServiceHealth(
                status="unhealthy",
                message=f"Database check failed: {str(database_health)}"
            )
        
        if isinstance(cache_health, Exception):
            cache_health = ServiceHealth(
                status="unhealthy", 
                message=f"Cache check failed: {str(cache_health)}"
            )
        
        if isinstance(external_services, Exception):
            external_services = {}
        
        # Compile all service statuses
        services = {
            "database": database_health,
            "cache": cache_health,
            "external_services": external_services
        }
        
        # Get system information
        system_info = get_system_info()
        metrics = get_application_metrics()
        
        # Determine overall status
        overall_status = determine_overall_status(services)
        
        return DetailedHealthStatus(
            overall_status=overall_status,
            version=settings.APP_VERSION,
            timestamp=datetime.utcnow().isoformat(),
            uptime=format_uptime(time.time() - app_start_time),
            services=services,
            system=system_info,
            metrics=metrics
        )
        
    except Exception as e:
        logger.error(f"Detailed health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}"
        )

@router.get("/liveness")
async def liveness_probe():
    """
    Kubernetes liveness probe endpoint
    Simple check to ensure the application is alive
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "pid": psutil.Process().pid
    }

@router.get("/readiness")
async def readiness_probe():
    """
    Kubernetes readiness probe endpoint
    Checks if the application is ready to receive traffic
    """
    try:
        # Check critical dependencies
        db_result = await DatabaseUtils.execute_query("SELECT 1", [], fetch_all=False)
        cache_healthy = await cache_health_check()
        
        if db_result and cache_healthy:
            return {
                "status": "ready",
                "timestamp": datetime.utcnow().isoformat(),
                "services": {
                    "database": "healthy",
                    "cache": "healthy"
                }
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not ready"
            )
            
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready"
        )