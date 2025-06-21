"""
API Lens Python SDK - Custom Exceptions

This module defines custom exception classes for API Lens SDK operations.
"""

from typing import Optional, Dict, Any


class APILensError(Exception):
    """Base exception for all API Lens errors"""
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}
        self.request_id = request_id
    
    def __str__(self) -> str:
        base_msg = self.message
        if self.status_code:
            base_msg = f"[{self.status_code}] {base_msg}"
        if self.request_id:
            base_msg = f"{base_msg} (Request ID: {self.request_id})"
        return base_msg
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message='{self.message}', status_code={self.status_code})"


class AuthenticationError(APILensError):
    """Authentication failed - invalid or expired API key"""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, **kwargs)


class AuthorizationError(APILensError):
    """Authorization failed - insufficient permissions"""
    
    def __init__(self, message: str = "Insufficient permissions", **kwargs):
        super().__init__(message, **kwargs)


class ValidationError(APILensError):
    """Request validation failed"""
    
    def __init__(self, message: str = "Request validation failed", **kwargs):
        super().__init__(message, **kwargs)
        
    @property
    def validation_errors(self) -> Dict[str, Any]:
        """Get validation error details from response"""
        return self.response_data.get("detail", {})


class NotFoundError(APILensError):
    """Resource not found"""
    
    def __init__(self, message: str = "Resource not found", **kwargs):
        super().__init__(message, **kwargs)


class RateLimitError(APILensError):
    """Rate limit exceeded"""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after
    
    @classmethod
    def from_response(cls, response_data: Dict[str, Any], **kwargs):
        """Create RateLimitError from API response"""
        retry_after = response_data.get("retry_after")
        limit_type = response_data.get("limit_type", "requests")
        current_usage = response_data.get("current_usage", 0)
        limit = response_data.get("limit", 0)
        
        message = f"Rate limit exceeded for {limit_type}: {current_usage}/{limit}"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
            
        return cls(message=message, retry_after=retry_after, **kwargs)


class QuotaExceededError(APILensError):
    """Usage quota exceeded"""
    
    def __init__(
        self,
        message: str = "Usage quota exceeded",
        quota_type: Optional[str] = None,
        current_usage: Optional[int] = None,
        quota_limit: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.quota_type = quota_type
        self.current_usage = current_usage
        self.quota_limit = quota_limit
    
    @classmethod
    def from_response(cls, response_data: Dict[str, Any], **kwargs):
        """Create QuotaExceededError from API response"""
        quota_type = response_data.get("quota_type", "requests")
        current_usage = response_data.get("current_usage", 0)
        quota_limit = response_data.get("quota_limit", 0)
        
        message = f"Quota exceeded for {quota_type}: {current_usage}/{quota_limit}"
        
        return cls(
            message=message,
            quota_type=quota_type,
            current_usage=current_usage,
            quota_limit=quota_limit,
            **kwargs
        )


class ServerError(APILensError):
    """Server-side error occurred"""
    
    def __init__(self, message: str = "Internal server error", **kwargs):
        super().__init__(message, **kwargs)


class ServiceUnavailableError(ServerError):
    """API Lens service is temporarily unavailable"""
    
    def __init__(self, message: str = "Service temporarily unavailable", **kwargs):
        super().__init__(message, **kwargs)


class VendorError(APILensError):
    """Error from AI vendor (OpenAI, Anthropic, etc.)"""
    
    def __init__(
        self,
        message: str,
        vendor: Optional[str] = None,
        vendor_error_code: Optional[str] = None,
        vendor_message: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.vendor = vendor
        self.vendor_error_code = vendor_error_code
        self.vendor_message = vendor_message
    
    @classmethod
    def from_response(cls, response_data: Dict[str, Any], **kwargs):
        """Create VendorError from API response"""
        vendor = response_data.get("vendor")
        vendor_error = response_data.get("vendor_error", {})
        vendor_error_code = vendor_error.get("code")
        vendor_message = vendor_error.get("message")
        
        message = f"Vendor error from {vendor}: {vendor_message or 'Unknown error'}"
        
        return cls(
            message=message,
            vendor=vendor,
            vendor_error_code=vendor_error_code,
            vendor_message=vendor_message,
            **kwargs
        )


class VendorKeyError(APILensError):
    """Error related to vendor API keys (BYOK)"""
    
    def __init__(
        self,
        message: str,
        vendor: Optional[str] = None,
        key_issue: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.vendor = vendor
        self.key_issue = key_issue


class NetworkError(APILensError):
    """Network connectivity error"""
    
    def __init__(self, message: str = "Network connection failed", **kwargs):
        super().__init__(message, **kwargs)


class TimeoutError(NetworkError):
    """Request timeout"""
    
    def __init__(self, message: str = "Request timed out", timeout: Optional[float] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.timeout = timeout


class ConfigurationError(APILensError):
    """SDK configuration error"""
    
    def __init__(self, message: str = "SDK configuration error", **kwargs):
        super().__init__(message, **kwargs)


class ExportError(APILensError):
    """Data export operation failed"""
    
    def __init__(
        self,
        message: str = "Export operation failed",
        export_type: Optional[str] = None,
        export_format: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.export_type = export_type
        self.export_format = export_format


# Exception mapping for HTTP status codes
STATUS_CODE_TO_EXCEPTION = {
    400: ValidationError,
    401: AuthenticationError,
    403: AuthorizationError,
    404: NotFoundError,
    422: ValidationError,
    429: RateLimitError,
    500: ServerError,
    502: ServiceUnavailableError,
    503: ServiceUnavailableError,
    504: TimeoutError,
}


def create_exception_from_response(
    status_code: int,
    response_data: Dict[str, Any],
    default_message: str = "API request failed"
) -> APILensError:
    """Create appropriate exception from HTTP response"""
    
    # Get error details from response
    error_message = response_data.get("detail", response_data.get("message", default_message))
    error_code = response_data.get("error_code")
    request_id = response_data.get("request_id")
    
    # Handle specific error types
    if status_code == 429:
        return RateLimitError.from_response(
            response_data,
            status_code=status_code,
            response_data=response_data,
            request_id=request_id
        )
    
    if response_data.get("vendor_error"):
        return VendorError.from_response(
            response_data,
            status_code=status_code,
            response_data=response_data,
            request_id=request_id
        )
    
    if response_data.get("quota_exceeded"):
        return QuotaExceededError.from_response(
            response_data,
            status_code=status_code,
            response_data=response_data,
            request_id=request_id
        )
    
    # Use status code mapping
    exception_class = STATUS_CODE_TO_EXCEPTION.get(status_code, APILensError)
    
    return exception_class(
        message=error_message,
        status_code=status_code,
        response_data=response_data,
        request_id=request_id
    )


# Utility functions for exception handling
def is_retryable_error(exception: Exception) -> bool:
    """Check if an error is retryable"""
    if isinstance(exception, (NetworkError, TimeoutError, ServerError)):
        return True
    
    if isinstance(exception, RateLimitError):
        return True
    
    if isinstance(exception, APILensError) and exception.status_code:
        # Retry on server errors and rate limits
        return exception.status_code >= 500 or exception.status_code == 429
    
    return False


def get_retry_delay(exception: Exception, attempt: int, base_delay: float = 1.0) -> float:
    """Calculate retry delay for an exception"""
    if isinstance(exception, RateLimitError) and exception.retry_after:
        return float(exception.retry_after)
    
    # Exponential backoff with jitter
    import random
    delay = base_delay * (2 ** attempt)
    jitter = random.uniform(0.1, 0.3) * delay
    return delay + jitter