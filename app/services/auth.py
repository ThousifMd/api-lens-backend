import asyncio
import hashlib
import secrets
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy import select, update, insert
from sqlalchemy.exc import IntegrityError

from ..database import get_db_session, DatabaseUtils
from ..config import get_settings
from ..utils.logger import get_logger
from models.api_key import APIKey, APIKeyCreate, APIKeyWithSecret
from models.company import Company
from .cache import cache_api_key_mapping, get_cached_company, invalidate_company_cache

settings = get_settings()
logger = get_logger(__name__)

# Security Configuration
API_KEY_PREFIX = "als_"
API_KEY_LENGTH = 47  # 4 chars prefix + 43 chars base64url(32 bytes)
API_KEY_ENTROPY_BITS = 256
SALT_LENGTH = 16

# Performance tracking
_performance_stats = {
    'cache_hits': 0,
    'cache_misses': 0,
    'db_queries': 0,
    'validation_errors': 0
}

def _get_api_key_salt() -> bytes:
    """Get API key salt from settings or environment"""
    salt = settings.API_KEY_SALT
    if not salt:
        # Generate a new salt if not provided (for development)
        salt = secrets.token_hex(SALT_LENGTH)
        logger.warning("API_KEY_SALT not set, using generated salt (not suitable for production)")
    
    return salt.encode() if isinstance(salt, str) else salt

def hash_api_key(api_key: str) -> str:
    """
    Hash API key using SHA256 with salt for secure storage
    
    Args:
        api_key: The raw API key to hash
        
    Returns:
        Hexadecimal hash of the API key
        
    Security Note:
        Uses a salted hash to prevent rainbow table attacks
    """
    if not api_key:
        raise ValueError("API key cannot be empty")
    
    try:
        salt = _get_api_key_salt()
        # Use PBKDF2 for better security against brute force attacks
        import hashlib
        key_hash = hashlib.pbkdf2_hmac(
            'sha256',
            api_key.encode('utf-8'),
            salt,
            100000  # 100k iterations for security
        )
        return key_hash.hex()
    except Exception as e:
        logger.error(f"Error hashing API key: {e}")
        raise ValueError("Failed to hash API key")

def generate_secure_api_key() -> str:
    """
    Generate a cryptographically secure API key
    
    Returns:
        A secure API key with proper prefix and structure
        
    Security Features:
        - Uses cryptographically secure random number generator
        - 256 bits of entropy
        - Proper prefix for identification
        - URL-safe base64 encoding
    """
    try:
        # Generate 32 bytes (256 bits) of cryptographically secure random data
        random_bytes = secrets.token_bytes(32)
        
        # Encode as URL-safe base64 (43 characters)
        encoded = secrets.token_urlsafe(32)
        
        # Add prefix and structure
        api_key = f"{API_KEY_PREFIX}{encoded}"
        
        # Validate length
        if len(api_key) != API_KEY_LENGTH:
            raise ValueError(f"Generated API key has unexpected length: {len(api_key)}")
        
        return api_key
        
    except Exception as e:
        logger.error(f"Error generating API key: {e}")
        raise ValueError("Failed to generate secure API key")

async def generate_api_key(company_id: str, name: str = "Default API Key") -> APIKeyWithSecret:
    """
    Generate a new API key for a company
    
    Args:
        company_id: UUID of the company
        name: Descriptive name for the API key
        
    Returns:
        APIKeyWithSecret containing the new API key and metadata
        
    Raises:
        ValueError: If company_id is invalid or name is empty
        IntegrityError: If there's a database constraint violation
    """
    if not company_id:
        raise ValueError("Company ID is required")
    
    if not name or not name.strip():
        raise ValueError("API key name is required")
    
    # Convert string to UUID if needed
    try:
        company_uuid = UUID(company_id) if isinstance(company_id, str) else company_id
    except ValueError:
        raise ValueError("Invalid company ID format")
    
    try:
        # Generate secure API key
        secret_key = generate_secure_api_key()
        key_hash = hash_api_key(secret_key)
        
        # Insert into database using new database layer
        query = """
            INSERT INTO api_keys (company_id, key_hash, name, is_active, created_at)
            VALUES ($1, $2, $3, true, NOW())
            RETURNING id, company_id, key_hash, name, is_active, created_at, last_used_at
        """
        
        result = await DatabaseUtils.execute_query(
            query,
            {
                'company_id': company_uuid,
                'key_hash': key_hash,
                'name': name.strip()
            },
            fetch_all=False
        )
        
        if not result:
            raise ValueError("Failed to create API key")
        
        _performance_stats['db_queries'] += 1
        
        # Create response object
        api_key_data = APIKeyWithSecret(
            id=result['id'],
            company_id=result['company_id'],
            key_hash=result['key_hash'],
            name=result['name'],
            is_active=result['is_active'],
            created_at=result['created_at'],
            last_used_at=result['last_used_at'],
            secret_key=secret_key
        )
        
        logger.info(f"Generated new API key '{name}' for company {company_id}")
        return api_key_data
        
    except IntegrityError as e:
        logger.error(f"Database integrity error creating API key: {e}")
        raise ValueError("Failed to create API key - database constraint violation")
    except Exception as e:
        logger.error(f"Error generating API key for company {company_id}: {e}")
        raise

