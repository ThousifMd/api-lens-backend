"""
Simplified Admin API Endpoints - Core administrative functionality
Provides essential CRUD operations for companies, system monitoring, and configuration
"""

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Union
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field, validator

from ..config import get_settings
from ..utils.logger import get_logger
from ..database import DatabaseUtils

settings = get_settings()
logger = get_logger(__name__)

# Create admin router (simplified authentication for now)
admin_router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)

# ============================================================================
# SIMPLIFIED PYDANTIC MODELS
# ============================================================================

class CompanyCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    tier: str = Field(default="basic", regex=r'^(free|basic|premium|enterprise|unlimited)$')
    monthly_request_limit: Optional[int] = Field(default=100000, ge=1)
    monthly_cost_limit: Optional[Decimal] = Field(default=Decimal('1000.00'), ge=0)

class CompanyUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    email: Optional[str] = Field(None, regex=r'^[^@]+@[^@]+\.[^@]+$')
    tier: Optional[str] = Field(None, regex=r'^(free|basic|premium|enterprise|unlimited)$')
    monthly_request_limit: Optional[int] = Field(None, ge=1)
    monthly_cost_limit: Optional[Decimal] = Field(None, ge=0)
    is_active: Optional[bool] = None

class VendorPricingRequest(BaseModel):
    vendor: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=100)
    pricing_model: str = Field(..., regex=r'^(token_based|character_based|request_based)$')
    input_price_per_unit: Decimal = Field(..., ge=0)
    output_price_per_unit: Decimal = Field(..., ge=0)
    currency: str = Field(default="USD", regex=r'^[A-Z]{3}$')

# ============================================================================
# COMPANY MANAGEMENT ENDPOINTS
# ============================================================================

@admin_router.post("/companies", status_code=201)
async def create_company(company_data: CompanyCreateRequest):
    """Create a new company with basic setup"""
    try:
        company_id = str(uuid.uuid4())
        schema_name = f"company_{company_id.replace('-', '_')}"
        current_time = datetime.now(timezone.utc)
        
        # Create company record
        company_query = """
            INSERT INTO companies (
                id, name, email, tier, schema_name, is_active,
                created_at, updated_at
            ) VALUES (
                :id, :name, :email, :tier, :schema_name, :is_active,
                :created_at, :updated_at
            )
        """
        
        await DatabaseUtils.execute_query(company_query, {
            'id': company_id,
            'name': company_data.name,
            'email': company_data.email,
            'tier': company_data.tier,
            'schema_name': schema_name,
            'is_active': True,
            'created_at': current_time,
            'updated_at': current_time
        })
        
        # Set up rate limiting configuration
        rate_limit_query = """
            INSERT INTO rate_limit_configs (
                company_id, tier, requests_per_minute, requests_per_hour,
                requests_per_day, is_active, created_at, updated_at
            ) VALUES (
                :company_id, :tier, :requests_per_minute, :requests_per_hour,
                :requests_per_day, :is_active, :created_at, :updated_at
            )
        """
        
        # Set defaults based on tier
        tier_defaults = {
            'free': {'rpm': 10, 'rph': 100, 'rpd': 1000},
            'basic': {'rpm': 100, 'rph': 1000, 'rpd': 10000},
            'premium': {'rpm': 500, 'rph': 5000, 'rpd': 50000},
            'enterprise': {'rpm': 1000, 'rph': 10000, 'rpd': 100000},
            'unlimited': {'rpm': 10000, 'rph': 100000, 'rpd': 1000000}
        }
        
        defaults = tier_defaults.get(company_data.tier, tier_defaults['basic'])
        
        await DatabaseUtils.execute_query(rate_limit_query, {
            'company_id': company_id,
            'tier': company_data.tier,
            'requests_per_minute': defaults['rpm'],
            'requests_per_hour': defaults['rph'],
            'requests_per_day': defaults['rpd'],
            'is_active': True,
            'created_at': current_time,
            'updated_at': current_time
        })
        
        # Set up quota configuration
        quota_query = """
            INSERT INTO quota_configurations (
                company_id, monthly_request_limit, monthly_cost_limit,
                is_active, created_at, updated_at
            ) VALUES (
                :company_id, :monthly_request_limit, :monthly_cost_limit,
                :is_active, :created_at, :updated_at
            )
        """
        
        await DatabaseUtils.execute_query(quota_query, {
            'company_id': company_id,
            'monthly_request_limit': company_data.monthly_request_limit,
            'monthly_cost_limit': company_data.monthly_cost_limit,
            'is_active': True,
            'created_at': current_time,
            'updated_at': current_time
        })
        
        logger.info(f"Created company {company_id}: {company_data.name}")
        
        return {
            'company_id': company_id,
            'name': company_data.name,
            'email': company_data.email,
            'tier': company_data.tier,
            'schema_name': schema_name,
            'created_at': current_time.isoformat(),
            'message': 'Company created successfully'
        }
        
    except Exception as e:
        logger.error(f"Failed to create company: {e}")
        raise HTTPException(status_code=500, detail="Failed to create company")

