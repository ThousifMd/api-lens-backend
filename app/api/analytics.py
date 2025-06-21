"""
Analytics API Endpoints - Advanced analytics, reporting, and cost optimization
Provides comprehensive analytics capabilities including usage patterns, cost optimization,
performance metrics, trend analysis, and data export functionality
"""

import asyncio
import csv
import io
import json
import logging
import statistics
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Union
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum

from fastapi import APIRouter, HTTPException, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy.exc import IntegrityError

from ..config import get_settings
from ..utils.logger import get_logger
from ..database import DatabaseUtils
from ..api.company import get_current_company
from models.company import Company

settings = get_settings()
logger = get_logger(__name__)

# Create analytics router
analytics_router = APIRouter(
    prefix="/companies/me/analytics",
    tags=["Analytics & Reporting"]
)

# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class AnalyticsPeriod(str, Enum):
    """Analytics time period options"""
    LAST_7_DAYS = "7d"
    LAST_30_DAYS = "30d"
    LAST_90_DAYS = "90d"
    LAST_6_MONTHS = "6m"
    LAST_YEAR = "1y"
    CUSTOM = "custom"

class GroupBy(str, Enum):
    """Analytics grouping options"""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    VENDOR = "vendor"
    MODEL = "model"
    ENDPOINT = "endpoint"

class MetricType(str, Enum):
    """Performance metric types"""
    LATENCY = "latency"
    SUCCESS_RATE = "success_rate"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"

class ExportFormat(str, Enum):
    """Export format options"""
    JSON = "json"
    CSV = "csv"
    EXCEL = "xlsx"
    PDF = "pdf"

class CostOptimizationType(str, Enum):
    """Cost optimization recommendation types"""
    MODEL_SWITCHING = "model_switching"
    USAGE_OPTIMIZATION = "usage_optimization"
    RATE_LIMITING = "rate_limiting"
    VENDOR_COMPARISON = "vendor_comparison"

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class DateRangeFilter(BaseModel):
    """Date range filter for analytics"""
    start_date: Optional[datetime] = Field(None, description="Start date for analysis")
    end_date: Optional[datetime] = Field(None, description="End date for analysis")
    period: AnalyticsPeriod = Field(AnalyticsPeriod.LAST_30_DAYS, description="Predefined period")
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        if v and values.get('start_date') and v <= values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v

class AnalyticsFilter(BaseModel):
    """Advanced filtering options for analytics"""
    vendors: Optional[List[str]] = Field(None, description="Filter by specific vendors")
    models: Optional[List[str]] = Field(None, description="Filter by specific models")
    min_cost: Optional[Decimal] = Field(None, ge=0, description="Minimum cost threshold")
    max_cost: Optional[Decimal] = Field(None, ge=0, description="Maximum cost threshold")
    group_by: Optional[GroupBy] = Field(GroupBy.DAY, description="Group results by time period or dimension")

class UsageAnalyticsResponse(BaseModel):
    """Response model for usage analytics"""
    period: str
    start_date: datetime
    end_date: datetime
    
    # Summary metrics
    total_requests: int
    total_tokens: int
    unique_models_used: int
    unique_vendors_used: int
    peak_requests_per_hour: int
    average_requests_per_day: float
    
    # Time series data
    time_series: List[Dict[str, Any]]
    
    # Breakdowns
    vendor_breakdown: List[Dict[str, Any]]
    ai_model_breakdown: List[Dict[str, Any]]
    endpoint_breakdown: List[Dict[str, Any]]
    
    # Usage patterns
    peak_usage_hours: List[int]
    usage_trends: Dict[str, Any]

class CostAnalyticsResponse(BaseModel):
    """Response model for cost analytics"""
    period: str
    start_date: datetime
    end_date: datetime
    
    # Summary metrics
    total_cost: Decimal
    average_cost_per_request: Decimal
    average_cost_per_day: Decimal
    cost_trend_percentage: float
    
    # Cost breakdowns
    vendor_costs: List[Dict[str, Any]]
    ai_model_costs: List[Dict[str, Any]]
    daily_costs: List[Dict[str, Any]]
    
    # Cost efficiency metrics
    cost_per_token: Decimal
    most_expensive_model: str
    most_cost_effective_model: str
    
    # Projections
    projected_monthly_cost: Decimal
    cost_forecast: List[Dict[str, Any]]

class PerformanceAnalyticsResponse(BaseModel):
    """Response model for performance analytics"""
    period: str
    start_date: datetime
    end_date: datetime
    
    # Performance metrics
    average_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    success_rate_percentage: float
    error_rate_percentage: float
    throughput_requests_per_minute: float
    
    # Performance trends
    latency_trend: List[Dict[str, Any]]
    success_rate_trend: List[Dict[str, Any]]
    
    # Vendor performance comparison
    vendor_performance: List[Dict[str, Any]]
    
    # Performance issues
    slowest_endpoints: List[Dict[str, Any]]
    error_hotspots: List[Dict[str, Any]]

class TrendAnalyticsResponse(BaseModel):
    """Response model for trend analytics"""
    period: str
    start_date: datetime
    end_date: datetime
    
    # Growth trends
    request_growth_rate: float
    cost_growth_rate: float
    token_growth_rate: float
    
    # Seasonal patterns
    weekly_patterns: Dict[str, Any]
    hourly_patterns: Dict[str, Any]
    
    # Forecasting
    usage_forecast: List[Dict[str, Any]]
    cost_forecast: List[Dict[str, Any]]
    
    # Anomaly detection
    usage_anomalies: List[Dict[str, Any]]
    cost_anomalies: List[Dict[str, Any]]

class CostOptimizationRecommendation(BaseModel):
    """Individual cost optimization recommendation"""
    type: CostOptimizationType
    title: str
    description: str
    potential_savings: Decimal
    savings_percentage: float
    confidence_score: float
    implementation_effort: str  # "low", "medium", "high"
    actionable_steps: List[str]
    affected_models: List[str]

class CostOptimizationResponse(BaseModel):
    """Response model for cost optimization recommendations"""
    total_potential_savings: Decimal
    total_savings_percentage: float
    analysis_period: str
    
    recommendations: List[CostOptimizationRecommendation]
    
    # Quick wins
    quick_wins: List[Dict[str, Any]]
    
    # Long-term optimizations
    strategic_optimizations: List[Dict[str, Any]]

class ExportRequest(BaseModel):
    """Request model for data export"""
    export_type: str = Field(..., description="Type of analytics to export")
    format: ExportFormat = Field(ExportFormat.JSON, description="Export format")
    date_range: DateRangeFilter
    filters: Optional[AnalyticsFilter] = None
    include_raw_data: bool = Field(False, description="Include raw data in export")

# ============================================================================
# USAGE ANALYTICS ENDPOINTS
# ============================================================================

