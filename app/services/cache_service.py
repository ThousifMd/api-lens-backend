"""
Query Result Caching Service
Implements caching for expensive database queries to improve performance
"""
import json
import hashlib
from typing import Any, Dict, Optional, List, Union, Callable
from datetime import datetime, timedelta
import asyncio
from functools import wraps
import redis.asyncio as redis
from redis.asyncio.client import Redis
import logging

from app.config import settings

logger = logging.getLogger(__name__)

class CacheService:
    """Service for caching query results and expensive computations"""
    
    def __init__(self):
        self.redis_client: Optional[Redis] = None
        self.connected = False
        self.default_ttl = 3600  # 1 hour default
        
        # Cache TTL configurations for different data types
        self.ttl_config = {
            'analytics_hourly': 3600,      # 1 hour
            'analytics_daily': 86400,      # 24 hours
            'vendor_pricing': 300,         # 5 minutes
            'company_limits': 60,          # 1 minute
            'user_sessions': 1800,         # 30 minutes
            'aggregations': 600,           # 10 minutes
        }
    
    async def connect(self):
        """Initialize Redis connection"""
        if self.connected:
            return
            
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                decode_responses=True,
                socket_keepalive=True,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            await self.redis_client.ping()
            self.connected = True
            logger.info("Redis cache service connected successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.connected = False
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            self.connected = False
    
    def _generate_cache_key(self, prefix: str, params: Dict[str, Any]) -> str:
        """Generate a consistent cache key from parameters"""
        # Sort parameters for consistent key generation
        sorted_params = sorted(params.items())
        param_str = json.dumps(sorted_params, sort_keys=True, default=str)
        
        # Create hash of parameters
        param_hash = hashlib.md5(param_str.encode()).hexdigest()
        
        return f"{prefix}:{param_hash}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.connected:
            return None
            
        try:
            value = await self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with TTL"""
        if not self.connected:
            return False
            
        try:
            ttl = ttl or self.default_ttl
            serialized = json.dumps(value, default=str)
            await self.redis_client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        if not self.connected:
            return False
            
        try:
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if not self.connected:
            return 0
            
        try:
            keys = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                deleted = await self.redis_client.delete(*keys)
                return deleted
            return 0
        except Exception as e:
            logger.error(f"Cache delete pattern error for {pattern}: {e}")
            return 0
    
    async def get_or_compute(self, 
                           cache_key: str,
                           compute_func: Callable,
                           ttl: Optional[int] = None,
                           force_refresh: bool = False) -> Any:
        """Get from cache or compute and cache the result"""
        if not force_refresh:
            cached = await self.get(cache_key)
            if cached is not None:
                return cached
        
        # Compute the value
        if asyncio.iscoroutinefunction(compute_func):
            result = await compute_func()
        else:
            result = compute_func()
        
        # Cache the result
        await self.set(cache_key, result, ttl)
        
        return result
    
    # Specific caching methods for different query types
    
    async def cache_analytics_query(self,
                                  company_id: str,
                                  query_type: str,
                                  time_range: Dict[str, Any],
                                  filters: Optional[Dict[str, Any]] = None) -> str:
        """Generate cache key for analytics queries"""
        params = {
            'company_id': company_id,
            'query_type': query_type,
            'start_time': time_range.get('start'),
            'end_time': time_range.get('end'),
            'filters': filters or {}
        }
        
        prefix = f"analytics:{query_type}"
        return self._generate_cache_key(prefix, params)
    
    async def cache_aggregation_query(self,
                                    table: str,
                                    group_by: List[str],
                                    filters: Dict[str, Any],
                                    aggregations: List[str]) -> str:
        """Generate cache key for aggregation queries"""
        params = {
            'table': table,
            'group_by': sorted(group_by),
            'filters': filters,
            'aggregations': sorted(aggregations)
        }
        
        prefix = f"aggregation:{table}"
        return self._generate_cache_key(prefix, params)
    
    async def invalidate_company_cache(self, company_id: str):
        """Invalidate all cache entries for a company"""
        patterns = [
            f"analytics:*:{company_id}:*",
            f"company_limits:{company_id}:*",
            f"user_sessions:{company_id}:*"
        ]
        
        deleted_count = 0
        for pattern in patterns:
            deleted_count += await self.delete_pattern(pattern)
        
        logger.info(f"Invalidated {deleted_count} cache entries for company {company_id}")
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.connected:
            return {"connected": False}
        
        try:
            info = await self.redis_client.info()
            return {
                "connected": True,
                "used_memory": info.get("used_memory_human", "N/A"),
                "total_keys": await self.redis_client.dbsize(),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                ),
                "evicted_keys": info.get("evicted_keys", 0)
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"connected": False, "error": str(e)}
    
    def _calculate_hit_rate(self, hits: int, misses: int) -> float:
        """Calculate cache hit rate percentage"""
        total = hits + misses
        if total == 0:
            return 0.0
        return round((hits / total) * 100, 2)

# Decorator for caching function results
def cached(cache_key_prefix: str, ttl: Optional[int] = None):
    """Decorator to cache function results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get cache service instance
            cache_service = kwargs.get('cache_service')
            if not cache_service or not cache_service.connected:
                # No cache available, execute function normally
                return await func(*args, **kwargs)
            
            # Generate cache key from function arguments
            cache_params = {
                'args': args,
                'kwargs': {k: v for k, v in kwargs.items() if k != 'cache_service'}
            }
            cache_key = cache_service._generate_cache_key(cache_key_prefix, cache_params)
            
            # Check if force refresh is requested
            force_refresh = kwargs.get('force_refresh', False)
            
            # Get or compute result
            result = await cache_service.get_or_compute(
                cache_key,
                lambda: func(*args, **kwargs),
                ttl=ttl,
                force_refresh=force_refresh
            )
            
            return result
        
        return wrapper
    return decorator

# Global cache service instance
cache_service = CacheService()

# Example usage in analytics service
async def get_cached_analytics(company_id: str, 
                             start_date: datetime,
                             end_date: datetime,
                             cache_service: CacheService) -> Dict[str, Any]:
    """Example of using cache service for analytics queries"""
    
    cache_key = await cache_service.cache_analytics_query(
        company_id=company_id,
        query_type='daily_summary',
        time_range={'start': start_date, 'end': end_date}
    )
    
    async def compute_analytics():
        # Your expensive analytics query here
        # This is just an example
        return {
            'total_requests': 1000,
            'total_cost': 150.0,
            'average_latency': 250.5
        }
    
    return await cache_service.get_or_compute(
        cache_key,
        compute_analytics,
        ttl=cache_service.ttl_config['analytics_daily']
    )