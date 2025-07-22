"""
Security Headers Middleware
Adds comprehensive security headers to protect against common attacks
"""
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..config import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers to all responses
    """
    
    def __init__(
        self, 
        app,
        force_https: bool = True,
        hsts_max_age: int = 31536000,  # 1 year
        hsts_include_subdomains: bool = True,
        hsts_preload: bool = True,
        content_type_nosniff: bool = True,
        frame_options: str = "DENY",
        xss_protection: bool = True,
        referrer_policy: str = "strict-origin-when-cross-origin",
        permissions_policy: Optional[str] = None,
        csp_policy: Optional[str] = None
    ):
        super().__init__(app)
        self.force_https = force_https
        self.hsts_max_age = hsts_max_age
        self.hsts_include_subdomains = hsts_include_subdomains
        self.hsts_preload = hsts_preload
        self.content_type_nosniff = content_type_nosniff
        self.frame_options = frame_options
        self.xss_protection = xss_protection
        self.referrer_policy = referrer_policy
        self.permissions_policy = permissions_policy
        self.csp_policy = csp_policy or self._default_csp_policy()
    
    async def dispatch(self, request: Request, call_next):
        """Add security headers to response"""
        
        response = await call_next(request)
        
        # Add security headers
        self._add_security_headers(request, response)
        
        return response
    
    def _add_security_headers(self, request: Request, response: Response):
        """Add all security headers to the response"""
        
        # HTTP Strict Transport Security (HSTS)
        if self._should_add_hsts(request):
            hsts_value = f"max-age={self.hsts_max_age}"
            if self.hsts_include_subdomains:
                hsts_value += "; includeSubDomains"
            if self.hsts_preload:
                hsts_value += "; preload"
            response.headers["Strict-Transport-Security"] = hsts_value
        
        # Content Type Options
        if self.content_type_nosniff:
            response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Frame Options
        if self.frame_options:
            response.headers["X-Frame-Options"] = self.frame_options
        
        # XSS Protection
        if self.xss_protection:
            response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Referrer Policy
        if self.referrer_policy:
            response.headers["Referrer-Policy"] = self.referrer_policy
        
        # Permissions Policy (formerly Feature Policy)
        if self.permissions_policy:
            response.headers["Permissions-Policy"] = self.permissions_policy
        
        # Content Security Policy
        if self.csp_policy:
            response.headers["Content-Security-Policy"] = self.csp_policy
        
        # Cross-Origin Policies
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
        
        # Additional security headers
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage"' if request.url.path == "/logout" else '""'
        
        # Cache control for sensitive endpoints
        if self._is_sensitive_endpoint(request):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
    
    def _should_add_hsts(self, request: Request) -> bool:
        """Determine if HSTS header should be added"""
        # Only add HSTS for HTTPS requests
        if not self.force_https:
            return False
        
        # Check if request is over HTTPS
        is_https = (
            request.url.scheme == "https" or
            request.headers.get("X-Forwarded-Proto") == "https" or
            request.headers.get("X-Forwarded-Ssl") == "on"
        )
        
        return is_https
    
    def _is_sensitive_endpoint(self, request: Request) -> bool:
        """Check if endpoint contains sensitive data"""
        sensitive_paths = [
            "/auth/",
            "/login",
            "/logout", 
            "/admin/",
            "/api/keys",
            "/profile",
            "/settings"
        ]
        
        return any(sensitive_path in request.url.path for sensitive_path in sensitive_paths)
    
    def _default_csp_policy(self) -> str:
        """Generate default Content Security Policy"""
        
        # Base policy for API endpoints
        policy_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://unpkg.com",
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data: https:",
            "connect-src 'self' https:",
            "frame-ancestors 'none'",
            "form-action 'self'",
            "base-uri 'self'",
            "object-src 'none'",
            "media-src 'self'",
            "worker-src 'self'",
            "manifest-src 'self'",
            "upgrade-insecure-requests"
        ]
        
        # Add report-uri if configured
        if hasattr(settings, 'CSP_REPORT_URI') and settings.CSP_REPORT_URI:
            policy_directives.append(f"report-uri {settings.CSP_REPORT_URI}")
        
        return "; ".join(policy_directives)


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """
    IP whitelist middleware for admin endpoints
    """
    
    def __init__(
        self,
        app,
        whitelist: list = None,
        admin_paths: list = None
    ):
        super().__init__(app)
        self.whitelist = set(whitelist or ["127.0.0.1", "::1"])
        self.admin_paths = admin_paths or ["/admin", "/metrics"]
    
    async def dispatch(self, request: Request, call_next):
        """Check IP whitelist for admin endpoints"""
        
        # Check if this is an admin path
        is_admin_path = any(
            request.url.path.startswith(path) 
            for path in self.admin_paths
        )
        
        if is_admin_path:
            client_ip = self._get_client_ip(request)
            
            if client_ip not in self.whitelist:
                from starlette.responses import JSONResponse
                from fastapi import status
                
                logger.warning(f"Blocked admin access from IP: {client_ip}")
                
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "error": {
                            "type": "access_denied",
                            "code": 403,
                            "message": "Access denied for this IP address"
                        }
                    }
                )
        
        return await call_next(request)
    
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

# Import time for rate limiting
import time

# Export middleware classes
__all__ = [
    "SecurityHeadersMiddleware", 
    "IPWhitelistMiddleware"
]