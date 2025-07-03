"""
Redis-Based Rate Limiting - Distributed sliding window rate limiting system
Implements enterprise-grade rate limiting with burst allowance, multiple limit types, and bypass capabilities
"""

import asyncio
import json
import logging
import time
import math
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple, Union
from decimal import Decimal
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib

import redis.asyncio as aioredis

from ..config import get_settings
from ..utils.logger import get_logger
from ..database import DatabaseUtils
from .cache import cache_service, _get_cache_key, TTL

settings = get_settings()
logger = get_logger(__name__)

class LimitType(str, Enum):
    """Rate limit time window types"""
    PER_MINUTE = "per_minute"
    PER_HOUR = "per_hour"
    PER_DAY = "per_day"
    PER_MONTH = "per_month"
    BURST = "burst"

class RateLimitStatus(str, Enum):
    """Rate limit check status"""
    ALLOWED = "allowed"           # Request allowed
    RATE_LIMITED = "rate_limited" # Rate limit exceeded
    BURST_USED = "burst_used"     # Using burst allowance
    BYPASSED = "bypassed"         # Bypass rule applied
    ERROR = "error"               # Error in checking

class CustomerTier(str, Enum):
    """Customer tier for different rate limits"""
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"
    UNLIMITED = "unlimited"

@dataclass
class RateLimitConfig:
    """Rate limit configuration for a company"""
    company_id: str
    tier: CustomerTier
    per_minute_limit: int
    per_hour_limit: int
    per_day_limit: int
    per_month_limit: Optional[int] = None
    burst_limit: int = 0
    burst_window_seconds: int = 60
    is_bypassed: bool = False
    bypass_reason: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None

@dataclass
class RateLimitResult:
    """Result of a rate limit check"""
    company_id: str
    limit_type: LimitType
    status: RateLimitStatus
    allowed: bool
    current_count: int
    limit_value: int
    remaining: int
    reset_time: datetime
    retry_after_seconds: Optional[int] = None
    burst_used: int = 0
    burst_remaining: int = 0
    window_start: datetime = None
    window_end: datetime = None
    bypass_applied: bool = False
    bypass_reason: Optional[str] = None

@dataclass
class SlidingWindowCounter:
    """Sliding window counter data"""
    company_id: str
    limit_type: LimitType
    window_start: datetime
    window_end: datetime
    total_requests: int
    current_window_requests: int
    previous_window_requests: int
    weighted_count: float

class RateLimitError(Exception):
    """Base exception for rate limiting operations"""
    pass

class RateLimitService:
    """Enterprise rate limiting service with sliding window algorithm"""
    
    def __init__(self):
        self._redis_client: Optional[aioredis.Redis] = None
        
        # Redis key patterns
        self.RATE_LIMIT_KEY = "ratelimit:{company_id}:{limit_type}:{window}"
        self.BURST_KEY = "burst:{company_id}:{timestamp}"
        self.CONFIG_KEY = "ratelimit_config:{company_id}"
        self.BYPASS_KEY = "ratelimit_bypass:{company_id}"
        self.STATS_KEY = "ratelimit_stats:{company_id}"
        
        # Window sizes in seconds
        self.WINDOW_SIZES = {
            LimitType.PER_MINUTE: 60,
            LimitType.PER_HOUR: 3600,
            LimitType.PER_DAY: 86400,
            LimitType.PER_MONTH: 2629746,  # 30.44 days average
            LimitType.BURST: 60
        }
        
        # Default rate limits by tier
        self.DEFAULT_LIMITS = {
            CustomerTier.FREE: {
                LimitType.PER_MINUTE: 10,
                LimitType.PER_HOUR: 100,
                LimitType.PER_DAY: 1000,
                LimitType.PER_MONTH: 10000,
                "burst_limit": 20
            },
            CustomerTier.BASIC: {
                LimitType.PER_MINUTE: 50,
                LimitType.PER_HOUR: 1000,
                LimitType.PER_DAY: 10000,
                LimitType.PER_MONTH: 100000,
                "burst_limit": 100
            },
            CustomerTier.PREMIUM: {
                LimitType.PER_MINUTE: 200,
                LimitType.PER_HOUR: 5000,
                LimitType.PER_DAY: 50000,
                LimitType.PER_MONTH: 500000,
                "burst_limit": 500
            },
            CustomerTier.ENTERPRISE: {
                LimitType.PER_MINUTE: 1000,
                LimitType.PER_HOUR: 25000,
                LimitType.PER_DAY: 250000,
                LimitType.PER_MONTH: 2500000,
                "burst_limit": 2000
            },
            CustomerTier.UNLIMITED: {
                LimitType.PER_MINUTE: 999999,
                LimitType.PER_HOUR: 999999,
                LimitType.PER_DAY: 999999,
                LimitType.PER_MONTH: 999999,
                "burst_limit": 999999
            }
        }
        
        # Sliding window precision (number of sub-windows)
        self.WINDOW_PRECISION = 10
        
    async def initialize(self):
        """Initialize the rate limit service"""
        try:
            # Initialize Redis connection
            await self._get_redis_client()
            logger.info("RateLimitService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize RateLimitService: {e}")
            raise
        
    async def _get_redis_client(self) -> aioredis.Redis:
        """Get Redis client with connection pooling"""
        if not self._redis_client:
            self._redis_client = await cache_service._get_redis_client()
        return self._redis_client