@admin_router.get("/companies/{company_id}")
async def get_company(company_id: str):
    """Get company details with usage statistics"""
    try:
        query = """
            SELECT 
                c.*,
                rlc.requests_per_minute, rlc.requests_per_hour, rlc.requests_per_day,
                qc.monthly_request_limit, qc.monthly_cost_limit,
                COALESCE(usage.total_requests, 0) as total_requests,
                COALESCE(usage.total_cost, 0) as total_cost,
                COALESCE(usage.current_month_requests, 0) as current_month_requests,
                COALESCE(usage.current_month_cost, 0) as current_month_cost,
                usage.last_request_at
            FROM companies c
            LEFT JOIN rate_limit_configs rlc ON c.id = rlc.company_id
            LEFT JOIN quota_configurations qc ON c.id = qc.company_id
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
        
        result = await DatabaseUtils.execute_query(query, {'company_id': company_id}, fetch_one=True)
        
        if not result:
            raise HTTPException(status_code=404, detail="Company not found")
        
        return {
            'id': result['id'],
            'name': result['name'],
            'email': result['email'],
            'tier': result['tier'],
            'schema_name': result['schema_name'],
            'is_active': result['is_active'],
            'created_at': result['created_at'].isoformat(),
            'updated_at': result['updated_at'].isoformat(),
            'rate_limits': {
                'requests_per_minute': result['requests_per_minute'],
                'requests_per_hour': result['requests_per_hour'],
                'requests_per_day': result['requests_per_day']
            },
            'quotas': {
                'monthly_request_limit': result['monthly_request_limit'],
                'monthly_cost_limit': float(result['monthly_cost_limit']) if result['monthly_cost_limit'] else 0
            },
            'usage_stats': {
                'total_requests': result['total_requests'],
                'total_cost': float(result['total_cost']),
                'current_month_requests': result['current_month_requests'],
                'current_month_cost': float(result['current_month_cost']),
                'last_request_at': result['last_request_at'].isoformat() if result['last_request_at'] else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get company {company_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve company")

@admin_router.put("/companies/{company_id}")
async def update_company(company_id: str, update_data: CompanyUpdateRequest):
    """Update company settings"""
    try:
        # Check if company exists
        check_query = "SELECT id FROM companies WHERE id = :company_id"
        existing = await DatabaseUtils.execute_query(check_query, {'company_id': company_id}, fetch_one=True)
        
        if not existing:
            raise HTTPException(status_code=404, detail="Company not found")
        
        current_time = datetime.now(timezone.utc)
        
        # Update company basic info
        company_updates = {}
        if update_data.name is not None:
            company_updates['name'] = update_data.name
        if update_data.email is not None:
            company_updates['email'] = update_data.email
        if update_data.tier is not None:
            company_updates['tier'] = update_data.tier
        if update_data.is_active is not None:
            company_updates['is_active'] = update_data.is_active
        
        if company_updates:
            company_updates['updated_at'] = current_time
            update_fields = ', '.join([f"{k} = :{k}" for k in company_updates.keys()])
            company_query = f"UPDATE companies SET {update_fields} WHERE id = :company_id"
            company_updates['company_id'] = company_id
            await DatabaseUtils.execute_query(company_query, company_updates)
        
        # Update quota configuration
        quota_updates = {}
        if update_data.monthly_request_limit is not None:
            quota_updates['monthly_request_limit'] = update_data.monthly_request_limit
        if update_data.monthly_cost_limit is not None:
            quota_updates['monthly_cost_limit'] = update_data.monthly_cost_limit
        
        if quota_updates:
            quota_updates['updated_at'] = current_time
            update_fields = ', '.join([f"{k} = :{k}" for k in quota_updates.keys()])
            quota_query = f"UPDATE quota_configurations SET {update_fields} WHERE company_id = :company_id"
            quota_updates['company_id'] = company_id
            await DatabaseUtils.execute_query(quota_query, quota_updates)
        
        logger.info(f"Updated company {company_id}")
        return {"message": "Company updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update company {company_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update company")

@admin_router.delete("/companies/{company_id}")
async def delete_company(company_id: str, confirm: bool = Query(False)):
    """Delete company and all data"""
    if not confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to delete company")
    
    try:
        # Check if company exists
        check_query = "SELECT schema_name FROM companies WHERE id = :company_id"
        company = await DatabaseUtils.execute_query(check_query, {'company_id': company_id}, fetch_one=True)
        
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Delete in order to handle foreign key constraints
        await DatabaseUtils.execute_query("DELETE FROM quota_configurations WHERE company_id = :company_id", {'company_id': company_id})
        await DatabaseUtils.execute_query("DELETE FROM rate_limit_configs WHERE company_id = :company_id", {'company_id': company_id})
        await DatabaseUtils.execute_query("DELETE FROM companies WHERE id = :company_id", {'company_id': company_id})
        
        logger.warning(f"Deleted company {company_id}")
        return {"message": "Company deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete company {company_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete company")

# ============================================================================
# SYSTEM HEALTH AND MONITORING
# ============================================================================

@admin_router.get("/system/health")
async def get_system_health():
    """Get system health status"""
    try:
        current_time = datetime.now(timezone.utc)
        
        # Check database connectivity
        try:
            await DatabaseUtils.execute_query("SELECT 1", {})
            database_status = "healthy"
        except Exception:
            database_status = "unhealthy"
        
        # Get basic system stats
        companies_query = "SELECT COUNT(*) as total, COUNT(CASE WHEN is_active THEN 1 END) as active FROM companies"
        companies_stats = await DatabaseUtils.execute_query(companies_query, {}, fetch_one=True)
        
        # Get recent request stats
        recent_query = """
            SELECT 
                COUNT(*) as requests_last_hour,
                SUM(total_cost) as cost_last_hour
            FROM cost_calculations 
            WHERE calculation_timestamp >= :since_time
        """
        
        since_time = current_time - timedelta(hours=1)
        recent_stats = await DatabaseUtils.execute_query(recent_query, {'since_time': since_time}, fetch_one=True)
        
        return {
            'status': 'healthy' if database_status == 'healthy' else 'unhealthy',
            'timestamp': current_time.isoformat(),
            'database_status': database_status,
            'system_stats': {
                'total_companies': companies_stats['total'],
                'active_companies': companies_stats['active'],
                'requests_last_hour': recent_stats['requests_last_hour'] or 0,
                'cost_last_hour': float(recent_stats['cost_last_hour'] or 0)
            }
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            'status': 'unhealthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': 'Health check failed'
        }

@admin_router.get("/analytics/system")
async def get_system_analytics(period: str = Query("24h", regex=r"^(1h|6h|24h|7d|30d)$")):
    """Get system-wide analytics"""
    try:
        current_time = datetime.now(timezone.utc)
        
        # Calculate time range
        period_hours = {"1h": 1, "6h": 6, "24h": 24, "7d": 168, "30d": 720}
        hours = period_hours.get(period, 24)
        start_time = current_time - timedelta(hours=hours)
        
        # Get usage statistics
        usage_query = """
            SELECT 
                COUNT(*) as total_requests,
                COUNT(DISTINCT company_id) as active_companies,
                SUM(total_cost) as total_cost,
                AVG(total_cost) as avg_cost_per_request,
                COUNT(CASE WHEN status_code >= 400 THEN 1 END) as error_count
            FROM cost_calculations 
            WHERE calculation_timestamp >= :start_time
        """
        
        usage_stats = await DatabaseUtils.execute_query(usage_query, {'start_time': start_time}, fetch_one=True)
        
        # Get vendor breakdown
        vendor_query = """
            SELECT 
                vendor,
                COUNT(*) as requests,
                SUM(total_cost) as cost
            FROM cost_calculations 
            WHERE calculation_timestamp >= :start_time
            GROUP BY vendor
            ORDER BY requests DESC
            LIMIT 10
        """
        
        vendor_data = await DatabaseUtils.execute_query(vendor_query, {'start_time': start_time}, fetch_all=True)
        
        return {
            'period': period,
            'start_time': start_time.isoformat(),
            'end_time': current_time.isoformat(),
            'summary': {
                'total_requests': usage_stats['total_requests'] or 0,
                'active_companies': usage_stats['active_companies'] or 0,
                'total_cost': float(usage_stats['total_cost'] or 0),
                'avg_cost_per_request': float(usage_stats['avg_cost_per_request'] or 0),
                'error_count': usage_stats['error_count'] or 0,
                'error_rate': (usage_stats['error_count'] or 0) / max(usage_stats['total_requests'] or 1, 1) * 100
            },
            'vendor_breakdown': [
                {
                    'vendor': row['vendor'],
                    'requests': row['requests'],
                    'cost': float(row['cost']),
                    'avg_cost_per_request': float(row['cost']) / row['requests'] if row['requests'] > 0 else 0
                }
                for row in vendor_data
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get system analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve analytics")

# ============================================================================
# VENDOR PRICING MANAGEMENT
# ============================================================================

@admin_router.post("/pricing/update")
async def update_vendor_pricing(pricing_data: VendorPricingRequest):
    """Update vendor pricing configuration"""
    try:
        current_time = datetime.now(timezone.utc)
        pricing_id = str(uuid.uuid4())
        
        # Deactivate existing pricing
        deactivate_query = """
            UPDATE global_vendor_pricing 
            SET is_active = false, updated_at = :updated_at 
            WHERE vendor = :vendor AND model = :model AND is_active = true
        """
        
        await DatabaseUtils.execute_query(deactivate_query, {
            'vendor': pricing_data.vendor.lower(),
            'model': pricing_data.model,
            'updated_at': current_time
        })
        
        # Insert new pricing
        pricing_query = """
            INSERT INTO global_vendor_pricing (
                id, vendor, model, pricing_model, input_price_per_unit,
                output_price_per_unit, currency, effective_date, is_active,
                created_at, updated_at
            ) VALUES (
                :id, :vendor, :model, :pricing_model, :input_price_per_unit,
                :output_price_per_unit, :currency, :effective_date, :is_active,
                :created_at, :updated_at
            )
        """
        
        await DatabaseUtils.execute_query(pricing_query, {
            'id': pricing_id,
            'vendor': pricing_data.vendor.lower(),
            'model': pricing_data.model,
            'pricing_model': pricing_data.pricing_model,
            'input_price_per_unit': pricing_data.input_price_per_unit,
            'output_price_per_unit': pricing_data.output_price_per_unit,
            'currency': pricing_data.currency,
            'effective_date': current_time,
            'is_active': True,
            'created_at': current_time,
            'updated_at': current_time
        })
        
        logger.info(f"Updated pricing for {pricing_data.vendor}/{pricing_data.model}")
        
        return {
            'message': 'Pricing updated successfully',
            'pricing_id': pricing_id,
            'vendor': pricing_data.vendor,
            'model': pricing_data.model,
            'effective_date': current_time.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to update pricing: {e}")
        raise HTTPException(status_code=500, detail="Failed to update pricing")

@admin_router.get("/pricing/vendors")
async def get_vendor_pricing():
    """Get current vendor pricing"""
    try:
        query = """
            SELECT 
                vendor, model, pricing_model, input_price_per_unit,
                output_price_per_unit, currency, effective_date, is_active
            FROM global_vendor_pricing
            WHERE is_active = true
            ORDER BY vendor, model
        """
        
        pricing_data = await DatabaseUtils.execute_query(query, {}, fetch_all=True)
        
        return {
            'pricing_count': len(pricing_data),
            'pricing_data': [
                {
                    'vendor': row['vendor'],
                    'model': row['model'],
                    'pricing_model': row['pricing_model'],
                    'input_price_per_unit': float(row['input_price_per_unit']),
                    'output_price_per_unit': float(row['output_price_per_unit']),
                    'currency': row['currency'],
                    'effective_date': row['effective_date'].isoformat(),
                    'is_active': row['is_active']
                }
                for row in pricing_data
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get pricing: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve pricing")