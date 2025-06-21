"""
Real-Time Cost Tracking - Redis-based cost monitoring and quota enforcement
Implements real-time cost counters, quota enforcement, alerting, and cost projections
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple
from decimal import Decimal, getcontext
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import statistics

import redis.asyncio as aioredis

from ..config import get_settings
from ..utils.logger import get_logger
from ..database import DatabaseUtils
from .cache import cache_service, _get_cache_key, TTL
from .cost import CostError

# Set decimal precision for cost calculations
getcontext().prec = 10

settings = get_settings()
logger = get_logger(__name__)

class QuotaStatus(str, Enum):
    """Cost quota status levels"""
    SAFE = "safe"                    # Under 70% of quota
    WARNING = "warning"              # 70-90% of quota
    CRITICAL = "critical"            # 90-100% of quota
    EXCEEDED = "exceeded"            # Over 100% of quota
    SUSPENDED = "suspended"          # Service suspended due to quota

class AlertType(str, Enum):
    """Cost alert types"""
    QUOTA_WARNING = "quota_warning"          # Approaching quota limit
    QUOTA_CRITICAL = "quota_critical"        # Critical quota usage
    QUOTA_EXCEEDED = "quota_exceeded"        # Quota exceeded
    COST_SPIKE = "cost_spike"                # Unusual cost increase
    USAGE_ANOMALY = "usage_anomaly"          # Unusual usage pattern
    PROJECTION_HIGH = "projection_high"      # High monthly projection
    OPTIMIZATION = "optimization"            # Cost optimization opportunity

class CostPeriod(str, Enum):
    """Cost tracking periods"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"

@dataclass
class QuotaInfo:
    """Company quota configuration"""
    company_id: str
    monthly_limit: Decimal
    daily_limit: Optional[Decimal] = None
    hourly_limit: Optional[Decimal] = None
    warning_threshold: float = 0.8  # 80% warning
    critical_threshold: float = 0.95  # 95% critical
    is_active: bool = True
    auto_suspend: bool = False
    created_at: datetime = None
    updated_at: datetime = None

@dataclass
class CostCounter:
    """Real-time cost counter"""
    company_id: str
    period: CostPeriod
    current_cost: Decimal
    request_count: int
    last_updated: datetime
    period_start: datetime
    period_end: datetime

@dataclass
class CostProjection:
    """Cost projection data"""
    company_id: str
    projected_monthly_cost: Decimal
    confidence_score: float
    current_month_cost: Decimal
    days_elapsed: int
    days_remaining: int
    average_daily_cost: Decimal
    trend_factor: float
    projection_date: datetime

@dataclass
class CostOptimization:
    """Cost optimization recommendation"""
    company_id: str
    optimization_type: str
    description: str
    potential_savings: Decimal
    confidence: float
    implementation_difficulty: str  # easy, medium, hard
    estimated_impact: str  # low, medium, high
    details: Dict[str, Any]

class RealTimeCostTracker:
    """Real-time cost tracking service"""
    
    def __init__(self):
        self._redis_client: Optional[aioredis.Redis] = None
        
        # Redis key patterns
        self.COST_COUNTER_KEY = "cost:counter:{company_id}:{period}:{timestamp}"
        self.QUOTA_KEY = "quota:{company_id}"
        self.ALERT_HISTORY_KEY = "alerts:history:{company_id}"
        self.PROJECTION_KEY = "projection:{company_id}"
        self.OPTIMIZATION_KEY = "optimization:{company_id}"
        
        # Cost tracking settings
        self.COUNTER_TTL = 86400 * 32  # 32 days
        self.PROJECTION_TTL = 3600  # 1 hour
        self.ALERT_COOLDOWN = 300  # 5 minutes between same alerts
    
    async def _get_redis_client(self) -> aioredis.Redis:
        """Get Redis client with connection pooling"""
        if not self._redis_client:
            self._redis_client = await cache_service._get_redis_client()
        return self._redis_client

# Global tracker instance
cost_tracker = RealTimeCostTracker()

