"""
API Lens Python SDK

The official Python client library for API Lens, providing easy integration
with AI API cost tracking and analytics.
"""

__version__ = "1.0.0"
__author__ = "API Lens Team"
__email__ = "support@apilens.dev"
__license__ = "MIT"

from .client import Client, AsyncClient
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

__all__ = [
    # Core client classes
    "Client",
    "AsyncClient",
    
    # Exception classes
    "APILensError",
    "AuthenticationError", 
    "RateLimitError",
    "ServerError",
    "ValidationError",
    "NotFoundError",
    
    # Data models
    "Company",
    "APIKey",
    "VendorKey", 
    "UsageAnalytics",
    "CostAnalytics",
    "PerformanceAnalytics",
    "CostOptimizationRecommendation",
]