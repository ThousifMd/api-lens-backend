"""
Metrics Collection and Monitoring
Integrates with Prometheus for metrics collection and monitoring
"""

from typing import Dict, Any, Optional
from prometheus_client import Counter, Histogram, Gauge, Info, CollectorRegistry
from prometheus_client.core import CollectorRegistry
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import time
from datetime import datetime
from functools import wraps

from ..config import get_settings
from ..utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Create a custom registry for our metrics
registry = CollectorRegistry()

# ============================================================================
# Core Metrics
# ============================================================================

# Request metrics
REQUEST_COUNT = Counter(
    'api_lens_requests_total',
    'Total number of API requests',
    ['method', 'endpoint', 'status_code', 'company_id'],
    registry=registry
)

REQUEST_DURATION = Histogram(
    'api_lens_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=registry
)

# AI API metrics
AI_REQUEST_COUNT = Counter(
    'api_lens_ai_requests_total',
    'Total number of AI API requests proxied',
    ['vendor', 'model', 'company_id', 'success'],
    registry=registry
)

AI_REQUEST_TOKENS = Counter(
    'api_lens_ai_tokens_total',
    'Total tokens processed',
    ['vendor', 'model', 'company_id', 'token_type'],
    registry=registry
)

AI_REQUEST_COST = Counter(
    'api_lens_ai_cost_dollars_total',
    'Total cost in dollars',
    ['vendor', 'model', 'company_id'],
    registry=registry
)

AI_REQUEST_LATENCY = Histogram(
    'api_lens_ai_latency_seconds',
    'AI API request latency',
    ['vendor', 'model'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
    registry=registry
)

# Image generation metrics
IMAGE_GENERATION_COUNT = Counter(
    'api_lens_image_generation_total',
    'Total number of images generated',
    ['vendor', 'model', 'company_id', 'dimensions'],
    registry=registry
)

# Rate limiting metrics
RATE_LIMIT_HITS = Counter(
    'api_lens_rate_limit_hits_total',
    'Number of rate limit hits',
    ['company_id', 'limit_type'],
    registry=registry
)

RATE_LIMIT_EXCEEDED = Counter(
    'api_lens_rate_limit_exceeded_total',
    'Number of requests rejected due to rate limiting',
    ['company_id', 'limit_type'],
    registry=registry
)

# Authentication metrics
AUTH_ATTEMPTS = Counter(
    'api_lens_auth_attempts_total',
    'Total authentication attempts',
    ['result', 'method'],
    registry=registry
)

AUTH_LATENCY = Histogram(
    'api_lens_auth_latency_seconds',
    'Authentication latency',
    ['method'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1],
    registry=registry
)

# Database metrics
DB_QUERY_COUNT = Counter(
    'api_lens_db_queries_total',
    'Total database queries',
    ['operation', 'table'],
    registry=registry
)

DB_QUERY_DURATION = Histogram(
    'api_lens_db_query_duration_seconds',
    'Database query duration',
    ['operation', 'table'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
    registry=registry
)

DB_CONNECTION_POOL = Gauge(
    'api_lens_db_connections',
    'Database connection pool stats',
    ['pool_name', 'state'],
    registry=registry
)

# Cache metrics
CACHE_HITS = Counter(
    'api_lens_cache_hits_total',
    'Cache hit count',
    ['cache_type', 'operation'],
    registry=registry
)

CACHE_MISSES = Counter(
    'api_lens_cache_misses_total',
    'Cache miss count',
    ['cache_type', 'operation'],
    registry=registry
)

CACHE_LATENCY = Histogram(
    'api_lens_cache_latency_seconds',
    'Cache operation latency',
    ['cache_type', 'operation'],
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05],
    registry=registry
)

# System metrics
ACTIVE_REQUESTS = Gauge(
    'api_lens_active_requests',
    'Number of requests currently being processed',
    registry=registry
)

ACTIVE_SESSIONS = Gauge(
    'api_lens_active_sessions',
    'Number of active user sessions',
    ['company_id'],
    registry=registry
)

ERROR_COUNT = Counter(
    'api_lens_errors_total',
    'Total number of errors',
    ['error_type', 'component'],
    registry=registry
)

# Business metrics
COMPANY_USAGE = Gauge(
    'api_lens_company_usage',
    'Company usage metrics',
    ['company_id', 'metric_type'],
    registry=registry
)

# Application info
APP_INFO = Info(
    'api_lens_app',
    'Application information',
    registry=registry
)

# Set application info
APP_INFO.info({
    'version': settings.VERSION,
    'environment': settings.ENVIRONMENT,
    'commit': getattr(settings, 'GIT_COMMIT', 'unknown')
})

# ============================================================================
# Metric Collection Functions
# ============================================================================

def record_request(method: str, endpoint: str, status_code: int, company_id: str, duration: float):
    """Record HTTP request metrics"""
    REQUEST_COUNT.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code),
        company_id=company_id
    ).inc()
    
    REQUEST_DURATION.labels(
        method=method,
        endpoint=endpoint
    ).observe(duration)

