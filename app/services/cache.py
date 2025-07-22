import aioredis
import json
from typing import Optional, Dict, Any
from datetime import timedelta
from ..config import get_settings
from ..utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Cache TTL configuration
API_KEY_CACHE_TTL = 3600  # 1 hour
COMPANY_CACHE_TTL = 1800  # 30 minutes

# Redis client singleton
_redis_client = None

async def get_redis_client():
    """Get or create Redis client singleton"""
    global _redis_client
    
    if _redis_client is None:
        try:
            _redis_client = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            await _redis_client.ping()
            logger.info("Redis client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            _redis_client = None
            raise
    
    return _redis_client

async def cache_api_key_mapping(key_hash: str, api_key_data: Dict[str, Any]) -> bool:
    """
    Cache API key mapping in Redis
    
    Args:
        key_hash: Hashed API key
        api_key_data: API key data to cache
        
    Returns:
        True if cached successfully, False otherwise
    """
    try:
        redis = await get_redis_client()
        cache_key = f"api_key:{key_hash}"
        
        # Convert data to JSON string
        json_data = json.dumps(api_key_data)
        
        # Set with expiration
        await redis.setex(cache_key, API_KEY_CACHE_TTL, json_data)
        
        logger.debug(f"Cached API key mapping: {key_hash[:16]}...")
        return True
        
    except Exception as e:
        logger.error(f"Error caching API key mapping: {e}")
        return False

async def get_cached_company(key_hash: str) -> Optional[Dict[str, Any]]:
    """
    Get cached company data for an API key
    
    Args:
        key_hash: Hashed API key
        
    Returns:
        Cached company data if found, None otherwise
    """
    try:
        redis = await get_redis_client()
        cache_key = f"api_key:{key_hash}"
        
        # Get cached data
        cached_data = await redis.get(cache_key)
        
        if cached_data:
            logger.debug(f"Cache hit for API key: {key_hash[:16]}...")
            return json.loads(cached_data)
        
        logger.debug(f"Cache miss for API key: {key_hash[:16]}...")
        return None
        
    except Exception as e:
        logger.error(f"Error getting cached company data: {e}")
        return None

async def invalidate_company_cache(company_id: str) -> bool:
    """
    Invalidate all cached data for a company
    
    Args:
        company_id: Company ID
        
    Returns:
        True if invalidated successfully, False otherwise
    """
    try:
        redis = await get_redis_client()
        
        # Pattern to match all API keys for this company
        # Note: This requires scanning keys which can be expensive
        # In production, consider maintaining a set of keys per company
        pattern = f"api_key:*"
        
        # Scan for matching keys
        cursor = "0"
        invalidated_count = 0
        
        while cursor != 0:
            cursor, keys = await redis.scan(cursor, pattern, count=100)
            
            for key in keys:
                # Get the cached data to check company_id
                cached_data = await redis.get(key)
                if cached_data:
                    data = json.loads(cached_data)
                    if data.get('company_id') == company_id:
                        await redis.delete(key)
                        invalidated_count += 1
        
        logger.info(f"Invalidated {invalidated_count} cache entries for company {company_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error invalidating company cache: {e}")
        return False

async def cache_vendor_api_key(company_id: str, vendor: str, encrypted_key: str) -> bool:
    """
    Cache encrypted vendor API key
    
    Args:
        company_id: Company ID
        vendor: Vendor name
        encrypted_key: Encrypted API key
        
    Returns:
        True if cached successfully, False otherwise
    """
    try:
        redis = await get_redis_client()
        cache_key = f"vendor_key:{company_id}:{vendor}"
        
        # Set with expiration
        await redis.setex(cache_key, API_KEY_CACHE_TTL, encrypted_key)
        
        logger.debug(f"Cached vendor API key for company {company_id}, vendor {vendor}")
        return True
        
    except Exception as e:
        logger.error(f"Error caching vendor API key: {e}")
        return False

async def get_cached_vendor_api_key(company_id: str, vendor: str) -> Optional[str]:
    """
    Get cached encrypted vendor API key
    
    Args:
        company_id: Company ID
        vendor: Vendor name
        
    Returns:
        Encrypted API key if found, None otherwise
    """
    try:
        redis = await get_redis_client()
        cache_key = f"vendor_key:{company_id}:{vendor}"
        
        encrypted_key = await redis.get(cache_key)
        
        if encrypted_key:
            logger.debug(f"Cache hit for vendor API key: company {company_id}, vendor {vendor}")
            return encrypted_key
        
        logger.debug(f"Cache miss for vendor API key: company {company_id}, vendor {vendor}")
        return None
        
    except Exception as e:
        logger.error(f"Error getting cached vendor API key: {e}")
        return None

async def close_redis_connection():
    """Close Redis connection gracefully"""
    global _redis_client
    
    if _redis_client:
        try:
            await _redis_client.close()
            _redis_client = None
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")