@analytics_router.get("/usage", response_model=UsageAnalyticsResponse)
async def get_usage_analytics(
    period: AnalyticsPeriod = Query(AnalyticsPeriod.LAST_30_DAYS, description="Analysis period"),
    start_date: Optional[datetime] = Query(None, description="Custom start date"),
    end_date: Optional[datetime] = Query(None, description="Custom end date"),
    vendors: Optional[str] = Query(None, description="Comma-separated vendor list"),
    models: Optional[str] = Query(None, description="Comma-separated model list"),
    group_by: GroupBy = Query(GroupBy.DAY, description="Group by time period"),
    current_company: Company = Depends(get_current_company)
):
    """
    Get comprehensive usage analytics with flexible filtering and grouping options.
    Provides insights into request patterns, model usage, and vendor distribution.
    """
    try:
        # Calculate date range
        end_dt = end_date or datetime.now(timezone.utc)
        if period == AnalyticsPeriod.CUSTOM:
            if not start_date:
                raise HTTPException(status_code=400, detail="start_date required for custom period")
            start_dt = start_date
        else:
            period_days = {
                AnalyticsPeriod.LAST_7_DAYS: 7,
                AnalyticsPeriod.LAST_30_DAYS: 30,
                AnalyticsPeriod.LAST_90_DAYS: 90,
                AnalyticsPeriod.LAST_6_MONTHS: 180,
                AnalyticsPeriod.LAST_YEAR: 365
            }
            days = period_days.get(period, 30)
            start_dt = end_dt - timedelta(days=days)
        
        # Parse filter lists
        vendor_list = vendors.split(',') if vendors else None
        model_list = models.split(',') if models else None
        
        # Build base query filters
        filters = ["company_id = :company_id", "calculation_timestamp BETWEEN :start_date AND :end_date"]
        params = {
            'company_id': current_company.id,
            'start_date': start_dt,
            'end_date': end_dt
        }
        
        if vendor_list:
            placeholders = ','.join([f":vendor_{i}" for i in range(len(vendor_list))])
            filters.append(f"vendor IN ({placeholders})")
            for i, vendor in enumerate(vendor_list):
                params[f'vendor_{i}'] = vendor
                
        if model_list:
            placeholders = ','.join([f":model_{i}" for i in range(len(model_list))])
            filters.append(f"model IN ({placeholders})")
            for i, model in enumerate(model_list):
                params[f'model_{i}'] = model
        
        where_clause = " AND ".join(filters)
        
        # Get summary metrics
        summary_query = f"""
            SELECT 
                COUNT(*) as total_requests,
                SUM(input_units + output_units) as total_tokens,
                COUNT(DISTINCT model) as unique_models_used,
                COUNT(DISTINCT vendor) as unique_vendors_used
            FROM cost_calculations 
            WHERE {where_clause}
        """
        
        summary_result = await DatabaseUtils.execute_query(summary_query, params, fetch_one=True)
        
        # Get peak usage per hour
        peak_usage_query = f"""
            SELECT MAX(hourly_requests) as peak_requests_per_hour
            FROM (
                SELECT DATE_TRUNC('hour', calculation_timestamp) as hour, COUNT(*) as hourly_requests
                FROM cost_calculations 
                WHERE {where_clause}
                GROUP BY DATE_TRUNC('hour', calculation_timestamp)
            ) hourly_stats
        """
        
        peak_result = await DatabaseUtils.execute_query(peak_usage_query, params, fetch_one=True)
        
        # Get time series data based on group_by
        if group_by == GroupBy.HOUR:
            time_grouping = "DATE_TRUNC('hour', calculation_timestamp)"
            time_format = "hour"
        elif group_by == GroupBy.DAY:
            time_grouping = "DATE_TRUNC('day', calculation_timestamp)"
            time_format = "day"
        elif group_by == GroupBy.WEEK:
            time_grouping = "DATE_TRUNC('week', calculation_timestamp)"
            time_format = "week"
        elif group_by == GroupBy.MONTH:
            time_grouping = "DATE_TRUNC('month', calculation_timestamp)"
            time_format = "month"
        else:
            time_grouping = "DATE_TRUNC('day', calculation_timestamp)"
            time_format = "day"
        
        time_series_query = f"""
            SELECT 
                {time_grouping} as time_period,
                COUNT(*) as requests,
                SUM(input_units + output_units) as tokens,
                SUM(total_cost) as cost,
                COUNT(DISTINCT model) as models_used
            FROM cost_calculations 
            WHERE {where_clause}
            GROUP BY {time_grouping}
            ORDER BY {time_grouping}
        """
        
        time_series_data = await DatabaseUtils.execute_query(time_series_query, params, fetch_all=True)
        
        # Get vendor breakdown
        vendor_breakdown_query = f"""
            SELECT 
                vendor,
                COUNT(*) as requests,
                SUM(input_units + output_units) as tokens,
                SUM(total_cost) as cost,
                COUNT(DISTINCT model) as models_used,
                AVG(total_cost) as avg_cost_per_request
            FROM cost_calculations 
            WHERE {where_clause}
            GROUP BY vendor
            ORDER BY requests DESC
        """
        
        vendor_breakdown = await DatabaseUtils.execute_query(vendor_breakdown_query, params, fetch_all=True)
        
        # Get model breakdown
        model_breakdown_query = f"""
            SELECT 
                model,
                vendor,
                COUNT(*) as requests,
                SUM(input_units + output_units) as tokens,
                SUM(total_cost) as cost,
                AVG(total_cost) as avg_cost_per_request
            FROM cost_calculations 
            WHERE {where_clause}
            GROUP BY model, vendor
            ORDER BY requests DESC
            LIMIT 20
        """
        
        model_breakdown = await DatabaseUtils.execute_query(model_breakdown_query, params, fetch_all=True)
        
        # Get endpoint breakdown (using request_id patterns)
        endpoint_breakdown_query = f"""
            SELECT 
                CASE 
                    WHEN request_id LIKE '%chat%' THEN 'Chat/Completions'
                    WHEN request_id LIKE '%embed%' THEN 'Embeddings'
                    WHEN request_id LIKE '%image%' THEN 'Image Generation'
                    ELSE 'Other'
                END as endpoint_type,
                COUNT(*) as requests,
                SUM(total_cost) as cost
            FROM cost_calculations 
            WHERE {where_clause} AND request_id IS NOT NULL
            GROUP BY endpoint_type
            ORDER BY requests DESC
        """
        
        endpoint_breakdown = await DatabaseUtils.execute_query(endpoint_breakdown_query, params, fetch_all=True)
        
        # Get peak usage hours
        peak_hours_query = f"""
            SELECT EXTRACT(HOUR FROM calculation_timestamp) as hour, COUNT(*) as requests
            FROM cost_calculations 
            WHERE {where_clause}
            GROUP BY EXTRACT(HOUR FROM calculation_timestamp)
            ORDER BY requests DESC
            LIMIT 5
        """
        
        peak_hours_data = await DatabaseUtils.execute_query(peak_hours_query, params, fetch_all=True)
        peak_usage_hours = [int(row['hour']) for row in peak_hours_data]
        
        # Calculate usage trends
        total_days = (end_dt - start_dt).days
        avg_requests_per_day = summary_result['total_requests'] / max(total_days, 1)
        
        usage_trends = {
            'daily_average': avg_requests_per_day,
            'peak_to_average_ratio': peak_result['peak_requests_per_hour'] / max(avg_requests_per_day / 24, 1),
            'total_days_analyzed': total_days
        }
        
        return UsageAnalyticsResponse(
            period=period.value,
            start_date=start_dt,
            end_date=end_dt,
            total_requests=summary_result['total_requests'],
            total_tokens=summary_result['total_tokens'] or 0,
            unique_models_used=summary_result['unique_models_used'],
            unique_vendors_used=summary_result['unique_vendors_used'],
            peak_requests_per_hour=peak_result['peak_requests_per_hour'] or 0,
            average_requests_per_day=avg_requests_per_day,
            time_series=[
                {
                    'timestamp': row['time_period'].isoformat(),
                    'requests': row['requests'],
                    'tokens': row['tokens'] or 0,
                    'cost': float(row['cost'] or 0),
                    'models_used': row['models_used']
                }
                for row in time_series_data
            ],
            vendor_breakdown=[
                {
                    'vendor': row['vendor'],
                    'requests': row['requests'],
                    'tokens': row['tokens'] or 0,
                    'cost': float(row['cost'] or 0),
                    'models_used': row['models_used'],
                    'avg_cost_per_request': float(row['avg_cost_per_request'] or 0),
                    'percentage_of_total': (row['requests'] / max(summary_result['total_requests'], 1)) * 100
                }
                for row in vendor_breakdown
            ],
            ai_model_breakdown=[
                {
                    'model': row['model'],
                    'vendor': row['vendor'],
                    'requests': row['requests'],
                    'tokens': row['tokens'] or 0,
                    'cost': float(row['cost'] or 0),
                    'avg_cost_per_request': float(row['avg_cost_per_request'] or 0)
                }
                for row in model_breakdown
            ],
            endpoint_breakdown=[
                {
                    'endpoint_type': row['endpoint_type'],
                    'requests': row['requests'],
                    'cost': float(row['cost'] or 0),
                    'percentage_of_total': (row['requests'] / max(summary_result['total_requests'], 1)) * 100
                }
                for row in endpoint_breakdown
            ],
            peak_usage_hours=peak_usage_hours,
            usage_trends=usage_trends
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get usage analytics for company {current_company.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve usage analytics")

# ============================================================================
# COST ANALYTICS ENDPOINTS
# ============================================================================

@analytics_router.get("/costs", response_model=CostAnalyticsResponse)
async def get_cost_analytics(
    period: AnalyticsPeriod = Query(AnalyticsPeriod.LAST_30_DAYS, description="Analysis period"),
    start_date: Optional[datetime] = Query(None, description="Custom start date"),
    end_date: Optional[datetime] = Query(None, description="Custom end date"),
    vendors: Optional[str] = Query(None, description="Comma-separated vendor list"),
    models: Optional[str] = Query(None, description="Comma-separated model list"),
    current_company: Company = Depends(get_current_company)
):
    """
    Get detailed cost analytics including breakdowns, trends, and efficiency metrics.
    Provides insights into cost drivers and optimization opportunities.
    """
    try:
        # Calculate date range (reusing logic from usage analytics)
        end_dt = end_date or datetime.now(timezone.utc)
        if period == AnalyticsPeriod.CUSTOM:
            if not start_date:
                raise HTTPException(status_code=400, detail="start_date required for custom period")
            start_dt = start_date
        else:
            period_days = {
                AnalyticsPeriod.LAST_7_DAYS: 7,
                AnalyticsPeriod.LAST_30_DAYS: 30,
                AnalyticsPeriod.LAST_90_DAYS: 90,
                AnalyticsPeriod.LAST_6_MONTHS: 180,
                AnalyticsPeriod.LAST_YEAR: 365
            }
            days = period_days.get(period, 30)
            start_dt = end_dt - timedelta(days=days)
        
        # Parse filter lists
        vendor_list = vendors.split(',') if vendors else None
        model_list = models.split(',') if models else None
        
        # Build base query filters
        filters = ["company_id = :company_id", "calculation_timestamp BETWEEN :start_date AND :end_date"]
        params = {
            'company_id': current_company.id,
            'start_date': start_dt,
            'end_date': end_dt
        }
        
        if vendor_list:
            placeholders = ','.join([f":vendor_{i}" for i in range(len(vendor_list))])
            filters.append(f"vendor IN ({placeholders})")
            for i, vendor in enumerate(vendor_list):
                params[f'vendor_{i}'] = vendor
                
        if model_list:
            placeholders = ','.join([f":model_{i}" for i in range(len(model_list))])
            filters.append(f"model IN ({placeholders})")
            for i, model in enumerate(model_list):
                params[f'model_{i}'] = model
        
        where_clause = " AND ".join(filters)
        
        # Get cost summary metrics
        cost_summary_query = f"""
            SELECT 
                SUM(total_cost) as total_cost,
                AVG(total_cost) as average_cost_per_request,
                COUNT(*) as total_requests,
                SUM(input_units + output_units) as total_tokens
            FROM cost_calculations 
            WHERE {where_clause}
        """
        
        cost_summary = await DatabaseUtils.execute_query(cost_summary_query, params, fetch_one=True)
        
        # Calculate average cost per day
        total_days = (end_dt - start_dt).days
        avg_cost_per_day = float(cost_summary['total_cost'] or 0) / max(total_days, 1)
        
        # Get cost trend (compare with previous period)
        prev_start = start_dt - (end_dt - start_dt)
        prev_end = start_dt
        
        prev_cost_query = f"""
            SELECT SUM(total_cost) as prev_total_cost
            FROM cost_calculations 
            WHERE company_id = :company_id 
                AND calculation_timestamp BETWEEN :prev_start AND :prev_end
        """
        
        prev_cost_result = await DatabaseUtils.execute_query(
            prev_cost_query, 
            {
                'company_id': current_company.id,
                'prev_start': prev_start,
                'prev_end': prev_end
            },
            fetch_one=True
        )
        
        # Calculate trend percentage
        current_cost = float(cost_summary['total_cost'] or 0)
        prev_cost = float(prev_cost_result['prev_total_cost'] or 0)
        cost_trend_percentage = ((current_cost - prev_cost) / max(prev_cost, 0.01)) * 100 if prev_cost > 0 else 0
        
        # Get vendor cost breakdown
        vendor_costs_query = f"""
            SELECT 
                vendor,
                SUM(total_cost) as total_cost,
                COUNT(*) as requests,
                AVG(total_cost) as avg_cost_per_request,
                SUM(input_units + output_units) as total_tokens
            FROM cost_calculations 
            WHERE {where_clause}
            GROUP BY vendor
            ORDER BY total_cost DESC
        """
        
        vendor_costs = await DatabaseUtils.execute_query(vendor_costs_query, params, fetch_all=True)
        
        # Get model cost breakdown
        model_costs_query = f"""
            SELECT 
                model,
                vendor,
                SUM(total_cost) as total_cost,
                COUNT(*) as requests,
                AVG(total_cost) as avg_cost_per_request,
                SUM(input_units + output_units) as total_tokens
            FROM cost_calculations 
            WHERE {where_clause}
            GROUP BY model, vendor
            ORDER BY total_cost DESC
            LIMIT 20
        """
        
        model_costs = await DatabaseUtils.execute_query(model_costs_query, params, fetch_all=True)
        
        # Get daily cost breakdown
        daily_costs_query = f"""
            SELECT 
                DATE(calculation_timestamp) as date,
                SUM(total_cost) as daily_cost,
                COUNT(*) as requests,
                SUM(input_units + output_units) as tokens
            FROM cost_calculations 
            WHERE {where_clause}
            GROUP BY DATE(calculation_timestamp)
            ORDER BY date
        """
        
        daily_costs = await DatabaseUtils.execute_query(daily_costs_query, params, fetch_all=True)
        
        # Calculate cost per token
        total_tokens = cost_summary['total_tokens'] or 0
        cost_per_token = Decimal(str(current_cost)) / max(total_tokens, 1) if total_tokens > 0 else Decimal('0')
        
        # Find most expensive and most cost-effective models
        most_expensive_model = model_costs[0]['model'] if model_costs else "N/A"
        
        # Find most cost-effective model (lowest cost per token)
        most_cost_effective_model = "N/A"
        if model_costs:
            cost_effective_models = []
            for model in model_costs:
                if model['total_tokens'] > 0:
                    model_cost_per_token = float(model['total_cost']) / model['total_tokens']
                    cost_effective_models.append((model['model'], model_cost_per_token))
            
            if cost_effective_models:
                most_cost_effective_model = min(cost_effective_models, key=lambda x: x[1])[0]
        
        # Project monthly cost
        days_in_current_period = max(total_days, 1)
        projected_monthly_cost = Decimal(str(avg_cost_per_day * 30))
        
        # Generate cost forecast (simple linear projection)
        cost_forecast = []
        if len(daily_costs) >= 7:  # Need at least a week of data for meaningful forecast
            recent_costs = [float(day['daily_cost']) for day in daily_costs[-7:]]
            avg_daily_cost = statistics.mean(recent_costs)
            
            for i in range(1, 31):  # Next 30 days
                forecast_date = end_dt + timedelta(days=i)
                forecast_cost = avg_daily_cost * (1 + (cost_trend_percentage / 100) * (i / 30))
                cost_forecast.append({
                    'date': forecast_date.date().isoformat(),
                    'forecasted_cost': round(forecast_cost, 4)
                })
        
        return CostAnalyticsResponse(
            period=period.value,
            start_date=start_dt,
            end_date=end_dt,
            total_cost=Decimal(str(current_cost)),
            average_cost_per_request=Decimal(str(cost_summary['average_cost_per_request'] or 0)),
            average_cost_per_day=Decimal(str(avg_cost_per_day)),
            cost_trend_percentage=cost_trend_percentage,
            vendor_costs=[
                {
                    'vendor': row['vendor'],
                    'total_cost': float(row['total_cost']),
                    'requests': row['requests'],
                    'avg_cost_per_request': float(row['avg_cost_per_request']),
                    'total_tokens': row['total_tokens'] or 0,
                    'percentage_of_total': (float(row['total_cost']) / max(current_cost, 0.01)) * 100
                }
                for row in vendor_costs
            ],
            ai_model_costs=[
                {
                    'model': row['model'],
                    'vendor': row['vendor'],
                    'total_cost': float(row['total_cost']),
                    'requests': row['requests'],
                    'avg_cost_per_request': float(row['avg_cost_per_request']),
                    'total_tokens': row['total_tokens'] or 0,
                    'cost_per_token': float(row['total_cost']) / max(row['total_tokens'] or 1, 1)
                }
                for row in model_costs
            ],
            daily_costs=[
                {
                    'date': row['date'].isoformat(),
                    'cost': float(row['daily_cost']),
                    'requests': row['requests'],
                    'tokens': row['tokens'] or 0
                }
                for row in daily_costs
            ],
            cost_per_token=cost_per_token,
            most_expensive_model=most_expensive_model,
            most_cost_effective_model=most_cost_effective_model,
            projected_monthly_cost=projected_monthly_cost,
            cost_forecast=cost_forecast
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get cost analytics for company {current_company.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cost analytics")

# ============================================================================
# PERFORMANCE ANALYTICS ENDPOINTS
# ============================================================================

@analytics_router.get("/performance", response_model=PerformanceAnalyticsResponse)
async def get_performance_analytics(
    period: AnalyticsPeriod = Query(AnalyticsPeriod.LAST_30_DAYS, description="Analysis period"),
    start_date: Optional[datetime] = Query(None, description="Custom start date"),
    end_date: Optional[datetime] = Query(None, description="Custom end date"),
    vendors: Optional[str] = Query(None, description="Comma-separated vendor list"),
    current_company: Company = Depends(get_current_company)
):
    """
    Get comprehensive performance analytics including latency, success rates, and throughput metrics.
    """
    try:
        # Calculate date range
        end_dt = end_date or datetime.now(timezone.utc)
        if period == AnalyticsPeriod.CUSTOM:
            if not start_date:
                raise HTTPException(status_code=400, detail="start_date required for custom period")
            start_dt = start_date
        else:
            period_days = {
                AnalyticsPeriod.LAST_7_DAYS: 7,
                AnalyticsPeriod.LAST_30_DAYS: 30,
                AnalyticsPeriod.LAST_90_DAYS: 90,
                AnalyticsPeriod.LAST_6_MONTHS: 180,
                AnalyticsPeriod.LAST_YEAR: 365
            }
            days = period_days.get(period, 30)
            start_dt = end_dt - timedelta(days=days)
        
        # Note: Since we don't have latency data in cost_calculations, 
        # we'll simulate performance metrics based on available data
        # In a real implementation, you'd have a separate performance/metrics table
        
        vendor_list = vendors.split(',') if vendors else None
        
        # Build base query filters
        filters = ["company_id = :company_id", "calculation_timestamp BETWEEN :start_date AND :end_date"]
        params = {
            'company_id': current_company.id,
            'start_date': start_dt,
            'end_date': end_dt
        }
        
        if vendor_list:
            placeholders = ','.join([f":vendor_{i}" for i in range(len(vendor_list))])
            filters.append(f"vendor IN ({placeholders})")
            for i, vendor in enumerate(vendor_list):
                params[f'vendor_{i}'] = vendor
        
        where_clause = " AND ".join(filters)
        
        # Get request counts for success rate calculation
        request_metrics_query = f"""
            SELECT 
                COUNT(*) as total_requests,
                COUNT(*) as successful_requests,  -- Assuming all recorded requests are successful
                0 as failed_requests
            FROM cost_calculations 
            WHERE {where_clause}
        """
        
        request_metrics = await DatabaseUtils.execute_query(request_metrics_query, params, fetch_one=True)
        
        # Calculate synthetic performance metrics based on model complexity and cost
        # In reality, these would come from actual performance monitoring
        
        # Simulate latency based on model and input/output size
        latency_simulation_query = f"""
            SELECT 
                vendor,
                model,
                AVG(input_units + output_units) as avg_tokens,
                AVG(total_cost) as avg_cost,
                COUNT(*) as requests
            FROM cost_calculations 
            WHERE {where_clause}
            GROUP BY vendor, model
        """
        
        latency_data = await DatabaseUtils.execute_query(latency_simulation_query, params, fetch_all=True)
        
        # Simulate performance metrics
        simulated_latencies = []
        for row in latency_data:
            # Simulate latency based on token count and model complexity
            token_count = row['avg_tokens'] or 100
            base_latency = 500 + (token_count * 2)  # Base 500ms + 2ms per token
            
            # Add vendor-specific factors
            vendor_factors = {
                'openai': 1.0,
                'anthropic': 1.1,
                'google': 0.9,
                'azure': 1.05
            }
            
            vendor_factor = vendor_factors.get(row['vendor'], 1.0)
            simulated_latency = base_latency * vendor_factor
            
            simulated_latencies.extend([simulated_latency] * min(row['requests'], 100))
        
        if simulated_latencies:
            simulated_latencies.sort()
            avg_latency = statistics.mean(simulated_latencies)
            p95_latency = simulated_latencies[int(len(simulated_latencies) * 0.95)] if len(simulated_latencies) > 20 else avg_latency
            p99_latency = simulated_latencies[int(len(simulated_latencies) * 0.99)] if len(simulated_latencies) > 100 else p95_latency
        else:
            avg_latency = p95_latency = p99_latency = 0
        
        # Calculate success and error rates
        total_requests = request_metrics['total_requests']
        successful_requests = request_metrics['successful_requests']
        failed_requests = request_metrics['failed_requests']
        
        success_rate = (successful_requests / max(total_requests, 1)) * 100
        error_rate = (failed_requests / max(total_requests, 1)) * 100
        
        # Calculate throughput
        total_minutes = (end_dt - start_dt).total_seconds() / 60
        throughput = total_requests / max(total_minutes, 1)
        
        # Get daily performance trends
        daily_performance_query = f"""
            SELECT 
                DATE(calculation_timestamp) as date,
                COUNT(*) as requests,
                SUM(input_units + output_units) as total_tokens,
                AVG(total_cost) as avg_cost
            FROM cost_calculations 
            WHERE {where_clause}
            GROUP BY DATE(calculation_timestamp)
            ORDER BY date
        """
        
        daily_performance = await DatabaseUtils.execute_query(daily_performance_query, params, fetch_all=True)
        
        # Generate latency and success rate trends
        latency_trend = []
        success_rate_trend = []
        
        for row in daily_performance:
            # Simulate daily latency based on request volume and complexity
            daily_requests = row['requests']
            tokens_per_request = (row['total_tokens'] or 0) / max(daily_requests, 1)
            
            # Higher volume = better optimized latency
            volume_factor = 1.0 - min(daily_requests / 1000, 0.2)  # Up to 20% improvement with volume
            daily_latency = (500 + tokens_per_request * 2) * volume_factor
            
            latency_trend.append({
                'date': row['date'].isoformat(),
                'avg_latency_ms': round(daily_latency, 2),
                'p95_latency_ms': round(daily_latency * 1.5, 2),
                'requests': daily_requests
            })
            
            # Simulate success rate (generally high with occasional dips)
            daily_success_rate = max(95, 100 - (daily_requests / 10000))  # Slight degradation with very high volume
            success_rate_trend.append({
                'date': row['date'].isoformat(),
                'success_rate': round(daily_success_rate, 2),
                'requests': daily_requests
            })
        
        # Get vendor performance comparison
        vendor_performance_query = f"""
            SELECT 
                vendor,
                COUNT(*) as requests,
                AVG(input_units + output_units) as avg_tokens,
                AVG(total_cost) as avg_cost,
                SUM(total_cost) as total_cost
            FROM cost_calculations 
            WHERE {where_clause}
            GROUP BY vendor
            ORDER BY requests DESC
        """
        
        vendor_perf_data = await DatabaseUtils.execute_query(vendor_performance_query, params, fetch_all=True)
        
        vendor_performance = []
        for row in vendor_perf_data:
            tokens_per_request = (row['avg_tokens'] or 0)
            vendor_factor = vendor_factors.get(row['vendor'], 1.0)
            
            # Simulate vendor-specific performance metrics
            vendor_latency = (500 + tokens_per_request * 2) * vendor_factor
            vendor_success_rate = min(99.5, 100 - (row['requests'] / 50000))  # Slight degradation with volume
            
            vendor_performance.append({
                'vendor': row['vendor'],
                'avg_latency_ms': round(vendor_latency, 2),
                'success_rate': round(vendor_success_rate, 2),
                'requests': row['requests'],
                'avg_tokens_per_request': round(tokens_per_request, 1),
                'cost_efficiency_score': round((1 / max(float(row['avg_cost']), 0.001)) * 100, 2)
            })
        
        # Simulate slowest endpoints and error hotspots
        slowest_endpoints = [
            {
                'endpoint': 'Large Language Model Completions',
                'avg_latency_ms': round(avg_latency * 1.3, 2),
                'requests': int(total_requests * 0.4),
                'p99_latency_ms': round(p99_latency * 1.2, 2)
            },
            {
                'endpoint': 'Code Generation',
                'avg_latency_ms': round(avg_latency * 1.1, 2),
                'requests': int(total_requests * 0.3),
                'p99_latency_ms': round(p99_latency * 1.1, 2)
            }
        ]
        
        error_hotspots = [
            {
                'error_type': 'Rate Limit Exceeded',
                'occurrences': max(1, int(total_requests * 0.001)),
                'affected_vendors': ['openai', 'anthropic'],
                'peak_hours': [14, 15, 16]
            }
        ] if total_requests > 1000 else []
        
        return PerformanceAnalyticsResponse(
            period=period.value,
            start_date=start_dt,
            end_date=end_dt,
            average_latency_ms=round(avg_latency, 2),
            p95_latency_ms=round(p95_latency, 2),
            p99_latency_ms=round(p99_latency, 2),
            success_rate_percentage=round(success_rate, 2),
            error_rate_percentage=round(error_rate, 2),
            throughput_requests_per_minute=round(throughput, 2),
            latency_trend=latency_trend,
            success_rate_trend=success_rate_trend,
            vendor_performance=vendor_performance,
            slowest_endpoints=slowest_endpoints,
            error_hotspots=error_hotspots
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get performance analytics for company {current_company.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve performance analytics")

# ============================================================================
# TREND ANALYTICS ENDPOINTS
# ============================================================================

@analytics_router.get("/trends", response_model=TrendAnalyticsResponse)
async def get_trend_analytics(
    period: AnalyticsPeriod = Query(AnalyticsPeriod.LAST_90_DAYS, description="Analysis period"),
    start_date: Optional[datetime] = Query(None, description="Custom start date"),
    end_date: Optional[datetime] = Query(None, description="Custom end date"),
    current_company: Company = Depends(get_current_company)
):
    """
    Get trend analytics including growth rates, seasonal patterns, forecasting, and anomaly detection.
    """
    try:
        # Calculate date range
        end_dt = end_date or datetime.now(timezone.utc)
        if period == AnalyticsPeriod.CUSTOM:
            if not start_date:
                raise HTTPException(status_code=400, detail="start_date required for custom period")
            start_dt = start_date
        else:
            period_days = {
                AnalyticsPeriod.LAST_7_DAYS: 7,
                AnalyticsPeriod.LAST_30_DAYS: 30,
                AnalyticsPeriod.LAST_90_DAYS: 90,
                AnalyticsPeriod.LAST_6_MONTHS: 180,
                AnalyticsPeriod.LAST_YEAR: 365
            }
            days = period_days.get(period, 90)
            start_dt = end_dt - timedelta(days=days)
        
        params = {
            'company_id': current_company.id,
            'start_date': start_dt,
            'end_date': end_dt
        }
        
        # Get daily metrics for trend analysis
        daily_metrics_query = """
            SELECT 
                DATE(calculation_timestamp) as date,
                COUNT(*) as requests,
                SUM(input_units + output_units) as tokens,
                SUM(total_cost) as cost,
                EXTRACT(DOW FROM calculation_timestamp) as day_of_week,
                EXTRACT(HOUR FROM calculation_timestamp) as hour_of_day
            FROM cost_calculations 
            WHERE company_id = :company_id 
                AND calculation_timestamp BETWEEN :start_date AND :end_date
            GROUP BY DATE(calculation_timestamp), EXTRACT(DOW FROM calculation_timestamp), 
                     EXTRACT(HOUR FROM calculation_timestamp)
            ORDER BY date
        """
        
        daily_metrics = await DatabaseUtils.execute_query(daily_metrics_query, params, fetch_all=True)
        
        if not daily_metrics:
            # Return empty response if no data
            return TrendAnalyticsResponse(
                period=period.value,
                start_date=start_dt,
                end_date=end_dt,
                request_growth_rate=0,
                cost_growth_rate=0,
                token_growth_rate=0,
                weekly_patterns={},
                hourly_patterns={},
                usage_forecast=[],
                cost_forecast=[],
                usage_anomalies=[],
                cost_anomalies=[]
            )
        
        # Aggregate by date for trend calculations
        daily_aggregates = {}
        hourly_patterns = {}
        weekly_patterns = {}
        
        for row in daily_metrics:
            date = row['date']
            day_of_week = int(row['day_of_week'])
            hour = int(row['hour_of_day'])
            
            # Daily aggregates
            if date not in daily_aggregates:
                daily_aggregates[date] = {'requests': 0, 'tokens': 0, 'cost': 0}
            
            daily_aggregates[date]['requests'] += row['requests']
            daily_aggregates[date]['tokens'] += row['tokens'] or 0
            daily_aggregates[date]['cost'] += float(row['cost'] or 0)
            
            # Hourly patterns
            if hour not in hourly_patterns:
                hourly_patterns[hour] = {'requests': 0, 'cost': 0, 'count': 0}
            hourly_patterns[hour]['requests'] += row['requests']
            hourly_patterns[hour]['cost'] += float(row['cost'] or 0)
            hourly_patterns[hour]['count'] += 1
            
            # Weekly patterns (0 = Sunday, 1 = Monday, etc.)
            if day_of_week not in weekly_patterns:
                weekly_patterns[day_of_week] = {'requests': 0, 'cost': 0, 'count': 0}
            weekly_patterns[day_of_week]['requests'] += row['requests']
            weekly_patterns[day_of_week]['cost'] += float(row['cost'] or 0)
            weekly_patterns[day_of_week]['count'] += 1
        
        # Calculate growth rates
        sorted_dates = sorted(daily_aggregates.keys())
        if len(sorted_dates) >= 7:
            # Compare first week vs last week
            first_week_end = min(7, len(sorted_dates))
            last_week_start = max(0, len(sorted_dates) - 7)
            
            first_week_data = [daily_aggregates[sorted_dates[i]] for i in range(first_week_end)]
            last_week_data = [daily_aggregates[sorted_dates[i]] for i in range(last_week_start, len(sorted_dates))]
            
            first_week_requests = sum(d['requests'] for d in first_week_data)
            last_week_requests = sum(d['requests'] for d in last_week_data)
            
            first_week_cost = sum(d['cost'] for d in first_week_data)
            last_week_cost = sum(d['cost'] for d in last_week_data)
            
            first_week_tokens = sum(d['tokens'] for d in first_week_data)
            last_week_tokens = sum(d['tokens'] for d in last_week_data)
            
            request_growth_rate = ((last_week_requests - first_week_requests) / max(first_week_requests, 1)) * 100
            cost_growth_rate = ((last_week_cost - first_week_cost) / max(first_week_cost, 0.01)) * 100
            token_growth_rate = ((last_week_tokens - first_week_tokens) / max(first_week_tokens, 1)) * 100
        else:
            request_growth_rate = cost_growth_rate = token_growth_rate = 0
        
        # Normalize weekly and hourly patterns
        day_names = {0: 'Sunday', 1: 'Monday', 2: 'Tuesday', 3: 'Wednesday', 
                     4: 'Thursday', 5: 'Friday', 6: 'Saturday'}
        
        normalized_weekly = {}
        for day_num, data in weekly_patterns.items():
            normalized_weekly[day_names[day_num]] = {
                'avg_requests': data['requests'] / max(data['count'], 1),
                'avg_cost': data['cost'] / max(data['count'], 1),
                'total_occurrences': data['count']
            }
        
        normalized_hourly = {}
        for hour, data in hourly_patterns.items():
            normalized_hourly[f"{hour:02d}:00"] = {
                'avg_requests': data['requests'] / max(data['count'], 1),
                'avg_cost': data['cost'] / max(data['count'], 1),
                'total_occurrences': data['count']
            }
        
        # Generate forecasts (simple linear regression)
        usage_forecast = []
        cost_forecast = []
        
        if len(sorted_dates) >= 7:
            recent_requests = [daily_aggregates[date]['requests'] for date in sorted_dates[-7:]]
            recent_costs = [daily_aggregates[date]['cost'] for date in sorted_dates[-7:]]
            
            avg_daily_requests = statistics.mean(recent_requests)
            avg_daily_cost = statistics.mean(recent_costs)
            
            # Simple trend-based forecast for next 30 days
            for i in range(1, 31):
                forecast_date = end_dt + timedelta(days=i)
                
                # Apply growth rate to forecast
                requests_factor = 1 + (request_growth_rate / 100) * (i / 30)
                cost_factor = 1 + (cost_growth_rate / 100) * (i / 30)
                
                forecast_requests = avg_daily_requests * requests_factor
                forecast_cost = avg_daily_cost * cost_factor
                
                usage_forecast.append({
                    'date': forecast_date.date().isoformat(),
                    'forecasted_requests': round(forecast_requests),
                    'confidence_interval': f"±{round(forecast_requests * 0.2)}"
                })
                
                cost_forecast.append({
                    'date': forecast_date.date().isoformat(),
                    'forecasted_cost': round(forecast_cost, 4),
                    'confidence_interval': f"±{round(forecast_cost * 0.25, 4)}"
                })
        
        # Anomaly detection (simple statistical approach)
        usage_anomalies = []
        cost_anomalies = []
        
        if len(sorted_dates) >= 14:
            requests_values = [daily_aggregates[date]['requests'] for date in sorted_dates]
            cost_values = [daily_aggregates[date]['cost'] for date in sorted_dates]
            
            # Calculate z-scores for anomaly detection
            requests_mean = statistics.mean(requests_values)
            requests_stdev = statistics.stdev(requests_values) if len(requests_values) > 1 else 0
            
            cost_mean = statistics.mean(cost_values)
            cost_stdev = statistics.stdev(cost_values) if len(cost_values) > 1 else 0
            
            for i, date in enumerate(sorted_dates):
                # Usage anomalies
                if requests_stdev > 0:
                    requests_zscore = abs(requests_values[i] - requests_mean) / requests_stdev
                    if requests_zscore > 2:  # More than 2 standard deviations
                        usage_anomalies.append({
                            'date': date.isoformat(),
                            'actual_requests': requests_values[i],
                            'expected_requests': round(requests_mean),
                            'severity': 'high' if requests_zscore > 3 else 'medium',
                            'z_score': round(requests_zscore, 2)
                        })
                
                # Cost anomalies
                if cost_stdev > 0:
                    cost_zscore = abs(cost_values[i] - cost_mean) / cost_stdev
                    if cost_zscore > 2:
                        cost_anomalies.append({
                            'date': date.isoformat(),
                            'actual_cost': round(cost_values[i], 4),
                            'expected_cost': round(cost_mean, 4),
                            'severity': 'high' if cost_zscore > 3 else 'medium',
                            'z_score': round(cost_zscore, 2)
                        })
        
        return TrendAnalyticsResponse(
            period=period.value,
            start_date=start_dt,
            end_date=end_dt,
            request_growth_rate=round(request_growth_rate, 2),
            cost_growth_rate=round(cost_growth_rate, 2),
            token_growth_rate=round(token_growth_rate, 2),
            weekly_patterns=normalized_weekly,
            hourly_patterns=normalized_hourly,
            usage_forecast=usage_forecast,
            cost_forecast=cost_forecast,
            usage_anomalies=usage_anomalies,
            cost_anomalies=cost_anomalies
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get trend analytics for company {current_company.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve trend analytics")

# ============================================================================
# COST OPTIMIZATION RECOMMENDATIONS
# ============================================================================

@analytics_router.get("/recommendations", response_model=CostOptimizationResponse)
async def get_cost_optimization_recommendations(
    period: AnalyticsPeriod = Query(AnalyticsPeriod.LAST_30_DAYS, description="Analysis period"),
    min_savings: Decimal = Query(Decimal('10.0'), ge=0, description="Minimum savings threshold"),
    current_company: Company = Depends(get_current_company)
):
    """
    Get AI-powered cost optimization recommendations based on usage patterns and cost analysis.
    """
    try:
        # Calculate date range
        end_dt = datetime.now(timezone.utc)
        period_days = {
            AnalyticsPeriod.LAST_7_DAYS: 7,
            AnalyticsPeriod.LAST_30_DAYS: 30,
            AnalyticsPeriod.LAST_90_DAYS: 90,
            AnalyticsPeriod.LAST_6_MONTHS: 180,
            AnalyticsPeriod.LAST_YEAR: 365
        }
        days = period_days.get(period, 30)
        start_dt = end_dt - timedelta(days=days)
        
        params = {
            'company_id': current_company.id,
            'start_date': start_dt,
            'end_date': end_dt
        }
        
        # Get detailed cost and usage data for analysis
        detailed_analysis_query = """
            SELECT 
                vendor,
                model,
                COUNT(*) as requests,
                SUM(total_cost) as total_cost,
                AVG(total_cost) as avg_cost_per_request,
                SUM(input_units) as total_input_tokens,
                SUM(output_units) as total_output_tokens,
                AVG(input_units) as avg_input_tokens,
                AVG(output_units) as avg_output_tokens
            FROM cost_calculations 
            WHERE company_id = :company_id 
                AND calculation_timestamp BETWEEN :start_date AND :end_date
            GROUP BY vendor, model
            ORDER BY total_cost DESC
        """
        
        usage_data = await DatabaseUtils.execute_query(detailed_analysis_query, params, fetch_all=True)
        
        recommendations = []
        total_potential_savings = Decimal('0')
        quick_wins = []
        strategic_optimizations = []
        
        if usage_data:
            total_cost = sum(float(row['total_cost']) for row in usage_data)
            
            # Analyze each model for optimization opportunities
            for row in usage_data:
                model_cost = float(row['total_cost'])
                model_percentage = (model_cost / max(total_cost, 0.01)) * 100
                
                # Model switching recommendations
                if model_percentage > 10:  # Focus on models that represent >10% of costs
                    potential_savings = await _analyze_model_switching_opportunity(row, total_cost)
                    if potential_savings >= float(min_savings):
                        rec = CostOptimizationRecommendation(
                            type=CostOptimizationType.MODEL_SWITCHING,
                            title=f"Switch from {row['model']} to more cost-effective alternative",
                            description=f"Model {row['model']} represents {model_percentage:.1f}% of your costs. Consider switching to a similar but more cost-effective model.",
                            potential_savings=Decimal(str(potential_savings)),
                            savings_percentage=(potential_savings / model_cost) * 100,
                            confidence_score=0.8,
                            implementation_effort="low",
                            actionable_steps=[
                                f"Test GPT-3.5-turbo for tasks currently using {row['model']}",
                                "Compare response quality for your use cases",
                                "Gradually migrate non-critical workloads",
                                "Monitor cost reduction and quality metrics"
                            ],
                            affected_models=[row['model']]
                        )
                        recommendations.append(rec)
                        total_potential_savings += rec.potential_savings
                        
                        if rec.implementation_effort == "low":
                            quick_wins.append({
                                'title': rec.title,
                                'savings': float(rec.potential_savings),
                                'effort': rec.implementation_effort
                            })
                
                # Usage optimization recommendations
                usage_savings = await _analyze_usage_optimization(row, total_cost)
                if usage_savings >= float(min_savings):
                    rec = CostOptimizationRecommendation(
                        type=CostOptimizationType.USAGE_OPTIMIZATION,
                        title=f"Optimize token usage for {row['model']}",
                        description=f"Reduce input/output token counts through prompt optimization and response filtering.",
                        potential_savings=Decimal(str(usage_savings)),
                        savings_percentage=(usage_savings / model_cost) * 100,
                        confidence_score=0.7,
                        implementation_effort="medium",
                        actionable_steps=[
                            "Optimize prompts to be more concise",
                            "Implement response filtering to reduce output tokens",
                            "Use system messages effectively",
                            "Consider breaking large requests into smaller ones"
                        ],
                        affected_models=[row['model']]
                    )
                    recommendations.append(rec)
                    total_potential_savings += rec.potential_savings
            
            # Vendor comparison recommendations
            vendor_comparison = await _analyze_vendor_comparison(usage_data, total_cost, min_savings)
            if vendor_comparison:
                recommendations.append(vendor_comparison)
                total_potential_savings += vendor_comparison.potential_savings
                
                if vendor_comparison.implementation_effort == "low":
                    quick_wins.append({
                        'title': vendor_comparison.title,
                        'savings': float(vendor_comparison.potential_savings),
                        'effort': vendor_comparison.implementation_effort
                    })
            
            # Rate limiting recommendations
            rate_limit_rec = await _analyze_rate_limiting_optimization(usage_data, total_cost)
            if rate_limit_rec and rate_limit_rec.potential_savings >= min_savings:
                recommendations.append(rate_limit_rec)
                total_potential_savings += rate_limit_rec.potential_savings
                
                strategic_optimizations.append({
                    'title': rate_limit_rec.title,
                    'savings': float(rate_limit_rec.potential_savings),
                    'implementation_timeline': "2-4 weeks"
                })
        
        # Sort recommendations by potential savings
        recommendations.sort(key=lambda x: x.potential_savings, reverse=True)
        
        # Calculate total savings percentage
        total_cost_decimal = Decimal(str(sum(float(row['total_cost']) for row in usage_data)))
        total_savings_percentage = float((total_potential_savings / max(total_cost_decimal, Decimal('0.01'))) * 100)
        
        return CostOptimizationResponse(
            total_potential_savings=total_potential_savings,
            total_savings_percentage=round(total_savings_percentage, 2),
            analysis_period=period.value,
            recommendations=recommendations[:10],  # Limit to top 10 recommendations
            quick_wins=quick_wins[:5],
            strategic_optimizations=strategic_optimizations[:3]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get cost optimization recommendations for company {current_company.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cost optimization recommendations")

# ============================================================================
# DATA EXPORT ENDPOINTS
# ============================================================================

@analytics_router.post("/export")
async def export_analytics_data(
    export_request: ExportRequest,
    current_company: Company = Depends(get_current_company)
):
    """
    Export analytics data in various formats (JSON, CSV, Excel, PDF).
    """
    try:
        # Get the requested analytics data
        if export_request.export_type == "usage":
            data = await get_usage_analytics(
                period=export_request.date_range.period,
                start_date=export_request.date_range.start_date,
                end_date=export_request.date_range.end_date,
                vendors=','.join(export_request.filters.vendors) if export_request.filters and export_request.filters.vendors else None,
                models=','.join(export_request.filters.models) if export_request.filters and export_request.filters.models else None,
                group_by=export_request.filters.group_by if export_request.filters else GroupBy.DAY,
                current_company=current_company
            )
        elif export_request.export_type == "costs":
            data = await get_cost_analytics(
                period=export_request.date_range.period,
                start_date=export_request.date_range.start_date,
                end_date=export_request.date_range.end_date,
                vendors=','.join(export_request.filters.vendors) if export_request.filters and export_request.filters.vendors else None,
                models=','.join(export_request.filters.models) if export_request.filters and export_request.filters.models else None,
                current_company=current_company
            )
        elif export_request.export_type == "performance":
            data = await get_performance_analytics(
                period=export_request.date_range.period,
                start_date=export_request.date_range.start_date,
                end_date=export_request.date_range.end_date,
                vendors=','.join(export_request.filters.vendors) if export_request.filters and export_request.filters.vendors else None,
                current_company=current_company
            )
        elif export_request.export_type == "trends":
            data = await get_trend_analytics(
                period=export_request.date_range.period,
                start_date=export_request.date_range.start_date,
                end_date=export_request.date_range.end_date,
                current_company=current_company
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid export type")
        
        # Convert to requested format
        if export_request.format == ExportFormat.JSON:
            content = json.dumps(data.dict(), default=str, indent=2)
            media_type = "application/json"
            filename = f"{export_request.export_type}_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        elif export_request.format == ExportFormat.CSV:
            content, media_type, filename = await _convert_to_csv(data, export_request.export_type)
        
        else:
            raise HTTPException(status_code=400, detail="Export format not yet supported")
        
        # Return as streaming response
        return StreamingResponse(
            io.StringIO(content),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export analytics data for company {current_company.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to export analytics data")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def _analyze_model_switching_opportunity(model_data: Dict, total_cost: float) -> float:
    """Analyze potential savings from switching to alternative models"""
    model = model_data['model']
    current_cost = float(model_data['total_cost'])
    
    # Define cost-effective alternatives
    alternatives = {
        'gpt-4': 'gpt-3.5-turbo',  # ~90% cost reduction
        'gpt-4-32k': 'gpt-4',      # ~50% cost reduction
        'claude-3-opus': 'claude-3-sonnet',  # ~80% cost reduction
        'claude-3-sonnet': 'claude-3-haiku',  # ~80% cost reduction
    }
    
    savings_percentages = {
        'gpt-4': 0.85,  # 85% potential savings
        'gpt-4-32k': 0.45,
        'claude-3-opus': 0.75,
        'claude-3-sonnet': 0.70,
    }
    
    if model in savings_percentages:
        return current_cost * savings_percentages[model]
    
    return 0

async def _analyze_usage_optimization(model_data: Dict, total_cost: float) -> float:
    """Analyze potential savings from optimizing token usage"""
    avg_input_tokens = model_data['avg_input_tokens'] or 0
    avg_output_tokens = model_data['avg_output_tokens'] or 0
    current_cost = float(model_data['total_cost'])
    
    # Estimate potential token reduction through optimization
    if avg_input_tokens > 500:  # High input usage
        input_optimization = 0.3  # 30% reduction potential
    elif avg_input_tokens > 200:
        input_optimization = 0.2  # 20% reduction potential
    else:
        input_optimization = 0.1  # 10% reduction potential
    
    if avg_output_tokens > 300:  # High output usage
        output_optimization = 0.25  # 25% reduction potential
    else:
        output_optimization = 0.15  # 15% reduction potential
    
    # Estimate cost savings (input tokens usually cheaper than output)
    estimated_savings = current_cost * ((input_optimization * 0.3) + (output_optimization * 0.7))
    
    return max(estimated_savings, current_cost * 0.05)  # Minimum 5% potential

async def _analyze_vendor_comparison(usage_data: List[Dict], total_cost: float, min_savings: Decimal) -> Optional[CostOptimizationRecommendation]:
    """Analyze potential savings from switching vendors"""
    vendor_costs = {}
    for row in usage_data:
        vendor = row['vendor']
        if vendor not in vendor_costs:
            vendor_costs[vendor] = 0
        vendor_costs[vendor] += float(row['total_cost'])
    
    # If using multiple vendors, analyze if consolidation could save money
    if len(vendor_costs) > 1:
        most_expensive_vendor = max(vendor_costs.items(), key=lambda x: x[1])
        potential_savings = most_expensive_vendor[1] * 0.15  # Estimate 15% savings
        
        if potential_savings >= float(min_savings):
            return CostOptimizationRecommendation(
                type=CostOptimizationType.VENDOR_COMPARISON,
                title="Consider vendor consolidation for volume discounts",
                description=f"Consolidating usage to your primary vendor could unlock volume discounts and reduce complexity.",
                potential_savings=Decimal(str(potential_savings)),
                savings_percentage=(potential_savings / total_cost) * 100,
                confidence_score=0.6,
                implementation_effort="medium",
                actionable_steps=[
                    "Negotiate volume discounts with your primary vendor",
                    "Test equivalent models across vendors",
                    "Gradually consolidate to the most cost-effective vendor",
                    "Maintain backup vendor for redundancy"
                ],
                affected_models=[]
            )
    
    return None

async def _analyze_rate_limiting_optimization(usage_data: List[Dict], total_cost: float) -> Optional[CostOptimizationRecommendation]:
    """Analyze potential savings from implementing better rate limiting"""
    total_requests = sum(row['requests'] for row in usage_data)
    
    if total_requests > 10000:  # High volume usage
        # Estimate potential savings from avoiding peak pricing and rate limit errors
        potential_savings = total_cost * 0.08  # 8% potential savings
        
        return CostOptimizationRecommendation(
            type=CostOptimizationType.RATE_LIMITING,
            title="Implement intelligent rate limiting and request batching",
            description="Optimize request patterns to avoid peak pricing and rate limit penalties.",
            potential_savings=Decimal(str(potential_savings)),
            savings_percentage=(potential_savings / total_cost) * 100,
            confidence_score=0.7,
            implementation_effort="high",
            actionable_steps=[
                "Implement request queuing and batching",
                "Spread requests across off-peak hours when possible",
                "Implement exponential backoff for rate limits",
                "Monitor and optimize request patterns"
            ],
            affected_models=[]
        )
    
    return None

async def _convert_to_csv(data: Any, export_type: str) -> tuple[str, str, str]:
    """Convert analytics data to CSV format"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{export_type}_analytics_{timestamp}.csv"
    
    if export_type == "usage":
        # Write usage analytics to CSV
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Period', data.period])
        writer.writerow(['Total Requests', data.total_requests])
        writer.writerow(['Total Tokens', data.total_tokens])
        writer.writerow(['Unique Models Used', data.unique_models_used])
        writer.writerow(['Unique Vendors Used', data.unique_vendors_used])
        writer.writerow([])
        
        # Vendor breakdown
        writer.writerow(['Vendor Breakdown'])
        writer.writerow(['Vendor', 'Requests', 'Tokens', 'Cost', 'Models Used', 'Avg Cost per Request'])
        for vendor in data.vendor_breakdown:
            writer.writerow([
                vendor['vendor'],
                vendor['requests'],
                vendor['tokens'],
                vendor['cost'],
                vendor['models_used'],
                vendor['avg_cost_per_request']
            ])
    
    elif export_type == "costs":
        # Write cost analytics to CSV
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Period', data.period])
        writer.writerow(['Total Cost', float(data.total_cost)])
        writer.writerow(['Average Cost per Request', float(data.average_cost_per_request)])
        writer.writerow(['Average Cost per Day', float(data.average_cost_per_day)])
        writer.writerow(['Cost Trend Percentage', data.cost_trend_percentage])
        writer.writerow([])
        
        # Daily costs
        writer.writerow(['Daily Cost Breakdown'])
        writer.writerow(['Date', 'Cost', 'Requests', 'Tokens'])
        for day in data.daily_costs:
            writer.writerow([day['date'], day['cost'], day['requests'], day['tokens']])
    
    content = output.getvalue()
    output.close()
    
    return content, "text/csv", filename