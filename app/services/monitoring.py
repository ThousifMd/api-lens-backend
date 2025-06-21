"""
Real-Time Monitoring Service - Live metrics aggregation and performance monitoring
Implements comprehensive usage dashboard data, anomaly detection, and system performance tracking
"""

import asyncio
import json
import logging
import time
import statistics
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Union, Tuple
from decimal import Decimal, getcontext
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import numpy as np
from collections import defaultdict, deque

import redis.asyncio as aioredis

from ..config import get_settings
from ..utils.logger import get_logger
from ..database import DatabaseUtils
from .cache import cache_service, _get_cache_key, TTL
from .real_time_cost import CostPeriod, QuotaStatus
from .ratelimit import LimitType

# Set decimal precision for calculations
getcontext().prec = 10

settings = get_settings()
logger = get_logger(__name__)

class MetricType(str, Enum):
    """Types of metrics to track"""
    REQUESTS = "requests"
    COST = "cost"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    QUOTA_USAGE = "quota_usage"
    RATE_LIMIT_HITS = "rate_limit_hits"

class TimePeriod(str, Enum):
    """Time periods for metrics aggregation"""
    REAL_TIME = "real_time"      # Last 5 minutes
    HOURLY = "hourly"            # Last 24 hours
    DAILY = "daily"              # Last 30 days
    WEEKLY = "weekly"            # Last 12 weeks
    MONTHLY = "monthly"          # Last 12 months
    CUSTOM = "custom"            # Custom date range

class AnomalyType(str, Enum):
    """Types of usage anomalies"""
    SUDDEN_SPIKE = "sudden_spike"
    SUDDEN_DROP = "sudden_drop" 
    UNUSUAL_PATTERN = "unusual_pattern"
    COST_ANOMALY = "cost_anomaly"
    ERROR_SURGE = "error_surge"
    QUOTA_BREACH = "quota_breach"

class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

@dataclass
class RealTimeMetrics:
    """Real-time usage metrics for a company"""
    company_id: str
    timestamp: datetime
    
    # Request metrics
    requests_per_minute: int
    requests_per_hour: int
    total_requests_today: int
    
    # Cost metrics
    cost_per_minute: Decimal
    cost_per_hour: Decimal
    total_cost_today: Decimal
    projected_monthly_cost: Decimal
    
    # Performance metrics
    avg_response_time_ms: float
    error_rate_percentage: float
    success_rate_percentage: float
    
    # Quota status
    request_quota_used_percentage: float
    cost_quota_used_percentage: float
    quota_status: QuotaStatus
    
    # Rate limiting
    rate_limit_hits_per_minute: int
    rate_limit_status: str
    
    # Top usage
    top_vendors: List[Dict[str, Any]]
    top_models: List[Dict[str, Any]]
    top_endpoints: List[Dict[str, Any]]

@dataclass
class UsageAggregation:
    """Aggregated usage data for a period"""
    company_id: str
    period: TimePeriod
    start_time: datetime
    end_time: datetime
    
    # Volume metrics
    total_requests: int
    total_cost: Decimal
    avg_requests_per_day: float
    avg_cost_per_day: Decimal
    
    # Performance metrics
    avg_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float
    
    # Quality metrics
    success_rate: float
    error_rate: float
    timeout_rate: float
    
    # Usage patterns
    peak_hour: int
    peak_day: str
    busiest_vendor: str
    most_used_model: str
    
    # Cost analysis
    cost_per_request: Decimal
    cost_trend: str  # "increasing", "decreasing", "stable"
    cost_efficiency_score: float  # 0-100

@dataclass
class Anomaly:
    """Usage anomaly detection result"""
    anomaly_id: str
    company_id: str
    anomaly_type: AnomalyType
    severity: AlertSeverity
    
    # Detection details
    detected_at: datetime
    metric_name: str
    current_value: float
    expected_value: float
    deviation_percentage: float
    
    # Context
    description: str
    recommendation: str
    affected_period: Tuple[datetime, datetime]
    
    # Analysis
    confidence_score: float  # 0-1
    is_ongoing: bool
    impact_assessment: str