# Global rate limit service instance
rate_limit_service = RateLimitService()

async def check_rate_limit(company_id: str, limit_type: str) -> RateLimitResult:
    """
    Check if a request is within rate limits using sliding window algorithm
    
    Args:
        company_id: Company identifier
        limit_type: Type of limit to check (per_minute, per_hour, per_day, etc.)
        
    Returns:
        RateLimitResult: Detailed rate limit check result
    """
    try:
        # Convert string to enum
        limit_enum = LimitType(limit_type)
        
        # Get rate limit configuration
        config = await _get_rate_limit_config(company_id)
        if not config:
            # Create default config for unknown companies
            config = await _create_default_config(company_id)
        
        # Check for bypass first
        if config.is_bypassed:
            return RateLimitResult(
                company_id=company_id,
                limit_type=limit_enum,
                status=RateLimitStatus.BYPASSED,
                allowed=True,
                current_count=0,
                limit_value=999999,
                remaining=999999,
                reset_time=datetime.utcnow() + timedelta(hours=1),
                bypass_applied=True,
                bypass_reason=config.bypass_reason
            )
        
        # Get limit value for this type
        limit_value = _get_limit_for_type(config, limit_enum)
        
        # Calculate sliding window
        current_time = datetime.utcnow()
        window_size = rate_limit_service.WINDOW_SIZES[limit_enum]
        window_start = current_time - timedelta(seconds=window_size)
        
        # Use sliding window algorithm
        current_count = await _get_sliding_window_count(
            company_id, limit_enum, current_time, window_size
        )
        
        # Check burst allowance if regular limit exceeded
        burst_used = 0
        burst_remaining = config.burst_limit
        
        if current_count >= limit_value and config.burst_limit > 0:
            burst_used = await _get_burst_usage(company_id, current_time)
            burst_remaining = max(0, config.burst_limit - burst_used)
            
            if burst_remaining > 0:
                # Allow using burst
                status = RateLimitStatus.BURST_USED
                allowed = True
            else:
                # Both regular and burst limits exceeded
                status = RateLimitStatus.RATE_LIMITED
                allowed = False
        elif current_count >= limit_value:
            # Regular limit exceeded, no burst available
            status = RateLimitStatus.RATE_LIMITED
            allowed = False
        else:
            # Within regular limits
            status = RateLimitStatus.ALLOWED
            allowed = True
        
        # Calculate reset time (next window)
        reset_time = _calculate_reset_time(current_time, limit_enum)
        
        # Calculate retry after seconds if rate limited
        retry_after_seconds = None
        if not allowed:
            retry_after_seconds = int((reset_time - current_time).total_seconds())
        
        return RateLimitResult(
            company_id=company_id,
            limit_type=limit_enum,
            status=status,
            allowed=allowed,
            current_count=current_count,
            limit_value=limit_value,
            remaining=max(0, limit_value - current_count),
            reset_time=reset_time,
            retry_after_seconds=retry_after_seconds,
            burst_used=burst_used,
            burst_remaining=burst_remaining,
            window_start=window_start,
            window_end=current_time,
            bypass_applied=False
        )
        
    except Exception as e:
        logger.error(f"Failed to check rate limit for company {company_id}: {e}")
        return RateLimitResult(
            company_id=company_id,
            limit_type=LimitType(limit_type),
            status=RateLimitStatus.ERROR,
            allowed=True,  # Fail open for availability
            current_count=0,
            limit_value=1000,  # Default fallback
            remaining=1000,
            reset_time=datetime.utcnow() + timedelta(hours=1)
        )