async def update_real_time_cost(company_id: str, cost: float) -> bool:
    """
    Update Redis-based real-time cost counters
    
    Args:
        company_id: Company identifier
        cost: Cost amount to add
        
    Returns:
        bool: True if successfully updated
    """
    try:
        redis_client = await cost_tracker._get_redis_client()
        cost_decimal = Decimal(str(cost))
        current_time = datetime.utcnow()
        
        # Update counters for different periods
        periods = {
            CostPeriod.HOURLY: current_time.replace(minute=0, second=0, microsecond=0),
            CostPeriod.DAILY: current_time.replace(hour=0, minute=0, second=0, microsecond=0),
            CostPeriod.MONTHLY: current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        }
        
        # Use pipeline for atomic updates
        pipe = redis_client.pipeline()
        
        for period, period_start in periods.items():
            timestamp = int(period_start.timestamp())
            counter_key = cost_tracker.COST_COUNTER_KEY.format(
                company_id=company_id, 
                period=period.value, 
                timestamp=timestamp
            )
            
            # Increment cost counter
            pipe.hincrbyfloat(counter_key, "cost", float(cost_decimal))
            pipe.hincrby(counter_key, "count", 1)
            pipe.hset(counter_key, "last_updated", current_time.isoformat())
            pipe.expire(counter_key, cost_tracker.COUNTER_TTL)
        
        # Execute all updates atomically
        await pipe.execute()
        
        # Check quota status after update
        quota_status = await check_cost_quota(company_id)
        
        # Send alerts if necessary
        if quota_status.status in [QuotaStatus.WARNING, QuotaStatus.CRITICAL, QuotaStatus.EXCEEDED]:
            await _trigger_quota_alert(company_id, quota_status)
        
        logger.debug(f"Updated real-time cost for company {company_id}: +${cost}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update real-time cost for company {company_id}: {e}")
        return False

async def get_current_cost(company_id: str, period: str) -> float:
    """
    Get current spending for a specific period
    
    Args:
        company_id: Company identifier
        period: Time period (hourly, daily, monthly)
        
    Returns:
        float: Current cost for the period
    """
    try:
        redis_client = await cost_tracker._get_redis_client()
        current_time = datetime.utcnow()
        
        # Calculate period start based on period type
        if period == CostPeriod.HOURLY.value:
            period_start = current_time.replace(minute=0, second=0, microsecond=0)
        elif period == CostPeriod.DAILY.value:
            period_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == CostPeriod.MONTHLY.value:
            period_start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            raise ValueError(f"Invalid period: {period}")
        
        timestamp = int(period_start.timestamp())
        counter_key = cost_tracker.COST_COUNTER_KEY.format(
            company_id=company_id, 
            period=period, 
            timestamp=timestamp
        )
        
        # Get current cost from Redis
        cost_data = await redis_client.hget(counter_key, "cost")
        
        if cost_data:
            return float(cost_data)
        else:
            return 0.0
            
    except Exception as e:
        logger.error(f"Failed to get current cost for company {company_id}, period {period}: {e}")
        return 0.0

@dataclass 
class QuotaStatusResult:
    """Quota status check result"""
    company_id: str
    status: QuotaStatus
    current_monthly_cost: Decimal
    monthly_limit: Decimal
    usage_percentage: float
    remaining_quota: Decimal
    daily_average: Decimal
    projected_monthly: Decimal
    days_until_limit: Optional[int]
    last_checked: datetime

