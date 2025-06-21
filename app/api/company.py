"""
Company Self-Service API - Customer-facing endpoints for company management
Provides comprehensive self-service capabilities for companies to manage their profile,
API keys, vendor keys (BYOK), usage tracking, and billing information
"""

import asyncio
import json
import logging
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy.exc import IntegrityError

from ..config import get_settings
from ..utils.logger import get_logger
from ..database import DatabaseUtils
from ..services.auth import validate_api_key, generate_api_key, revoke_api_key, list_company_api_keys
from ..services.encryption import encrypt_vendor_key, decrypt_vendor_key, store_vendor_key
from models.company import Company
from models.api_key import APIKeyWithSecret, APIKey

settings = get_settings()
logger = get_logger(__name__)

# Create company router
company_router = APIRouter(
    prefix="/companies",
    tags=["Company Self-Service"]
)

# ============================================================================
# DEPENDENCY FUNCTIONS
# ============================================================================

async def get_current_company(request: Request) -> Company:
    """Extract and validate company from API key"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    api_key = auth_header.replace("Bearer ", "")
    company = await validate_api_key(api_key)
    
    if not company:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")
    
    return company

# ============================================================================
# PYDANTIC MODELS FOR REQUEST/RESPONSE VALIDATION
# ============================================================================

class CompanyProfileUpdate(BaseModel):
    """Request model for updating company profile"""
    name: Optional[str] = Field(None, min_length=2, max_length=255, description="Company name")
    description: Optional[str] = Field(None, max_length=1000, description="Company description")
    contact_email: Optional[str] = Field(None, description="Primary contact email")
    billing_email: Optional[str] = Field(None, description="Billing contact email")
    billing_address: Optional[str] = Field(None, max_length=500, description="Billing address")
    vat_number: Optional[str] = Field(None, max_length=50, description="VAT/Tax ID number")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for notifications")

class APIKeyCreateRequest(BaseModel):
    """Request model for creating new API key"""
    name: str = Field(..., min_length=1, max_length=255, description="Descriptive name for the API key")

class VendorKeyRequest(BaseModel):
    """Request model for storing vendor API key (BYOK)"""
    vendor: str = Field(..., min_length=1, max_length=50, description="Vendor name (openai, anthropic, google, etc.)")
    api_key: str = Field(..., min_length=10, description="Vendor API key")
    description: Optional[str] = Field(None, max_length=500, description="Key description")

class VendorKeyResponse(BaseModel):
    """Response model for vendor key information"""
    vendor: str
    description: Optional[str]
    key_preview: str  # Only shows first/last few characters
    is_active: bool
    created_at: datetime
    updated_at: datetime

class CompanyProfileResponse(BaseModel):
    """Response model for company profile"""
    id: str
    name: str
    description: Optional[str]
    contact_email: Optional[str]
    billing_email: Optional[str]
    billing_address: Optional[str]
    vat_number: Optional[str]
    tier: str
    schema_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    # Settings
    webhook_url: Optional[str]
    
    # Current usage stats
    current_month_requests: int
    current_month_cost: Decimal
    total_requests: int
    total_cost: Decimal
    last_request_at: Optional[datetime]

class UsageStatsResponse(BaseModel):
    """Response model for usage statistics"""
    period: str
    start_date: datetime
    end_date: datetime
    
    # Request statistics
    total_requests: int
    successful_requests: int
    failed_requests: int
    
    # Cost statistics
    total_cost: Decimal
    average_cost_per_request: Decimal
    
    # Vendor breakdown
    vendor_breakdown: List[Dict[str, Any]]
    
    # Daily breakdown
    daily_breakdown: List[Dict[str, Any]]

class BillingInvoiceResponse(BaseModel):
    """Response model for billing invoice"""
    invoice_id: str
    period_start: datetime
    period_end: datetime
    total_amount: Decimal
    currency: str
    status: str
    line_items: List[Dict[str, Any]]
    created_at: datetime

# ============================================================================
# COMPANY PROFILE MANAGEMENT ENDPOINTS
# ============================================================================

@company_router.get("/me", response_model=CompanyProfileResponse)
async def get_company_profile(current_company: Company = Depends(get_current_company)):
    """
    Get current company information including profile details,
    usage statistics, and account status.
    """
    try:
        # Get comprehensive company data with usage stats
        query = """
            SELECT 
                c.*,
                COALESCE(usage.current_month_requests, 0) as current_month_requests,
                COALESCE(usage.current_month_cost, 0) as current_month_cost,
                COALESCE(usage.total_requests, 0) as total_requests,
                COALESCE(usage.total_cost, 0) as total_cost,
                usage.last_request_at
            FROM companies c
            LEFT JOIN (
                SELECT 
                    company_id,
                    COUNT(*) as total_requests,
                    SUM(total_cost) as total_cost,
                    COUNT(CASE WHEN calculation_timestamp >= DATE_TRUNC('month', CURRENT_TIMESTAMP) THEN 1 END) as current_month_requests,
                    SUM(CASE WHEN calculation_timestamp >= DATE_TRUNC('month', CURRENT_TIMESTAMP) THEN total_cost ELSE 0 END) as current_month_cost,
                    MAX(calculation_timestamp) as last_request_at
                FROM cost_calculations
                GROUP BY company_id
            ) usage ON c.id = usage.company_id
            WHERE c.id = :company_id
        """
        
        result = await DatabaseUtils.execute_query(
            query, 
            {'company_id': current_company.id}, 
            fetch_one=True
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Company not found")
        
        return CompanyProfileResponse(
            id=str(result['id']),
            name=result['name'],
            description=result.get('description'),
            contact_email=result.get('contact_email'),
            billing_email=result.get('billing_email'),
            billing_address=result.get('billing_address'),
            vat_number=result.get('vat_number'),
            tier=result.get('tier', 'basic'),
            schema_name=result['schema_name'],
            is_active=result['is_active'],
            created_at=result['created_at'],
            updated_at=result['updated_at'],
            webhook_url=result.get('webhook_url'),
            current_month_requests=result['current_month_requests'],
            current_month_cost=Decimal(str(result['current_month_cost'])),
            total_requests=result['total_requests'],
            total_cost=Decimal(str(result['total_cost'])),
            last_request_at=result['last_request_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get company profile for {current_company.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve company profile")

@company_router.put("/me", response_model=CompanyProfileResponse)
async def update_company_profile(
    profile_update: CompanyProfileUpdate,
    current_company: Company = Depends(get_current_company)
):
    """
    Update company profile information including contact details,
    billing information, and notification settings.
    """
    try:
        current_time = datetime.now(timezone.utc)
        updates = {}
        
        # Build update dictionary from provided fields
        update_data = profile_update.dict(exclude_unset=True)
        if update_data:
            for field, value in update_data.items():
                updates[field] = value
            
            updates['updated_at'] = current_time
            
            # Build dynamic update query
            update_fields = ', '.join([f"{k} = :{k}" for k in updates.keys()])
            query = f"UPDATE companies SET {update_fields} WHERE id = :company_id"
            updates['company_id'] = current_company.id
            
            await DatabaseUtils.execute_query(query, updates)
            
            logger.info(f"Updated company profile for {current_company.id}: {list(update_data.keys())}")
        
        # Return updated profile
        return await get_company_profile(current_company)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update company profile for {current_company.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update company profile")

# ============================================================================
# API KEY MANAGEMENT ENDPOINTS
# ============================================================================

@company_router.post("/me/api-keys", response_model=APIKeyWithSecret, status_code=201)
async def create_api_key(
    key_request: APIKeyCreateRequest,
    current_company: Company = Depends(get_current_company)
):
    """
    Generate a new API key for the company with the specified name.
    Returns the secret key only once - it cannot be retrieved again.
    """
    try:
        # Check if company has reached API key limit
        existing_keys = await list_company_api_keys(str(current_company.id))
        active_keys = [key for key in existing_keys if key.is_active]
        
        if len(active_keys) >= 10:  # Default limit, could be configurable
            raise HTTPException(
                status_code=400, 
                detail="Maximum number of API keys reached (10). Please revoke unused keys first."
            )
        
        # Generate new API key
        new_api_key = await generate_api_key(str(current_company.id), key_request.name)
        
        logger.info(f"Created new API key '{key_request.name}' for company {current_company.id}")
        return new_api_key
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create API key for company {current_company.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create API key")

@company_router.get("/me/api-keys", response_model=List[APIKey])
async def list_api_keys(current_company: Company = Depends(get_current_company)):
    """
    List all API keys for the current company.
    Does not include the actual secret keys for security.
    """
    try:
        api_keys = await list_company_api_keys(str(current_company.id))
        return api_keys
        
    except Exception as e:
        logger.error(f"Failed to list API keys for company {current_company.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve API keys")

@company_router.delete("/me/api-keys/{key_id}", status_code=204)
async def revoke_api_key_endpoint(
    key_id: str,
    current_company: Company = Depends(get_current_company)
):
    """
    Revoke an API key. This action cannot be undone.
    The revoked key will immediately stop working for API access.
    """
    try:
        # Verify the key belongs to the current company
        company_keys = await list_company_api_keys(str(current_company.id))
        key_exists = any(key.id == uuid.UUID(key_id) for key in company_keys)
        
        if not key_exists:
            raise HTTPException(status_code=404, detail="API key not found")
        
        # Revoke the key
        success = await revoke_api_key(key_id)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to revoke API key")
        
        logger.info(f"Revoked API key {key_id} for company {current_company.id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke API key {key_id} for company {current_company.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to revoke API key")

# ============================================================================
# VENDOR KEY MANAGEMENT (BYOK) ENDPOINTS
# ============================================================================

@company_router.post("/me/vendor-keys", response_model=VendorKeyResponse, status_code=201)
async def store_vendor_key(
    vendor_key_request: VendorKeyRequest,
    current_company: Company = Depends(get_current_company)
):
    """
    Store a vendor API key (Bring Your Own Key - BYOK).
    The key is encrypted before storage for security.
    """
    try:
        vendor = vendor_key_request.vendor.lower()
        current_time = datetime.now(timezone.utc)
        
        # Encrypt the vendor API key
        encrypted_key = await encrypt_vendor_key(str(current_company.id), vendor_key_request.api_key)
        
        # Create preview (first 4 and last 4 characters)
        key_preview = f"{vendor_key_request.api_key[:4]}{'*' * 12}{vendor_key_request.api_key[-4:]}"
        
        # Check if vendor key already exists for this company
        existing_query = f"""
            SELECT id FROM {current_company.schema_name}.vendor_keys 
            WHERE vendor = :vendor
        """
        
        existing_key = await DatabaseUtils.execute_query(
            existing_query,
            {'vendor': vendor},
            fetch_one=True
        )
        
        if existing_key:
            # Update existing key
            update_query = f"""
                UPDATE {current_company.schema_name}.vendor_keys 
                SET encrypted_key = :encrypted_key, updated_at = :updated_at, is_active = true
                WHERE vendor = :vendor
            """
            
            await DatabaseUtils.execute_query(update_query, {
                'vendor': vendor,
                'encrypted_key': encrypted_key,
                'updated_at': current_time
            })
            
            logger.info(f"Updated vendor key for {vendor} for company {current_company.id}")
        else:
            # Insert new vendor key
            insert_query = f"""
                INSERT INTO {current_company.schema_name}.vendor_keys 
                (vendor, encrypted_key, is_active, created_at, updated_at)
                VALUES (:vendor, :encrypted_key, true, :created_at, :updated_at)
            """
            
            await DatabaseUtils.execute_query(insert_query, {
                'vendor': vendor,
                'encrypted_key': encrypted_key,
                'created_at': current_time,
                'updated_at': current_time
            })
            
            logger.info(f"Stored new vendor key for {vendor} for company {current_company.id}")
        
        return VendorKeyResponse(
            vendor=vendor,
            description=vendor_key_request.description,
            key_preview=key_preview,
            is_active=True,
            created_at=current_time,
            updated_at=current_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to store vendor key for company {current_company.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to store vendor key")

@company_router.get("/me/vendor-keys", response_model=List[VendorKeyResponse])
async def list_vendor_keys(current_company: Company = Depends(get_current_company)):
    """
    List all configured vendor keys for the company.
    Shows only metadata and key previews for security.
    """
    try:
        query = f"""
            SELECT vendor, is_active, created_at, updated_at, encrypted_key
            FROM {current_company.schema_name}.vendor_keys 
            WHERE is_active = true
            ORDER BY vendor
        """
        
        results = await DatabaseUtils.execute_query(query, {}, fetch_all=True)
        
        vendor_keys = []
        for row in results:
            # Create safe preview without decrypting
            key_preview = f"****{'*' * 12}****"
            
            vendor_keys.append(VendorKeyResponse(
                vendor=row['vendor'],
                description=None,  # Could be stored in metadata if needed
                key_preview=key_preview,
                is_active=row['is_active'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            ))
        
        return vendor_keys
        
    except Exception as e:
        logger.error(f"Failed to list vendor keys for company {current_company.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve vendor keys")

@company_router.put("/me/vendor-keys/{vendor}", response_model=VendorKeyResponse)
async def update_vendor_key(
    vendor: str,
    vendor_key_request: VendorKeyRequest,
    current_company: Company = Depends(get_current_company)
):
    """
    Update an existing vendor API key.
    """
    try:
        vendor = vendor.lower()
        current_time = datetime.now(timezone.utc)
        
        # Check if vendor key exists
        existing_query = f"""
            SELECT id FROM {current_company.schema_name}.vendor_keys 
            WHERE vendor = :vendor AND is_active = true
        """
        
        existing_key = await DatabaseUtils.execute_query(
            existing_query,
            {'vendor': vendor},
            fetch_one=True
        )
        
        if not existing_key:
            raise HTTPException(status_code=404, detail=f"Vendor key for {vendor} not found")
        
        # Encrypt the new API key
        encrypted_key = await encrypt_vendor_key(str(current_company.id), vendor_key_request.api_key)
        key_preview = f"{vendor_key_request.api_key[:4]}{'*' * 12}{vendor_key_request.api_key[-4:]}"
        
        # Update the vendor key
        update_query = f"""
            UPDATE {current_company.schema_name}.vendor_keys 
            SET encrypted_key = :encrypted_key, updated_at = :updated_at
            WHERE vendor = :vendor
        """
        
        await DatabaseUtils.execute_query(update_query, {
            'vendor': vendor,
            'encrypted_key': encrypted_key,
            'updated_at': current_time
        })
        
        logger.info(f"Updated vendor key for {vendor} for company {current_company.id}")
        
        return VendorKeyResponse(
            vendor=vendor,
            description=vendor_key_request.description,
            key_preview=key_preview,
            is_active=True,
            created_at=current_time,  # Would need to get actual created_at from DB
            updated_at=current_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update vendor key for company {current_company.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update vendor key")

@company_router.delete("/me/vendor-keys/{vendor}", status_code=204)
async def remove_vendor_key(
    vendor: str,
    current_company: Company = Depends(get_current_company)
):
    """
    Remove a vendor API key. This will deactivate the key but keep it for audit purposes.
    """
    try:
        vendor = vendor.lower()
        
        # Check if vendor key exists
        existing_query = f"""
            SELECT id FROM {current_company.schema_name}.vendor_keys 
            WHERE vendor = :vendor AND is_active = true
        """
        
        existing_key = await DatabaseUtils.execute_query(
            existing_query,
            {'vendor': vendor},
            fetch_one=True
        )
        
        if not existing_key:
            raise HTTPException(status_code=404, detail=f"Vendor key for {vendor} not found")
        
        # Deactivate the vendor key
        update_query = f"""
            UPDATE {current_company.schema_name}.vendor_keys 
            SET is_active = false, updated_at = CURRENT_TIMESTAMP
            WHERE vendor = :vendor
        """
        
        await DatabaseUtils.execute_query(update_query, {'vendor': vendor})
        
        logger.info(f"Removed vendor key for {vendor} for company {current_company.id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove vendor key for company {current_company.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove vendor key")

# ============================================================================
# USAGE AND COST TRACKING ENDPOINTS
# ============================================================================

@company_router.get("/me/usage", response_model=UsageStatsResponse)
async def get_usage_statistics(
    period: str = Query("30d", pattern=r"^(1d|7d|30d|90d)$", description="Usage period"),
    current_company: Company = Depends(get_current_company)
):
    """
    Get detailed usage statistics for the company including costs,
    request counts, vendor breakdown, and daily trends.
    """
    try:
        current_time = datetime.now(timezone.utc)
        
        # Calculate date range
        period_days = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}
        days = period_days.get(period, 30)
        start_date = current_time - timedelta(days=days)
        
        # Get overall usage statistics
        usage_query = """
            SELECT 
                COUNT(*) as total_requests,
                COUNT(*) as successful_requests,  -- Assuming all recorded requests are successful
                0 as failed_requests,  -- Would need error tracking table for actual failures
                SUM(total_cost) as total_cost,
                AVG(total_cost) as average_cost_per_request
            FROM cost_calculations 
            WHERE company_id = :company_id 
                AND calculation_timestamp >= :start_date
        """
        
        usage_stats = await DatabaseUtils.execute_query(
            usage_query,
            {'company_id': current_company.id, 'start_date': start_date},
            fetch_one=True
        )
        
        # Get vendor breakdown
        vendor_query = """
            SELECT 
                vendor,
                COUNT(*) as requests,
                SUM(total_cost) as cost,
                AVG(total_cost) as avg_cost_per_request
            FROM cost_calculations 
            WHERE company_id = :company_id 
                AND calculation_timestamp >= :start_date
            GROUP BY vendor
            ORDER BY requests DESC
        """
        
        vendor_data = await DatabaseUtils.execute_query(
            vendor_query,
            {'company_id': current_company.id, 'start_date': start_date},
            fetch_all=True
        )
        
        # Get daily breakdown
        daily_query = """
            SELECT 
                DATE(calculation_timestamp) as date,
                COUNT(*) as requests,
                SUM(total_cost) as cost,
                COUNT(DISTINCT vendor) as vendors_used
            FROM cost_calculations 
            WHERE company_id = :company_id 
                AND calculation_timestamp >= :start_date
            GROUP BY DATE(calculation_timestamp)
            ORDER BY date
        """
        
        daily_data = await DatabaseUtils.execute_query(
            daily_query,
            {'company_id': current_company.id, 'start_date': start_date},
            fetch_all=True
        )
        
        return UsageStatsResponse(
            period=period,
            start_date=start_date,
            end_date=current_time,
            total_requests=usage_stats.get('total_requests', 0),
            successful_requests=usage_stats.get('successful_requests', 0),
            failed_requests=usage_stats.get('failed_requests', 0),
            total_cost=Decimal(str(usage_stats.get('total_cost', 0))),
            average_cost_per_request=Decimal(str(usage_stats.get('average_cost_per_request', 0))),
            vendor_breakdown=[
                {
                    'vendor': row['vendor'],
                    'requests': row['requests'],
                    'cost': float(row['cost']),
                    'avg_cost_per_request': float(row['avg_cost_per_request'])
                }
                for row in vendor_data
            ],
            daily_breakdown=[
                {
                    'date': row['date'].isoformat(),
                    'requests': row['requests'],
                    'cost': float(row['cost']),
                    'vendors_used': row['vendors_used']
                }
                for row in daily_data
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get usage statistics for company {current_company.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve usage statistics")

# ============================================================================
# BILLING AND INVOICE ENDPOINTS
# ============================================================================

@company_router.get("/me/billing/invoices")
async def get_invoices(
    limit: int = Query(10, ge=1, le=100, description="Number of invoices to return"),
    current_company: Company = Depends(get_current_company)
):
    """
    Get billing invoices for the company.
    Returns generated invoices based on usage data.
    """
    try:
        # For now, generate mock invoices based on billing_data table
        # In a real implementation, this would integrate with a billing system
        
        invoice_query = """
            SELECT 
                vendor,
                SUM(total_cost) as amount,
                MIN(period_start) as period_start,
                MAX(period_end) as period_end,
                status,
                created_at
            FROM billing_data 
            WHERE company_id = :company_id
            GROUP BY vendor, status, created_at
            ORDER BY created_at DESC
            LIMIT :limit
        """
        
        invoices_data = await DatabaseUtils.execute_query(
            invoice_query,
            {'company_id': current_company.id, 'limit': limit},
            fetch_all=True
        )
        
        invoices = []
        for row in invoices_data:
            invoice_id = f"INV-{current_company.id}-{row['created_at'].strftime('%Y%m')}-{secrets.token_hex(4).upper()}"
            
            invoices.append({
                'invoice_id': invoice_id,
                'period_start': row['period_start'].isoformat(),
                'period_end': row['period_end'].isoformat(),
                'total_amount': float(row['amount']),
                'currency': 'USD',
                'status': row['status'],
                'vendor': row['vendor'],
                'created_at': row['created_at'].isoformat()
            })
        
        return {
            'invoices': invoices,
            'total_count': len(invoices)
        }
        
    except Exception as e:
        logger.error(f"Failed to get invoices for company {current_company.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve invoices")

@company_router.get("/me/billing/current-usage")
async def get_current_billing_usage(current_company: Company = Depends(get_current_company)):
    """
    Get current month billing usage and projected costs.
    """
    try:
        current_time = datetime.now(timezone.utc)
        month_start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Get current month usage
        usage_query = """
            SELECT 
                COUNT(*) as requests_this_month,
                SUM(total_cost) as cost_this_month,
                COUNT(DISTINCT vendor) as vendors_used,
                COUNT(DISTINCT DATE(calculation_timestamp)) as active_days
            FROM cost_calculations 
            WHERE company_id = :company_id 
                AND calculation_timestamp >= :month_start
        """
        
        usage_data = await DatabaseUtils.execute_query(
            usage_query,
            {'company_id': current_company.id, 'month_start': month_start},
            fetch_one=True
        )
        
        # Calculate projections
        days_in_month = 30  # Simplified
        days_elapsed = (current_time - month_start).days + 1
        days_remaining = days_in_month - days_elapsed
        
        current_cost = float(usage_data.get('cost_this_month', 0))
        daily_avg = current_cost / max(days_elapsed, 1)
        projected_month_cost = daily_avg * days_in_month
        
        return {
            'current_month': {
                'period_start': month_start.isoformat(),
                'period_end': current_time.isoformat(),
                'requests': usage_data.get('requests_this_month', 0),
                'cost': current_cost,
                'vendors_used': usage_data.get('vendors_used', 0),
                'active_days': usage_data.get('active_days', 0)
            },
            'projections': {
                'daily_average_cost': daily_avg,
                'projected_month_cost': projected_month_cost,
                'days_remaining': days_remaining,
                'estimated_month_end_cost': projected_month_cost
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get current billing usage for company {current_company.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve current billing usage")