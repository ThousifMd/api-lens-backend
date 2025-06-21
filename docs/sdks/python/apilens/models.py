"""
API Lens Python SDK - Data Models

This module contains Pydantic models for all API Lens data structures.
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class CompanyTier(str, Enum):
    """Company subscription tiers"""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class VendorType(str, Enum):
    """Supported AI vendors"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    COHERE = "cohere"
    HUGGINGFACE = "huggingface"


class Company(BaseModel):
    """Company profile model"""
    id: str
    name: str
    description: Optional[str] = None
    tier: CompanyTier
    is_active: bool = True
    contact_email: Optional[str] = None
    webhook_url: Optional[str] = None
    current_month_requests: int = 0
    current_month_cost: float = 0.0
    monthly_budget_limit: Optional[float] = None
    monthly_request_limit: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class APIKey(BaseModel):
    """API key model"""
    id: str
    name: str
    secret_key: Optional[str] = None  # Only included when first created
    key_preview: str  # First 8 and last 4 characters
    is_active: bool = True
    last_used_at: Optional[datetime] = None
    usage_count: int = 0
    created_at: datetime
    expires_at: Optional[datetime] = None


class VendorKey(BaseModel):
    """Vendor API key model (BYOK)"""
    vendor: VendorType
    key_preview: str  # Encrypted key preview
    description: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime] = None
    usage_count: int = 0


class UsageMetrics(BaseModel):
    """Usage metrics for a specific period"""
    requests: int = 0
    tokens: int = 0
    cost: float = 0.0


class VendorBreakdown(BaseModel):
    """Usage breakdown by vendor"""
    vendor: VendorType
    requests: int = 0
    tokens: int = 0
    cost: float = 0.0
    models: List[Dict[str, Any]] = []


class ModelBreakdown(BaseModel):
    """Usage breakdown by AI model"""
    vendor: VendorType
    model: str
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    average_cost_per_request: float = 0.0


class TimeSeriesPoint(BaseModel):
    """Time series data point"""
    timestamp: datetime
    requests: int = 0
    tokens: int = 0
    cost: float = 0.0


class UsageAnalytics(BaseModel):
    """Comprehensive usage analytics"""
    period: str
    start_date: datetime
    end_date: datetime
    total_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    average_requests_per_day: float = 0.0
    average_cost_per_request: float = 0.0
    peak_requests_per_hour: int = 0
    vendor_breakdown: List[VendorBreakdown] = []
    ai_model_breakdown: List[ModelBreakdown] = []
    time_series: List[TimeSeriesPoint] = []


class CostBreakdown(BaseModel):
    """Cost breakdown by vendor or model"""
    vendor: VendorType
    model: Optional[str] = None
    total_cost: float = 0.0
    cost_percentage: float = 0.0
    requests: int = 0
    cost_per_request: float = 0.0
    cost_per_token: float = 0.0


class CostTrend(BaseModel):
    """Cost trend analysis"""
    current_period_cost: float = 0.0
    previous_period_cost: float = 0.0
    cost_change: float = 0.0
    cost_change_percentage: float = 0.0
    trend_direction: str = "stable"  # up, down, stable


class CostAnalytics(BaseModel):
    """Comprehensive cost analytics"""
    period: str
    start_date: datetime
    end_date: datetime
    total_cost: float = 0.0
    average_cost_per_request: float = 0.0
    cost_trend_percentage: float = 0.0
    projected_monthly_cost: float = 0.0
    cost_efficiency_score: float = 0.0
    vendor_costs: List[CostBreakdown] = []
    ai_model_costs: List[CostBreakdown] = []
    cost_trend: CostTrend
    daily_costs: List[TimeSeriesPoint] = []


class VendorPerformance(BaseModel):
    """Performance metrics by vendor"""
    vendor: VendorType
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    success_rate_percentage: float = 0.0
    error_rate_percentage: float = 0.0
    requests: int = 0


class PerformanceAnalytics(BaseModel):
    """Comprehensive performance analytics"""
    period: str
    start_date: datetime
    end_date: datetime
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    success_rate_percentage: float = 0.0
    error_rate_percentage: float = 0.0
    vendor_performance: List[VendorPerformance] = []
    latency_trend: List[TimeSeriesPoint] = []


class OptimizationRecommendation(BaseModel):
    """Individual cost optimization recommendation"""
    id: str
    title: str
    description: str
    category: str  # model_optimization, usage_pattern, cost_reduction
    impact_level: str  # high, medium, low
    potential_savings: float = 0.0
    savings_percentage: float = 0.0
    confidence_score: float = 0.0
    implementation_effort: str  # easy, medium, hard
    actionable_steps: List[str] = []
    affected_vendors: List[VendorType] = []
    affected_models: List[str] = []
    created_at: datetime


class CostOptimizationRecommendation(BaseModel):
    """Complete cost optimization analysis"""
    total_potential_savings: float = 0.0
    total_savings_percentage: float = 0.0
    recommendations: List[OptimizationRecommendation] = []
    analysis_date: datetime
    period_analyzed: str


class ExportRequest(BaseModel):
    """Data export request"""
    export_type: str  # usage, costs, performance, recommendations
    format: str = "json"  # json, csv, excel
    date_range: Dict[str, Any]
    filters: Optional[Dict[str, Any]] = None
    include_raw_data: bool = False


class SystemHealth(BaseModel):
    """System health status"""
    status: str  # healthy, degraded, down
    version: str
    uptime_seconds: int
    database_status: str
    redis_status: str
    vendor_api_status: Dict[str, str]
    response_time_ms: float
    active_companies: int
    total_requests_24h: int
    error_rate_24h: float


class RateLimit(BaseModel):
    """Rate limit information"""
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    current_usage: Dict[str, int]
    reset_times: Dict[str, datetime]


class AuthInfo(BaseModel):
    """Authentication information"""
    valid: bool
    company_id: str
    company_name: str
    tier: CompanyTier
    rate_limits: RateLimit
    expires_at: Optional[datetime] = None


class ErrorDetail(BaseModel):
    """API error detail"""
    error: str
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    timestamp: datetime


class PaginatedResponse(BaseModel):
    """Paginated API response"""
    items: List[Any]
    total: int
    page: int = 1
    per_page: int = 100
    total_pages: int
    has_next: bool
    has_prev: bool


# Response wrapper models
class CompanyResponse(BaseModel):
    """Company API response"""
    company: Company


class APIKeysResponse(BaseModel):
    """API keys list response"""
    api_keys: List[APIKey]


class VendorKeysResponse(BaseModel):
    """Vendor keys list response"""
    vendor_keys: List[VendorKey]


class AnalyticsResponse(BaseModel):
    """Analytics API response wrapper"""
    analytics: Union[UsageAnalytics, CostAnalytics, PerformanceAnalytics]
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class RecommendationsResponse(BaseModel):
    """Recommendations API response"""
    recommendations: List[OptimizationRecommendation]
    total_potential_savings: float = 0.0
    analysis_date: datetime = Field(default_factory=datetime.utcnow)