async def increment_rate_counter(company_id: str, limit_type: str) -> int:
    """
    Increment rate counter for a company and limit type
    
    Args:
        company_id: Company identifier
        limit_type: Type of limit (per_minute, per_hour, per_day)
        
    Returns:
        int: New counter value
    """
    try:
        redis_client = await rate_limit_service._get_redis_client()
        limit_enum = LimitType(limit_type)
        current_time = datetime.utcnow()
        
        # Get rate limit configuration to determine if this should use burst
        config = await _get_rate_limit_config(company_id)
        if not config:
            config = await _create_default_config(company_id)
        
        # Check current count before incrementing
        window_size = rate_limit_service.WINDOW_SIZES[limit_enum]
        current_count = await _get_sliding_window_count(
            company_id, limit_enum, current_time, window_size
        )
        
        limit_value = _get_limit_for_type(config, limit_enum)
        
        # Determine which counter to increment
        if current_count >= limit_value and config.burst_limit > 0:
            # Use burst counter
            burst_key = rate_limit_service.BURST_KEY.format(
                company_id=company_id, 
                timestamp=int(current_time.timestamp() // 60)  # 1-minute burst windows
            )
            new_count = await redis_client.incr(burst_key)
            await redis_client.expire(burst_key, config.burst_window_seconds)
        else:
            # Use regular sliding window counter
            new_count = await _increment_sliding_window_counter(
                company_id, limit_enum, current_time
            )
        
        # Update usage statistics
        await _update_rate_limit_stats(company_id, limit_enum, new_count)
        
        return new_count
        
    except Exception as e:
        logger.error(f"Failed to increment rate counter for company {company_id}: {e}")
        return 0

async def get_rate_limit_status(company_id: str) -> dict:
    """
    Get current status for all rate limits for a company
    
    Args:
        company_id: Company identifier
        
    Returns:
        dict: Status for all limit types
    """
    try:
        status = {
            "company_id": company_id,
            "timestamp": datetime.utcnow().isoformat(),
            "limits": {},
            "burst_usage": {},
            "bypass_active": False,
            "tier": "unknown"
        }
        
        # Get configuration
        config = await _get_rate_limit_config(company_id)
        if config:
            status["tier"] = config.tier.value
            status["bypass_active"] = config.is_bypassed
            if config.bypass_reason:
                status["bypass_reason"] = config.bypass_reason
        
        # Check each limit type
        limit_types = [LimitType.PER_MINUTE, LimitType.PER_HOUR, LimitType.PER_DAY]
        if config and config.per_month_limit:
            limit_types.append(LimitType.PER_MONTH)
        
        for limit_type in limit_types:
            try:
                result = await check_rate_limit(company_id, limit_type.value)
                status["limits"][limit_type.value] = {
                    "current_count": result.current_count,
                    "limit_value": result.limit_value,
                    "remaining": result.remaining,
                    "reset_time": result.reset_time.isoformat(),
                    "status": result.status.value,
                    "allowed": result.allowed
                }
                
                if result.burst_used > 0:
                    status["burst_usage"][limit_type.value] = {
                        "used": result.burst_used,
                        "remaining": result.burst_remaining,
                        "total_burst_limit": config.burst_limit if config else 0
                    }
                    
            except Exception as e:
                logger.error(f"Failed to get status for {limit_type.value}: {e}")
                status["limits"][limit_type.value] = {"error": str(e)}
        
        return status
        
    except Exception as e:
        logger.error(f"Failed to get rate limit status for company {company_id}: {e}")
        return {
            "company_id": company_id,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

async def reset_rate_limits(company_id: str) -> bool:
    """
    Reset all rate limits for a company (emergency use)
    
    Args:
        company_id: Company identifier
        
    Returns:
        bool: True if successfully reset
    """
    try:
        redis_client = await rate_limit_service._get_redis_client()
        
        # Get all rate limit keys for this company
        patterns = [
            f"ratelimit:{company_id}:*",
            f"burst:{company_id}:*",
            f"ratelimit_stats:{company_id}"
        ]
        
        keys_to_delete = []
        for pattern in patterns:
            keys = await redis_client.keys(pattern)
            keys_to_delete.extend(keys)
        
        if keys_to_delete:
            await redis_client.delete(*keys_to_delete)
        
        # Log the reset action
        logger.warning(f"Rate limits reset for company {company_id} - Emergency action")
        
        # Store reset action in database for audit
        query = """
            INSERT INTO rate_limit_resets (
                company_id, reset_timestamp, reset_reason, reset_by
            ) VALUES ($1, $2, $3, $4)
        """
        await DatabaseUtils.execute_query(query, [
            company_id, datetime.utcnow(), "manual_reset", "system"
        ])
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to reset rate limits for company {company_id}: {e}")
        return False

async def configure_rate_limits(company_id: str, limits: dict) -> bool:
    """
    Update rate limit configuration for a company
    
    Args:
        company_id: Company identifier
        limits: Dictionary with new limit values
        
    Returns:
        bool: True if successfully configured
    """
    try:
        # Get existing configuration or create new one
        existing_config = await _get_rate_limit_config(company_id)
        
        # Prepare new configuration
        config_data = {
            'company_id': company_id,
            'tier': limits.get('tier', CustomerTier.BASIC.value),
            'per_minute_limit': limits.get('per_minute_limit', 50),
            'per_hour_limit': limits.get('per_hour_limit', 1000),
            'per_day_limit': limits.get('per_day_limit', 10000),
            'per_month_limit': limits.get('per_month_limit'),
            'burst_limit': limits.get('burst_limit', 100),
            'burst_window_seconds': limits.get('burst_window_seconds', 60),
            'is_bypassed': limits.get('is_bypassed', False),
            'bypass_reason': limits.get('bypass_reason'),
            'updated_at': datetime.utcnow()
        }
        
        if not existing_config:
            config_data['created_at'] = datetime.utcnow()
        
        # Update database
        if existing_config:
            query = """
                UPDATE rate_limit_configs SET
                    tier = $2, per_minute_limit = $3, per_hour_limit = $4,
                    per_day_limit = $5, per_month_limit = $6, burst_limit = $7,
                    burst_window_seconds = $8, is_bypassed = $9, bypass_reason = $10,
                    updated_at = $11
                WHERE company_id = $1
            """
            params = [
                company_id, config_data['tier'], config_data['per_minute_limit'],
                config_data['per_hour_limit'], config_data['per_day_limit'],
                config_data['per_month_limit'], config_data['burst_limit'],
                config_data['burst_window_seconds'], config_data['is_bypassed'],
                config_data['bypass_reason'], config_data['updated_at']
            ]
        else:
            query = """
                INSERT INTO rate_limit_configs (
                    company_id, tier, per_minute_limit, per_hour_limit, per_day_limit,
                    per_month_limit, burst_limit, burst_window_seconds, is_bypassed,
                    bypass_reason, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            """
            params = [
                config_data['company_id'], config_data['tier'], config_data['per_minute_limit'],
                config_data['per_hour_limit'], config_data['per_day_limit'],
                config_data['per_month_limit'], config_data['burst_limit'],
                config_data['burst_window_seconds'], config_data['is_bypassed'],
                config_data['bypass_reason'], config_data['created_at'], config_data['updated_at']
            ]
        
        await DatabaseUtils.execute_query(query, params)
        
        # Clear Redis cache for this company's config
        redis_client = await rate_limit_service._get_redis_client()
        config_key = rate_limit_service.CONFIG_KEY.format(company_id=company_id)
        await redis_client.delete(config_key)
        
        logger.info(f"Rate limit configuration updated for company {company_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to configure rate limits for company {company_id}: {e}")
        return False

# ============================================================================
# Helper Functions
# ============================================================================

async def _get_rate_limit_config(company_id: str) -> Optional[RateLimitConfig]:
    """Get rate limit configuration for a company"""
    try:
        redis_client = await rate_limit_service._get_redis_client()
        config_key = rate_limit_service.CONFIG_KEY.format(company_id=company_id)
        
        # Try cache first
        cached_config = await redis_client.get(config_key)
        if cached_config:
            config_data = json.loads(cached_config)
            return RateLimitConfig(
                company_id=config_data['company_id'],
                tier=CustomerTier(config_data['tier']),
                per_minute_limit=config_data['per_minute_limit'],
                per_hour_limit=config_data['per_hour_limit'],
                per_day_limit=config_data['per_day_limit'],
                per_month_limit=config_data.get('per_month_limit'),
                burst_limit=config_data.get('burst_limit', 0),
                burst_window_seconds=config_data.get('burst_window_seconds', 60),
                is_bypassed=config_data.get('is_bypassed', False),
                bypass_reason=config_data.get('bypass_reason'),
                created_at=datetime.fromisoformat(config_data['created_at']) if config_data.get('created_at') else None,
                updated_at=datetime.fromisoformat(config_data['updated_at']) if config_data.get('updated_at') else None
            )
        
        # Load from database
        query = """
            SELECT company_id, tier, per_minute_limit, per_hour_limit, per_day_limit,
                   per_month_limit, burst_limit, burst_window_seconds, is_bypassed,
                   bypass_reason, created_at, updated_at
            FROM rate_limit_configs
            WHERE company_id = $1
        """
        
        result = await DatabaseUtils.execute_query(query, [company_id])
        
        if result:
            config = RateLimitConfig(
                company_id=result['company_id'],
                tier=CustomerTier(result['tier']),
                per_minute_limit=result['per_minute_limit'],
                per_hour_limit=result['per_hour_limit'],
                per_day_limit=result['per_day_limit'],
                per_month_limit=result.get('per_month_limit'),
                burst_limit=result.get('burst_limit', 0),
                burst_window_seconds=result.get('burst_window_seconds', 60),
                is_bypassed=result.get('is_bypassed', False),
                bypass_reason=result.get('bypass_reason'),
                created_at=result.get('created_at'),
                updated_at=result.get('updated_at')
            )
            
            # Cache the config
            config_dict = asdict(config)
            config_dict['tier'] = config_dict['tier'].value
            if config_dict['created_at']:
                config_dict['created_at'] = config_dict['created_at'].isoformat()
            if config_dict['updated_at']:
                config_dict['updated_at'] = config_dict['updated_at'].isoformat()
            
            await redis_client.setex(config_key, TTL.RATE_LIMIT_CONFIG, json.dumps(config_dict))
            
            return config
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to get rate limit config for company {company_id}: {e}")
        return None

async def _create_default_config(company_id: str) -> RateLimitConfig:
    """Create default rate limit configuration for a company"""
    try:
        # Default to BASIC tier
        default_limits = rate_limit_service.DEFAULT_LIMITS[CustomerTier.BASIC]
        
        config = RateLimitConfig(
            company_id=company_id,
            tier=CustomerTier.BASIC,
            per_minute_limit=default_limits[LimitType.PER_MINUTE],
            per_hour_limit=default_limits[LimitType.PER_HOUR],
            per_day_limit=default_limits[LimitType.PER_DAY],
            per_month_limit=default_limits[LimitType.PER_MONTH],
            burst_limit=default_limits["burst_limit"],
            burst_window_seconds=60,
            is_bypassed=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Store in database
        query = """
            INSERT INTO rate_limit_configs (
                company_id, tier, per_minute_limit, per_hour_limit, per_day_limit,
                per_month_limit, burst_limit, burst_window_seconds, is_bypassed,
                bypass_reason, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (company_id) DO NOTHING
        """
        
        await DatabaseUtils.execute_query(query, [
            config.company_id, config.tier.value, config.per_minute_limit,
            config.per_hour_limit, config.per_day_limit, config.per_month_limit,
            config.burst_limit, config.burst_window_seconds, config.is_bypassed,
            config.bypass_reason, config.created_at, config.updated_at
        ])
        
        return config
        
    except Exception as e:
        logger.error(f"Failed to create default config for company {company_id}: {e}")
        # Return minimal config on error
        return RateLimitConfig(
            company_id=company_id,
            tier=CustomerTier.BASIC,
            per_minute_limit=50,
            per_hour_limit=1000,
            per_day_limit=10000,
            burst_limit=100
        )

def _get_limit_for_type(config: RateLimitConfig, limit_type: LimitType) -> int:
    """Get the limit value for a specific limit type"""
    if limit_type == LimitType.PER_MINUTE:
        return config.per_minute_limit
    elif limit_type == LimitType.PER_HOUR:
        return config.per_hour_limit
    elif limit_type == LimitType.PER_DAY:
        return config.per_day_limit
    elif limit_type == LimitType.PER_MONTH:
        return config.per_month_limit or 999999
    elif limit_type == LimitType.BURST:
        return config.burst_limit
    else:
        return 1000  # Default fallback

async def _get_sliding_window_count(
    company_id: str, 
    limit_type: LimitType, 
    current_time: datetime, 
    window_size: int
) -> int:
    """
    Get current count using sliding window algorithm
    
    This implements a precise sliding window by dividing the window into sub-windows
    and calculating a weighted count based on the overlap.
    """
    try:
        redis_client = await rate_limit_service._get_redis_client()
        
        # Calculate current and previous window timestamps
        sub_window_size = window_size // rate_limit_service.WINDOW_PRECISION
        current_window = int(current_time.timestamp() // sub_window_size)
        
        # Get counts from multiple sub-windows to create sliding effect
        total_count = 0
        now_timestamp = current_time.timestamp()
        window_start_timestamp = now_timestamp - window_size
        
        # Check each sub-window within the sliding window
        for i in range(rate_limit_service.WINDOW_PRECISION + 1):
            window_timestamp = current_window - i
            window_key = rate_limit_service.RATE_LIMIT_KEY.format(
                company_id=company_id,
                limit_type=limit_type.value,
                window=window_timestamp
            )
            
            # Get count for this sub-window
            count = await redis_client.get(window_key)
            if count:
                sub_window_count = int(count)
                
                # Calculate how much of this sub-window overlaps with our sliding window
                sub_window_start = window_timestamp * sub_window_size
                sub_window_end = sub_window_start + sub_window_size
                
                # Calculate overlap percentage
                overlap_start = max(sub_window_start, window_start_timestamp)
                overlap_end = min(sub_window_end, now_timestamp)
                
                if overlap_end > overlap_start:
                    overlap_ratio = (overlap_end - overlap_start) / sub_window_size
                    weighted_count = sub_window_count * overlap_ratio
                    total_count += weighted_count
        
        return int(total_count)
        
    except Exception as e:
        logger.error(f"Failed to get sliding window count: {e}")
        return 0

async def _increment_sliding_window_counter(
    company_id: str, 
    limit_type: LimitType, 
    current_time: datetime
) -> int:
    """Increment counter in the current sliding window sub-window"""
    try:
        redis_client = await rate_limit_service._get_redis_client()
        
        window_size = rate_limit_service.WINDOW_SIZES[limit_type]
        sub_window_size = window_size // rate_limit_service.WINDOW_PRECISION
        current_window = int(current_time.timestamp() // sub_window_size)
        
        window_key = rate_limit_service.RATE_LIMIT_KEY.format(
            company_id=company_id,
            limit_type=limit_type.value,
            window=current_window
        )
        
        # Increment counter and set expiry
        new_count = await redis_client.incr(window_key)
        await redis_client.expire(window_key, window_size + sub_window_size)  # Expire after window + buffer
        
        return new_count
        
    except Exception as e:
        logger.error(f"Failed to increment sliding window counter: {e}")
        return 0

async def _get_burst_usage(company_id: str, current_time: datetime) -> int:
    """Get current burst usage for a company"""
    try:
        redis_client = await rate_limit_service._get_redis_client()
        
        # Check burst usage in current minute
        burst_window = int(current_time.timestamp() // 60)
        burst_key = rate_limit_service.BURST_KEY.format(
            company_id=company_id,
            timestamp=burst_window
        )
        
        burst_count = await redis_client.get(burst_key)
        return int(burst_count) if burst_count else 0
        
    except Exception as e:
        logger.error(f"Failed to get burst usage: {e}")
        return 0

def _calculate_reset_time(current_time: datetime, limit_type: LimitType) -> datetime:
    """Calculate when the rate limit will reset"""
    if limit_type == LimitType.PER_MINUTE:
        return current_time.replace(second=0, microsecond=0) + timedelta(minutes=1)
    elif limit_type == LimitType.PER_HOUR:
        return current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    elif limit_type == LimitType.PER_DAY:
        return current_time.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    elif limit_type == LimitType.PER_MONTH:
        # Next month, first day
        if current_time.month == 12:
            return current_time.replace(year=current_time.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            return current_time.replace(month=current_time.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        return current_time + timedelta(minutes=1)

async def _update_rate_limit_stats(company_id: str, limit_type: LimitType, current_count: int):
    """Update rate limiting statistics"""
    try:
        redis_client = await rate_limit_service._get_redis_client()
        stats_key = rate_limit_service.STATS_KEY.format(company_id=company_id)
        
        # Update stats in Redis hash
        current_time = datetime.utcnow()
        stats_data = {
            f"{limit_type.value}_count": current_count,
            f"{limit_type.value}_last_updated": current_time.isoformat(),
            "total_requests": await redis_client.hincrby(stats_key, "total_requests", 1)
        }
        
        # Set stats with expiry
        await redis_client.hmset(stats_key, stats_data)
        await redis_client.expire(stats_key, 86400)  # 24 hours
        
    except Exception as e:
        logger.error(f"Failed to update rate limit stats: {e}")

async def close_rate_limit_connections():
    """Close rate limiting service connections"""
    if rate_limit_service._redis_client:
        await rate_limit_service._redis_client.aclose()
    logger.info("Rate limiting service connections closed")