from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from uuid import UUID

class APIKeyBase(BaseModel):
    """Base API key model"""
    name: str = Field(..., min_length=1, max_length=255)
    is_active: bool = True

class APIKeyCreate(APIKeyBase):
    """API key creation model"""
    pass

class APIKeyUpdate(BaseModel):
    """API key update model"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None

class APIKey(APIKeyBase):
    """API key response model"""
    id: UUID
    company_id: UUID
    key_hash: str
    created_at: datetime
    last_used_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class APIKeyWithSecret(APIKey):
    """API key response model including the secret key"""
    secret_key: str 