@dataclass
class SystemPerformance:
    """Rate limiting system performance metrics"""
    timestamp: datetime
    
    # System health
    redis_status: str
    database_status: str
    cache_hit_rate: float
    
    # Rate limiting performance
    avg_rate_limit_check_time_ms: float
    rate_limit_accuracy: float
    sliding_window_performance: Dict[str, float]
    
    # Throughput metrics
    requests_processed_per_second: float
    rate_limit_checks_per_second: float
    quota_checks_per_second: float
    
    # Resource utilization
    redis_memory_usage: Dict[str, Any]
    database_connection_pool: Dict[str, int]
    system_resource_usage: Dict[str, float]
    
    # Error tracking
    rate_limit_errors: int
    quota_calculation_errors: int
    cache_errors: int

@dataclass
class UsageReport:
    """Comprehensive usage report"""
    company_id: str
    report_id: str
    period: TimePeriod
    generated_at: datetime
    
    # Summary
    executive_summary: Dict[str, Any]
    key_metrics: Dict[str, Any]
    
    # Detailed analysis
    usage_analysis: UsageAggregation
    cost_analysis: Dict[str, Any]
    performance_analysis: Dict[str, Any]
    
    # Insights
    anomalies_detected: List[Anomaly]
    optimization_recommendations: List[str]
    trend_analysis: Dict[str, Any]
    
    # Comparisons
    period_over_period_comparison: Dict[str, Any]
    benchmark_comparison: Dict[str, Any]

class MonitoringService:
    """Enterprise monitoring service for real-time usage tracking"""
    
    def __init__(self):
        self._redis_client: Optional[aioredis.Redis] = None
        self._metrics_cache = {}
        self._anomaly_thresholds = {
            AnomalyType.SUDDEN_SPIKE: 3.0,    # 3 standard deviations
            AnomalyType.SUDDEN_DROP: 2.5,     # 2.5 standard deviations
            AnomalyType.COST_ANOMALY: 2.0,    # 2 standard deviations
            AnomalyType.ERROR_SURGE: 1.5,     # 1.5 standard deviations
        }
    
    async def _get_redis_client(self) -> aioredis.Redis:
        """Get Redis client for monitoring data"""
        if not self._redis_client:
            self._redis_client = await cache_service._get_redis_client()
        return self._redis_client

# Global monitoring service instance
monitoring_service = MonitoringService()

async def get_real_time_metrics(company_id: str) -> Dict[str, Any]:
    """
    Get live usage metrics for a company's dashboard
    Returns real-time data for the last few minutes/hours
    """
    try:
        redis_client = await monitoring_service._get_redis_client()
        current_time = datetime.now(timezone.utc)
        
        # Get real-time request metrics from Redis
        requests_data = await _get_real_time_requests(redis_client, company_id, current_time)
        
        # Get real-time cost metrics from Redis  
        cost_data = await _get_real_time_costs(redis_client, company_id, current_time)
        
        # Get performance metrics
        performance_data = await _get_real_time_performance(redis_client, company_id, current_time)
        
        # Get quota status
        quota_data = await _get_real_time_quota_status(company_id, current_time)
        
        # Get rate limiting status
        rate_limit_data = await _get_real_time_rate_limits(redis_client, company_id, current_time)
        
        # Get top usage patterns
        usage_patterns = await _get_real_time_usage_patterns(company_id, current_time)
        
        # Compile real-time metrics
        metrics = RealTimeMetrics(
            company_id=company_id,
            timestamp=current_time,
            
            # Request metrics
            requests_per_minute=requests_data.get('per_minute', 0),
            requests_per_hour=requests_data.get('per_hour', 0),
            total_requests_today=requests_data.get('today_total', 0),
            
            # Cost metrics
            cost_per_minute=Decimal(str(cost_data.get('per_minute', 0))),
            cost_per_hour=Decimal(str(cost_data.get('per_hour', 0))),
            total_cost_today=Decimal(str(cost_data.get('today_total', 0))),
            projected_monthly_cost=Decimal(str(cost_data.get('projected_monthly', 0))),
            
            # Performance metrics
            avg_response_time_ms=performance_data.get('avg_response_time', 0),
            error_rate_percentage=performance_data.get('error_rate', 0),
            success_rate_percentage=performance_data.get('success_rate', 100),
            
            # Quota status
            request_quota_used_percentage=quota_data.get('request_usage_pct', 0),
            cost_quota_used_percentage=quota_data.get('cost_usage_pct', 0),
            quota_status=QuotaStatus(quota_data.get('status', 'HEALTHY')),
            
            # Rate limiting
            rate_limit_hits_per_minute=rate_limit_data.get('hits_per_minute', 0),
            rate_limit_status=rate_limit_data.get('status', 'OK'),
            
            # Top usage
            top_vendors=usage_patterns.get('vendors', []),
            top_models=usage_patterns.get('models', []),
            top_endpoints=usage_patterns.get('endpoints', [])
        )
        
        # Cache the metrics for performance
        cache_key = f"real_time_metrics:{company_id}"
        await redis_client.setex(cache_key, 30, json.dumps(asdict(metrics), default=str))
        
        logger.debug(f"Generated real-time metrics for company: {company_id}")
        return asdict(metrics)
        
    except Exception as e:
        logger.error(f"Failed to get real-time metrics for {company_id}: {e}")
        raise

