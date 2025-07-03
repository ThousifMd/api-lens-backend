"""
Production-Ready Logging Configuration
Provides structured logging with multiple outputs and log rotation
"""
import os
import sys
import logging
import logging.handlers
from datetime import datetime
from typing import Dict, Any, Optional
import json
from pathlib import Path

from ..config import get_settings

settings = get_settings()

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        """Format log record as JSON"""
        # Base log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add process/thread info if configured
        if settings.LOG_INCLUDE_PROCESS_ID:
            log_entry["process_id"] = os.getpid()
        
        if hasattr(settings, 'LOG_INCLUDE_THREAD_ID') and settings.LOG_INCLUDE_THREAD_ID:
            log_entry["thread_id"] = record.thread
        
        # Add extra fields
        if hasattr(record, 'request_id'):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, 'user_id'):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, 'company_id'):
            log_entry["company_id"] = record.company_id
        
        if hasattr(record, 'api_key_id'):
            log_entry["api_key_id"] = record.api_key_id
        
        if hasattr(record, 'duration_ms'):
            log_entry["duration_ms"] = record.duration_ms
        
        if hasattr(record, 'status_code'):
            log_entry["status_code"] = record.status_code
        
        if hasattr(record, 'method'):
            log_entry["method"] = record.method
        
        if hasattr(record, 'url'):
            log_entry["url"] = record.url
        
        if hasattr(record, 'client_ip'):
            log_entry["client_ip"] = record.client_ip
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }
        
        # Add any additional fields from the extra parameter
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 'msecs', 
                          'relativeCreated', 'thread', 'threadName', 'processName', 'process',
                          'getMessage', 'exc_info', 'exc_text', 'stack_info', 'message']:
                if not key.startswith('_') and key not in log_entry:
                    try:
                        # Ensure the value is JSON serializable
                        json.dumps(value)
                        log_entry[key] = value
                    except (TypeError, ValueError):
                        log_entry[key] = str(value)
        
        return json.dumps(log_entry, ensure_ascii=False)

class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output in development"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record):
        """Format log record with colors"""
        if settings.ENVIRONMENT == "production":
            # No colors in production
            return super().format(record)
        
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        
        # Build log message
        log_parts = [
            f"{color}{timestamp}{reset}",
            f"{color}[{record.levelname}]{reset}",
            f"{record.name}:",
            record.getMessage()
        ]
        
        # Add request ID if present
        if hasattr(record, 'request_id'):
            log_parts.insert(-1, f"[{record.request_id}]")
        
        return " ".join(log_parts)

def setup_production_logging():
    """Configure production-ready logging"""
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    if settings.LOG_FORMAT == "json":
        console_formatter = JSONFormatter()
    else:
        console_formatter = ColoredFormatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if enabled)
    if hasattr(settings, 'LOG_FILE_ENABLED') and settings.LOG_FILE_ENABLED:
        setup_file_logging(root_logger)
    
    # Set specific logger levels
    _configure_logger_levels()
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(
        "Production logging configured",
        extra={
            "log_level": settings.LOG_LEVEL,
            "log_format": settings.LOG_FORMAT,
            "environment": settings.ENVIRONMENT,
            "structured_logging": settings.LOG_STRUCTURED
        }
    )

def setup_file_logging(root_logger):
    """Setup file logging with rotation"""
    
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # File path
    log_file = log_dir / "api_lens.log"
    
    # Rotating file handler
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_file,
        when='midnight',
        interval=1,
        backupCount=30,  # Keep 30 days of logs
        encoding='utf-8'
    )
    
    file_handler.setLevel(logging.INFO)  # File logs are always INFO or higher
    
    # Use JSON format for file logs
    file_formatter = JSONFormatter()
    file_handler.setFormatter(file_formatter)
    
    root_logger.addHandler(file_handler)
    
    # Error file handler (separate file for errors)
    error_file = log_dir / "api_lens_errors.log"
    error_handler = logging.handlers.TimedRotatingFileHandler(
        filename=error_file,
        when='midnight',
        interval=1,
        backupCount=90,  # Keep error logs longer
        encoding='utf-8'
    )
    
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    
    root_logger.addHandler(error_handler)

def _configure_logger_levels():
    """Configure log levels for specific loggers"""
    
    # Reduce noise from external libraries
    external_loggers = {
        'uvicorn': logging.WARNING,
        'uvicorn.access': logging.WARNING,
        'uvicorn.error': logging.INFO,
        'fastapi': logging.INFO,
        'httpx': logging.WARNING,
        'asyncpg': logging.WARNING,
        'redis': logging.WARNING,
        'urllib3': logging.WARNING,
        'requests': logging.WARNING,
    }
    
    for logger_name, level in external_loggers.items():
        logging.getLogger(logger_name).setLevel(level)
    
    # Set application loggers to appropriate levels
    app_loggers = {
        'app.database': logging.INFO,
        'app.services': logging.INFO,
        'app.middleware': logging.INFO,
        'app.api': logging.INFO,
    }
    
    for logger_name, level in app_loggers.items():
        logging.getLogger(logger_name).setLevel(level)

class LogContext:
    """Context manager for adding context to logs"""
    
    def __init__(self, **context):
        self.context = context
        self.old_factory = logging.getLogRecordFactory()
    
    def __enter__(self):
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record
        
        logging.setLogRecordFactory(record_factory)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self.old_factory)

def get_structured_logger(name: str) -> logging.Logger:
    """Get a logger configured for structured logging"""
    return logging.getLogger(name)

def log_api_request(
    logger: logging.Logger,
    request_id: str,
    method: str,
    url: str,
    status_code: int,
    duration_ms: float,
    client_ip: str = None,
    user_agent: str = None,
    **extra_fields
):
    """Log an API request in a structured format"""
    
    logger.info(
        f"{method} {url} - {status_code} in {duration_ms:.2f}ms",
        extra={
            "request_id": request_id,
            "method": method,
            "url": url,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "client_ip": client_ip,
            "user_agent": user_agent,
            **extra_fields
        }
    )

def log_database_operation(
    logger: logging.Logger,
    operation: str,
    table: str,
    duration_ms: float,
    affected_rows: int = None,
    **extra_fields
):
    """Log a database operation in a structured format"""
    
    logger.debug(
        f"Database {operation} on {table} completed in {duration_ms:.2f}ms",
        extra={
            "operation": operation,
            "table": table,
            "duration_ms": duration_ms,
            "affected_rows": affected_rows,
            **extra_fields
        }
    )

def log_external_api_call(
    logger: logging.Logger,
    vendor: str,
    endpoint: str,
    status_code: int,
    duration_ms: float,
    request_tokens: int = None,
    response_tokens: int = None,
    cost: float = None,
    **extra_fields
):
    """Log an external API call in a structured format"""
    
    logger.info(
        f"External API call to {vendor} {endpoint} - {status_code} in {duration_ms:.2f}ms",
        extra={
            "vendor": vendor,
            "endpoint": endpoint,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "request_tokens": request_tokens,
            "response_tokens": response_tokens,
            "cost": cost,
            **extra_fields
        }
    )

# Initialize logging when module is imported
if settings.ENVIRONMENT == "production" or settings.LOG_STRUCTURED:
    setup_production_logging()

# Export main functions
__all__ = [
    "setup_production_logging",
    "LogContext", 
    "get_structured_logger",
    "log_api_request",
    "log_database_operation", 
    "log_external_api_call"
]