async def check_cost_quota(company_id: str) -> QuotaStatusResult:
    """
    Check current usage against cost quota limits
    
    Args:
        company_id: Company identifier
        
    Returns:
        QuotaStatusResult: Current quota status and details
    """
    try:
        # Get quota configuration
        quota_info = await _get_quota_info(company_id)
        if not quota_info:
            # No quota set - return safe status
            return QuotaStatusResult(
                company_id=company_id,
                status=QuotaStatus.SAFE,
                current_monthly_cost=Decimal('0'),
                monthly_limit=Decimal('999999'),  # High default
                usage_percentage=0.0,
                remaining_quota=Decimal('999999'),
                daily_average=Decimal('0'),
                projected_monthly=Decimal('0'),
                days_until_limit=None,
                last_checked=datetime.utcnow()
            )
        
        # Get current monthly cost
        current_monthly_cost = Decimal(str(await get_current_cost(company_id, CostPeriod.MONTHLY.value)))
        
        # Calculate usage percentage
        usage_percentage = float((current_monthly_cost / quota_info.monthly_limit) * 100)
        remaining_quota = quota_info.monthly_limit - current_monthly_cost
        
        # Calculate daily average and projection
        current_time = datetime.utcnow()
        days_elapsed = current_time.day
        days_in_month = (current_time.replace(month=current_time.month + 1, day=1) - timedelta(days=1)).day
        days_remaining = days_in_month - days_elapsed
        
        daily_average = current_monthly_cost / days_elapsed if days_elapsed > 0 else Decimal('0')
        projected_monthly = daily_average * days_in_month
        
        # Calculate days until limit reached
        days_until_limit = None
        if daily_average > 0 and remaining_quota > 0:
            days_until_limit = int(remaining_quota / daily_average)
        
        # Determine status
        if usage_percentage >= 100:
            status = QuotaStatus.EXCEEDED
        elif usage_percentage >= 95:
            status = QuotaStatus.CRITICAL
        elif usage_percentage >= 80:
            status = QuotaStatus.WARNING
        else:
            status = QuotaStatus.SAFE
        
        result = QuotaStatusResult(
            company_id=company_id,
            status=status,
            current_monthly_cost=current_monthly_cost,
            monthly_limit=quota_info.monthly_limit,
            usage_percentage=usage_percentage,
            remaining_quota=remaining_quota,
            daily_average=daily_average,
            projected_monthly=projected_monthly,
            days_until_limit=days_until_limit,
            last_checked=datetime.utcnow()
        )
        
        # Cache the result
        redis_client = await cost_tracker._get_redis_client()
        quota_status_key = f"quota_status:{company_id}"
        result_dict = asdict(result)
        
        # Convert Decimal fields to strings for JSON serialization
        for field in ['current_monthly_cost', 'monthly_limit', 'remaining_quota', 'daily_average', 'projected_monthly']:
            result_dict[field] = str(result_dict[field])
        result_dict['last_checked'] = result_dict['last_checked'].isoformat()
        result_dict['status'] = result_dict['status'].value
        
        await redis_client.setex(quota_status_key, 300, json.dumps(result_dict))  # 5 min cache
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to check cost quota for company {company_id}: {e}")
        # Return safe status on error
        return QuotaStatusResult(
            company_id=company_id,
            status=QuotaStatus.SAFE,
            current_monthly_cost=Decimal('0'),
            monthly_limit=Decimal('999999'),
            usage_percentage=0.0,
            remaining_quota=Decimal('999999'),
            daily_average=Decimal('0'),
            projected_monthly=Decimal('0'),
            days_until_limit=None,
            last_checked=datetime.utcnow()
        )

async def send_cost_alert(company_id: str, alert_type: str, **kwargs) -> bool:
    """
    Send cost notification/alert
    
    Args:
        company_id: Company identifier
        alert_type: Type of alert (quota_warning, quota_critical, etc.)
        **kwargs: Additional alert data
        
    Returns:
        bool: True if alert sent successfully
    """
    try:
        # Check alert cooldown to prevent spam
        if await _is_alert_in_cooldown(company_id, alert_type):
            logger.debug(f"Alert {alert_type} for company {company_id} is in cooldown")
            return False
        
        # Create alert data
        alert_data = {
            'company_id': company_id,
            'alert_type': alert_type,
            'timestamp': datetime.utcnow().isoformat(),
            'data': kwargs
        }
        
        # Store alert in Redis for history
        redis_client = await cost_tracker._get_redis_client()
        alert_history_key = cost_tracker.ALERT_HISTORY_KEY.format(company_id=company_id)
        
        # Add to alert history list (keep last 100 alerts)
        pipe = redis_client.pipeline()
        pipe.lpush(alert_history_key, json.dumps(alert_data))
        pipe.ltrim(alert_history_key, 0, 99)  # Keep only last 100 alerts
        pipe.expire(alert_history_key, 86400 * 30)  # 30 days TTL
        await pipe.execute()
        
        # Set cooldown for this alert type
        cooldown_key = f"alert_cooldown:{company_id}:{alert_type}"
        await redis_client.setex(cooldown_key, cost_tracker.ALERT_COOLDOWN, "1")
        
        # Store in database for persistence
        await _store_alert_in_database(alert_data)
        
        # TODO: Integrate with notification system (email, webhook, etc.)
        logger.info(f"Cost alert sent: {alert_type} for company {company_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to send cost alert for company {company_id}: {e}")
        return False