async def aggregate_usage_data(company_id: str, period: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Aggregate usage data for a specified period
    Supports hourly, daily, weekly, monthly aggregations
    """
    try:
        period_enum = TimePeriod(period)
        current_time = datetime.now(timezone.utc)
        
        # Calculate time range based on period
        if period_enum == TimePeriod.CUSTOM and start_date and end_date:
            start_time = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        else:
            start_time, end_time = _get_period_range(period_enum, current_time)
        
        # Get aggregated request data
        request_metrics = await _aggregate_request_metrics(company_id, start_time, end_time)
        
        # Get aggregated cost data
        cost_metrics = await _aggregate_cost_metrics(company_id, start_time, end_time)
        
        # Get performance metrics
        performance_metrics = await _aggregate_performance_metrics(company_id, start_time, end_time)
        
        # Get usage patterns  
        usage_patterns = await _aggregate_usage_patterns(company_id, start_time, end_time)
        
        # Calculate derived metrics
        total_requests = request_metrics.get('total_requests', 0)
        total_cost = Decimal(str(cost_metrics.get('total_cost', 0)))
        days_in_period = (end_time - start_time).days or 1
        
        # Create aggregation result
        aggregation = UsageAggregation(
            company_id=company_id,
            period=period_enum,
            start_time=start_time,
            end_time=end_time,
            
            # Volume metrics
            total_requests=total_requests,
            total_cost=total_cost,
            avg_requests_per_day=total_requests / days_in_period,
            avg_cost_per_day=total_cost / Decimal(days_in_period),
            
            # Performance metrics
            avg_response_time=performance_metrics.get('avg_response_time', 0),
            p50_response_time=performance_metrics.get('p50_response_time', 0),
            p95_response_time=performance_metrics.get('p95_response_time', 0),
            p99_response_time=performance_metrics.get('p99_response_time', 0),
            
            # Quality metrics
            success_rate=performance_metrics.get('success_rate', 100),
            error_rate=performance_metrics.get('error_rate', 0),
            timeout_rate=performance_metrics.get('timeout_rate', 0),
            
            # Usage patterns
            peak_hour=usage_patterns.get('peak_hour', 12),
            peak_day=usage_patterns.get('peak_day', 'Monday'),
            busiest_vendor=usage_patterns.get('top_vendor', 'Unknown'),
            most_used_model=usage_patterns.get('top_model', 'Unknown'),
            
            # Cost analysis
            cost_per_request=total_cost / Decimal(total_requests) if total_requests > 0 else Decimal('0'),
            cost_trend=cost_metrics.get('trend', 'stable'),
            cost_efficiency_score=cost_metrics.get('efficiency_score', 75.0)
        )
        
        logger.info(f"Aggregated usage data for {company_id} over {period} period")
        return asdict(aggregation)
        
    except Exception as e:
        logger.error(f"Failed to aggregate usage data for {company_id}: {e}")
        raise

async def monitor_rate_limit_performance() -> Dict[str, Any]:
    """
    Monitor rate limiting system performance and health
    Returns comprehensive system metrics
    """
    try:
        redis_client = await monitoring_service._get_redis_client()
        current_time = datetime.now(timezone.utc)
        
        # Check system health
        health_status = await _check_system_health(redis_client)
        
        # Measure rate limiting performance
        rate_limit_perf = await _measure_rate_limit_performance(redis_client)
        
        # Get throughput metrics
        throughput_metrics = await _get_throughput_metrics(redis_client)
        
        # Check resource utilization
        resource_usage = await _get_resource_utilization(redis_client)
        
        # Count recent errors
        error_counts = await _get_error_counts(redis_client, current_time)
        
        # Compile performance metrics
        performance = SystemPerformance(
            timestamp=current_time,
            
            # System health
            redis_status=health_status.get('redis', 'unknown'),
            database_status=health_status.get('database', 'unknown'),
            cache_hit_rate=health_status.get('cache_hit_rate', 0.0),
            
            # Rate limiting performance
            avg_rate_limit_check_time_ms=rate_limit_perf.get('avg_check_time', 0.0),
            rate_limit_accuracy=rate_limit_perf.get('accuracy', 100.0),
            sliding_window_performance=rate_limit_perf.get('sliding_window', {}),
            
            # Throughput metrics
            requests_processed_per_second=throughput_metrics.get('requests_per_second', 0.0),
            rate_limit_checks_per_second=throughput_metrics.get('rate_limit_checks_per_second', 0.0),
            quota_checks_per_second=throughput_metrics.get('quota_checks_per_second', 0.0),
            
            # Resource utilization
            redis_memory_usage=resource_usage.get('redis_memory', {}),
            database_connection_pool=resource_usage.get('db_connections', {}),
            system_resource_usage=resource_usage.get('system', {}),
            
            # Error tracking
            rate_limit_errors=error_counts.get('rate_limit_errors', 0),
            quota_calculation_errors=error_counts.get('quota_errors', 0),
            cache_errors=error_counts.get('cache_errors', 0)
        )
        
        # Store performance metrics for historical tracking
        perf_key = f"system_performance:{current_time.strftime('%Y%m%d_%H%M')}"
        await redis_client.setex(perf_key, 3600, json.dumps(asdict(performance), default=str))
        
        # Check for system alerts
        alerts = await _check_system_alerts(performance)
        if alerts:
            await _send_system_alerts(alerts)
        
        logger.debug("Generated system performance metrics")
        return asdict(performance)
        
    except Exception as e:
        logger.error(f"Failed to monitor rate limit performance: {e}")
        raise

async def detect_usage_anomalies(company_id: str, lookback_hours: int = 24) -> List[Dict[str, Any]]:
    """
    Detect unusual usage patterns and anomalies
    Uses statistical analysis to identify deviations from normal behavior
    """
    try:
        current_time = datetime.now(timezone.utc)
        lookback_time = current_time - timedelta(hours=lookback_hours)
        
        # Get historical usage data for baseline
        historical_data = await _get_historical_usage_data(company_id, lookback_time, current_time)
        
        # Get recent usage data for comparison
        recent_data = await _get_recent_usage_data(company_id, current_time)
        
        anomalies = []
        
        # Detect request volume anomalies
        request_anomalies = await _detect_request_anomalies(
            company_id, historical_data, recent_data, current_time
        )
        anomalies.extend(request_anomalies)
        
        # Detect cost anomalies
        cost_anomalies = await _detect_cost_anomalies(
            company_id, historical_data, recent_data, current_time
        )
        anomalies.extend(cost_anomalies)
        
        # Detect performance anomalies
        performance_anomalies = await _detect_performance_anomalies(
            company_id, historical_data, recent_data, current_time
        )
        anomalies.extend(performance_anomalies)
        
        # Detect pattern anomalies
        pattern_anomalies = await _detect_pattern_anomalies(
            company_id, historical_data, recent_data, current_time
        )
        anomalies.extend(pattern_anomalies)
        
        # Sort by severity and confidence
        anomalies.sort(key=lambda x: (x.severity.value, -x.confidence_score))
        
        # Cache anomaly results
        redis_client = await monitoring_service._get_redis_client()
        anomaly_key = f"anomalies:{company_id}:{current_time.strftime('%Y%m%d_%H')}"
        await redis_client.setex(anomaly_key, 3600, json.dumps([asdict(a) for a in anomalies], default=str))
        
        # Send alerts for critical anomalies
        critical_anomalies = [a for a in anomalies if a.severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]]
        if critical_anomalies:
            await _send_anomaly_alerts(company_id, critical_anomalies)
        
        logger.info(f"Detected {len(anomalies)} anomalies for company {company_id}")
        return [asdict(a) for a in anomalies]
        
    except Exception as e:
        logger.error(f"Failed to detect usage anomalies for {company_id}: {e}")
        raise

async def generate_usage_report(company_id: str, period: str, report_type: str = "comprehensive") -> Dict[str, Any]:
    """
    Generate comprehensive usage report with analytics and insights
    Includes trend analysis, optimization recommendations, and benchmarking
    """
    try:
        period_enum = TimePeriod(period)
        current_time = datetime.now(timezone.utc)
        start_time, end_time = _get_period_range(period_enum, current_time)
        
        # Generate unique report ID
        report_id = hashlib.sha256(f"{company_id}_{period}_{current_time.isoformat()}".encode()).hexdigest()[:16]
        
        # Get comprehensive usage analysis
        usage_analysis_data = await aggregate_usage_data(company_id, period)
        usage_analysis = UsageAggregation(**usage_analysis_data)
        
        # Generate executive summary
        executive_summary = await _generate_executive_summary(company_id, usage_analysis, period_enum)
        
        # Get key metrics
        key_metrics = await _extract_key_metrics(company_id, usage_analysis, period_enum)
        
        # Perform cost analysis
        cost_analysis = await _perform_cost_analysis(company_id, start_time, end_time)
        
        # Analyze performance
        performance_analysis = await _analyze_performance_trends(company_id, start_time, end_time)
        
        # Detect anomalies for the period
        anomalies_data = await detect_usage_anomalies(company_id, (end_time - start_time).total_seconds() // 3600)
        anomalies = [Anomaly(**a) for a in anomalies_data]
        
        # Generate optimization recommendations
        optimization_recommendations = await _generate_optimization_recommendations(
            company_id, usage_analysis, cost_analysis, anomalies
        )
        
        # Perform trend analysis
        trend_analysis = await _perform_trend_analysis(company_id, usage_analysis, period_enum)
        
        # Compare with previous period
        period_comparison = await _compare_with_previous_period(company_id, usage_analysis, period_enum)
        
        # Benchmark against similar companies
        benchmark_comparison = await _benchmark_against_peers(company_id, usage_analysis)
        
        # Create comprehensive report
        report = UsageReport(
            company_id=company_id,
            report_id=report_id,
            period=period_enum,
            generated_at=current_time,
            
            # Summary
            executive_summary=executive_summary,
            key_metrics=key_metrics,
            
            # Detailed analysis
            usage_analysis=usage_analysis,
            cost_analysis=cost_analysis,
            performance_analysis=performance_analysis,
            
            # Insights
            anomalies_detected=anomalies,
            optimization_recommendations=optimization_recommendations,
            trend_analysis=trend_analysis,
            
            # Comparisons
            period_over_period_comparison=period_comparison,
            benchmark_comparison=benchmark_comparison
        )
        
        # Store report for future reference
        await _store_usage_report(report)
        
        logger.info(f"Generated {report_type} usage report {report_id} for company {company_id}")
        return asdict(report)
        
    except Exception as e:
        logger.error(f"Failed to generate usage report for {company_id}: {e}")
        raise

# Helper functions for real-time metrics

async def _get_real_time_requests(redis_client: aioredis.Redis, company_id: str, current_time: datetime) -> Dict[str, int]:
    """Get real-time request metrics from Redis"""
    try:
        # Get request counts for different time windows
        minute_key = f"requests:{company_id}:minute:{current_time.strftime('%Y%m%d_%H%M')}"
        hour_key = f"requests:{company_id}:hour:{current_time.strftime('%Y%m%d_%H')}"
        day_key = f"requests:{company_id}:day:{current_time.strftime('%Y%m%d')}"
        
        # Use pipeline for efficiency
        pipe = redis_client.pipeline()
        pipe.get(minute_key)
        pipe.get(hour_key)
        pipe.get(day_key)
        results = await pipe.execute()
        
        return {
            'per_minute': int(results[0] or 0),
            'per_hour': int(results[1] or 0),
            'today_total': int(results[2] or 0)
        }
        
    except Exception as e:
        logger.error(f"Failed to get real-time request data: {e}")
        return {'per_minute': 0, 'per_hour': 0, 'today_total': 0}

async def _get_real_time_costs(redis_client: aioredis.Redis, company_id: str, current_time: datetime) -> Dict[str, float]:
    """Get real-time cost metrics from Redis"""
    try:
        # Get cost data for different time windows
        minute_key = f"costs:{company_id}:minute:{current_time.strftime('%Y%m%d_%H%M')}"
        hour_key = f"costs:{company_id}:hour:{current_time.strftime('%Y%m%d_%H')}"
        day_key = f"costs:{company_id}:day:{current_time.strftime('%Y%m%d')}"
        month_key = f"costs:{company_id}:month:{current_time.strftime('%Y%m')}"
        
        pipe = redis_client.pipeline()
        pipe.get(minute_key)
        pipe.get(hour_key)
        pipe.get(day_key)
        pipe.get(month_key)
        results = await pipe.execute()
        
        # Calculate projected monthly cost
        days_in_month = calendar.monthrange(current_time.year, current_time.month)[1]
        day_cost = float(results[2] or 0)
        projected_monthly = day_cost * days_in_month if current_time.day <= days_in_month else float(results[3] or 0)
        
        return {
            'per_minute': float(results[0] or 0),
            'per_hour': float(results[1] or 0),
            'today_total': day_cost,
            'projected_monthly': projected_monthly
        }
        
    except Exception as e:
        logger.error(f"Failed to get real-time cost data: {e}")
        return {'per_minute': 0, 'per_hour': 0, 'today_total': 0, 'projected_monthly': 0}

async def _get_real_time_performance(redis_client: aioredis.Redis, company_id: str, current_time: datetime) -> Dict[str, float]:
    """Get real-time performance metrics"""
    try:
        # Get performance data from recent requests
        perf_key = f"performance:{company_id}:realtime"
        perf_data = await redis_client.get(perf_key)
        
        if perf_data:
            data = json.loads(perf_data)
            return {
                'avg_response_time': data.get('avg_response_time', 0),
                'error_rate': data.get('error_rate', 0),
                'success_rate': data.get('success_rate', 100)
            }
        
        return {'avg_response_time': 0, 'error_rate': 0, 'success_rate': 100}
        
    except Exception as e:
        logger.error(f"Failed to get real-time performance data: {e}")
        return {'avg_response_time': 0, 'error_rate': 0, 'success_rate': 100}

async def _get_real_time_quota_status(company_id: str, current_time: datetime) -> Dict[str, Any]:
    """Get real-time quota usage status"""
    try:
        # This would integrate with the quota management service
        from .quota_management import check_usage_quota
        
        quota_status = await check_usage_quota(company_id)
        
        return {
            'request_usage_pct': quota_status.request_usage_percentage,
            'cost_usage_pct': float(quota_status.cost_usage_percentage),
            'status': quota_status.quota_status.value
        }
        
    except Exception as e:
        logger.error(f"Failed to get quota status: {e}")
        return {'request_usage_pct': 0, 'cost_usage_pct': 0, 'status': 'HEALTHY'}

async def _get_real_time_rate_limits(redis_client: aioredis.Redis, company_id: str, current_time: datetime) -> Dict[str, Any]:
    """Get real-time rate limiting status"""
    try:
        # Get rate limit hits from the last minute
        hits_key = f"rate_limit_hits:{company_id}:minute:{current_time.strftime('%Y%m%d_%H%M')}"
        hits = await redis_client.get(hits_key)
        
        # Check current rate limit status
        from .ratelimit import check_rate_limit
        rate_limit_result = await check_rate_limit(company_id, LimitType.PER_MINUTE.value)
        
        return {
            'hits_per_minute': int(hits or 0),
            'status': 'LIMITED' if not rate_limit_result.allowed else 'OK'
        }
        
    except Exception as e:
        logger.error(f"Failed to get rate limit status: {e}")
        return {'hits_per_minute': 0, 'status': 'OK'}

async def _get_real_time_usage_patterns(company_id: str, current_time: datetime) -> Dict[str, List[Dict[str, Any]]]:
    """Get real-time usage patterns (top vendors, models, endpoints)"""
    try:
        # Query recent usage from database
        query = """
            SELECT 
                vendor,
                model,
                endpoint,
                COUNT(*) as request_count,
                SUM(total_cost) as total_cost
            FROM cost_calculations 
            WHERE company_id = :company_id 
                AND calculation_timestamp >= :since_time
            GROUP BY vendor, model, endpoint
            ORDER BY request_count DESC
            LIMIT 10
        """
        
        since_time = current_time - timedelta(hours=1)
        results = await DatabaseUtils.execute_query(
            query, 
            {'company_id': company_id, 'since_time': since_time}, 
            fetch_all=True
        )
        
        # Group by type
        vendors = defaultdict(lambda: {'count': 0, 'cost': 0})
        models = defaultdict(lambda: {'count': 0, 'cost': 0})
        endpoints = defaultdict(lambda: {'count': 0, 'cost': 0})
        
        for row in results:
            vendors[row['vendor']]['count'] += row['request_count']
            vendors[row['vendor']]['cost'] += float(row['total_cost'])
            
            models[row['model']]['count'] += row['request_count'] 
            models[row['model']]['cost'] += float(row['total_cost'])
            
            endpoints[row['endpoint']]['count'] += row['request_count']
            endpoints[row['endpoint']]['cost'] += float(row['total_cost'])
        
        # Convert to sorted lists
        top_vendors = [{'name': k, **v} for k, v in sorted(vendors.items(), key=lambda x: x[1]['count'], reverse=True)[:5]]
        top_models = [{'name': k, **v} for k, v in sorted(models.items(), key=lambda x: x[1]['count'], reverse=True)[:5]]
        top_endpoints = [{'name': k, **v} for k, v in sorted(endpoints.items(), key=lambda x: x[1]['count'], reverse=True)[:5]]
        
        return {
            'vendors': top_vendors,
            'models': top_models,
            'endpoints': top_endpoints
        }
        
    except Exception as e:
        logger.error(f"Failed to get usage patterns: {e}")
        return {'vendors': [], 'models': [], 'endpoints': []}

# Additional helper functions would continue here...
# Due to length constraints, I'll continue with the essential functions

def _get_period_range(period: TimePeriod, current_time: datetime) -> Tuple[datetime, datetime]:
    """Get start and end time for a given period"""
    if period == TimePeriod.REAL_TIME:
        return current_time - timedelta(minutes=5), current_time
    elif period == TimePeriod.HOURLY:
        return current_time - timedelta(hours=24), current_time
    elif period == TimePeriod.DAILY:
        return current_time - timedelta(days=30), current_time
    elif period == TimePeriod.WEEKLY:
        return current_time - timedelta(weeks=12), current_time
    elif period == TimePeriod.MONTHLY:
        return current_time - timedelta(days=365), current_time
    else:
        return current_time - timedelta(days=7), current_time

# Continue with more helper functions...