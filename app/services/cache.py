"""
Cache Layer Service - High-performance Redis caching with intelligent strategies
Implements multi-tier caching, cache warming, and performance monitoring
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union, Set
from uuid import UUID
import hashlib
import re

import redis.asyncio as aioredis
from redis.asyncio import ConnectionPool

from ..config import get_settings
from ..utils.logger import get_logger
from ..database import DatabaseUtils

settings = get_settings()
logger = get_logger(__name__)

class CacheError(Exception):
    """Base exception for cache operations"""
    pass

class CacheStats:
    """Cache performance statistics tracker"""
    
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.errors = 0
        self.total_time = 0.0
        self.start_time = time.time()
    
    def record_hit(self, duration: float = 0.0):
        self.hits += 1
        self.total_time += duration
    
    def record_miss(self, duration: float = 0.0):
        self.misses += 1
        self.total_time += duration
    
    def record_set(self, duration: float = 0.0):
        self.sets += 1
        self.total_time += duration
    
    def record_delete(self, duration: float = 0.0):
        self.deletes += 1
        self.total_time += duration
    
    def record_error(self):
        self.errors += 1
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0
    
    @property
    def avg_response_time(self) -> float:
        total_ops = self.hits + self.misses + self.sets + self.deletes
        return (self.total_time / total_ops * 1000) if total_ops > 0 else 0.0  # in ms
    
    @property
    def uptime(self) -> float:
        return time.time() - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'hits': self.hits,
            'misses': self.misses,
            'sets': self.sets,
            'deletes': self.deletes,
            'errors': self.errors,
            'hit_rate': round(self.hit_rate, 2),
            'avg_response_time_ms': round(self.avg_response_time, 2),
            'uptime_seconds': round(self.uptime, 2),
            'total_operations': self.hits + self.misses + self.sets + self.deletes
        }

class CacheService:
    """Enterprise cache service with intelligent caching strategies"""
    
    def __init__(self):
        self._redis_client: Optional[aioredis.Redis] = None
        self._connection_pool: Optional[ConnectionPool] = None
        self._stats = CacheStats()
        
    async def _get_redis_client(self) -> aioredis.Redis:
        """Get Redis client with connection pooling"""
        if not self._redis_client:
            self._connection_pool = ConnectionPool.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                retry_on_error=[ConnectionError, TimeoutError],
                health_check_interval=30
            )
            self._redis_client = aioredis.Redis(
                connection_pool=self._connection_pool
            )
        return self._redis_client
    
    async def initialize(self):
        """Initialize the cache service"""
        try:
            # Initialize Redis connection
            await self._get_redis_client()
            logger.info("CacheService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize CacheService: {e}")
            raise
    
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set a key-value pair in Redis cache"""
        try:
            redis_client = await self._get_redis_client()
            
            # Convert value to string if it's not already
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value)
            elif isinstance(value, (int, float)):
                value_str = str(value)
            else:
                value_str = str(value)
            
            if ttl:
                result = await redis_client.setex(key, ttl, value_str)
            else:
                result = await redis_client.set(key, value_str)
            return result is not None
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False
    
    async def get(self, key: str) -> Optional[str]:
        """Get a value from Redis cache"""
        try:
            redis_client = await self._get_redis_client()
            result = await redis_client.get(key)
            return result
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return None
    
    async def delete(self, key: str) -> bool:
        """Delete a key from Redis cache"""
        try:
            redis_client = await self._get_redis_client()
            result = await redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists in Redis cache"""
        try:
            redis_client = await self._get_redis_client()
            result = await redis_client.exists(key)
            return result > 0
        except Exception as e:
            logger.error(f"Error checking cache key {key}: {e}")
            return False

    async def close(self):
        """Close Redis connections"""
        if self._connection_pool:
            await self._connection_pool.disconnect()
        if self._redis_client:
            await self._redis_client.aclose()

# Global cache service instance
cache_service = CacheService()

# Environment prefix for key namespacing
ENV_PREFIX = f"{settings.ENVIRONMENT}:" if settings.ENVIRONMENT != "development" else "dev:"

# Cache TTL Constants (in seconds)
class TTL:
    API_KEY_MAPPING = 3600      # 1 hour - API key to company mapping
    VENDOR_KEY = 1800           # 30 minutes - Encrypted vendor keys
    COMPANY_DATA = 3600         # 1 hour - Company information
    RATE_LIMIT = 60             # 1 minute - Rate limit counters
    RATE_LIMIT_CONFIG = 3600    # 1 hour - Rate limit configuration
    QUOTA_CONFIG = 3600         # 1 hour - Quota configuration
    COST_DATA = 86400           # 1 day - Cost analytics
    ANALYTICS = 900             # 15 minutes - Analytics data
    SESSION = 86400             # 24 hours - User sessions
    HEALTH_CHECK = 300          # 5 minutes - Health check results
    PERFORMANCE_STATS = 60      # 1 minute - Performance metrics

# Cache Key Patterns
class KeyPattern:
    API_KEY_MAPPING = "api_key_mapping:{hash}"
    COMPANY_DATA = "company:{company_id}"
    VENDOR_KEY = "vendor_key:{company_id}:{vendor}"
    RATE_LIMIT = "rate_limit:{company_id}:{type}"
    COST_DATA = "cost:{company_id}:{period}"
    ANALYTICS = "analytics:{company_id}:{metric}:{timeframe}"
    SESSION = "session:{session_id}"
    HEALTH_CHECK = "health_check:{component}"
    PERFORMANCE = "performance:{service}:{metric}"
    CACHE_WARMING = "warming:{data_type}"

def _get_cache_key(pattern: str, **kwargs) -> str:
    """Generate namespaced Redis key"""
    key = pattern.format(**kwargs)
    return f"{ENV_PREFIX}{key}"

def _hash_data(data: str) -> str:
    """Generate consistent hash for cache keys"""
    return hashlib.sha256(data.encode()).hexdigest()[:16]

# Global stats instance
_cache_stats = CacheStats()

async def cache_api_key_mapping(api_key_hash: str, company_data: dict) -> bool:
    """Cache API key to company mapping"""
    start_time = time.time()
    try:
        redis_client = await cache_service._get_redis_client()
        key = _get_cache_key(KeyPattern.API_KEY_MAPPING, hash=api_key_hash)
        
        # Add metadata for cache management
        cache_data = {
            'company_data': company_data,
            'cached_at': datetime.utcnow().isoformat(),
            'ttl': TTL.API_KEY_MAPPING
        }
        
        await redis_client.setex(key, TTL.API_KEY_MAPPING, json.dumps(cache_data))
        
        duration = time.time() - start_time
        _cache_stats.record_set(duration)
        
        logger.debug(f"Cached API key mapping: {key}")
        return True
        
    except Exception as e:
        _cache_stats.record_error()
        logger.error(f"Failed to cache API key mapping: {e}")
        raise CacheError(f"Failed to cache API key mapping: {e}")

async def get_cached_company(api_key_hash: str) -> Optional[dict]:
    """Get cached company data for an API key"""
    start_time = time.time()
    try:
        redis_client = await cache_service._get_redis_client()
        key = _get_cache_key(KeyPattern.API_KEY_MAPPING, hash=api_key_hash)
        
        data = await redis_client.get(key)
        duration = time.time() - start_time
        
        if data:
            _cache_stats.record_hit(duration)
            cache_data = json.loads(data)
            logger.debug(f"Cache hit for API key mapping: {key}")
            return cache_data.get('company_data')
        else:
            _cache_stats.record_miss(duration)
            logger.debug(f"Cache miss for API key mapping: {key}")
            return None
            
    except Exception as e:
        _cache_stats.record_error()
        logger.error(f"Failed to get cached company: {e}")
        return None

async def cache_vendor_key(company_id: str, vendor: str, encrypted_key: str) -> bool:
    """Cache encrypted vendor API key"""
    start_time = time.time()
    try:
        redis_client = await cache_service._get_redis_client()
        key = _get_cache_key(KeyPattern.VENDOR_KEY, company_id=company_id, vendor=vendor.lower())
        
        cache_data = {
            'encrypted_key': encrypted_key,
            'cached_at': datetime.utcnow().isoformat(),
            'company_id': company_id,
            'vendor': vendor.lower()
        }
        
        await redis_client.setex(key, TTL.VENDOR_KEY, json.dumps(cache_data))
        
        duration = time.time() - start_time
        _cache_stats.record_set(duration)
        
        logger.debug(f"Cached vendor key: {key}")
        return True
        
    except Exception as e:
        _cache_stats.record_error()
        logger.error(f"Failed to cache vendor key: {e}")
        raise CacheError(f"Failed to cache vendor key: {e}")

async def get_cached_vendor_key(company_id: str, vendor: str) -> Optional[str]:
    """Get cached encrypted vendor API key"""
    start_time = time.time()
    try:
        redis_client = await cache_service._get_redis_client()
        key = _get_cache_key(KeyPattern.VENDOR_KEY, company_id=company_id, vendor=vendor.lower())
        
        data = await redis_client.get(key)
        duration = time.time() - start_time
        
        if data:
            _cache_stats.record_hit(duration)
            cache_data = json.loads(data)
            logger.debug(f"Cache hit for vendor key: {key}")
            return cache_data.get('encrypted_key')
        else:
            _cache_stats.record_miss(duration)
            logger.debug(f"Cache miss for vendor key: {key}")
            return None
            
    except Exception as e:
        _cache_stats.record_error()
        logger.error(f"Failed to get cached vendor key: {e}")
        return None

async def invalidate_company_cache(company_id: str) -> int:
    """Clear all company-related caches"""
    start_time = time.time()
    try:
        redis_client = await cache_service._get_redis_client()
        
        # Patterns to invalidate
        patterns = [
            f"{ENV_PREFIX}company:{company_id}",
            f"{ENV_PREFIX}vendor_key:{company_id}:*",
            f"{ENV_PREFIX}rate_limit:{company_id}:*",
            f"{ENV_PREFIX}cost:{company_id}:*",
            f"{ENV_PREFIX}analytics:{company_id}:*"
        ]
        
        total_deleted = 0
        for pattern in patterns:
            if pattern.endswith('*'):
                # Use SCAN for patterns to avoid blocking Redis
                keys = []
                async for key in redis_client.scan_iter(match=pattern, count=100):
                    keys.append(key)
                
                if keys:
                    deleted = await redis_client.delete(*keys)
                    total_deleted += deleted
                    logger.debug(f"Deleted {deleted} keys for pattern: {pattern}")
            else:
                # Direct key deletion
                deleted = await redis_client.delete(pattern)
                total_deleted += deleted
                if deleted:
                    logger.debug(f"Deleted key: {pattern}")
        
        duration = time.time() - start_time
        _cache_stats.record_delete(duration)
        
        logger.info(f"Invalidated {total_deleted} cache entries for company: {company_id}")
        return total_deleted
        
    except Exception as e:
        _cache_stats.record_error()
        logger.error(f"Failed to invalidate company cache: {e}")
        raise CacheError(f"Failed to invalidate company cache: {e}")

async def get_cache_stats() -> dict:
    """Get comprehensive cache performance statistics"""
    try:
        redis_client = await cache_service._get_redis_client()
        
        # Get Redis server info
        redis_info = await redis_client.info()
        redis_dbsize = await redis_client.dbsize()
        
        # Get memory usage patterns
        memory_stats = await _get_memory_usage_by_pattern()
        
        # Compile comprehensive stats
        stats = {
            'timestamp': datetime.utcnow().isoformat(),
            'environment': settings.ENVIRONMENT,
            'key_prefix': ENV_PREFIX,
            
            # Application-level stats
            'app_stats': _cache_stats.to_dict(),
            
            # Redis server stats
            'redis_stats': {
                'total_keys': redis_dbsize,
                'used_memory': redis_info.get('used_memory', 0),
                'used_memory_human': redis_info.get('used_memory_human', '0B'),
                'connected_clients': redis_info.get('connected_clients', 0),
                'total_commands_processed': redis_info.get('total_commands_processed', 0),
                'instantaneous_ops_per_sec': redis_info.get('instantaneous_ops_per_sec', 0),
                'keyspace_hits': redis_info.get('keyspace_hits', 0),
                'keyspace_misses': redis_info.get('keyspace_misses', 0),
                'expired_keys': redis_info.get('expired_keys', 0),
                'evicted_keys': redis_info.get('evicted_keys', 0)
            },
            
            # Memory usage by data type
            'memory_usage': memory_stats,
            
            # Cache health indicators
            'health': {
                'redis_connected': True,
                'error_rate': _calculate_error_rate(),
                'performance_grade': _calculate_performance_grade()
            }
        }
        
        # Calculate Redis hit rate if available
        redis_hits = redis_info.get('keyspace_hits', 0)
        redis_misses = redis_info.get('keyspace_misses', 0)
        if redis_hits + redis_misses > 0:
            stats['redis_stats']['hit_rate'] = round((redis_hits / (redis_hits + redis_misses)) * 100, 2)
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        return {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat(),
            'health': {'redis_connected': False}
        }

async def _get_memory_usage_by_pattern() -> Dict[str, int]:
    """Get memory usage breakdown by cache data types"""
    try:
        redis_client = await cache_service._get_redis_client()
        
        patterns = {
            'api_key_mappings': f"{ENV_PREFIX}api_key_mapping:*",
            'vendor_keys': f"{ENV_PREFIX}vendor_key:*",
            'company_data': f"{ENV_PREFIX}company:*",
            'rate_limits': f"{ENV_PREFIX}rate_limit:*",
            'analytics': f"{ENV_PREFIX}analytics:*",
            'sessions': f"{ENV_PREFIX}session:*"
        }
        
        usage = {}
        for data_type, pattern in patterns.items():
            count = 0
            async for key in redis_client.scan_iter(match=pattern, count=100):
                count += 1
            usage[data_type] = count
        
        return usage
        
    except Exception as e:
        logger.error(f"Failed to get memory usage by pattern: {e}")
        return {}

def _calculate_error_rate() -> float:
    """Calculate cache error rate percentage"""
    total_ops = _cache_stats.hits + _cache_stats.misses + _cache_stats.sets + _cache_stats.deletes
    if total_ops == 0:
        return 0.0
    return round((_cache_stats.errors / total_ops) * 100, 2)

def _calculate_performance_grade() -> str:
    """Calculate cache performance grade based on hit rate and response time"""
    hit_rate = _cache_stats.hit_rate
    response_time = _cache_stats.avg_response_time
    
    if hit_rate >= 95 and response_time <= 1.0:
        return 'A+'
    elif hit_rate >= 90 and response_time <= 2.0:
        return 'A'
    elif hit_rate >= 85 and response_time <= 5.0:
        return 'B+'
    elif hit_rate >= 80 and response_time <= 10.0:
        return 'B'
    elif hit_rate >= 70 and response_time <= 20.0:
        return 'C'
    else:
        return 'D'

# Cache warming functions for frequently accessed data

async def warm_api_key_cache() -> int:
    """Pre-load frequently used API key mappings"""
    try:
        # Get most active API keys from database
        query = """
            SELECT ak.key_hash, c.id, c.name, c.slug as schema_name, c.rate_limit_rps, c.monthly_quota
            FROM api_keys ak
            JOIN companies c ON ak.company_id = c.id
            WHERE ak.is_active = true AND c.is_active = true
            ORDER BY ak.last_used_at DESC NULLS LAST
            LIMIT 100
        """
        
        results = await DatabaseUtils.execute_query(query, {}, fetch_all=True)
        
        warmed_count = 0
        for result in results:
            company_data = {
                'id': str(result['id']),
                'name': result['name'],
                'schema_name': result['schema_name'],
                'rate_limit_rps': result['rate_limit_rps'],
                'monthly_quota': result['monthly_quota']
            }
            
            await cache_api_key_mapping(result['key_hash'], company_data)
            warmed_count += 1
        
        logger.info(f"Warmed {warmed_count} API key mappings")
        return warmed_count
        
    except Exception as e:
        logger.error(f"Failed to warm API key cache: {e}")
        return 0

async def warm_vendor_key_cache() -> int:
    """Pre-load frequently used vendor keys"""
    try:
        # Get companies with recent activity
        query = """
            SELECT DISTINCT c.id, c.slug as schema_name
            FROM companies c
            JOIN api_keys ak ON c.id = ak.company_id
            WHERE c.is_active = true AND ak.is_active = true
            AND ak.last_used_at > NOW() - INTERVAL '24 hours'
            LIMIT 50
        """
        
        results = await DatabaseUtils.execute_query(query, {}, fetch_all=True)
        
        warmed_count = 0
        for result in results:
            company_id = str(result['id'])
            schema_name = result['schema_name']
            
            # Get vendor keys for this company (single schema approach)
            vendor_query = """
                SELECT vendor, encrypted_key
                FROM vendor_keys
                WHERE company_id = $1 AND is_active = true
            """
            
            vendor_results = await DatabaseUtils.execute_query(vendor_query, {'company_id': UUID(company_id)}, fetch_all=True)
            
            for vendor_result in vendor_results:
                await cache_vendor_key(
                    company_id,
                    vendor_result['vendor'],
                    vendor_result['encrypted_key']
                )
                warmed_count += 1
        
        logger.info(f"Warmed {warmed_count} vendor keys")
        return warmed_count
        
    except Exception as e:
        logger.error(f"Failed to warm vendor key cache: {e}")
        return 0

async def warm_all_caches() -> Dict[str, int]:
    """Warm all cache types"""
    results = {}
    
    try:
        # Run cache warming operations concurrently
        api_key_task = asyncio.create_task(warm_api_key_cache())
        vendor_key_task = asyncio.create_task(warm_vendor_key_cache())
        
        results['api_key_mappings'] = await api_key_task
        results['vendor_keys'] = await vendor_key_task
        results['total'] = sum(results.values())
        
        logger.info(f"Cache warming completed: {results}")
        return results
        
    except Exception as e:
        logger.error(f"Failed to warm caches: {e}")
        return {'error': str(e)}

# Additional utility functions

async def cache_health_check() -> bool:
    """Check cache system health"""
    try:
        redis_client = await cache_service._get_redis_client()
        start_time = time.time()
        
        # Test basic operations
        test_key = f"{ENV_PREFIX}health_check_test"
        await redis_client.set(test_key, "test_value", ex=10)
        value = await redis_client.get(test_key)
        await redis_client.delete(test_key)
        
        response_time = time.time() - start_time
        
        # Cache health check result
        health_data = {
            'status': 'healthy' if value == 'test_value' else 'unhealthy',
            'response_time_ms': round(response_time * 1000, 2),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        health_key = _get_cache_key(KeyPattern.HEALTH_CHECK, component='redis')
        await redis_client.setex(health_key, TTL.HEALTH_CHECK, json.dumps(health_data))
        
        return value == 'test_value'
        
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        return False

async def reset_cache_stats() -> None:
    """Reset cache performance statistics"""
    global _cache_stats
    _cache_stats = CacheStats()
    logger.info("Cache statistics reset")

async def close_cache_connections():
    """Close all cache connections"""
    await cache_service.close()
    logger.info("Cache connections closed")

# Scheduled cache maintenance

async def cache_maintenance() -> Dict[str, Any]:
    """Perform periodic cache maintenance"""
    try:
        redis_client = await cache_service._get_redis_client()
        
        # Get memory info before cleanup
        info_before = await redis_client.info('memory')
        
        # Clean up expired keys (Redis does this automatically, but we can check)
        dbsize_before = await redis_client.dbsize()
        
        # Optimize memory if needed
        # Note: This is more relevant for self-hosted Redis
        
        # Get info after
        info_after = await redis_client.info('memory')
        dbsize_after = await redis_client.dbsize()
        
        maintenance_result = {
            'timestamp': datetime.utcnow().isoformat(),
            'keys_before': dbsize_before,
            'keys_after': dbsize_after,
            'memory_before': info_before.get('used_memory', 0),
            'memory_after': info_after.get('used_memory', 0),
            'status': 'completed'
        }
        
        logger.info(f"Cache maintenance completed: {maintenance_result}")
        return maintenance_result
        
    except Exception as e:
        logger.error(f"Cache maintenance failed: {e}")
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'failed',
            'error': str(e)
        }