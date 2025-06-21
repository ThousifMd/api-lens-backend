from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import Optional, List
from uuid import UUID

class UsageData(BaseModel):
    """Usage data model"""
    vendor: str
    model: str
    tokens_used: Optional[int] = None
    characters_used: Optional[int] = None
    cost: float
    timestamp: datetime

class CostBreakdown(BaseModel):
    """Cost breakdown model"""
    total_cost: float
    input_cost: float
    output_cost: float
    token_count: Optional[int] = None
    character_count: Optional[int] = None
    usage_data: List[UsageData]

class BillingPeriod(BaseModel):
    """Billing period model"""
    period_start: date
    period_end: date
    total_requests: int
    total_tokens: int
    total_cost: float
    status: str

class BillingData(BillingPeriod):
    """Billing data response model"""
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CostQuota(BaseModel):
    """Cost quota model"""
    monthly_quota: float = Field(..., gt=0)
    current_usage: float
    remaining_quota: float
    percentage_used: float 