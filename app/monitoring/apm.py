"""
Application Performance Monitoring (APM)
Integrates with APM services like New Relic, Datadog, or Elastic APM
"""

import time
import sys
import os
from typing import Dict, Any, Optional, Callable
from functools import wraps
from contextlib import contextmanager
import asyncio
import psutil
import platform

from ..config import get_settings
from ..utils.logger import get_logger
from .metrics import (
    record_request, record_ai_request, record_error,
    update_active_requests, update_db_pool_stats
)
from .tracing import trace_span, set_span_attribute

settings = get_settings()
logger = get_logger(__name__)

class APMService:
    """Unified APM service supporting multiple providers"""
    
    def __init__(self):
        self.provider = getattr(settings, 'APM_PROVIDER', 'none').lower()
        self.initialized = False
        self.agent = None
        
    def initialize(self, app=None):
        """Initialize APM based on configured provider"""
        try:
            if self.provider == 'none':
                logger.info("APM disabled")
                return
                
            elif self.provider == 'newrelic':
                self._init_newrelic()
                
            elif self.provider == 'datadog':
                self._init_datadog(app)
                
            elif self.provider == 'elastic':
                self._init_elastic(app)
                
            elif self.provider == 'sentry':
                self._init_sentry()
                
            else:
                logger.warning(f"Unknown APM provider: {self.provider}")
                return
                
            self.initialized = True
            logger.info(f"APM initialized with provider: {self.provider}")
            
        except Exception as e:
            logger.error(f"Failed to initialize APM: {e}")
            # Continue without APM rather than failing startup
            self.initialized = False
    
    def _init_newrelic(self):
        """Initialize New Relic APM"""
        try:
            import newrelic.agent
            
            # Configure New Relic
            config_file = getattr(settings, 'NEWRELIC_CONFIG_FILE', None)
            environment = settings.ENVIRONMENT
            
            if config_file and os.path.exists(config_file):
                newrelic.agent.initialize(config_file, environment)
            else:
                # Configure programmatically
                newrelic_settings = newrelic.agent.global_settings()
                newrelic_settings.app_name = f"API Lens Backend [{environment}]"
                newrelic_settings.license_key = getattr(settings, 'NEWRELIC_LICENSE_KEY', '')
                newrelic_settings.distributed_tracing.enabled = True
                newrelic_settings.application_logging.enabled = True
                newrelic_settings.application_logging.forwarding.enabled = True
                
                newrelic.agent.initialize()
            
            self.agent = newrelic.agent
            logger.info("New Relic APM initialized")
            
        except ImportError:
            logger.error("New Relic package not installed. Run: pip install newrelic")
        except Exception as e:
            logger.error(f"Failed to initialize New Relic: {e}")
    
    def _init_datadog(self, app=None):
        """Initialize Datadog APM"""
        try:
            from ddtrace import patch_all, config
            from ddtrace.contrib.asgi import TraceMiddleware
            
            # Configure Datadog
            config.env = settings.ENVIRONMENT
            config.service = "api-lens-backend"
            config.version = settings.VERSION
            
            # Set additional tags
            config.tags = {
                "environment": settings.ENVIRONMENT,
                "version": settings.VERSION,
                "service": "api-lens-backend"
            }
            
            # Patch all supported libraries
            patch_all(
                fastapi=True,
                asyncpg=True,
                redis=True,
                httpx=True
            )
            
            # Add trace middleware to FastAPI app
            if app:
                app.add_middleware(
                    TraceMiddleware,
                    service="api-lens-backend",
                    tags={
                        "env": settings.ENVIRONMENT,
                        "version": settings.VERSION
                    }
                )
            
            logger.info("Datadog APM initialized")
            
        except ImportError:
            logger.error("Datadog package not installed. Run: pip install ddtrace")
        except Exception as e:
            logger.error(f"Failed to initialize Datadog: {e}")
    
    def _init_elastic(self, app=None):
        """Initialize Elastic APM"""
        try:
            from elasticapm import Client
            from elasticapm.contrib.starlette import make_apm_client, ElasticAPM
            
            # Create APM client
            apm_config = {
                'SERVICE_NAME': 'api-lens-backend',
                'SERVER_URL': getattr(settings, 'ELASTIC_APM_SERVER_URL', 'http://localhost:8200'),
                'SECRET_TOKEN': getattr(settings, 'ELASTIC_APM_SECRET_TOKEN', ''),
                'ENVIRONMENT': settings.ENVIRONMENT,
                'SERVICE_VERSION': settings.VERSION,
                'CAPTURE_HEADERS': True,
                'CAPTURE_BODY': 'all',
                'TRANSACTION_SAMPLE_RATE': getattr(settings, 'ELASTIC_APM_SAMPLE_RATE', 0.1)
            }
            
            # Add to FastAPI app
            if app:
                apm = make_apm_client(apm_config)
                app.add_middleware(ElasticAPM, client=apm)
                self.agent = apm
            else:
                self.agent = Client(apm_config)
            
            logger.info("Elastic APM initialized")
            
        except ImportError:
            logger.error("Elastic APM package not installed. Run: pip install elastic-apm")
        except Exception as e:
            logger.error(f"Failed to initialize Elastic APM: {e}")
    
    def _init_sentry(self):
        """Initialize Sentry for error tracking and performance monitoring"""
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
            from sentry_sdk.integrations.redis import RedisIntegration
            from sentry_sdk.integrations.asyncio import AsyncioIntegration
            
            sentry_sdk.init(
                dsn=getattr(settings, 'SENTRY_DSN', ''),
                environment=settings.ENVIRONMENT,
                release=f"api-lens-backend@{settings.VERSION}",
                integrations=[
                    FastApiIntegration(transaction_style="endpoint"),
                    SqlalchemyIntegration(),
                    RedisIntegration(),
                    AsyncioIntegration()
                ],
                traces_sample_rate=getattr(settings, 'SENTRY_TRACES_SAMPLE_RATE', 0.1),
                profiles_sample_rate=getattr(settings, 'SENTRY_PROFILES_SAMPLE_RATE', 0.1),
                attach_stacktrace=True,
                send_default_pii=False,
                before_send=self._sentry_before_send
            )
            
            self.agent = sentry_sdk
            logger.info("Sentry APM initialized")
            
        except ImportError:
            logger.error("Sentry package not installed. Run: pip install sentry-sdk")
        except Exception as e:
            logger.error(f"Failed to initialize Sentry: {e}")
    
    def _sentry_before_send(self, event, hint):
        """Filter sensitive data before sending to Sentry"""
        # Remove sensitive headers
        if 'request' in event and 'headers' in event['request']:
            sensitive_headers = ['authorization', 'x-api-key', 'cookie']
            for header in sensitive_headers:
                if header in event['request']['headers']:
                    event['request']['headers'][header] = '[FILTERED]'
        
        # Remove sensitive query params
        if 'request' in event and 'query_string' in event['request']:
            # Filter API keys from query strings
            import re
            event['request']['query_string'] = re.sub(
                r'(api_key|token|secret)=[^&]+',
                r'\1=[FILTERED]',
                event['request']['query_string']
            )
        
        return event
    
    def capture_exception(self, exception: Exception, context: Optional[Dict[str, Any]] = None):
        """Capture exception in APM"""
        if not self.initialized:
            return
            
        try:
            if self.provider == 'newrelic' and self.agent:
                self.agent.notice_error(attributes=context)
                
            elif self.provider == 'datadog':
                from ddtrace import tracer
                span = tracer.current_span()
                if span:
                    span.set_exc_info(sys.exc_info())
                    if context:
                        for key, value in context.items():
                            span.set_tag(key, value)
                            
            elif self.provider == 'elastic' and self.agent:
                self.agent.capture_exception(exc_info=sys.exc_info(), context=context)
                
            elif self.provider == 'sentry' and self.agent:
                with self.agent.configure_scope() as scope:
                    if context:
                        for key, value in context.items():
                            scope.set_tag(key, value)
                    self.agent.capture_exception(exception)
                    
        except Exception as e:
            logger.error(f"Failed to capture exception in APM: {e}")
    
    def create_transaction(self, name: str, transaction_type: str = 'request'):
        """Create APM transaction context"""
        if not self.initialized:
            return None
            
        try:
            if self.provider == 'newrelic' and self.agent:
                return self.agent.BackgroundTask(
                    self.agent.application(), 
                    name=name,
                    group=transaction_type
                )
                
            elif self.provider == 'elastic' and self.agent:
                return self.agent.begin_transaction(transaction_type, name)
                
            # For other providers, return None (they handle transactions automatically)
            return None
            
        except Exception as e:
            logger.error(f"Failed to create APM transaction: {e}")
            return None
    
    def set_transaction_result(self, result: str):
        """Set transaction result"""
        if not self.initialized:
            return
            
        try:
            if self.provider == 'elastic' and self.agent:
                self.agent.set_transaction_result(result)
                
        except Exception as e:
            logger.error(f"Failed to set transaction result: {e}")
    
    def add_custom_metric(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Add custom metric to APM"""
        if not self.initialized:
            return
            
        try:
            if self.provider == 'newrelic' and self.agent:
                self.agent.record_custom_metric(name, value)
                
            elif self.provider == 'datadog':
                from datadog import statsd
                statsd.gauge(name, value, tags=list(tags.items()) if tags else None)
                
            elif self.provider == 'elastic' and self.agent:
                self.agent.capture_metric(name, value, labels=tags)
                
        except Exception as e:
            logger.error(f"Failed to add custom metric: {e}")

# Global APM service instance
apm_service = APMService()

# ============================================================================
# Performance Monitoring Decorators
# ============================================================================

@contextmanager
def apm_transaction(name: str, transaction_type: str = 'request'):
    """Context manager for APM transactions"""
    transaction = apm_service.create_transaction(name, transaction_type)
    
    if transaction:
        # Provider-specific transaction handling
        if apm_service.provider == 'newrelic':
            with transaction:
                yield transaction
        elif apm_service.provider == 'elastic':
            try:
                yield transaction
                apm_service.agent.end_transaction(name, 'success')
            except Exception as e:
                apm_service.agent.end_transaction(name, 'error')
                raise
        else:
            yield None
    else:
        yield None

def monitor_performance(name: Optional[str] = None):
    """Decorator to monitor function performance"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            func_name = name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            
            # Start APM transaction
            with apm_transaction(func_name, 'function'):
                # Add to tracing
                with trace_span(func_name, attributes={"function.type": "monitored"}):
                    try:
                        result = await func(*args, **kwargs)
                        
                        # Record success metric
                        duration = time.time() - start_time
                        apm_service.add_custom_metric(
                            f"function.duration.{func_name}",
                            duration,
                            tags={"status": "success"}
                        )
                        
                        return result
                        
                    except Exception as e:
                        # Record error
                        duration = time.time() - start_time
                        apm_service.add_custom_metric(
                            f"function.duration.{func_name}",
                            duration,
                            tags={"status": "error"}
                        )
                        
                        # Capture exception
                        apm_service.capture_exception(e, context={
                            "function": func_name,
                            "duration": duration
                        })
                        
                        raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            func_name = name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            
            # Start APM transaction
            with apm_transaction(func_name, 'function'):
                # Add to tracing
                with trace_span(func_name, attributes={"function.type": "monitored"}):
                    try:
                        result = func(*args, **kwargs)
                        
                        # Record success metric
                        duration = time.time() - start_time
                        apm_service.add_custom_metric(
                            f"function.duration.{func_name}",
                            duration,
                            tags={"status": "success"}
                        )
                        
                        return result
                        
                    except Exception as e:
                        # Record error
                        duration = time.time() - start_time
                        apm_service.add_custom_metric(
                            f"function.duration.{func_name}",
                            duration,
                            tags={"status": "error"}
                        )
                        
                        # Capture exception
                        apm_service.capture_exception(e, context={
                            "function": func_name,
                            "duration": duration
                        })
                        
                        raise
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator

# ============================================================================
# System Monitoring
# ============================================================================

class SystemMonitor:
    """Monitor system resources and performance"""
    
    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        """Collect system metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            
            # Network metrics
            network = psutil.net_io_counters()
            
            # Process metrics
            process = psutil.Process()
            
            metrics = {
                "cpu": {
                    "percent": cpu_percent,
                    "count": cpu_count,
                    "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else None
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": disk.percent
                },
                "network": {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv
                },
                "process": {
                    "memory_rss": process.memory_info().rss,
                    "memory_vms": process.memory_info().vms,
                    "cpu_percent": process.cpu_percent(),
                    "num_threads": process.num_threads(),
                    "num_fds": process.num_fds() if hasattr(process, 'num_fds') else None
                }
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return {}
    
    @staticmethod
    async def monitor_system_health():
        """Background task to monitor system health"""
        while True:
            try:
                metrics = SystemMonitor.get_system_metrics()
                
                # Send metrics to APM
                if apm_service.initialized:
                    # CPU metrics
                    apm_service.add_custom_metric(
                        "system.cpu.percent",
                        metrics["cpu"]["percent"]
                    )
                    
                    # Memory metrics
                    apm_service.add_custom_metric(
                        "system.memory.percent",
                        metrics["memory"]["percent"]
                    )
                    
                    # Disk metrics
                    apm_service.add_custom_metric(
                        "system.disk.percent",
                        metrics["disk"]["percent"]
                    )
                    
                    # Process metrics
                    apm_service.add_custom_metric(
                        "process.memory.rss",
                        metrics["process"]["memory_rss"]
                    )
                    
                    apm_service.add_custom_metric(
                        "process.cpu.percent",
                        metrics["process"]["cpu_percent"]
                    )
                
                # Sleep for monitoring interval
                await asyncio.sleep(60)  # Monitor every minute
                
            except Exception as e:
                logger.error(f"Error in system monitoring: {e}")
                await asyncio.sleep(60)