def record_ai_request(
    vendor: str,
    model: str,
    company_id: str,
    success: bool,
    input_tokens: int,
    output_tokens: int,
    cost: float,
    latency: float
):
    """Record AI API request metrics"""
    AI_REQUEST_COUNT.labels(
        vendor=vendor,
        model=model,
        company_id=company_id,
        success=str(success)
    ).inc()
    
    AI_REQUEST_TOKENS.labels(
        vendor=vendor,
        model=model,
        company_id=company_id,
        token_type='input'
    ).inc(input_tokens)
    
    AI_REQUEST_TOKENS.labels(
        vendor=vendor,
        model=model,
        company_id=company_id,
        token_type='output'
    ).inc(output_tokens)
    
    AI_REQUEST_COST.labels(
        vendor=vendor,
        model=model,
        company_id=company_id
    ).inc(cost)
    
    AI_REQUEST_LATENCY.labels(
        vendor=vendor,
        model=model
    ).observe(latency / 1000)  # Convert ms to seconds

def record_image_generation(
    vendor: str,
    model: str,
    company_id: str,
    count: int,
    dimensions: str
):
    """Record image generation metrics"""
    IMAGE_GENERATION_COUNT.labels(
        vendor=vendor,
        model=model,
        company_id=company_id,
        dimensions=dimensions
    ).inc(count)

def record_rate_limit(company_id: str, limit_type: str, exceeded: bool = False):
    """Record rate limiting metrics"""
    RATE_LIMIT_HITS.labels(
        company_id=company_id,
        limit_type=limit_type
    ).inc()
    
    if exceeded:
        RATE_LIMIT_EXCEEDED.labels(
            company_id=company_id,
            limit_type=limit_type
        ).inc()

def record_auth_attempt(result: str, method: str = 'api_key', latency: float = 0):
    """Record authentication attempt metrics"""
    AUTH_ATTEMPTS.labels(
        result=result,
        method=method
    ).inc()
    
    if latency > 0:
        AUTH_LATENCY.labels(
            method=method
        ).observe(latency)

def record_db_query(operation: str, table: str, duration: float):
    """Record database query metrics"""
    DB_QUERY_COUNT.labels(
        operation=operation,
        table=table
    ).inc()
    
    DB_QUERY_DURATION.labels(
        operation=operation,
        table=table
    ).observe(duration)

def update_db_pool_stats(pool_name: str, active: int, idle: int, total: int):
    """Update database connection pool metrics"""
    DB_CONNECTION_POOL.labels(
        pool_name=pool_name,
        state='active'
    ).set(active)
    
    DB_CONNECTION_POOL.labels(
        pool_name=pool_name,
        state='idle'
    ).set(idle)
    
    DB_CONNECTION_POOL.labels(
        pool_name=pool_name,
        state='total'
    ).set(total)

def record_cache_operation(
    cache_type: str,
    operation: str,
    hit: bool,
    latency: float
):
    """Record cache operation metrics"""
    if hit:
        CACHE_HITS.labels(
            cache_type=cache_type,
            operation=operation
        ).inc()
    else:
        CACHE_MISSES.labels(
            cache_type=cache_type,
            operation=operation
        ).inc()
    
    CACHE_LATENCY.labels(
        cache_type=cache_type,
        operation=operation
    ).observe(latency)

def record_error(error_type: str, component: str):
    """Record error metrics"""
    ERROR_COUNT.labels(
        error_type=error_type,
        component=component
    ).inc()

def update_active_requests(delta: int):
    """Update active requests gauge"""
    if delta > 0:
        ACTIVE_REQUESTS.inc(delta)
    else:
        ACTIVE_REQUESTS.dec(abs(delta))

def update_active_sessions(company_id: str, count: int):
    """Update active sessions gauge"""
    ACTIVE_SESSIONS.labels(
        company_id=company_id
    ).set(count)

def update_company_usage(company_id: str, metric_type: str, value: float):
    """Update company usage metrics"""
    COMPANY_USAGE.labels(
        company_id=company_id,
        metric_type=metric_type
    ).set(value)

# ============================================================================
# Decorators for Automatic Metric Collection
# ============================================================================

def track_request_metrics(func):
    """Decorator to automatically track request metrics"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        update_active_requests(1)
        
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            update_active_requests(-1)
            duration = time.time() - start_time
            
            # Extract request info if available
            request = kwargs.get('request')
            if request:
                method = request.method
                endpoint = request.url.path
                status_code = getattr(result, 'status_code', 200)
                company_id = getattr(request.state, 'company_id', 'unknown')
                
                record_request(method, endpoint, status_code, company_id, duration)
    
    return wrapper

def track_db_metrics(operation: str, table: str):
    """Decorator to track database operation metrics"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                record_db_query(operation, table, duration)
        
        return wrapper
    return decorator

def track_cache_metrics(cache_type: str, operation: str):
    """Decorator to track cache operation metrics"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Determine if it was a hit based on result
            hit = result is not None
            record_cache_operation(cache_type, operation, hit, duration)
            
            return result
        
        return wrapper
    return decorator

# ============================================================================
# Metrics Export Functions
# ============================================================================

def get_metrics() -> bytes:
    """Get metrics in Prometheus format"""
    return generate_latest(registry)

def get_metrics_content_type() -> str:
    """Get the content type for Prometheus metrics"""
    return CONTENT_TYPE_LATEST

async def collect_system_metrics():
    """Collect system-level metrics (called periodically)"""
    try:
        # This would be called by a background task to update gauges
        # For example, collecting active sessions, database pool stats, etc.
        pass
    except Exception as e:
        logger.error(f"Error collecting system metrics: {e}")
        record_error('system_metrics_collection', 'metrics')