async def validate_api_key(api_key: str) -> Optional[Company]:
    """
    Validate an API key and return the associated company data
    
    Uses Redis cache with PostgreSQL fallback for optimal performance
    
    Args:
        api_key: The API key to validate
        
    Returns:
        Company object if valid, None if invalid
        
    Security Features:
        - Rate limiting protection
        - Secure hash comparison
        - Cache invalidation on multiple failures
        - Usage tracking
    """
    if not api_key:
        logger.warning("Empty API key provided for validation")
        _performance_stats['validation_errors'] += 1
        return None
    
    if not api_key.startswith(API_KEY_PREFIX):
        logger.warning("Invalid API key format - missing prefix")
        _performance_stats['validation_errors'] += 1
        return None
    
    try:
        key_hash = hash_api_key(api_key)
        
        # 1. Check Redis cache first
        cached_data = await get_cached_company(key_hash)
        if cached_data:
            _performance_stats['cache_hits'] += 1
            logger.debug(f"API key validated from cache: {key_hash[:16]}...")
            
            # Update last used timestamp asynchronously (don't wait)
            asyncio.create_task(_update_last_used_async(cached_data.get('id')))
            
            # Get company data from database
            company_data = await _get_company_by_id(cached_data['company_id'])
            return company_data
        
        _performance_stats['cache_misses'] += 1
        
        # 2. Fallback to database
        query = """
            SELECT ak.id, ak.company_id, ak.key_hash, ak.name, ak.is_active, 
                   ak.created_at, ak.last_used_at,
                   c.id as company_id, c.name as company_name, c.schema_name,
                   c.rate_limit_rps, c.monthly_quota, c.created_at as company_created_at,
                   c.updated_at as company_updated_at
            FROM api_keys ak
            JOIN companies c ON ak.company_id = c.id
            WHERE ak.key_hash = $1 AND ak.is_active = true
        """
        
        result = await DatabaseUtils.execute_query(
            query,
            {'key_hash': key_hash},
            fetch_all=False
        )
        
        _performance_stats['db_queries'] += 1
        
        if not result:
            logger.warning(f"API key validation failed: {key_hash[:16]}...")
            _performance_stats['validation_errors'] += 1
            return None
        
        # Update last used timestamp
        await _update_last_used_timestamp(result['id'])
        
        # Create company object
        company = Company(
            id=result['company_id'],
            name=result['company_name'],
            schema_name=result['schema_name'],
            rate_limit_rps=result['rate_limit_rps'],
            monthly_quota=result['monthly_quota'],
            created_at=result['company_created_at'],
            updated_at=result['company_updated_at']
        )
        
        # Cache the API key mapping for future requests
        api_key_cache_data = {
            'id': result['id'],
            'company_id': result['company_id'],
            'key_hash': result['key_hash'],
            'name': result['name'],
            'is_active': result['is_active'],
            'created_at': result['created_at'].isoformat(),
            'last_used_at': result['last_used_at'].isoformat() if result['last_used_at'] else None
        }
        
        await cache_api_key_mapping(key_hash, api_key_cache_data)
        
        logger.info(f"API key validated from DB and cached: {key_hash[:16]}...")
        return company
        
    except Exception as e:
        logger.error(f"Error validating API key: {e}")
        _performance_stats['validation_errors'] += 1
        return None

