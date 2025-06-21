"""
Usage Quota Management - Monthly request and cost quota tracking with enforcement
Implements comprehensive quota management with real-time tracking, alerts, and automated resets
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
import calendar

import redis.asyncio as aioredis

from ..config import get_settings
from ..utils.logger import get_logger
from ..database import DatabaseUtils
from .cache import cache_service, _get_cache_key, TTL
from .real_time_cost import QuotaStatus, QuotaStatusResult

# Set decimal precision for cost calculations
getcontext().prec = 10

settings = get_settings()
logger = get_logger(__name__)

class QuotaType(str, Enum):
    """Types of quotas"""
    REQUESTS = "requests"
    COST = "cost"
    COMBINED = "combined"

class QuotaAlert(str, Enum):
    """Quota alert thresholds"""
    WARNING_75 = "warning_75"    # 75% of quota used
    CRITICAL_90 = "critical_90"  # 90% of quota used
    DANGER_95 = "danger_95"      # 95% of quota used
    EXCEEDED = "exceeded"        # 100% quota exceeded
    BLOCKED = "blocked"          # Service blocked due to quota

class QuotaPeriod(str, Enum):
    """Quota tracking periods"""
    MONTHLY = "monthly"
    DAILY = "daily"
    YEARLY = "yearly"

@dataclass
class QuotaConfiguration:
    """Complete quota configuration for a company"""
    company_id: str
    monthly_request_limit: int
    monthly_cost_limit: Decimal
    daily_request_limit: Optional[int] = None
    daily_cost_limit: Optional[Decimal] = None
    warning_threshold: float = 0.75      # 75%
    critical_threshold: float = 0.90     # 90%
    danger_threshold: float = 0.95       # 95%
    is_active: bool = True
    auto_block: bool = True              # Block requests when quota exceeded
    grace_period_hours: int = 24         # Grace period before blocking
    reset_day: int = 1                   # Day of month to reset (1st)
    timezone: str = "UTC"
    created_at: datetime = None
    updated_at: datetime = None

@dataclass
class UsageMetrics:
    """Current usage metrics for a company"""
    company_id: str
    period: QuotaPeriod
    period_start: datetime
    period_end: datetime
    total_requests: int
    total_cost: Decimal
    current_month_requests: int
    current_month_cost: Decimal
    last_request_time: Optional[datetime] = None
    last_cost_update: Optional[datetime] = None

@dataclass
class QuotaStatusDetail:
    """Detailed quota status including both request and cost quotas"""
    company_id: str
    period: QuotaPeriod
    
    # Request quota status
    request_quota_status: QuotaStatus
    current_requests: int
    request_limit: int
    remaining_requests: int
    request_usage_percentage: float
    
    # Cost quota status  
    cost_quota_status: QuotaStatus
    current_cost: Decimal
    cost_limit: Decimal
    remaining_cost: Decimal
    cost_usage_percentage: float
    
    # Overall status (most restrictive)
    overall_status: QuotaStatus
    is_blocked: bool
    block_reason: Optional[str]
    
    # Time information
    period_start: datetime
    period_end: datetime
    days_remaining: int
    reset_time: datetime
    
    # Alert information
    triggered_alerts: List[str]
    last_alert_time: Optional[datetime]
    
    checked_at: datetime

class QuotaManagementService:
    """Enterprise quota management service"""
    
    def __init__(self):
        self._redis_client: Optional[aioredis.Redis] = None
        
        # Redis key patterns
        self.QUOTA_USAGE_KEY = "quota:usage:{company_id}:{period}:{timestamp}"
        self.QUOTA_CONFIG_KEY = "quota:config:{company_id}"
        self.QUOTA_ALERTS_KEY = "quota:alerts:{company_id}"
        self.QUOTA_BLOCK_KEY = "quota:blocked:{company_id}"
        self.QUOTA_STATS_KEY = "quota:stats:{company_id}:{period}"
        
        # Alert cooldown periods (prevent spam)
        self.ALERT_COOLDOWNS = {
            QuotaAlert.WARNING_75: 3600,     # 1 hour
            QuotaAlert.CRITICAL_90: 1800,    # 30 minutes
            QuotaAlert.DANGER_95: 900,       # 15 minutes
            QuotaAlert.EXCEEDED: 300,        # 5 minutes
            QuotaAlert.BLOCKED: 60           # 1 minute
        }
        
        # Default quota configurations by tier
        self.DEFAULT_QUOTAS = {
            'free': {
                'monthly_request_limit': 1000,
                'monthly_cost_limit': Decimal('10.00'),
                'daily_request_limit': 100,
                'daily_cost_limit': Decimal('1.00')
            },
            'basic': {
                'monthly_request_limit': 10000,
                'monthly_cost_limit': Decimal('100.00'),
                'daily_request_limit': 1000,
                'daily_cost_limit': Decimal('10.00')
            },
            'premium': {
                'monthly_request_limit': 100000,
                'monthly_cost_limit': Decimal('1000.00'),
                'daily_request_limit': 10000,
                'daily_cost_limit': Decimal('100.00')
            },
            'enterprise': {
                'monthly_request_limit': 1000000,
                'monthly_cost_limit': Decimal('10000.00'),
                'daily_request_limit': 50000,
                'daily_cost_limit': Decimal('500.00')
            }
        }
    
    async def _get_redis_client(self) -> aioredis.Redis:
        """Get Redis client with connection pooling"""
        if not self._redis_client:
            self._redis_client = await cache_service._get_redis_client()
        return self._redis_client

# Global quota management service instance
quota_service = QuotaManagementService()

async def check_usage_quota(company_id: str) -> QuotaStatusDetail:
    """
    Check current request quota status for a company
    
    Args:
        company_id: Company identifier
        
    Returns:
        QuotaStatusDetail: Comprehensive quota status
    """
    try:
        # Get quota configuration
        config = await _get_quota_config(company_id)
        if not config:
            config = await _create_default_quota_config(company_id)
        
        # Get current usage metrics
        current_time = datetime.utcnow()
        usage_metrics = await _get_usage_metrics(company_id, QuotaPeriod.MONTHLY, current_time)
        
        # Calculate request quota status
        request_usage_percentage = (usage_metrics.current_month_requests / config.monthly_request_limit) * 100
        remaining_requests = max(0, config.monthly_request_limit - usage_metrics.current_month_requests)
        
        # Determine request quota status
        if request_usage_percentage >= 100:
            request_quota_status = QuotaStatus.EXCEEDED
        elif request_usage_percentage >= config.danger_threshold * 100:
            request_quota_status = QuotaStatus.CRITICAL
        elif request_usage_percentage >= config.warning_threshold * 100:
            request_quota_status = QuotaStatus.WARNING
        else:
            request_quota_status = QuotaStatus.SAFE
        
        # Calculate cost quota status (reuse existing logic)
        cost_result = await check_cost_quota(company_id)
        
        # Determine overall status (most restrictive)
        if request_quota_status == QuotaStatus.EXCEEDED or cost_result.status == QuotaStatus.EXCEEDED:
            overall_status = QuotaStatus.EXCEEDED
        elif request_quota_status == QuotaStatus.CRITICAL or cost_result.status == QuotaStatus.CRITICAL:
            overall_status = QuotaStatus.CRITICAL
        elif request_quota_status == QuotaStatus.WARNING or cost_result.status == QuotaStatus.WARNING:
            overall_status = QuotaStatus.WARNING
        else:
            overall_status = QuotaStatus.SAFE
        
        # Check if company is blocked
        is_blocked, block_reason = await _check_quota_block_status(company_id)
        
        # Calculate time information
        period_start = usage_metrics.period_start
        period_end = usage_metrics.period_end
        days_remaining = (period_end - current_time).days
        reset_time = _calculate_next_reset_time(current_time, config.reset_day)
        
        # Check for triggered alerts
        triggered_alerts = await _get_triggered_alerts(company_id, request_usage_percentage, cost_result.usage_percentage)
        
        # Get last alert time
        last_alert_time = await _get_last_alert_time(company_id)
        
        return QuotaStatusDetail(
            company_id=company_id,
            period=QuotaPeriod.MONTHLY,
            request_quota_status=request_quota_status,
            current_requests=usage_metrics.current_month_requests,
            request_limit=config.monthly_request_limit,
            remaining_requests=remaining_requests,
            request_usage_percentage=request_usage_percentage,
            cost_quota_status=cost_result.status,
            current_cost=cost_result.current_monthly_cost,
            cost_limit=cost_result.monthly_limit,
            remaining_cost=cost_result.remaining_quota,
            cost_usage_percentage=cost_result.usage_percentage,
            overall_status=overall_status,
            is_blocked=is_blocked,
            block_reason=block_reason,
            period_start=period_start,
            period_end=period_end,
            days_remaining=days_remaining,
            reset_time=reset_time,
            triggered_alerts=triggered_alerts,
            last_alert_time=last_alert_time,
            checked_at=current_time
        )
        
    except Exception as e:
        logger.error(f"Failed to check usage quota for company {company_id}: {e}")
        # Return safe status on error
        return QuotaStatusDetail(
            company_id=company_id,
            period=QuotaPeriod.MONTHLY,
            request_quota_status=QuotaStatus.SAFE,
            current_requests=0,
            request_limit=10000,
            remaining_requests=10000,
            request_usage_percentage=0.0,
            cost_quota_status=QuotaStatus.SAFE,
            current_cost=Decimal('0'),
            cost_limit=Decimal('1000'),
            remaining_cost=Decimal('1000'),
            cost_usage_percentage=0.0,
            overall_status=QuotaStatus.SAFE,
            is_blocked=False,
            block_reason=None,
            period_start=datetime.utcnow().replace(day=1),
            period_end=_get_month_end(datetime.utcnow()),
            days_remaining=30,
            reset_time=_calculate_next_reset_time(datetime.utcnow(), 1),
            triggered_alerts=[],
            last_alert_time=None,
            checked_at=datetime.utcnow()
        )

async def check_cost_quota(company_id: str) -> QuotaStatusResult:
    """
    Check current cost quota status for a company
    This extends the existing cost quota check from real_time_cost.py
    
    Args:
        company_id: Company identifier
        
    Returns:
        QuotaStatusResult: Cost quota status details
    """
    try:
        # Import here to avoid circular imports
        from .real_time_cost import check_cost_quota as check_cost_quota_existing
        
        # Use existing cost quota check
        result = await check_cost_quota_existing(company_id)
        
        # Enhance with additional quota management features
        config = await _get_quota_config(company_id)
        if config:
            # Update thresholds based on quota config
            usage_percentage = result.usage_percentage
            
            if usage_percentage >= config.danger_threshold * 100:
                result.status = QuotaStatus.CRITICAL
            elif usage_percentage >= config.critical_threshold * 100:
                result.status = QuotaStatus.CRITICAL  
            elif usage_percentage >= config.warning_threshold * 100:
                result.status = QuotaStatus.WARNING
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to check cost quota for company {company_id}: {e}")
        # Return safe status on error
        return QuotaStatusResult(
            company_id=company_id,
            status=QuotaStatus.SAFE,
            current_monthly_cost=Decimal('0'),
            monthly_limit=Decimal('1000'),
            usage_percentage=0.0,
            remaining_quota=Decimal('1000'),
            daily_average=Decimal('0'),
            projected_monthly=Decimal('0'),
            days_until_limit=None,
            last_checked=datetime.utcnow()
        )

async def update_quota_usage(company_id: str, requests: int, cost: float) -> bool:
    """
    Update quota usage counters for requests and cost
    
    Args:
        company_id: Company identifier
        requests: Number of requests to add
        cost: Cost amount to add
        
    Returns:
        bool: True if updated successfully
    """
    try:
        redis_client = await quota_service._get_redis_client()
        current_time = datetime.utcnow()
        cost_decimal = Decimal(str(cost))
        
        # Update request and cost counters atomically
        pipe = redis_client.pipeline()
        
        # Monthly counters
        month_start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_timestamp = int(month_start.timestamp())
        
        request_key = quota_service.QUOTA_USAGE_KEY.format(
            company_id=company_id,
            period=QuotaPeriod.MONTHLY.value,
            timestamp=f"requests_{month_timestamp}"
        )
        
        cost_key = quota_service.QUOTA_USAGE_KEY.format(
            company_id=company_id,
            period=QuotaPeriod.MONTHLY.value,
            timestamp=f"cost_{month_timestamp}"
        )
        
        # Increment counters
        pipe.incrby(request_key, requests)
        pipe.incrbyfloat(cost_key, float(cost_decimal))
        
        # Set expiry (end of next month)
        next_month = _get_next_month_start(current_time)
        expire_time = int((next_month - current_time).total_seconds())
        pipe.expire(request_key, expire_time + 86400)  # Add 1 day buffer
        pipe.expire(cost_key, expire_time + 86400)
        
        # Update last usage timestamp
        stats_key = quota_service.QUOTA_STATS_KEY.format(
            company_id=company_id,
            period=QuotaPeriod.MONTHLY.value
        )
        pipe.hset(stats_key, "last_request_time", current_time.isoformat())
        pipe.hset(stats_key, "last_cost_update", current_time.isoformat())
        pipe.expire(stats_key, expire_time + 86400)
        
        # Execute pipeline
        await pipe.execute()
        
        # Also update real-time cost tracking
        from .real_time_cost import update_real_time_cost
        await update_real_time_cost(company_id, cost)
        
        # Check if this update triggers quota alerts
        await _check_and_trigger_quota_alerts(company_id, requests, cost_decimal)
        
        logger.debug(f"Updated quota usage for company {company_id}: +{requests} requests, +${cost}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update quota usage for company {company_id}: {e}")
        return False

async def send_quota_alert(company_id: str, quota_type: str, percentage: float) -> bool:
    """
    Send quota alert notification
    
    Args:
        company_id: Company identifier
        quota_type: Type of quota (requests, cost, combined)
        percentage: Current usage percentage
        
    Returns:
        bool: True if alert sent successfully
    """
    try:
        # Determine alert level based on percentage
        if percentage >= 100:
            alert_level = QuotaAlert.EXCEEDED
        elif percentage >= 95:
            alert_level = QuotaAlert.DANGER_95
        elif percentage >= 90:
            alert_level = QuotaAlert.CRITICAL_90
        elif percentage >= 75:
            alert_level = QuotaAlert.WARNING_75
        else:
            # No alert needed
            return True
        
        # Check cooldown to prevent spam
        if await _is_quota_alert_in_cooldown(company_id, alert_level):
            logger.debug(f"Quota alert {alert_level} for company {company_id} is in cooldown")
            return False
        
        # Get quota configuration for context
        config = await _get_quota_config(company_id)
        if not config:
            config = await _create_default_quota_config(company_id)
        
        # Create alert data
        alert_data = {
            'company_id': company_id,
            'quota_type': quota_type,
            'alert_level': alert_level.value,
            'usage_percentage': percentage,
            'threshold_triggered': _get_threshold_for_alert(alert_level),
            'timestamp': datetime.utcnow().isoformat(),
            'config': {
                'monthly_request_limit': config.monthly_request_limit,
                'monthly_cost_limit': str(config.monthly_cost_limit),
                'auto_block': config.auto_block,
                'grace_period_hours': config.grace_period_hours
            }
        }
        
        # Store alert in Redis
        redis_client = await quota_service._get_redis_client()
        alert_key = quota_service.QUOTA_ALERTS_KEY.format(company_id=company_id)
        
        # Add to alert history list
        pipe = redis_client.pipeline()
        pipe.lpush(alert_key, json.dumps(alert_data))
        pipe.ltrim(alert_key, 0, 99)  # Keep last 100 alerts
        pipe.expire(alert_key, 86400 * 30)  # 30 days TTL
        await pipe.execute()
        
        # Set cooldown
        cooldown_key = f"quota_alert_cooldown:{company_id}:{alert_level.value}"
        await redis_client.setex(cooldown_key, quota_service.ALERT_COOLDOWNS[alert_level], "1")
        
        # Store in database for persistence
        await _store_quota_alert_in_database(alert_data)
        
        # If quota exceeded and auto-block enabled, block the company
        if alert_level == QuotaAlert.EXCEEDED and config.auto_block:
            await _block_company_for_quota_violation(company_id, quota_type, percentage)
        
        # TODO: Integrate with notification system (email, webhook, etc.)
        logger.info(f"Quota alert sent: {alert_level.value} for company {company_id} ({quota_type}: {percentage:.1f}%)")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to send quota alert for company {company_id}: {e}")
        return False

async def reset_monthly_quotas() -> Dict[str, Any]:
    """
    Automated monthly quota reset for all companies
    This should be run as a scheduled job (e.g., monthly cron job)
    
    Returns:
        Dict: Reset operation results
    """
    try:
        start_time = time.time()
        logger.info("Starting automated monthly quota reset...")
        
        # Get all companies that need quota reset
        query = """
            SELECT DISTINCT company_id, reset_day, timezone
            FROM quota_configurations 
            WHERE is_active = true
        """
        
        companies = await DatabaseUtils.execute_query(query, fetch_all=True)
        
        reset_results = {
            'total_companies': len(companies) if companies else 0,
            'successful_resets': 0,
            'failed_resets': 0,
            'errors': [],
            'reset_timestamp': datetime.utcnow().isoformat(),
            'execution_time_seconds': 0
        }
        
        if not companies:
            logger.info("No companies found for quota reset")
            return reset_results
        
        redis_client = await quota_service._get_redis_client()
        current_time = datetime.utcnow()
        
        for company_data in companies:
            try:
                company_id = company_data['company_id']
                reset_day = company_data.get('reset_day', 1)
                company_timezone = company_data.get('timezone', 'UTC')
                
                # Check if it's time to reset for this company
                if not _should_reset_quota_for_company(current_time, reset_day, company_timezone):
                    continue
                
                # Reset Redis counters
                await _reset_company_quota_counters(company_id, current_time, redis_client)
                
                # Clear any quota blocks
                await _unblock_company_quota(company_id, redis_client)
                
                # Log reset in database
                await _log_quota_reset(company_id, current_time)
                
                reset_results['successful_resets'] += 1
                logger.info(f"Successfully reset quotas for company {company_id}")
                
            except Exception as e:
                error_msg = f"Failed to reset quota for company {company_data.get('company_id', 'unknown')}: {e}"
                logger.error(error_msg)
                reset_results['errors'].append(error_msg)
                reset_results['failed_resets'] += 1
        
        execution_time = time.time() - start_time
        reset_results['execution_time_seconds'] = round(execution_time, 2)
        
        logger.info(f"Monthly quota reset completed: {reset_results['successful_resets']} successful, {reset_results['failed_resets']} failed in {execution_time:.2f}s")
        
        return reset_results
        
    except Exception as e:
        logger.error(f"Failed to execute monthly quota reset: {e}")
        return {
            'error': str(e),
            'reset_timestamp': datetime.utcnow().isoformat(),
            'total_companies': 0,
            'successful_resets': 0,
            'failed_resets': 0
        }

# ============================================================================
# Helper Functions
# ============================================================================

async def _get_quota_config(company_id: str) -> Optional[QuotaConfiguration]:
    """Get quota configuration for a company"""
    try:
        redis_client = await quota_service._get_redis_client()
        config_key = quota_service.QUOTA_CONFIG_KEY.format(company_id=company_id)
        
        # Try cache first
        cached_config = await redis_client.get(config_key)
        if cached_config:
            config_data = json.loads(cached_config)
            return QuotaConfiguration(
                company_id=config_data['company_id'],
                monthly_request_limit=config_data['monthly_request_limit'],
                monthly_cost_limit=Decimal(str(config_data['monthly_cost_limit'])),
                daily_request_limit=config_data.get('daily_request_limit'),
                daily_cost_limit=Decimal(str(config_data['daily_cost_limit'])) if config_data.get('daily_cost_limit') else None,
                warning_threshold=config_data.get('warning_threshold', 0.75),
                critical_threshold=config_data.get('critical_threshold', 0.90),
                danger_threshold=config_data.get('danger_threshold', 0.95),
                is_active=config_data.get('is_active', True),
                auto_block=config_data.get('auto_block', True),
                grace_period_hours=config_data.get('grace_period_hours', 24),
                reset_day=config_data.get('reset_day', 1),
                timezone=config_data.get('timezone', 'UTC'),
                created_at=datetime.fromisoformat(config_data['created_at']) if config_data.get('created_at') else None,
                updated_at=datetime.fromisoformat(config_data['updated_at']) if config_data.get('updated_at') else None
            )
        
        # Load from database
        query = """
            SELECT company_id, monthly_request_limit, monthly_cost_limit, daily_request_limit,
                   daily_cost_limit, warning_threshold, critical_threshold, danger_threshold,
                   is_active, auto_block, grace_period_hours, reset_day, timezone,
                   created_at, updated_at
            FROM quota_configurations
            WHERE company_id = $1
        """
        
        result = await DatabaseUtils.execute_query(query, [company_id])
        
        if result:
            config = QuotaConfiguration(
                company_id=result['company_id'],
                monthly_request_limit=result['monthly_request_limit'],
                monthly_cost_limit=Decimal(str(result['monthly_cost_limit'])),
                daily_request_limit=result.get('daily_request_limit'),
                daily_cost_limit=Decimal(str(result['daily_cost_limit'])) if result.get('daily_cost_limit') else None,
                warning_threshold=result.get('warning_threshold', 0.75),
                critical_threshold=result.get('critical_threshold', 0.90),
                danger_threshold=result.get('danger_threshold', 0.95),
                is_active=result.get('is_active', True),
                auto_block=result.get('auto_block', True),
                grace_period_hours=result.get('grace_period_hours', 24),
                reset_day=result.get('reset_day', 1),
                timezone=result.get('timezone', 'UTC'),
                created_at=result.get('created_at'),
                updated_at=result.get('updated_at')
            )
            
            # Cache the config
            config_dict = asdict(config)
            config_dict['monthly_cost_limit'] = str(config_dict['monthly_cost_limit'])
            if config_dict['daily_cost_limit']:
                config_dict['daily_cost_limit'] = str(config_dict['daily_cost_limit'])
            if config_dict['created_at']:
                config_dict['created_at'] = config_dict['created_at'].isoformat()
            if config_dict['updated_at']:
                config_dict['updated_at'] = config_dict['updated_at'].isoformat()
            
            await redis_client.setex(config_key, TTL.QUOTA_CONFIG, json.dumps(config_dict))
            
            return config
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to get quota config for company {company_id}: {e}")
        return None

async def _create_default_quota_config(company_id: str) -> QuotaConfiguration:
    """Create default quota configuration for a company"""
    try:
        # Get company tier to determine default quotas
        tier_query = """
            SELECT tier FROM rate_limit_configs WHERE company_id = $1
        """
        tier_result = await DatabaseUtils.execute_query(tier_query, [company_id])
        tier = tier_result.get('tier', 'basic') if tier_result else 'basic'
        
        # Get default quotas for tier
        defaults = quota_service.DEFAULT_QUOTAS.get(tier, quota_service.DEFAULT_QUOTAS['basic'])
        
        config = QuotaConfiguration(
            company_id=company_id,
            monthly_request_limit=defaults['monthly_request_limit'],
            monthly_cost_limit=defaults['monthly_cost_limit'],
            daily_request_limit=defaults.get('daily_request_limit'),
            daily_cost_limit=defaults.get('daily_cost_limit'),
            warning_threshold=0.75,
            critical_threshold=0.90,
            danger_threshold=0.95,
            is_active=True,
            auto_block=True,
            grace_period_hours=24,
            reset_day=1,
            timezone='UTC',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Store in database
        query = """
            INSERT INTO quota_configurations (
                company_id, monthly_request_limit, monthly_cost_limit, daily_request_limit,
                daily_cost_limit, warning_threshold, critical_threshold, danger_threshold,
                is_active, auto_block, grace_period_hours, reset_day, timezone,
                created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            ON CONFLICT (company_id) DO NOTHING
        """
        
        await DatabaseUtils.execute_query(query, [
            config.company_id, config.monthly_request_limit, config.monthly_cost_limit,
            config.daily_request_limit, config.daily_cost_limit, config.warning_threshold,
            config.critical_threshold, config.danger_threshold, config.is_active,
            config.auto_block, config.grace_period_hours, config.reset_day,
            config.timezone, config.created_at, config.updated_at
        ])
        
        return config
        
    except Exception as e:
        logger.error(f"Failed to create default quota config for company {company_id}: {e}")
        # Return minimal config on error
        return QuotaConfiguration(
            company_id=company_id,
            monthly_request_limit=10000,
            monthly_cost_limit=Decimal('100.00'),
            warning_threshold=0.75,
            critical_threshold=0.90,
            danger_threshold=0.95
        )

async def _get_usage_metrics(company_id: str, period: QuotaPeriod, current_time: datetime) -> UsageMetrics:
    """Get current usage metrics for a company"""
    try:
        redis_client = await quota_service._get_redis_client()
        
        # Calculate period boundaries
        if period == QuotaPeriod.MONTHLY:
            period_start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            period_end = _get_month_end(current_time)
        else:
            # For now, only monthly is implemented
            period_start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            period_end = _get_month_end(current_time)
        
        month_timestamp = int(period_start.timestamp())
        
        # Get request and cost counters
        request_key = quota_service.QUOTA_USAGE_KEY.format(
            company_id=company_id,
            period=period.value,
            timestamp=f"requests_{month_timestamp}"
        )
        
        cost_key = quota_service.QUOTA_USAGE_KEY.format(
            company_id=company_id,
            period=period.value,
            timestamp=f"cost_{month_timestamp}"
        )
        
        # Get current values
        request_count = await redis_client.get(request_key)
        cost_amount = await redis_client.get(cost_key)
        
        current_requests = int(request_count) if request_count else 0
        current_cost = Decimal(str(cost_amount)) if cost_amount else Decimal('0')
        
        # Get last activity timestamps
        stats_key = quota_service.QUOTA_STATS_KEY.format(
            company_id=company_id,
            period=period.value
        )
        stats = await redis_client.hmget(stats_key, "last_request_time", "last_cost_update")
        
        last_request_time = None
        last_cost_update = None
        
        if stats[0]:
            last_request_time = datetime.fromisoformat(stats[0])
        if stats[1]:
            last_cost_update = datetime.fromisoformat(stats[1])
        
        return UsageMetrics(
            company_id=company_id,
            period=period,
            period_start=period_start,
            period_end=period_end,
            total_requests=current_requests,  # For monthly, total = current
            total_cost=current_cost,
            current_month_requests=current_requests,
            current_month_cost=current_cost,
            last_request_time=last_request_time,
            last_cost_update=last_cost_update
        )
        
    except Exception as e:
        logger.error(f"Failed to get usage metrics for company {company_id}: {e}")
        # Return empty metrics on error
        period_start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return UsageMetrics(
            company_id=company_id,
            period=period,
            period_start=period_start,
            period_end=_get_month_end(current_time),
            total_requests=0,
            total_cost=Decimal('0'),
            current_month_requests=0,
            current_month_cost=Decimal('0')
        )

async def _check_quota_block_status(company_id: str) -> Tuple[bool, Optional[str]]:
    """Check if company is blocked due to quota violations"""
    try:
        redis_client = await quota_service._get_redis_client()
        block_key = quota_service.QUOTA_BLOCK_KEY.format(company_id=company_id)
        
        block_data = await redis_client.get(block_key)
        if block_data:
            block_info = json.loads(block_data)
            return True, block_info.get('reason', 'Quota exceeded')
        
        return False, None
        
    except Exception as e:
        logger.error(f"Failed to check quota block status for company {company_id}: {e}")
        return False, None

def _calculate_next_reset_time(current_time: datetime, reset_day: int) -> datetime:
    """Calculate the next quota reset time"""
    # Reset on the specified day of next month
    if current_time.day >= reset_day:
        # Next reset is next month
        if current_time.month == 12:
            next_reset = current_time.replace(year=current_time.year + 1, month=1, day=reset_day, hour=0, minute=0, second=0, microsecond=0)
        else:
            next_reset = current_time.replace(month=current_time.month + 1, day=reset_day, hour=0, minute=0, second=0, microsecond=0)
    else:
        # Next reset is this month
        next_reset = current_time.replace(day=reset_day, hour=0, minute=0, second=0, microsecond=0)
    
    return next_reset

def _get_month_end(date: datetime) -> datetime:
    """Get the last day of the month for a given date"""
    last_day = calendar.monthrange(date.year, date.month)[1]
    return date.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)

def _get_next_month_start(date: datetime) -> datetime:
    """Get the first day of next month"""
    if date.month == 12:
        return date.replace(year=date.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        return date.replace(month=date.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)

async def _get_triggered_alerts(company_id: str, request_percentage: float, cost_percentage: float) -> List[str]:
    """Get list of alerts that should be triggered based on current usage"""
    alerts = []
    
    max_percentage = max(request_percentage, cost_percentage)
    
    if max_percentage >= 100:
        alerts.append(QuotaAlert.EXCEEDED.value)
    elif max_percentage >= 95:
        alerts.append(QuotaAlert.DANGER_95.value)
    elif max_percentage >= 90:
        alerts.append(QuotaAlert.CRITICAL_90.value)
    elif max_percentage >= 75:
        alerts.append(QuotaAlert.WARNING_75.value)
    
    return alerts

async def _get_last_alert_time(company_id: str) -> Optional[datetime]:
    """Get the timestamp of the last alert sent for this company"""
    try:
        redis_client = await quota_service._get_redis_client()
        alert_key = quota_service.QUOTA_ALERTS_KEY.format(company_id=company_id)
        
        # Get the most recent alert
        recent_alert = await redis_client.lindex(alert_key, 0)
        if recent_alert:
            alert_data = json.loads(recent_alert)
            return datetime.fromisoformat(alert_data['timestamp'])
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to get last alert time for company {company_id}: {e}")
        return None

async def _check_and_trigger_quota_alerts(company_id: str, requests: int, cost: Decimal):
    """Check if quota usage triggers any alerts"""
    try:
        # Get current quota status
        quota_status = await check_usage_quota(company_id)
        
        # Check request quota alerts
        if quota_status.request_usage_percentage >= 75:
            await send_quota_alert(company_id, QuotaType.REQUESTS.value, quota_status.request_usage_percentage)
        
        # Check cost quota alerts
        if quota_status.cost_usage_percentage >= 75:
            await send_quota_alert(company_id, QuotaType.COST.value, quota_status.cost_usage_percentage)
        
    except Exception as e:
        logger.error(f"Failed to check and trigger quota alerts for company {company_id}: {e}")

async def _is_quota_alert_in_cooldown(company_id: str, alert_level: QuotaAlert) -> bool:
    """Check if alert is in cooldown period"""
    try:
        redis_client = await quota_service._get_redis_client()
        cooldown_key = f"quota_alert_cooldown:{company_id}:{alert_level.value}"
        
        result = await redis_client.get(cooldown_key)
        return result is not None
        
    except Exception as e:
        logger.error(f"Failed to check quota alert cooldown: {e}")
        return False

def _get_threshold_for_alert(alert_level: QuotaAlert) -> float:
    """Get the threshold percentage for an alert level"""
    thresholds = {
        QuotaAlert.WARNING_75: 75.0,
        QuotaAlert.CRITICAL_90: 90.0,
        QuotaAlert.DANGER_95: 95.0,
        QuotaAlert.EXCEEDED: 100.0,
        QuotaAlert.BLOCKED: 100.0
    }
    return thresholds.get(alert_level, 0.0)

async def _store_quota_alert_in_database(alert_data: Dict[str, Any]):
    """Store quota alert in database for persistence"""
    try:
        query = """
            INSERT INTO quota_alerts (
                company_id, alert_type, alert_level, usage_percentage, 
                threshold_triggered, alert_data, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        """
        
        await DatabaseUtils.execute_query(query, [
            alert_data['company_id'],
            alert_data['quota_type'],
            alert_data['alert_level'],
            alert_data['usage_percentage'],
            alert_data['threshold_triggered'],
            json.dumps(alert_data),
            datetime.fromisoformat(alert_data['timestamp'])
        ])
        
    except Exception as e:
        logger.error(f"Failed to store quota alert in database: {e}")

async def _block_company_for_quota_violation(company_id: str, quota_type: str, percentage: float):
    """Block company due to quota violation"""
    try:
        redis_client = await quota_service._get_redis_client()
        block_key = quota_service.QUOTA_BLOCK_KEY.format(company_id=company_id)
        
        block_data = {
            'company_id': company_id,
            'quota_type': quota_type,
            'usage_percentage': percentage,
            'blocked_at': datetime.utcnow().isoformat(),
            'reason': f'{quota_type.title()} quota exceeded ({percentage:.1f}%)',
            'auto_blocked': True
        }
        
        # Block until end of current period (month)
        current_time = datetime.utcnow()
        period_end = _get_month_end(current_time)
        ttl = int((period_end - current_time).total_seconds())
        
        await redis_client.setex(block_key, ttl, json.dumps(block_data))
        
        # Log block action
        logger.warning(f"Company {company_id} blocked for quota violation: {quota_type} at {percentage:.1f}%")
        
        # Send blocked alert
        await send_quota_alert(company_id, quota_type, percentage)
        
    except Exception as e:
        logger.error(f"Failed to block company {company_id} for quota violation: {e}")

def _should_reset_quota_for_company(current_time: datetime, reset_day: int, timezone: str) -> bool:
    """Check if it's time to reset quota for a company"""
    # For simplicity, we'll reset on the first day of each month
    # In production, you might want to handle different timezones
    return current_time.day == reset_day and current_time.hour == 0

async def _reset_company_quota_counters(company_id: str, current_time: datetime, redis_client: aioredis.Redis):
    """Reset quota counters for a company"""
    try:
        # Get all quota usage keys for this company
        patterns = [
            f"quota:usage:{company_id}:*",
            f"quota:stats:{company_id}:*"
        ]
        
        keys_to_delete = []
        for pattern in patterns:
            keys = await redis_client.keys(pattern)
            keys_to_delete.extend(keys)
        
        if keys_to_delete:
            await redis_client.delete(*keys_to_delete)
        
        logger.info(f"Reset quota counters for company {company_id}")
        
    except Exception as e:
        logger.error(f"Failed to reset quota counters for company {company_id}: {e}")

async def _unblock_company_quota(company_id: str, redis_client: aioredis.Redis):
    """Remove quota block for a company"""
    try:
        block_key = quota_service.QUOTA_BLOCK_KEY.format(company_id=company_id)
        await redis_client.delete(block_key)
        
        logger.info(f"Removed quota block for company {company_id}")
        
    except Exception as e:
        logger.error(f"Failed to unblock company {company_id}: {e}")

async def _log_quota_reset(company_id: str, reset_time: datetime):
    """Log quota reset in database"""
    try:
        query = """
            INSERT INTO quota_resets (
                company_id, reset_timestamp, reset_type, reset_by
            ) VALUES ($1, $2, $3, $4)
        """
        
        await DatabaseUtils.execute_query(query, [
            company_id, reset_time, 'monthly_auto', 'system'
        ])
        
    except Exception as e:
        logger.error(f"Failed to log quota reset for company {company_id}: {e}")

async def close_quota_management_connections():
    """Close quota management service connections"""
    if quota_service._redis_client:
        await quota_service._redis_client.aclose()
    logger.info("Quota management service connections closed")