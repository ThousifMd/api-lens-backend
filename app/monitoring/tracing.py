"""
Distributed Tracing with OpenTelemetry
Provides distributed tracing capabilities for monitoring request flow
"""

from typing import Dict, Any, Optional, Callable
from contextlib import contextmanager
import json
from functools import wraps

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.zipkin.json import ZipkinExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Status, StatusCode
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from ..config import get_settings
from ..utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Global tracer instance
tracer: Optional[trace.Tracer] = None

class TracingService:
    """Service for managing distributed tracing"""
    
    def __init__(self):
        self.tracer_provider: Optional[TracerProvider] = None
        self.tracer: Optional[trace.Tracer] = None
        self.initialized = False
        
    def initialize(self, app=None):
        """Initialize tracing with configured exporter"""
        try:
            # Create resource with service information
            resource = Resource.create({
                SERVICE_NAME: "api-lens-backend",
                SERVICE_VERSION: settings.VERSION,
                "service.environment": settings.ENVIRONMENT,
                "service.namespace": "api-lens",
                "deployment.environment": settings.ENVIRONMENT,
            })
            
            # Create tracer provider
            self.tracer_provider = TracerProvider(resource=resource)
            
            # Configure exporter based on settings
            exporter = self._create_exporter()
            if exporter:
                # Add span processor with the exporter
                span_processor = BatchSpanProcessor(exporter)
                self.tracer_provider.add_span_processor(span_processor)
            
            # Add console exporter in development
            if settings.ENVIRONMENT == "development":
                console_processor = BatchSpanProcessor(ConsoleSpanExporter())
                self.tracer_provider.add_span_processor(console_processor)
            
            # Set as global tracer provider
            trace.set_tracer_provider(self.tracer_provider)
            
            # Set propagator for distributed tracing
            set_global_textmap(TraceContextTextMapPropagator())
            
            # Get tracer
            self.tracer = trace.get_tracer(__name__, settings.VERSION)
            
            # Set global tracer reference
            global tracer
            tracer = self.tracer
            
            # Auto-instrument libraries
            self._instrument_libraries(app)
            
            self.initialized = True
            logger.info("Tracing service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize tracing: {e}")
            # Continue without tracing rather than failing startup
            self.initialized = False
    
    def _create_exporter(self):
        """Create the appropriate span exporter based on configuration"""
        exporter_type = getattr(settings, 'TRACING_EXPORTER', 'none').lower()
        
        if exporter_type == 'none':
            return None
            
        elif exporter_type == 'otlp':
            # OpenTelemetry Protocol exporter (for Tempo, etc.)
            endpoint = getattr(settings, 'OTLP_ENDPOINT', 'localhost:4317')
            headers = getattr(settings, 'OTLP_HEADERS', {})
            
            return OTLPSpanExporter(
                endpoint=endpoint,
                headers=headers,
                insecure=settings.ENVIRONMENT != 'production'
            )
            
        elif exporter_type == 'jaeger':
            # Jaeger exporter
            agent_host = getattr(settings, 'JAEGER_AGENT_HOST', 'localhost')
            agent_port = getattr(settings, 'JAEGER_AGENT_PORT', 6831)
            
            return JaegerExporter(
                agent_host_name=agent_host,
                agent_port=agent_port,
                collector_endpoint=getattr(settings, 'JAEGER_COLLECTOR_ENDPOINT', None)
            )
            
        elif exporter_type == 'zipkin':
            # Zipkin exporter
            endpoint = getattr(settings, 'ZIPKIN_ENDPOINT', 'http://localhost:9411/api/v2/spans')
            
            return ZipkinExporter(endpoint=endpoint)
            
        else:
            logger.warning(f"Unknown tracing exporter type: {exporter_type}")
            return None
    
    def _instrument_libraries(self, app=None):
        """Auto-instrument supported libraries"""
        try:
            # Instrument FastAPI
            if app:
                FastAPIInstrumentor.instrument_app(
                    app,
                    excluded_urls="/health.*,/metrics.*",
                    tracer_provider=self.tracer_provider
                )
            
            # Instrument database clients
            AsyncPGInstrumentor().instrument(tracer_provider=self.tracer_provider)
            
            
            # Instrument HTTP client
            HTTPXClientInstrumentor().instrument(tracer_provider=self.tracer_provider)
            
            logger.info("Auto-instrumentation completed")
            
        except Exception as e:
            logger.error(f"Error during auto-instrumentation: {e}")
    
    def shutdown(self):
        """Shutdown tracing and flush remaining spans"""
        if self.tracer_provider and self.initialized:
            self.tracer_provider.shutdown()
            logger.info("Tracing service shut down")

# Global tracing service instance
tracing_service = TracingService()

# ============================================================================
# Tracing Context Managers and Decorators
# ============================================================================

@contextmanager
def trace_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL
):
    """
    Context manager for creating a traced span
    
    Usage:
        with trace_span("database.query", {"db.table": "users"}):
            # Your code here
            pass
    """
    if not tracer:
        yield None
        return
        
    with tracer.start_as_current_span(name, kind=kind) as span:
        if span and attributes:
            for key, value in attributes.items():
                span.set_attribute(key, str(value))
        
        try:
            yield span
        except Exception as e:
            if span:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
            raise

