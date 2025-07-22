"""
Simple API Key Verification Endpoint
Used by Cloudflare Workers to authenticate API keys
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional
import hashlib

from ..database import DatabaseUtils
from ..utils.logger import get_logger
from ..config import get_settings

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Authentication"])

class VerifyRequest(BaseModel):
    """Request model for API key verification"""
    api_key: str

class VerifyResponse(BaseModel):
    """Response model for API key verification"""
    valid: bool
    company_id: Optional[str] = None
    api_key_hash: Optional[str] = None
    api_key_id: Optional[str] = None
    company_name: Optional[str] = None
    tier: Optional[str] = None
    message: Optional[str] = None

@router.post("/verify", response_model=VerifyResponse)
async def verify_api_key(request: VerifyRequest):
    """
    Verify if an API key is valid by checking its hash in the database.
    Used by Cloudflare Workers for authentication.
    """
    try:
        # First, try to find by partial match to handle different hash formats
        # Get first 8 chars and last 4 chars for prefix matching
        if len(request.api_key) > 12:
            prefix_pattern = f"{request.api_key[:8]}%{request.api_key[-4:]}"
        else:
            prefix_pattern = f"{request.api_key}%"
            
        # Query the database for the API key
        query = """
            SELECT 
                k.id,
                k.company_id,
                k.is_active,
                k.key_hash,
                c.name as company_name,
                c.tier,
                c.is_active as company_active
            FROM api_keys k
            JOIN companies c ON k.company_id = c.id
            WHERE k.key_prefix LIKE $1
        """
        
        result = await DatabaseUtils.execute_query(
            query, 
            [prefix_pattern], 
            fetch_all=False
        )
        
        # If we found a result, verify the hash
        if result:
            stored_hash = result['key_hash']
            
            # Check if stored hash is in passlib format
            if stored_hash.startswith('$pbkdf2-sha256$'):
                # Use passlib to verify
                from passlib.hash import pbkdf2_sha256
                if not pbkdf2_sha256.verify(request.api_key, stored_hash):
                    logger.warning(f"Invalid API key attempted (passlib verification failed)")
                    return VerifyResponse(
                        valid=False,
                        message="Invalid API key"
                    )
                # For passlib format, we'll use the stored hash for caching
                api_key_hash = stored_hash
            else:
                # Standard hex comparison - need to generate hash
                from ..services.auth import hash_api_key
                api_key_hash = hash_api_key(request.api_key)
                if stored_hash != api_key_hash:
                    logger.warning(f"Invalid API key attempted (hex verification failed)")
                    return VerifyResponse(
                        valid=False,
                        message="Invalid API key"
                    )
        else:
            logger.warning(f"Invalid API key attempted: no match found")
            return VerifyResponse(
                valid=False,
                message="Invalid API key"
            )
        
        # Check if key and company are active
        if not result['is_active'] or not result['company_active']:
            logger.warning(f"Inactive API key used: {api_key_hash[:8]}...")
            return VerifyResponse(
                valid=False,
                message="API key is inactive"
            )
        
        # Valid key - return company info
        logger.info(f"API key verified for company: {result['company_name']}")
        return VerifyResponse(
            valid=True,
            company_id=str(result['company_id']),
            api_key_hash=api_key_hash,  # Return the hash for Redis caching
            api_key_id=str(result['id']),  # Return the key ID for logging
            company_name=result['company_name'],
            tier=result['tier']
        )
        
    except Exception as e:
        logger.error(f"Error verifying API key: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error verifying API key"
        )

@router.get("/health")
async def auth_health():
    """Simple health check for auth service"""
    return {"status": "healthy"}