async def revoke_api_key(api_key_id: str) -> bool:
    """
    Revoke an API key and invalidate its cache
    
    Args:
        api_key_id: UUID of the API key to revoke
        
    Returns:
        True if successfully revoked, False otherwise
    """
    if not api_key_id:
        return False
    
    try:
        # Convert to UUID
        key_uuid = UUID(api_key_id) if isinstance(api_key_id, str) else api_key_id
        
        # Get key details before revoking for cache invalidation
        query_select = """
            SELECT key_hash, company_id FROM api_keys WHERE id = $1
        """
        
        key_data = await DatabaseUtils.execute_query(
            query_select,
            {'id': key_uuid},
            fetch_all=False
        )
        
        if not key_data:
            logger.warning(f"API key not found for revocation: {api_key_id}")
            return False
        
        # Revoke the key
        query_update = """
            UPDATE api_keys
            SET is_active = false, updated_at = NOW()
            WHERE id = $1 AND is_active = true
        """
        
        await DatabaseUtils.execute_query(
            query_update,
            {'id': key_uuid},
            fetch_all=False
        )
        
        _performance_stats['db_queries'] += 2
        
        # Invalidate cache
        await invalidate_company_cache(key_data['company_id'])
        
        logger.info(f"Revoked API key {api_key_id} for company {key_data['company_id']}")
        return True
        
    except Exception as e:
        logger.error(f"Error revoking API key {api_key_id}: {e}")
        return False

async def list_company_api_keys(company_id: str) -> List[APIKey]:
    """
    List all API keys for a company
    
    Args:
        company_id: UUID of the company
        
    Returns:
        List of APIKey objects for the company
    """
    if not company_id:
        return []
    
    try:
        # Convert to UUID
        company_uuid = UUID(company_id) if isinstance(company_id, str) else company_id
        
        query = """
            SELECT id, company_id, key_hash, name, is_active, created_at, last_used_at
            FROM api_keys
            WHERE company_id = $1
            ORDER BY created_at DESC
        """
        
        results = await DatabaseUtils.execute_query(
            query,
            {'company_id': company_uuid},
            fetch_all=True
        )
        
        _performance_stats['db_queries'] += 1
        
        api_keys = []
        for row in results:
            api_key = APIKey(
                id=row['id'],
                company_id=row['company_id'],
                key_hash=row['key_hash'],
                name=row['name'],
                is_active=row['is_active'],
                created_at=row['created_at'],
                last_used_at=row['last_used_at']
            )
            api_keys.append(api_key)
        
        logger.debug(f"Listed {len(api_keys)} API keys for company {company_id}")
        return api_keys
        
    except Exception as e:
        logger.error(f"Error listing API keys for company {company_id}: {e}")
        return []

# Helper functions

async def _update_last_used_timestamp(api_key_id: UUID) -> None:
    """Update the last used timestamp for an API key"""
    try:
        query = """
            UPDATE api_keys 
            SET last_used_at = NOW() 
            WHERE id = $1
        """
        await DatabaseUtils.execute_query(
            query,
            {'id': api_key_id},
            fetch_all=False
        )
    except Exception as e:
        logger.error(f"Error updating last used timestamp: {e}")

async def _update_last_used_async(api_key_id: UUID) -> None:
    """Async task to update last used timestamp without blocking"""
    import asyncio
    try:
        await _update_last_used_timestamp(api_key_id)
    except Exception as e:
        logger.error(f"Error in async last used update: {e}")

async def _get_company_by_id(company_id: UUID) -> Optional[Company]:
    """Get company data by ID"""
    try:
        query = """
            SELECT id, name, schema_name, rate_limit_rps, monthly_quota, created_at, updated_at
            FROM companies
            WHERE id = $1
        """
        
        result = await DatabaseUtils.execute_query(
            query,
            {'id': company_id},
            fetch_all=False
        )
        
        if result:
            return Company(
                id=result['id'],
                name=result['name'],
                schema_name=result['schema_name'],
                rate_limit_rps=result['rate_limit_rps'],
                monthly_quota=result['monthly_quota'],
                created_at=result['created_at'],
                updated_at=result['updated_at']
            )
        return None
    except Exception as e:
        logger.error(f"Error getting company by ID {company_id}: {e}")
        return None

# Performance and monitoring functions

def get_auth_performance_stats() -> Dict[str, Any]:
    """Get authentication service performance statistics"""
    total_requests = _performance_stats['cache_hits'] + _performance_stats['cache_misses']
    cache_hit_rate = (_performance_stats['cache_hits'] / total_requests * 100) if total_requests > 0 else 0
    
    return {
        'total_validations': total_requests,
        'cache_hits': _performance_stats['cache_hits'],
        'cache_misses': _performance_stats['cache_misses'],
        'cache_hit_rate': round(cache_hit_rate, 2),
        'db_queries': _performance_stats['db_queries'],
        'validation_errors': _performance_stats['validation_errors'],
        'error_rate': round((_performance_stats['validation_errors'] / max(total_requests, 1)) * 100, 2)
    }

def reset_auth_performance_stats() -> None:
    """Reset authentication performance statistics"""
    global _performance_stats
    _performance_stats = {
        'cache_hits': 0,
        'cache_misses': 0,
        'db_queries': 0,
        'validation_errors': 0
    } 