def trace_async(
    name: Optional[str] = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None
):
    """
    Decorator for tracing async functions
    
    Usage:
        @trace_async("process_request", attributes={"request.type": "api"})
        async def process_request(request):
            # Your code here
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            span_name = name or f"{func.__module__}.{func.__name__}"
            
            with trace_span(span_name, attributes, kind) as span:
                # Add function arguments as span attributes
                if span and args:
                    span.set_attribute("function.args_count", len(args))
                if span and kwargs:
                    span.set_attribute("function.kwargs_count", len(kwargs))
                
                result = await func(*args, **kwargs)
                
                # Add result info if available
                if span and result is not None:
                    if isinstance(result, dict):
                        span.set_attribute("result.type", "dict")
                        span.set_attribute("result.keys", ",".join(result.keys()))
                    elif isinstance(result, (list, tuple)):
                        span.set_attribute("result.type", type(result).__name__)
                        span.set_attribute("result.length", len(result))
                    else:
                        span.set_attribute("result.type", type(result).__name__)
                
                return result
        
        return wrapper
    return decorator

def trace_sync(
    name: Optional[str] = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None
):
    """
    Decorator for tracing sync functions
    
    Usage:
        @trace_sync("calculate_cost", attributes={"calculation.type": "ai_tokens"})
        def calculate_cost(tokens):
            # Your code here
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            span_name = name or f"{func.__module__}.{func.__name__}"
            
            with trace_span(span_name, attributes, kind) as span:
                # Add function arguments as span attributes
                if span and args:
                    span.set_attribute("function.args_count", len(args))
                if span and kwargs:
                    span.set_attribute("function.kwargs_count", len(kwargs))
                
                result = func(*args, **kwargs)
                
                # Add result info if available
                if span and result is not None:
                    if isinstance(result, dict):
                        span.set_attribute("result.type", "dict")
                        span.set_attribute("result.keys", ",".join(result.keys()))
                    elif isinstance(result, (list, tuple)):
                        span.set_attribute("result.type", type(result).__name__)
                        span.set_attribute("result.length", len(result))
                    else:
                        span.set_attribute("result.type", type(result).__name__)
                
                return result
        
        return wrapper
    return decorator

# ============================================================================
# Specialized Tracing Functions
# ============================================================================

def trace_ai_request(
    vendor: str,
    model: str,
    company_id: str,
    request_id: str
) -> Optional[trace.Span]:
    """Create a span for AI API request"""
    if not tracer:
        return None
        
    return tracer.start_span(
        "ai_api.request",
        kind=trace.SpanKind.CLIENT,
        attributes={
            "ai.vendor": vendor,
            "ai.model": model,
            "ai.company_id": company_id,
            "ai.request_id": request_id,
            "ai.service": f"{vendor}.{model}"
        }
    )

def trace_db_operation(
    operation: str,
    table: str,
    query_id: Optional[str] = None
) -> Optional[trace.Span]:
    """Create a span for database operation"""
    if not tracer:
        return None
        
    return tracer.start_span(
        f"db.{operation}",
        kind=trace.SpanKind.CLIENT,
        attributes={
            "db.operation": operation,
            "db.table": table,
            "db.system": "postgresql",
            "db.query_id": query_id or "unknown"
        }
    )

def trace_cache_operation(
    operation: str,
    cache_type: str,
    key: str
) -> Optional[trace.Span]:
    """Create a span for cache operation"""
    if not tracer:
        return None
        
    return tracer.start_span(
        f"cache.{operation}",
        kind=trace.SpanKind.CLIENT,
        attributes={
            "cache.operation": operation,
            "cache.type": cache_type,
            "cache.key": key,
            "cache.system": "redis"
        }
    )

def add_span_event(
    name: str,
    attributes: Optional[Dict[str, Any]] = None
):
    """Add an event to the current span"""
    span = trace.get_current_span()
    if span and span.is_recording():
        span.add_event(name, attributes=attributes or {})

def set_span_attribute(key: str, value: Any):
    """Set an attribute on the current span"""
    span = trace.get_current_span()
    if span and span.is_recording():
        span.set_attribute(key, str(value))

def record_span_exception(exception: Exception):
    """Record an exception in the current span"""
    span = trace.get_current_span()
    if span and span.is_recording():
        span.record_exception(exception)
        span.set_status(Status(StatusCode.ERROR, str(exception)))

# ============================================================================
# Trace Context Propagation
# ============================================================================

def inject_trace_context(headers: Dict[str, str]) -> Dict[str, str]:
    """Inject trace context into outgoing request headers"""
    if not tracer:
        return headers
        
    from opentelemetry.propagate import inject
    inject(headers)
    return headers

def extract_trace_context(headers: Dict[str, str]):
    """Extract trace context from incoming request headers"""
    if not tracer:
        return None
        
    from opentelemetry.propagate import extract
    return extract(headers)