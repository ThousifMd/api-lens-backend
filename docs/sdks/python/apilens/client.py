"""
API Lens Python SDK - Main Client Implementation
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from urllib.parse import urljoin
import httpx

from .exceptions import (
    APILensError,
    AuthenticationError,
    RateLimitError,
    ServerError,
    ValidationError,
    NotFoundError
)
from .models import (
    Company,
    APIKey,
    VendorKey,
    UsageAnalytics,
    CostAnalytics,
    PerformanceAnalytics,
    CostOptimizationRecommendation
)
from .vendors import OpenAIClient, AnthropicClient, GoogleClient


class BaseClient:
    """Base client with common functionality"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.apilens.dev",
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        user_agent: Optional[str] = None,
        debug: bool = False,
        default_headers: Optional[Dict[str, str]] = None
    ):
        self.api_key = api_key or os.getenv("API_LENS_API_KEY")
        if not self.api_key:
            raise ValueError("API key is required. Set API_LENS_API_KEY environment variable or pass api_key parameter.")
        
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.debug = debug
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        if debug:
            logging.basicConfig(level=logging.DEBUG)
        
        # Default headers
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": user_agent or f"apilens-python/{self._get_version()}",
            **(default_headers or {})
        }
    
    def _get_version(self) -> str:
        """Get SDK version"""
        try:
            from . import __version__
            return __version__
        except ImportError:
            return "unknown"
    
    def _build_url(self, path: str) -> str:
        """Build full URL from path"""
        return urljoin(self.base_url + "/", path.lstrip("/"))
    
    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle HTTP response and convert to appropriate exception if needed"""
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 201:
            return response.json()
        elif response.status_code == 204:
            return {}
        elif response.status_code == 401:
            raise AuthenticationError("Invalid or expired API key")
        elif response.status_code == 403:
            raise AuthenticationError("Insufficient permissions")
        elif response.status_code == 404:
            raise NotFoundError("Resource not found")
        elif response.status_code == 422:
            error_detail = response.json().get("detail", "Validation error")
            raise ValidationError(f"Validation error: {error_detail}")
        elif response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "60")
            raise RateLimitError(f"Rate limit exceeded. Retry after {retry_after} seconds")
        elif response.status_code >= 500:
            raise ServerError(f"Server error: {response.status_code}")
        else:
            raise APILensError(f"Unexpected status code: {response.status_code}")


class Client(BaseClient):
    """Synchronous API Lens client"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Initialize HTTP client
        self._client = httpx.Client(
            timeout=self.timeout,
            headers=self.headers
        )
        
        # Initialize vendor clients
        self.openai = OpenAIClient(self)
        self.anthropic = AnthropicClient(self)
        self.google = GoogleClient(self)
        
        # Initialize service clients
        self.api_keys = APIKeyService(self)
        self.vendor_keys = VendorKeyService(self)
        self.analytics = AnalyticsService(self)
    
    def close(self):
        """Close the HTTP client"""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic"""
        url = self._build_url(path)
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.request(
                    method=method,
                    url=url,
                    json=json,
                    params=params,
                    **kwargs
                )
                return self._handle_response(response)
            
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt == self.max_retries:
                    raise APILensError(f"Connection error after {self.max_retries} retries: {e}")
                
                import time
                time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
    
    def get_company(self) -> Company:
        """Get current company information"""
        data = self._request("GET", "/companies/me")
        return Company(**data)
    
    def update_company(self, **kwargs) -> Company:
        """Update company profile"""
        data = self._request("PUT", "/companies/me", json=kwargs)
        return Company(**data)


class AsyncClient(BaseClient):
    """Asynchronous API Lens client"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Initialize async HTTP client
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            headers=self.headers
        )
        
        # Initialize vendor clients
        self.openai = OpenAIClient(self, async_mode=True)
        self.anthropic = AnthropicClient(self, async_mode=True)
        self.google = GoogleClient(self, async_mode=True)
        
        # Initialize service clients
        self.api_keys = APIKeyService(self, async_mode=True)
        self.vendor_keys = VendorKeyService(self, async_mode=True)
        self.analytics = AnalyticsService(self, async_mode=True)
    
    async def close(self):
        """Close the HTTP client"""
        await self._client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make async HTTP request with retry logic"""
        url = self._build_url(path)
        
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._client.request(
                    method=method,
                    url=url,
                    json=json,
                    params=params,
                    **kwargs
                )
                return self._handle_response(response)
            
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt == self.max_retries:
                    raise APILensError(f"Connection error after {self.max_retries} retries: {e}")
                
                await asyncio.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
    
    async def get_company(self) -> Company:
        """Get current company information"""
        data = await self._request("GET", "/companies/me")
        return Company(**data)
    
    async def update_company(self, **kwargs) -> Company:
        """Update company profile"""
        data = await self._request("PUT", "/companies/me", json=kwargs)
        return Company(**data)


class APIKeyService:
    """API key management service"""
    
    def __init__(self, client, async_mode: bool = False):
        self.client = client
        self.async_mode = async_mode
    
    def list(self) -> List[APIKey]:
        """List all API keys for the company"""
        if self.async_mode:
            raise RuntimeError("Use async methods with AsyncClient")
        
        data = self.client._request("GET", "/companies/me/api-keys")
        return [APIKey(**item) for item in data]
    
    async def alist(self) -> List[APIKey]:
        """Async version of list()"""
        if not self.async_mode:
            raise RuntimeError("Use sync methods with Client")
        
        data = await self.client._request("GET", "/companies/me/api-keys")
        return [APIKey(**item) for item in data]
    
    def create(self, name: str) -> APIKey:
        """Create a new API key"""
        if self.async_mode:
            raise RuntimeError("Use async methods with AsyncClient")
        
        data = self.client._request("POST", "/companies/me/api-keys", json={"name": name})
        return APIKey(**data)
    
    async def acreate(self, name: str) -> APIKey:
        """Async version of create()"""
        if not self.async_mode:
            raise RuntimeError("Use sync methods with Client")
        
        data = await self.client._request("POST", "/companies/me/api-keys", json={"name": name})
        return APIKey(**data)
    
    def revoke(self, key_id: str) -> None:
        """Revoke an API key"""
        if self.async_mode:
            raise RuntimeError("Use async methods with AsyncClient")
        
        self.client._request("DELETE", f"/companies/me/api-keys/{key_id}")
    
    async def arevoke(self, key_id: str) -> None:
        """Async version of revoke()"""
        if not self.async_mode:
            raise RuntimeError("Use sync methods with Client")
        
        await self.client._request("DELETE", f"/companies/me/api-keys/{key_id}")


class VendorKeyService:
    """Vendor key management service (BYOK)"""
    
    def __init__(self, client, async_mode: bool = False):
        self.client = client
        self.async_mode = async_mode
    
    def list(self) -> List[VendorKey]:
        """List all vendor keys"""
        if self.async_mode:
            raise RuntimeError("Use async methods with AsyncClient")
        
        data = self.client._request("GET", "/companies/me/vendor-keys")
        return [VendorKey(**item) for item in data]
    
    async def alist(self) -> List[VendorKey]:
        """Async version of list()"""
        if not self.async_mode:
            raise RuntimeError("Use sync methods with Client")
        
        data = await self.client._request("GET", "/companies/me/vendor-keys")
        return [VendorKey(**item) for item in data]
    
    def store(self, vendor: str, api_key: str, description: Optional[str] = None) -> VendorKey:
        """Store a vendor API key"""
        if self.async_mode:
            raise RuntimeError("Use async methods with AsyncClient")
        
        payload = {"vendor": vendor, "api_key": api_key}
        if description:
            payload["description"] = description
        
        data = self.client._request("POST", "/companies/me/vendor-keys", json=payload)
        return VendorKey(**data)
    
    async def astore(self, vendor: str, api_key: str, description: Optional[str] = None) -> VendorKey:
        """Async version of store()"""
        if not self.async_mode:
            raise RuntimeError("Use sync methods with Client")
        
        payload = {"vendor": vendor, "api_key": api_key}
        if description:
            payload["description"] = description
        
        data = await self.client._request("POST", "/companies/me/vendor-keys", json=payload)
        return VendorKey(**data)
    
    def update(self, vendor: str, api_key: str, description: Optional[str] = None) -> VendorKey:
        """Update a vendor API key"""
        if self.async_mode:
            raise RuntimeError("Use async methods with AsyncClient")
        
        payload = {"vendor": vendor, "api_key": api_key}
        if description:
            payload["description"] = description
        
        data = self.client._request("PUT", f"/companies/me/vendor-keys/{vendor}", json=payload)
        return VendorKey(**data)
    
    async def aupdate(self, vendor: str, api_key: str, description: Optional[str] = None) -> VendorKey:
        """Async version of update()"""
        if not self.async_mode:
            raise RuntimeError("Use sync methods with Client")
        
        payload = {"vendor": vendor, "api_key": api_key}
        if description:
            payload["description"] = description
        
        data = await self.client._request("PUT", f"/companies/me/vendor-keys/{vendor}", json=payload)
        return VendorKey(**data)
    
    def remove(self, vendor: str) -> None:
        """Remove a vendor API key"""
        if self.async_mode:
            raise RuntimeError("Use async methods with AsyncClient")
        
        self.client._request("DELETE", f"/companies/me/vendor-keys/{vendor}")
    
    async def aremove(self, vendor: str) -> None:
        """Async version of remove()"""
        if not self.async_mode:
            raise RuntimeError("Use sync methods with Client")
        
        await self.client._request("DELETE", f"/companies/me/vendor-keys/{vendor}")


class AnalyticsService:
    """Analytics and reporting service"""
    
    def __init__(self, client, async_mode: bool = False):
        self.client = client
        self.async_mode = async_mode
    
    def get_usage(
        self,
        period: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        vendors: Optional[List[str]] = None,
        models: Optional[List[str]] = None,
        group_by: str = "day"
    ) -> UsageAnalytics:
        """Get usage analytics"""
        if self.async_mode:
            raise RuntimeError("Use async methods with AsyncClient")
        
        params = {}
        if period:
            params["period"] = period
        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()
        if vendors:
            params["vendors"] = ",".join(vendors)
        if models:
            params["models"] = ",".join(models)
        if group_by:
            params["group_by"] = group_by
        
        data = self.client._request("GET", "/companies/me/analytics/usage", params=params)
        return UsageAnalytics(**data)
    
    async def aget_usage(
        self,
        period: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        vendors: Optional[List[str]] = None,
        models: Optional[List[str]] = None,
        group_by: str = "day"
    ) -> UsageAnalytics:
        """Async version of get_usage()"""
        if not self.async_mode:
            raise RuntimeError("Use sync methods with Client")
        
        params = {}
        if period:
            params["period"] = period
        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()
        if vendors:
            params["vendors"] = ",".join(vendors)
        if models:
            params["models"] = ",".join(models)
        if group_by:
            params["group_by"] = group_by
        
        data = await self.client._request("GET", "/companies/me/analytics/usage", params=params)
        return UsageAnalytics(**data)
    
    def get_costs(self, period: Optional[str] = None, **kwargs) -> CostAnalytics:
        """Get cost analytics"""
        if self.async_mode:
            raise RuntimeError("Use async methods with AsyncClient")
        
        params = {"period": period} if period else {}
        params.update(kwargs)
        
        data = self.client._request("GET", "/companies/me/analytics/costs", params=params)
        return CostAnalytics(**data)
    
    async def aget_costs(self, period: Optional[str] = None, **kwargs) -> CostAnalytics:
        """Async version of get_costs()"""
        if not self.async_mode:
            raise RuntimeError("Use sync methods with Client")
        
        params = {"period": period} if period else {}
        params.update(kwargs)
        
        data = await self.client._request("GET", "/companies/me/analytics/costs", params=params)
        return CostAnalytics(**data)
    
    def get_performance(self, period: Optional[str] = None, **kwargs) -> PerformanceAnalytics:
        """Get performance analytics"""
        if self.async_mode:
            raise RuntimeError("Use async methods with AsyncClient")
        
        params = {"period": period} if period else {}
        params.update(kwargs)
        
        data = self.client._request("GET", "/companies/me/analytics/performance", params=params)
        return PerformanceAnalytics(**data)
    
    async def aget_performance(self, period: Optional[str] = None, **kwargs) -> PerformanceAnalytics:
        """Async version of get_performance()"""
        if not self.async_mode:
            raise RuntimeError("Use sync methods with Client")
        
        params = {"period": period} if period else {}
        params.update(kwargs)
        
        data = await self.client._request("GET", "/companies/me/analytics/performance", params=params)
        return PerformanceAnalytics(**data)
    
    def get_recommendations(self, min_savings: float = 10.0) -> List[CostOptimizationRecommendation]:
        """Get cost optimization recommendations"""
        if self.async_mode:
            raise RuntimeError("Use async methods with AsyncClient")
        
        params = {"min_savings": min_savings}
        data = self.client._request("GET", "/companies/me/analytics/recommendations", params=params)
        return [CostOptimizationRecommendation(**rec) for rec in data.get("recommendations", [])]
    
    async def aget_recommendations(self, min_savings: float = 10.0) -> List[CostOptimizationRecommendation]:
        """Async version of get_recommendations()"""
        if not self.async_mode:
            raise RuntimeError("Use sync methods with Client")
        
        params = {"min_savings": min_savings}
        data = await self.client._request("GET", "/companies/me/analytics/recommendations", params=params)
        return [CostOptimizationRecommendation(**rec) for rec in data.get("recommendations", [])]
    
    def export(
        self,
        export_type: str,
        format: str = "json",
        period: Optional[str] = None,
        **kwargs
    ) -> str:
        """Export analytics data"""
        if self.async_mode:
            raise RuntimeError("Use async methods with AsyncClient")
        
        payload = {
            "export_type": export_type,
            "format": format,
            "date_range": {"period": period or "30d"},
            **kwargs
        }
        
        # This would return raw export data as string
        response = self.client._client.post(
            self.client._build_url("/companies/me/analytics/export"),
            json=payload
        )
        
        if response.status_code == 200:
            return response.text
        else:
            self.client._handle_response(response)
    
    async def aexport(
        self,
        export_type: str,
        format: str = "json",
        period: Optional[str] = None,
        **kwargs
    ) -> str:
        """Async version of export()"""
        if not self.async_mode:
            raise RuntimeError("Use sync methods with Client")
        
        payload = {
            "export_type": export_type,
            "format": format,
            "date_range": {"period": period or "30d"},
            **kwargs
        }
        
        # This would return raw export data as string
        response = await self.client._client.post(
            self.client._build_url("/companies/me/analytics/export"),
            json=payload
        )
        
        if response.status_code == 200:
            return response.text
        else:
            self.client._handle_response(response)