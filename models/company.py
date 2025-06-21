from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from uuid import UUID

class CompanySettings(BaseModel):
    """Company configuration settings"""
    rate_limit_rps: int = Field(default=100, ge=1, le=10000, description="Requests per second limit")
    monthly_quota: int = Field(default=1000000, ge=1000, description="Monthly API call quota")
    max_api_keys: int = Field(default=10, ge=1, le=100, description="Maximum number of API keys")
    allowed_ips: Optional[List[str]] = Field(default=None, description="Allowed IP addresses (CIDR format)")
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL for notifications")
    webhook_secret: Optional[str] = Field(default=None, description="Webhook secret for verification")

class CompanyBase(BaseModel):
    """Base company model"""
    name: str = Field(..., min_length=3, max_length=255, description="Company name")
    description: Optional[str] = Field(None, max_length=1000, description="Company description")
    contact_email: Optional[str] = Field(None, description="Primary contact email")
    billing_email: Optional[str] = Field(None, description="Billing contact email")
    billing_address: Optional[str] = Field(None, max_length=500, description="Billing address")
    vat_number: Optional[str] = Field(None, max_length=50, description="VAT/Tax ID number")

class CompanyCreate(CompanyBase):
    """Company creation model"""
    settings: Optional[CompanySettings] = Field(default_factory=CompanySettings, description="Company settings")

class CompanyUpdate(BaseModel):
    """Company update model"""
    name: Optional[str] = Field(None, min_length=3, max_length=255, description="Company name")
    description: Optional[str] = Field(None, max_length=1000, description="Company description")
    contact_email: Optional[str] = Field(None, description="Primary contact email")
    billing_email: Optional[str] = Field(None, description="Billing contact email")
    billing_address: Optional[str] = Field(None, max_length=500, description="Billing address")
    vat_number: Optional[str] = Field(None, max_length=50, description="VAT/Tax ID number")
    settings: Optional[CompanySettings] = Field(None, description="Company settings")

class Company(CompanyBase):
    """Company response model"""
    id: UUID
    schema_name: str
    settings: CompanySettings
    created_at: datetime
    updated_at: datetime
    is_active: bool = True

    class Config:
        from_attributes = True

class CompanyStats(BaseModel):
    """Company statistics model"""
    company_id: str
    company_name: str
    active_api_keys: int
    active_vendor_keys: int
    total_api_calls: int
    unique_endpoints: int
    last_activity: Optional[datetime]
    settings: CompanySettings 