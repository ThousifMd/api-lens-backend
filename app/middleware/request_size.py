"""
Request Size Limiting Middleware
Prevents excessively large requests to protect against DoS attacks
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import status
import io

from ..config import get_settings
from ..utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to limit request body size
    """
    
    def __init__(self, app, max_size: int = None):
        super().__init__(app)
        self.max_size = max_size or settings.MAX_REQUEST_SIZE
        
    async def dispatch(self, request: Request, call_next):
        """Check request size before processing"""
        
        # Check Content-Length header first
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_size:
                    logger.warning(
                        f"Request too large: {size} bytes > {self.max_size} bytes",
                        extra={
                            "client_ip": request.client.host if request.client else "unknown",
                            "path": request.url.path,
                            "size": size
                        }
                    )
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={
                            "error": {
                                "type": "request_too_large",
                                "code": 413,
                                "message": f"Request body too large. Maximum size is {self.max_size} bytes.",
                                "max_size": self.max_size,
                                "request_size": size
                            }
                        }
                    )
            except ValueError:
                pass
        
        # For streaming requests, we need to check as we read
        if request.method in ["POST", "PUT", "PATCH"]:
            # Store original body for later use
            body_bytes = await request.body()
            
            if len(body_bytes) > self.max_size:
                logger.warning(
                    f"Request too large after reading: {len(body_bytes)} bytes > {self.max_size} bytes",
                    extra={
                        "client_ip": request.client.host if request.client else "unknown",
                        "path": request.url.path,
                        "size": len(body_bytes)
                    }
                )
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={
                        "error": {
                            "type": "request_too_large",
                            "code": 413,
                            "message": f"Request body too large. Maximum size is {self.max_size} bytes.",
                            "max_size": self.max_size,
                            "request_size": len(body_bytes)
                        }
                    }
                )
            
            # Create a new stream for the request body
            async def receive():
                return {"type": "http.request", "body": body_bytes}
            
            request._receive = receive
        
        # Process the request
        response = await call_next(request)
        return response

class MultipartSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Special handling for multipart uploads with different size limits
    """
    
    def __init__(self, app, max_upload_size: int = None):
        super().__init__(app)
        self.max_upload_size = max_upload_size or settings.MAX_UPLOAD_SIZE
        
    async def dispatch(self, request: Request, call_next):
        """Check multipart upload size"""
        
        # Only check multipart requests
        content_type = request.headers.get("content-type", "")
        if not content_type.startswith("multipart/form-data"):
            return await call_next(request)
        
        # Check Content-Length for uploads
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_upload_size:
                    logger.warning(
                        f"Upload too large: {size} bytes > {self.max_upload_size} bytes",
                        extra={
                            "client_ip": request.client.host if request.client else "unknown",
                            "path": request.url.path,
                            "size": size
                        }
                    )
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={
                            "error": {
                                "type": "upload_too_large",
                                "code": 413,
                                "message": f"Upload too large. Maximum size is {self.max_upload_size} bytes.",
                                "max_size": self.max_upload_size,
                                "request_size": size
                            }
                        }
                    )
            except ValueError:
                pass
        
        return await call_next(request)