async def project_monthly_cost(company_id: str) -> float:
    """
    Project end-of-month cost based on current usage patterns
    
    Args:
        company_id: Company identifier
        
    Returns:
        float: Projected monthly cost
    """
    try:
        redis_client = await cost_tracker._get_redis_client()
        
        # Check cache first
        projection_key = cost_tracker.PROJECTION_KEY.format(company_id=company_id)
        cached_projection = await redis_client.get(projection_key)
        
        if cached_projection:
            data = json.loads(cached_projection)
            return float(data['projected_monthly_cost'])
        
        # Calculate projection
        current_time = datetime.utcnow()
        current_monthly_cost = Decimal(str(await get_current_cost(company_id, CostPeriod.MONTHLY.value)))
        
        # Get historical daily costs for trend analysis
        daily_costs = await _get_daily_costs_for_month(company_id, current_time)
        
        if not daily_costs:
            # No historical data - use current month average
            days_elapsed = current_time.day
            if days_elapsed > 0:
                daily_average = current_monthly_cost / days_elapsed
                days_in_month = (current_time.replace(month=current_time.month + 1, day=1) - timedelta(days=1)).day
                projected_cost = daily_average * days_in_month
            else:
                projected_cost = current_monthly_cost
            
            confidence = 60.0  # Low confidence without historical data
        else:
            # Calculate trend-based projection
            projected_cost, confidence = await _calculate_trend_projection(
                daily_costs, current_monthly_cost, current_time
            )
        
        # Create projection object
        projection = CostProjection(
            company_id=company_id,
            projected_monthly_cost=projected_cost,
            confidence_score=confidence,
            current_month_cost=current_monthly_cost,
            days_elapsed=current_time.day,
            days_remaining=(datetime(current_time.year, current_time.month + 1, 1) - current_time).days,
            average_daily_cost=current_monthly_cost / current_time.day if current_time.day > 0 else Decimal('0'),
            trend_factor=1.0,  # TODO: Calculate actual trend factor
            projection_date=current_time
        )
        
        # Cache the projection
        projection_dict = asdict(projection)
        for field in ['projected_monthly_cost', 'current_month_cost', 'average_daily_cost']:
            projection_dict[field] = str(projection_dict[field])
        projection_dict['projection_date'] = projection_dict['projection_date'].isoformat()
        
        await redis_client.setex(projection_key, cost_tracker.PROJECTION_TTL, json.dumps(projection_dict))
        
        # Check if projection warrants an alert
        quota_status = await check_cost_quota(company_id)
        if projected_cost > quota_status.monthly_limit * Decimal('0.9'):  # 90% of quota
            await send_cost_alert(
                company_id, 
                AlertType.PROJECTION_HIGH.value,
                projected_cost=str(projected_cost),
                quota_limit=str(quota_status.monthly_limit),
                confidence=confidence
            )
        
        return float(projected_cost)
        
    except Exception as e:
        logger.error(f"Failed to project monthly cost for company {company_id}: {e}")
        return 0.0

async def get_cost_optimization_recommendations(company_id: str) -> List[CostOptimization]:
    """
    Generate cost optimization recommendations based on usage patterns
    
    Args:
        company_id: Company identifier
        
    Returns:
        List[CostOptimization]: List of optimization recommendations
    """
    try:
        recommendations = []
        
        # Get usage analytics for the company
        usage_data = await _get_company_usage_analytics(company_id)
        
        if not usage_data:
            return recommendations
        
        # Analyze vendor distribution
        vendor_analysis = await _analyze_vendor_usage(usage_data)
        if vendor_analysis:
            recommendations.extend(vendor_analysis)
        
        # Analyze model usage patterns
        model_analysis = await _analyze_model_usage(usage_data)
        if model_analysis:
            recommendations.extend(model_analysis)
        
        # Analyze time-based patterns
        time_analysis = await _analyze_time_patterns(usage_data)
        if time_analysis:
            recommendations.extend(time_analysis)
        
        # Sort by potential savings (highest first)
        recommendations.sort(key=lambda x: x.potential_savings, reverse=True)
        
        # Cache recommendations
        redis_client = await cost_tracker._get_redis_client()
        optimization_key = cost_tracker.OPTIMIZATION_KEY.format(company_id=company_id)
        
        recommendations_dict = []
        for rec in recommendations:
            rec_dict = asdict(rec)
            rec_dict['potential_savings'] = str(rec_dict['potential_savings'])
            recommendations_dict.append(rec_dict)
        
        await redis_client.setex(optimization_key, 3600, json.dumps(recommendations_dict))  # 1 hour cache
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Failed to get cost optimization recommendations for company {company_id}: {e}")
        return []

