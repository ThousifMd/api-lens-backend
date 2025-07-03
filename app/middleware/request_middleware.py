"""
Request Middleware for IP Detection and Authentication
Provides real IP address detection and API key authentication
"""
from fastapi import Request, HTTPException, Header
from typing import Optional, Dict, Any
import ipaddress
from ..utils.logger import get_logger
from ..services.auth import validate_api_key

logger = get_logger(__name__)

class RequestMiddleware:
    """Middleware for processing incoming requests"""
    
    @staticmethod
    def get_client_ip(request: Request) -> str:
        """
        Extract real client IP address from request headers
        Handles proxy forwarding headers properly
        
        Args:
            request: FastAPI request object
            
        Returns:
            Client IP address string
        """
        try:
            # Check common proxy headers in order of preference
            proxy_headers = [
                'CF-Connecting-IP',      # Cloudflare
                'X-Forwarded-For',       # Standard proxy header
                'X-Real-IP',             # Nginx proxy
                'X-Client-IP',           # Some proxies
                'X-Cluster-Client-IP',   # Cluster setups
                'Forwarded',             # RFC 7239
            ]
            
            # First try proxy headers
            for header_name in proxy_headers:
                header_value = request.headers.get(header_name)
                if header_value:
                    # X-Forwarded-For can contain multiple IPs (client, proxy1, proxy2)
                    # We want the first one (original client)
                    if header_name == 'X-Forwarded-For':
                        ip = header_value.split(',')[0].strip()
                    elif header_name == 'Forwarded':
                        # Parse RFC 7239 format: for=192.0.2.60;proto=http;by=203.0.113.43
                        ip = RequestMiddleware._parse_forwarded_header(header_value)
                        if not ip:
                            continue
                    else:
                        ip = header_value.strip()
                    
                    # Validate IP address
                    if RequestMiddleware._is_valid_ip(ip):
                        logger.debug(f"Detected client IP from {header_name}: {ip}")
                        return ip
            
            # Fallback to direct connection IP
            client_host = request.client.host if request.client else None
            if client_host and RequestMiddleware._is_valid_ip(client_host):
                logger.debug(f"Using direct connection IP: {client_host}")
                return client_host
            
            # Final fallback
            logger.warning("Could not determine client IP, using fallback")
            return "127.0.0.1"
            
        except Exception as e:
            logger.error(f"Error extracting client IP: {e}")
            return "127.0.0.1"
    
    @staticmethod
    def _parse_forwarded_header(forwarded_value: str) -> Optional[str]:
        """Parse RFC 7239 Forwarded header"""
        try:
            # Simple parsing for "for=" parameter
            parts = forwarded_value.split(';')
            for part in parts:
                part = part.strip()
                if part.startswith('for='):
                    ip_part = part[4:]  # Remove "for="
                    # Remove quotes if present
                    ip_part = ip_part.strip('"')
                    # Handle IPv6 brackets
                    if ip_part.startswith('[') and ']' in ip_part:
                        ip_part = ip_part[1:ip_part.index(']')]
                    # Handle port numbers
                    if ':' in ip_part and not RequestMiddleware._is_ipv6(ip_part):
                        ip_part = ip_part.split(':')[0]
                    return ip_part
            return None
        except Exception:
            return None
    
    @staticmethod
    def _is_valid_ip(ip_str: str) -> bool:
        """Check if string is a valid IP address"""
        try:
            ipaddress.ip_address(ip_str)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def _is_ipv6(ip_str: str) -> bool:
        """Check if string is an IPv6 address"""
        try:
            return isinstance(ipaddress.ip_address(ip_str), ipaddress.IPv6Address)
        except ValueError:
            return False
    
    @staticmethod
    def extract_user_agent(request: Request) -> Optional[str]:
        """Extract User-Agent header"""
        return request.headers.get('User-Agent')
    
    @staticmethod
    def extract_referer(request: Request) -> Optional[str]:
        """Extract Referer header"""
        return request.headers.get('Referer') or request.headers.get('Referrer')
    
    @staticmethod
    def extract_custom_headers(request: Request, prefix: str = 'X-') -> Dict[str, str]:
        """
        Extract custom headers with a specific prefix
        
        Args:
            request: FastAPI request object
            prefix: Header prefix to filter by
            
        Returns:
            Dictionary of custom headers
        """
        custom_headers = {}
        try:
            for header_name, header_value in request.headers.items():
                if header_name.startswith(prefix):
                    custom_headers[header_name] = header_value
            return custom_headers
        except Exception as e:
            logger.error(f"Error extracting custom headers: {e}")
            return {}

class AuthenticationMiddleware:
    """Middleware for API key authentication"""
    
    @staticmethod
    async def authenticate_request(
        request: Request,
        authorization: Optional[str] = Header(None),
        x_api_key: Optional[str] = Header(None)
    ) -> Dict[str, Any]:
        """
        Authenticate request using API key
        
        Args:
            request: FastAPI request object
            authorization: Authorization header
            x_api_key: X-API-Key header
            
        Returns:
            Dictionary with authentication results
        """
        try:
            # Extract API key from multiple possible sources
            api_key = AuthenticationMiddleware._extract_api_key(
                authorization, x_api_key, request
            )
            
            if not api_key:
                raise HTTPException(
                    status_code=401,
                    detail="API key required. Provide via Authorization header (Bearer token) or X-API-Key header"
                )
            
            # Validate API key
            company = await validate_api_key(api_key)
            
            if not company:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid API key"
                )
            
            # Get API key record for additional info
            from ..services.auth import list_company_api_keys
            api_keys = await list_company_api_keys(company.id)
            
            # Find the current API key record
            current_api_key = None
            for key in api_keys:
                # This requires implementing a way to match the key
                # For now, we'll use the first active key
                if key.is_active:
                    current_api_key = key
                    break
            
            return {
                'authenticated': True,
                'api_key': api_key,
                'api_key_id': current_api_key.id if current_api_key else None,
                'company': company,
                'company_id': company.id
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise HTTPException(
                status_code=500,
                detail="Authentication service error"
            )
    
    @staticmethod
    def _extract_api_key(
        authorization: Optional[str],
        x_api_key: Optional[str], 
        request: Request
    ) -> Optional[str]:
        """Extract API key from various sources"""
        
        # Method 1: X-API-Key header
        if x_api_key:
            return x_api_key.strip()
        
        # Method 2: Authorization Bearer token
        if authorization:
            auth_parts = authorization.strip().split()
            if len(auth_parts) == 2 and auth_parts[0].lower() == 'bearer':
                return auth_parts[1]
        
        # Method 3: Query parameter (less secure, for development only)
        api_key_param = request.query_params.get('api_key')
        if api_key_param:
            logger.warning("API key provided via query parameter - this is insecure for production")
            return api_key_param
        
        return None

# Dependency functions for FastAPI
async def get_client_info(request: Request) -> Dict[str, Any]:
    """
    FastAPI dependency to extract client information
    
    Returns:
        Dictionary with client IP, user agent, etc.
    """
    return {
        'ip_address': RequestMiddleware.get_client_ip(request),
        'user_agent': RequestMiddleware.extract_user_agent(request),
        'referer': RequestMiddleware.extract_referer(request),
        'custom_headers': RequestMiddleware.extract_custom_headers(request)
    }

async def authenticate_api_key(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    FastAPI dependency for API key authentication
    
    Returns:
        Dictionary with authentication results
    """
    return await AuthenticationMiddleware.authenticate_request(
        request, authorization, x_api_key
    )