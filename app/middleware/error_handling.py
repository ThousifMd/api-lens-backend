"""
Global Error Handling Middleware
Provides comprehensive error handling, logging, and response formatting
"""
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import status
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.responses import Response

import asyncpg
import redis.exceptions
from pydantic import ValidationError

from ..utils.logger import get_logger
from ..config import get_settings

logger = get_logger(__name__)
settings = get_settings()

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Global error handling middleware that catches and formats all exceptions
    """
    
    async def dispatch(self, request: Request, call_next):
        """Process request and handle any exceptions"""
        
        # Generate request ID for tracking
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        
        # Add request start time
        start_time = datetime.utcnow()
        request.state.start_time = start_time
        
        try:
            response = await call_next(request)
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as exc:
            return await self._handle_exception(request, exc, request_id)
    
    async def _handle_exception(
        self, 
        request: Request, 
        exc: Exception, 
        request_id: str
    ) -> JSONResponse:
        """Handle different types of exceptions and return appropriate responses"""
        
        # Calculate request duration
        start_time = getattr(request.state, 'start_time', datetime.utcnow())
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Base error context
        error_context = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("User-Agent", "Unknown"),
            "duration_ms": round(duration_ms, 2),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Handle specific exception types
        if isinstance(exc, HTTPException):
            return await self._handle_http_exception(exc, error_context)
        
        elif isinstance(exc, RequestValidationError):
            return await self._handle_validation_error(exc, error_context)
        
        elif isinstance(exc, ValidationError):
            return await self._handle_pydantic_validation_error(exc, error_context)
        
        elif isinstance(exc, asyncpg.PostgresError):
            return await self._handle_database_error(exc, error_context)
        
        elif isinstance(exc, redis.exceptions.RedisError):
            return await self._handle_redis_error(exc, error_context)
        
        elif isinstance(exc, TimeoutError):
            return await self._handle_timeout_error(exc, error_context)
        
        elif isinstance(exc, PermissionError):
            return await self._handle_permission_error(exc, error_context)
        
        else:
            return await self._handle_generic_error(exc, error_context)
    
    async def _handle_http_exception(
        self, 
        exc: HTTPException, 
        context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle FastAPI HTTP exceptions"""
        
        logger.warning(
            f"HTTP Exception: {exc.status_code} - {exc.detail}",
            extra={
                **context,
                "exception_type": "HTTPException",
                "status_code": exc.status_code,
                "detail": exc.detail
            }
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "type": "http_error",
                    "code": exc.status_code,
                    "message": exc.detail,
                    "request_id": context["request_id"],
                    "timestamp": context["timestamp"]
                }
            },
            headers={"X-Request-ID": context["request_id"]}
        )
    
    async def _handle_validation_error(
        self, 
        exc: RequestValidationError, 
        context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle FastAPI request validation errors"""
        
        # Format validation errors
        validation_errors = []
        for error in exc.errors():
            validation_errors.append({
                "field": " -> ".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
                "input": error.get("input", "N/A")
            })
        
        logger.warning(
            f"Validation Error: {len(validation_errors)} field(s) failed validation",
            extra={
                **context,
                "exception_type": "RequestValidationError",
                "validation_errors": validation_errors
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "type": "validation_error",
                    "code": 422,
                    "message": "Request validation failed",
                    "details": validation_errors,
                    "request_id": context["request_id"],
                    "timestamp": context["timestamp"]
                }
            },
            headers={"X-Request-ID": context["request_id"]}
        )
    
    async def _handle_pydantic_validation_error(
        self, 
        exc: ValidationError, 
        context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle Pydantic validation errors"""
        
        validation_errors = []
        for error in exc.errors():
            validation_errors.append({
                "field": " -> ".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            })
        
        logger.warning(
            f"Pydantic Validation Error: {len(validation_errors)} field(s) failed",
            extra={
                **context,
                "exception_type": "ValidationError",
                "validation_errors": validation_errors
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "type": "data_validation_error",
                    "code": 400,
                    "message": "Data validation failed",
                    "details": validation_errors,
                    "request_id": context["request_id"],
                    "timestamp": context["timestamp"]
                }
            },
            headers={"X-Request-ID": context["request_id"]}
        )
    
    async def _handle_database_error(
        self, 
        exc: asyncpg.PostgresError, 
        context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle PostgreSQL database errors"""
        
        # Determine error type and user-friendly message
        error_code = getattr(exc, 'sqlstate', 'Unknown')
        error_message = str(exc)
        
        # Map common PostgreSQL errors to user-friendly messages
        user_message = self._get_user_friendly_db_message(error_code, error_message)
        
        # Log detailed error for debugging
        logger.error(
            f"Database Error: {error_code} - {error_message}",
            extra={
                **context,
                "exception_type": "PostgresError",
                "sqlstate": error_code,
                "db_message": error_message
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "type": "database_error",
                    "code": 500,
                    "message": user_message,
                    "request_id": context["request_id"],
                    "timestamp": context["timestamp"]
                }
            },
            headers={"X-Request-ID": context["request_id"]}
        )
    
    async def _handle_redis_error(
        self, 
        exc: redis.exceptions.RedisError, 
        context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle Redis cache errors"""
        
        logger.error(
            f"Redis Error: {str(exc)}",
            extra={
                **context,
                "exception_type": "RedisError",
                "redis_message": str(exc)
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "type": "cache_error",
                    "code": 503,
                    "message": "Cache service temporarily unavailable",
                    "request_id": context["request_id"],
                    "timestamp": context["timestamp"]
                }
            },
            headers={"X-Request-ID": context["request_id"]}
        )
    
    async def _handle_timeout_error(
        self, 
        exc: TimeoutError, 
        context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle timeout errors"""
        
        logger.warning(
            f"Timeout Error: {str(exc)}",
            extra={
                **context,
                "exception_type": "TimeoutError",
                "timeout_message": str(exc)
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            content={
                "error": {
                    "type": "timeout_error",
                    "code": 408,
                    "message": "Request timed out. Please try again.",
                    "request_id": context["request_id"],
                    "timestamp": context["timestamp"]
                }
            },
            headers={"X-Request-ID": context["request_id"]}
        )
    
    async def _handle_permission_error(
        self, 
        exc: PermissionError, 
        context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle permission errors"""
        
        logger.warning(
            f"Permission Error: {str(exc)}",
            extra={
                **context,
                "exception_type": "PermissionError",
                "permission_message": str(exc)
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": {
                    "type": "permission_error",
                    "code": 403,
                    "message": "Insufficient permissions for this operation",
                    "request_id": context["request_id"],
                    "timestamp": context["timestamp"]
                }
            },
            headers={"X-Request-ID": context["request_id"]}
        )
    
    async def _handle_generic_error(
        self, 
        exc: Exception, 
        context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle generic/unexpected errors"""
        
        # Log full traceback for debugging
        error_traceback = traceback.format_exc()
        
        logger.error(
            f"Unhandled Exception: {type(exc).__name__} - {str(exc)}",
            extra={
                **context,
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "traceback": error_traceback
            }
        )
        
        # In production, don't expose internal error details
        if settings.ENVIRONMENT == "production":
            error_message = "An internal server error occurred"
        else:
            error_message = f"{type(exc).__name__}: {str(exc)}"
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "type": "internal_error",
                    "code": 500,
                    "message": error_message,
                    "request_id": context["request_id"],
                    "timestamp": context["timestamp"]
                }
            },
            headers={"X-Request-ID": context["request_id"]}
        )
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address"""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        # Fallback to direct client
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _get_user_friendly_db_message(self, error_code: str, error_message: str) -> str:
        """Convert PostgreSQL error codes to user-friendly messages"""
        
        error_code_messages = {
            "23505": "Duplicate entry - this record already exists",
            "23503": "Referenced record not found",
            "23502": "Required field is missing",
            "42703": "Invalid field name",
            "42P01": "Table does not exist",
            "28P01": "Authentication failed",
            "53300": "Too many connections",
            "57014": "Query cancelled due to timeout",
        }
        
        user_message = error_code_messages.get(error_code)
        if user_message:
            return user_message
        
        # For unknown errors, provide a generic message
        if "duplicate key" in error_message.lower():
            return "Duplicate entry - this record already exists"
        elif "foreign key" in error_message.lower():
            return "Referenced record not found"
        elif "not null" in error_message.lower():
            return "Required field is missing"
        elif "timeout" in error_message.lower():
            return "Database operation timed out"
        else:
            return "Database operation failed"

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging all requests and responses
    """
    
    async def dispatch(self, request: Request, call_next):
        """Log request and response details"""
        
        # Get request ID from error handling middleware
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4())[:8])
        start_time = datetime.utcnow()
        
        # Log request
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_ip": self._get_client_ip(request),
                "user_agent": request.headers.get("User-Agent", "Unknown"),
                "content_type": request.headers.get("Content-Type"),
                "content_length": request.headers.get("Content-Length"),
                "timestamp": start_time.isoformat()
            }
        )
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        end_time = datetime.utcnow()
        duration_ms = (end_time - start_time).total_seconds() * 1000
        
        # Log response
        logger.info(
            f"Request completed: {response.status_code} in {duration_ms:.2f}ms",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "response_size": response.headers.get("Content-Length"),
                "content_type": response.headers.get("Content-Type"),
                "timestamp": end_time.isoformat()
            }
        )
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        if request.client:
            return request.client.host
        
        return "unknown"

# Export middleware classes
__all__ = ["ErrorHandlingMiddleware", "RequestLoggingMiddleware"]