# ============================================================================
# Helper Functions
# ============================================================================

async def _get_quota_info(company_id: str) -> Optional[QuotaInfo]:
    """Get quota configuration for a company"""
    try:
        query = """
            SELECT company_id, monthly_limit, daily_limit, hourly_limit,
                   warning_threshold, critical_threshold, is_active, auto_suspend,
                   created_at, updated_at
            FROM company_quotas
            WHERE company_id = $1 AND is_active = true
        """
        
        result = await DatabaseUtils.execute_query(query, [company_id])
        
        if result:
            return QuotaInfo(
                company_id=result['company_id'],
                monthly_limit=Decimal(str(result['monthly_limit'])),
                daily_limit=Decimal(str(result['daily_limit'])) if result['daily_limit'] else None,
                hourly_limit=Decimal(str(result['hourly_limit'])) if result['hourly_limit'] else None,
                warning_threshold=float(result.get('warning_threshold', 0.8)),
                critical_threshold=float(result.get('critical_threshold', 0.95)),
                is_active=result.get('is_active', True),
                auto_suspend=result.get('auto_suspend', False),
                created_at=result.get('created_at'),
                updated_at=result.get('updated_at')
            )
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to get quota info for company {company_id}: {e}")
        return None

async def _trigger_quota_alert(company_id: str, quota_status: QuotaStatusResult):
    """Trigger appropriate quota alerts based on status"""
    try:
        alert_data = {
            'current_cost': str(quota_status.current_monthly_cost),
            'quota_limit': str(quota_status.monthly_limit),
            'usage_percentage': quota_status.usage_percentage,
            'remaining_quota': str(quota_status.remaining_quota),
            'projected_monthly': str(quota_status.projected_monthly)
        }
        
        if quota_status.status == QuotaStatus.WARNING:
            await send_cost_alert(company_id, AlertType.QUOTA_WARNING.value, **alert_data)
        elif quota_status.status == QuotaStatus.CRITICAL:
            await send_cost_alert(company_id, AlertType.QUOTA_CRITICAL.value, **alert_data)
        elif quota_status.status == QuotaStatus.EXCEEDED:
            await send_cost_alert(company_id, AlertType.QUOTA_EXCEEDED.value, **alert_data)
            
    except Exception as e:
        logger.error(f"Failed to trigger quota alert for company {company_id}: {e}")

async def _is_alert_in_cooldown(company_id: str, alert_type: str) -> bool:
    """Check if alert type is in cooldown period"""
    try:
        redis_client = await cost_tracker._get_redis_client()
        cooldown_key = f"alert_cooldown:{company_id}:{alert_type}"
        
        result = await redis_client.get(cooldown_key)
        return result is not None
        
    except Exception as e:
        logger.error(f"Failed to check alert cooldown: {e}")
        return False

async def _store_alert_in_database(alert_data: Dict[str, Any]):
    """Store alert in database for persistence"""
    try:
        query = """
            INSERT INTO cost_alerts_log (
                company_id, alert_type, alert_data, created_at
            ) VALUES ($1, $2, $3, $4)
        """
        
        await DatabaseUtils.execute_query(query, [
            alert_data['company_id'],
            alert_data['alert_type'],
            json.dumps(alert_data['data']),
            datetime.fromisoformat(alert_data['timestamp'])
        ])
        
    except Exception as e:
        logger.error(f"Failed to store alert in database: {e}")

async def _get_daily_costs_for_month(company_id: str, month_date: datetime) -> List[Tuple[datetime, Decimal]]:
    """Get daily costs for the current month"""
    try:
        month_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        query = """
            SELECT DATE(calculation_timestamp) as day, SUM(total_cost) as daily_cost
            FROM cost_calculations
            WHERE company_id = $1 
            AND calculation_timestamp >= $2
            AND calculation_timestamp < $3
            GROUP BY DATE(calculation_timestamp)
            ORDER BY day
        """
        
        month_end = month_date.replace(day=1) + timedelta(days=32)
        month_end = month_end.replace(day=1)  # First day of next month
        
        results = await DatabaseUtils.execute_query(query, [company_id, month_start, month_end], fetch_all=True)
        
        daily_costs = []
        for result in results:
            daily_costs.append((result['day'], Decimal(str(result['daily_cost']))))
        
        return daily_costs
        
    except Exception as e:
        logger.error(f"Failed to get daily costs for company {company_id}: {e}")
        return []

async def _calculate_trend_projection(
    daily_costs: List[Tuple[datetime, Decimal]], 
    current_cost: Decimal, 
    current_time: datetime
) -> Tuple[Decimal, float]:
    """Calculate trend-based cost projection"""
    try:
        if len(daily_costs) < 3:
            # Not enough data for trend analysis
            days_elapsed = current_time.day
            daily_average = current_cost / days_elapsed if days_elapsed > 0 else Decimal('0')
            days_in_month = (current_time.replace(month=current_time.month + 1, day=1) - timedelta(days=1)).day
            return daily_average * days_in_month, 70.0
        
        # Extract costs and calculate trend
        costs = [float(cost) for _, cost in daily_costs]
        
        # Simple linear trend calculation
        x = list(range(len(costs)))
        y = costs
        
        # Calculate linear regression slope
        n = len(x)
        if n > 1:
            slope = (n * sum(x[i] * y[i] for i in range(n)) - sum(x) * sum(y)) / (n * sum(x[i]**2 for i in range(n)) - sum(x)**2)
            
            # Project remaining days with trend
            days_elapsed = len(daily_costs)
            days_in_month = (current_time.replace(month=current_time.month + 1, day=1) - timedelta(days=1)).day
            days_remaining = days_in_month - days_elapsed
            
            # Calculate projected cost with trend
            recent_average = sum(costs[-7:]) / min(7, len(costs))  # Last 7 days average
            trend_adjusted_daily = recent_average + (slope * days_remaining / 2)  # Apply trend
            
            projected_remaining = Decimal(str(max(0, trend_adjusted_daily * days_remaining)))
            projected_total = current_cost + projected_remaining
            
            # Calculate confidence based on trend consistency
            if len(costs) >= 7:
                recent_variance = statistics.variance(costs[-7:])
                confidence = max(60.0, min(95.0, 90.0 - (recent_variance / recent_average * 10)))
            else:
                confidence = 75.0
            
            return projected_total, confidence
        else:
            # Fallback to simple average
            daily_average = current_cost / current_time.day
            days_in_month = (current_time.replace(month=current_time.month + 1, day=1) - timedelta(days=1)).day
            return daily_average * days_in_month, 70.0
            
    except Exception as e:
        logger.error(f"Failed to calculate trend projection: {e}")
        # Fallback calculation
        days_elapsed = current_time.day
        daily_average = current_cost / days_elapsed if days_elapsed > 0 else Decimal('0')
        days_in_month = (current_time.replace(month=current_time.month + 1, day=1) - timedelta(days=1)).day
        return daily_average * days_in_month, 60.0

async def _get_company_usage_analytics(company_id: str) -> Optional[Dict[str, Any]]:
    """Get comprehensive usage analytics for a company"""
    try:
        # Get last 30 days of usage data
        query = """
            SELECT vendor, model, 
                   SUM(total_cost) as total_cost,
                   SUM(input_units) as total_input_units,
                   SUM(output_units) as total_output_units,
                   COUNT(*) as request_count,
                   AVG(total_cost) as avg_cost_per_request
            FROM cost_calculations
            WHERE company_id = $1 
            AND calculation_timestamp >= $2
            GROUP BY vendor, model
            ORDER BY total_cost DESC
        """
        
        since_date = datetime.utcnow() - timedelta(days=30)
        results = await DatabaseUtils.execute_query(query, [company_id, since_date], fetch_all=True)
        
        if not results:
            return None
        
        usage_data = {
            'vendor_model_breakdown': [],
            'total_cost': Decimal('0'),
            'total_requests': 0,
            'analysis_period': 30
        }
        
        for result in results:
            vendor_model_data = {
                'vendor': result['vendor'],
                'model': result['model'],
                'total_cost': Decimal(str(result['total_cost'])),
                'total_input_units': result['total_input_units'],
                'total_output_units': result['total_output_units'],
                'request_count': result['request_count'],
                'avg_cost_per_request': Decimal(str(result['avg_cost_per_request']))
            }
            
            usage_data['vendor_model_breakdown'].append(vendor_model_data)
            usage_data['total_cost'] += vendor_model_data['total_cost']
            usage_data['total_requests'] += vendor_model_data['request_count']
        
        return usage_data
        
    except Exception as e:
        logger.error(f"Failed to get usage analytics for company {company_id}: {e}")
        return None

async def _analyze_vendor_usage(usage_data: Dict[str, Any]) -> List[CostOptimization]:
    """Analyze vendor usage patterns for optimization opportunities"""
    recommendations = []
    
    try:
        vendor_totals = {}
        for item in usage_data['vendor_model_breakdown']:
            vendor = item['vendor']
            if vendor not in vendor_totals:
                vendor_totals[vendor] = {
                    'cost': Decimal('0'),
                    'requests': 0,
                    'models': []
                }
            
            vendor_totals[vendor]['cost'] += item['total_cost']
            vendor_totals[vendor]['requests'] += item['request_count']
            vendor_totals[vendor]['models'].append(item)
        
        # Check for vendor concentration
        total_cost = usage_data['total_cost']
        for vendor, data in vendor_totals.items():
            vendor_percentage = (data['cost'] / total_cost) * 100
            
            if vendor_percentage > 80:
                # High vendor concentration - recommend diversification
                potential_savings = data['cost'] * Decimal('0.15')  # Assume 15% savings from diversification
                
                recommendations.append(CostOptimization(
                    company_id=usage_data.get('company_id', ''),
                    optimization_type='vendor_diversification',
                    description=f"Consider diversifying from {vendor} (currently {vendor_percentage:.1f}% of costs)",
                    potential_savings=potential_savings,
                    confidence=0.7,
                    implementation_difficulty='medium',
                    estimated_impact='medium',
                    details={
                        'current_vendor': vendor,
                        'current_percentage': vendor_percentage,
                        'recommended_action': 'Evaluate alternative vendors for similar capabilities'
                    }
                ))
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Failed to analyze vendor usage: {e}")
        return []

async def _analyze_model_usage(usage_data: Dict[str, Any]) -> List[CostOptimization]:
    """Analyze model usage patterns for optimization opportunities"""
    recommendations = []
    
    try:
        # Look for expensive models with low utilization
        for item in usage_data['vendor_model_breakdown']:
            avg_cost = item['avg_cost_per_request']
            
            # If average cost per request is high, suggest model optimization
            if avg_cost > Decimal('0.10'):  # $0.10 per request threshold
                potential_savings = item['total_cost'] * Decimal('0.3')  # Assume 30% savings from model optimization
                
                recommendations.append(CostOptimization(
                    company_id=usage_data.get('company_id', ''),
                    optimization_type='model_optimization',
                    description=f"Consider using a more cost-effective model than {item['vendor']}:{item['model']}",
                    potential_savings=potential_savings,
                    confidence=0.6,
                    implementation_difficulty='easy',
                    estimated_impact='high',
                    details={
                        'current_model': f"{item['vendor']}:{item['model']}",
                        'avg_cost_per_request': str(avg_cost),
                        'total_requests': item['request_count'],
                        'recommended_action': 'Evaluate lower-cost models with similar capabilities'
                    }
                ))
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Failed to analyze model usage: {e}")
        return []

async def _analyze_time_patterns(usage_data: Dict[str, Any]) -> List[CostOptimization]:
    """Analyze time-based usage patterns for optimization opportunities"""
    recommendations = []
    
    try:
        # This would require time-series data analysis
        # For now, provide a general recommendation about usage patterns
        
        if usage_data['total_requests'] > 10000:  # High volume usage
            potential_savings = usage_data['total_cost'] * Decimal('0.1')  # 10% savings from batching
            
            recommendations.append(CostOptimization(
                company_id=usage_data.get('company_id', ''),
                optimization_type='request_batching',
                description="Consider batching requests during off-peak hours for better rates",
                potential_savings=potential_savings,
                confidence=0.5,
                implementation_difficulty='hard',
                estimated_impact='low',
                details={
                    'total_requests': usage_data['total_requests'],
                    'recommended_action': 'Implement request batching and scheduling optimization'
                }
            ))
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Failed to analyze time patterns: {e}")
        return []

async def close_real_time_cost_connections():
    """Close real-time cost tracking connections"""
    if cost_tracker._redis_client:
        await cost_tracker._redis_client.aclose()
    logger.info("Real-time cost tracking connections closed")