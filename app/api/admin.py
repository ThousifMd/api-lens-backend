"""
Admin API Endpoints - Administrative management for API Lens system
Provides comprehensive CRUD operations for companies, system configuration, and monitoring
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Union
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy.exc import IntegrityError

from ..config import get_settings
from ..utils.logger import get_logger
from ..database import DatabaseUtils
from ..services.monitoring import get_real_time_metrics, monitor_rate_limit_performance
from ..services.cache import get_cache_stats
from ..auth.admin_auth import verify_admin_token  # Admin authentication

settings = get_settings()
logger = get_logger(__name__)

# Create admin router with prefix and authentication
admin_router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(verify_admin_token)]  # Require admin authentication
)

# ============================================================================
# PYDANTIC MODELS FOR REQUEST/RESPONSE VALIDATION
# ============================================================================

class CompanyCreateRequest(BaseModel):
    """Request model for creating a new company"""
    name: str = Field(..., min_length=2, max_length=255, description="Company name")
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$', description="Admin email")
    tier: str = Field(default="basic", pattern=r'^(free|basic|premium|enterprise|unlimited)$', description="Service tier")
    
    # Rate limiting configuration
    requests_per_minute: Optional[int] = Field(default=100, ge=1, le=10000, description="Requests per minute limit")
    requests_per_hour: Optional[int] = Field(default=1000, ge=1, le=100000, description="Requests per hour limit")
    requests_per_day: Optional[int] = Field(default=10000, ge=1, le=1000000, description="Requests per day limit")
    
    # Quota configuration
    monthly_request_limit: Optional[int] = Field(default=100000, ge=1, description="Monthly request quota")
    monthly_cost_limit: Optional[Decimal] = Field(default=Decimal('1000.00'), ge=0, description="Monthly cost limit")
    
    # Settings
    is_active: bool = Field(default=True, description="Company active status")
    enable_analytics: bool = Field(default=True, description="Enable analytics")
    enable_monitoring: bool = Field(default=True, description="Enable monitoring")
    
    # Custom settings
    custom_settings: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Custom company settings")

class CompanyUpdateRequest(BaseModel):
    """Request model for updating an existing company"""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    email: Optional[str] = Field(None, pattern=r'^[^@]+@[^@]+\.[^@]+$')
    tier: Optional[str] = Field(None, pattern=r'^(free|basic|premium|enterprise|unlimited)$')
    
    # Rate limiting configuration
    requests_per_minute: Optional[int] = Field(None, ge=1, le=10000)
    requests_per_hour: Optional[int] = Field(None, ge=1, le=100000)
    requests_per_day: Optional[int] = Field(None, ge=1, le=1000000)
    
    # Quota configuration
    monthly_request_limit: Optional[int] = Field(None, ge=1)
    monthly_cost_limit: Optional[Decimal] = Field(None, ge=0)
    
    # Settings
    is_active: Optional[bool] = None
    enable_analytics: Optional[bool] = None
    enable_monitoring: Optional[bool] = None
    
    # Custom settings
    custom_settings: Optional[Dict[str, Any]] = None

class VendorPricingUpdateRequest(BaseModel):
    """Request model for updating vendor pricing"""
    vendor: str = Field(..., min_length=1, max_length=50, description="Vendor name")
    model: str = Field(..., min_length=1, max_length=100, description="Model name")
    pricing_model: str = Field(..., pattern=r'^(token_based|character_based|request_based|time_based)$')
    
    # Pricing details
    input_price: Decimal = Field(..., ge=0, description="Input price per unit")
    output_price: Decimal = Field(..., ge=0, description="Output price per unit")
    currency: str = Field(default="USD", pattern=r'^[A-Z]{3}$', description="Currency code")
    
    # Metadata
    effective_date: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = Field(default=True)
    pricing_tier: Optional[str] = Field(default="standard", description="Pricing tier")
    
    # Additional pricing info
    minimum_charge: Optional[Decimal] = Field(default=Decimal('0'), ge=0)
    bulk_discount_threshold: Optional[int] = Field(default=None, ge=1)
    bulk_discount_rate: Optional[Decimal] = Field(default=None, ge=0, le=1)

class SystemConfigUpdateRequest(BaseModel):
    """Request model for updating system configuration"""
    config_key: str = Field(..., min_length=1, max_length=100, description="Configuration key")
    config_value: Union[str, int, float, bool, Dict, List] = Field(..., description="Configuration value")
    description: Optional[str] = Field(None, max_length=500, description="Configuration description")
    is_sensitive: bool = Field(default=False, description="Whether config contains sensitive data")

class CompanyResponse(BaseModel):
    """Response model for company data"""
    id: str
    name: str
    email: str
    tier: str
    schema_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    # Usage statistics
    total_requests: int
    total_cost: Decimal
    last_request_at: Optional[datetime]
    
    # Current quotas and limits
    monthly_request_limit: int
    monthly_cost_limit: Decimal
    current_month_requests: int
    current_month_cost: Decimal
    
    # Settings
    enable_analytics: bool
    enable_monitoring: bool
    custom_settings: Dict[str, Any]

class SystemHealthResponse(BaseModel):
    """Response model for system health"""
    status: str
    timestamp: datetime
    uptime_seconds: float
    
    # System components
    redis_status: str
    database_status: str
    cache_hit_rate: float
    
    # Performance metrics
    avg_response_time_ms: float
    requests_per_second: float
    error_rate_percentage: float
    
    # Resource utilization
    memory_usage: Dict[str, Any]
    connection_pools: Dict[str, Any]
    
    # Alerts and issues
    active_alerts: int
    critical_issues: List[str]

# ============================================================================
# COMPANY MANAGEMENT ENDPOINTS
# ============================================================================

@admin_router.post("/companies", response_model=CompanyResponse, status_code=201)
async def create_company(company_data: CompanyCreateRequest):
    """
    Create a new company with complete setup including schema provisioning,
    rate limiting configuration, and quota management.
    """
    try:
        company_id = str(uuid.uuid4())
        schema_name = f"company_{company_id.replace('-', '_')}"
        current_time = datetime.now(timezone.utc)
        
        # Begin transaction for atomic company creation
        # Note: Using individual queries for now - would use proper transaction in production
        
        # 1. Create company record
        company_query = """
            INSERT INTO companies (
                id, name, email, tier, schema_name, is_active,
                enable_analytics, enable_monitoring, custom_settings,
                created_at, updated_at
            ) VALUES (
                :id, :name, :email, :tier, :schema_name, :is_active,
                :enable_analytics, :enable_monitoring, :custom_settings,
                :created_at, :updated_at
            )
        """
        
        await DatabaseUtils.execute_query(company_query, {
            'id': company_id,
            'name': company_data.name,
            'email': company_data.email,
            'tier': company_data.tier,
            'schema_name': schema_name,
            'is_active': company_data.is_active,
            'enable_analytics': company_data.enable_analytics,
            'enable_monitoring': company_data.enable_monitoring,
            'custom_settings': json.dumps(company_data.custom_settings),
            'created_at': current_time,
            'updated_at': current_time
        })
        
        # 2. Create company-specific schema
        await DatabaseUtils.execute_query(f"CREATE SCHEMA IF NOT EXISTS {schema_name}", {})
        
        # 3. Set up rate limiting configuration
        rate_limit_query = """
            INSERT INTO rate_limit_configs (
                company_id, tier, requests_per_minute, requests_per_hour,
                requests_per_day, is_active, created_at, updated_at
            ) VALUES (
                :company_id, :tier, :requests_per_minute, :requests_per_hour,
                :requests_per_day, :is_active, :created_at, :updated_at
            )
        """
        
        await DatabaseUtils.execute_query(rate_limit_query, {
                'company_id': company_id,
                'tier': company_data.tier,
                'requests_per_minute': company_data.requests_per_minute,
                'requests_per_hour': company_data.requests_per_hour,
                'requests_per_day': company_data.requests_per_day,
                'is_active': True,
                'created_at': current_time,
                'updated_at': current_time
            })
            
        # 4. Set up quota configuration
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
        
        # 5. Set up monitoring configuration
        monitoring_query = """
            INSERT INTO monitoring_configs (
                company_id, anomaly_detection_enabled, anomaly_sensitivity,
                anomaly_notification_enabled, created_at, updated_at
            ) VALUES (
                :company_id, :anomaly_detection_enabled, :anomaly_sensitivity,
                :anomaly_notification_enabled, :created_at, :updated_at
            )
        """
        
        await DatabaseUtils.execute_query(monitoring_query, {
            'company_id': company_id,
            'anomaly_detection_enabled': company_data.enable_monitoring,
            'anomaly_sensitivity': 'medium',
            'anomaly_notification_enabled': company_data.enable_monitoring,
            'created_at': current_time,
            'updated_at': current_time
        })
        
        # 6. Create company-specific tables in schema
        await _provision_company_schema(schema_name)
        
        # Get complete company data for response
        company_response = await _get_company_details(company_id)
        
        logger.info(f"Successfully created company {company_id} with schema {schema_name}")
        return company_response
        
    except IntegrityError as e:
        logger.error(f"Database integrity error creating company: {e}")
        raise HTTPException(status_code=400, detail="Company with this email already exists")
    except Exception as e:
        logger.error(f"Failed to create company: {e}")
        raise HTTPException(status_code=500, detail="Failed to create company")

@admin_router.get("/companies/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: str):
    """
    Get detailed company information including usage statistics,
    current quotas, and configuration settings.
    """
    try:
        company_data = await _get_company_details(company_id)
        if not company_data:
            raise HTTPException(status_code=404, detail="Company not found")
        
        return company_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get company {company_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve company data")

@admin_router.put("/companies/{company_id}", response_model=CompanyResponse)
async def update_company(company_id: str, update_data: CompanyUpdateRequest):
    """
    Update company settings including tier changes, quota adjustments,
    and configuration updates with proper validation.
    """
    try:
        # Verify company exists
        existing_company = await _get_company_details(company_id)
        if not existing_company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        current_time = datetime.now(timezone.utc)
        updates_made = []
        
        # Update company basic info
        company_updates = {}
        if update_data.name is not None:
            company_updates['name'] = update_data.name
            updates_made.append('name')
        if update_data.email is not None:
            company_updates['email'] = update_data.email
            updates_made.append('email')
        if update_data.tier is not None:
            company_updates['tier'] = update_data.tier
            updates_made.append('tier')
        if update_data.is_active is not None:
            company_updates['is_active'] = update_data.is_active
            updates_made.append('status')
        if update_data.enable_analytics is not None:
            company_updates['enable_analytics'] = update_data.enable_analytics
            updates_made.append('analytics')
        if update_data.enable_monitoring is not None:
            company_updates['enable_monitoring'] = update_data.enable_monitoring
            updates_made.append('monitoring')
        if update_data.custom_settings is not None:
            company_updates['custom_settings'] = json.dumps(update_data.custom_settings)
            updates_made.append('settings')
        
        if company_updates:
            company_updates['updated_at'] = current_time
            update_fields = ', '.join([f"{k} = :{k}" for k in company_updates.keys()])
            company_query = f"UPDATE companies SET {update_fields} WHERE id = :company_id"
            company_updates['company_id'] = company_id
            await DatabaseUtils.execute_query(company_query, company_updates)
        
        # Update rate limiting configuration
        rate_limit_updates = {}
        if update_data.requests_per_minute is not None:
            rate_limit_updates['requests_per_minute'] = update_data.requests_per_minute
            updates_made.append('rate_limits')
        if update_data.requests_per_hour is not None:
            rate_limit_updates['requests_per_hour'] = update_data.requests_per_hour
            updates_made.append('rate_limits')
        if update_data.requests_per_day is not None:
            rate_limit_updates['requests_per_day'] = update_data.requests_per_day
            updates_made.append('rate_limits')
        
        if rate_limit_updates:
            rate_limit_updates['updated_at'] = current_time
            update_fields = ', '.join([f"{k} = :{k}" for k in rate_limit_updates.keys()])
            rate_limit_query = f"UPDATE rate_limit_configs SET {update_fields} WHERE company_id = :company_id"
            rate_limit_updates['company_id'] = company_id
            await DatabaseUtils.execute_query(rate_limit_query, rate_limit_updates)
        
        # Update quota configuration
        quota_updates = {}
        if update_data.monthly_request_limit is not None:
            quota_updates['monthly_request_limit'] = update_data.monthly_request_limit
            updates_made.append('quotas')
        if update_data.monthly_cost_limit is not None:
            quota_updates['monthly_cost_limit'] = update_data.monthly_cost_limit
            updates_made.append('quotas')
        
        if quota_updates:
            quota_updates['updated_at'] = current_time
            update_fields = ', '.join([f"{k} = :{k}" for k in quota_updates.keys()])
            quota_query = f"UPDATE quota_configurations SET {update_fields} WHERE company_id = :company_id"
            quota_updates['company_id'] = company_id
            await DatabaseUtils.execute_query(quota_query, quota_updates)
        
        # Update monitoring configuration if monitoring settings changed
        if update_data.enable_monitoring is not None:
            monitoring_query = """
                UPDATE monitoring_configs 
                SET anomaly_detection_enabled = :enabled, 
                    anomaly_notification_enabled = :enabled,
                    updated_at = :updated_at
                WHERE company_id = :company_id
            """
            await DatabaseUtils.execute_query(monitoring_query, {
                'enabled': update_data.enable_monitoring,
                'updated_at': current_time,
                'company_id': company_id
            })
        
        # Get updated company data
        updated_company = await _get_company_details(company_id)
        
        logger.info(f"Updated company {company_id}: {', '.join(updates_made)}")
        return updated_company
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update company {company_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update company")

@admin_router.delete("/companies/{company_id}", status_code=204)
async def delete_company(company_id: str, confirm: bool = Query(False, description="Confirmation flag for deletion")):
    """
    Delete a company and all associated data including schema, 
    usage history, and configurations. Requires confirmation.
    """
    if not confirm:
        raise HTTPException(
            status_code=400, 
            detail="Company deletion requires confirmation. Set confirm=true query parameter."
        )
    
    try:
        # Get company details before deletion
        company_data = await _get_company_details(company_id)
        if not company_data:
            raise HTTPException(status_code=404, detail="Company not found")
        
        schema_name = company_data.schema_name
        
        # 1. Delete company-specific schema and all data
        await DatabaseUtils.execute_query(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE", {})
        
        # 2. Delete all company-related data (cascading deletes will handle most)
        # Cost calculations, alerts, reports, etc. will be deleted by foreign key constraints
        
        # 3. Delete monitoring configurations
        await DatabaseUtils.execute_query(
            "DELETE FROM monitoring_configs WHERE company_id = :company_id", 
            {'company_id': company_id}
        )
        
        # 4. Delete quota configurations
        await DatabaseUtils.execute_query(
            "DELETE FROM quota_configurations WHERE company_id = :company_id",
            {'company_id': company_id}
        )
        
        # 5. Delete rate limit configurations
        await DatabaseUtils.execute_query(
            "DELETE FROM rate_limit_configs WHERE company_id = :company_id",
            {'company_id': company_id}
        )
        
        # 6. Delete API keys
        await DatabaseUtils.execute_query(
            "DELETE FROM api_keys WHERE company_id = :company_id",
            {'company_id': company_id}
        )
        
        # 7. Finally delete the company record
        await DatabaseUtils.execute_query(
            "DELETE FROM companies WHERE id = :company_id",
            {'company_id': company_id}
        )
        
        # Clear any cached data for this company
        from ..services.cache import invalidate_company_cache
        await invalidate_company_cache(company_id)
        
        logger.warning(f"Deleted company {company_id} ({company_data.name}) and all associated data")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete company {company_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete company")

# ============================================================================
# SYSTEM HEALTH AND MONITORING ENDPOINTS
# ============================================================================

@admin_router.get("/system/health", response_model=SystemHealthResponse)
async def get_system_health():
    """
    Get comprehensive system health metrics including Redis, database,
    performance statistics, and active alerts.
    """
    try:
        current_time = datetime.now(timezone.utc)
        
        # Get system performance metrics
        performance_metrics = await monitor_rate_limit_performance()
        
        # Get cache statistics
        cache_stats = await get_cache_stats()
        
        # Get active alerts count
        alerts_query = """
            SELECT COUNT(*) as active_alerts,
                   COUNT(CASE WHEN severity = 'critical' THEN 1 END) as critical_alerts,
                   COUNT(CASE WHEN severity = 'emergency' THEN 1 END) as emergency_alerts
            FROM system_alerts 
            WHERE is_resolved = false 
                AND created_at >= :since_time
        """
        
        alerts_result = await DatabaseUtils.execute_query(
            alerts_query, 
            {'since_time': current_time - timedelta(hours=24)}, 
            fetch_one=True
        )
        
        # Get critical issues
        critical_issues = await _get_critical_issues()
        
        # Calculate overall system status
        redis_healthy = performance_metrics.get('redis_status') == 'healthy'
        db_healthy = performance_metrics.get('database_status') == 'healthy'
        cache_healthy = cache_stats.get('app_stats', {}).get('hit_rate', 0) > 70
        
        if redis_healthy and db_healthy and cache_healthy and not critical_issues:
            overall_status = "healthy"
        elif not redis_healthy or not db_healthy or critical_issues:
            overall_status = "critical"
        else:
            overall_status = "degraded"
        
        # Calculate uptime (simplified - would be actual uptime in production)
        uptime_seconds = cache_stats.get('app_stats', {}).get('uptime_seconds', 0)
        
        return SystemHealthResponse(
            status=overall_status,
            timestamp=current_time,
            uptime_seconds=uptime_seconds,
            
            # System components
            redis_status=performance_metrics.get('redis_status', 'unknown'),
            database_status=performance_metrics.get('database_status', 'unknown'),
            cache_hit_rate=cache_stats.get('app_stats', {}).get('hit_rate', 0),
            
            # Performance metrics
            avg_response_time_ms=performance_metrics.get('avg_rate_limit_check_time_ms', 0),
            requests_per_second=performance_metrics.get('requests_processed_per_second', 0),
            error_rate_percentage=0,  # Would calculate from recent errors
            
            # Resource utilization
            memory_usage=performance_metrics.get('redis_memory_usage', {}),
            connection_pools=performance_metrics.get('database_connection_pool', {}),
            
            # Alerts and issues
            active_alerts=alerts_result.get('active_alerts', 0),
            critical_issues=critical_issues
        )
        
    except Exception as e:
        logger.error(f"Failed to get system health: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system health")

@admin_router.get("/analytics/system")
async def get_system_analytics(
    period: str = Query("24h", pattern=r"^(1h|6h|24h|7d|30d)$", description="Analytics period"),
    include_companies: bool = Query(True, description="Include per-company breakdown")
):
    """
    Get system-wide analytics including usage statistics, cost data,
    performance metrics, and company breakdowns.
    """
    try:
        current_time = datetime.now(timezone.utc)
        
        # Calculate time range based on period
        period_hours = {
            "1h": 1, "6h": 6, "24h": 24, "7d": 168, "30d": 720
        }
        hours = period_hours.get(period, 24)
        start_time = current_time - timedelta(hours=hours)
        
        # Get system-wide usage statistics
        usage_query = """
            SELECT 
                COUNT(*) as total_requests,
                COUNT(DISTINCT company_id) as active_companies,
                SUM(total_cost) as total_cost,
                AVG(total_cost) as avg_cost_per_request,
                AVG(EXTRACT(EPOCH FROM (response_received_at - request_sent_at)) * 1000) as avg_response_time,
                COUNT(CASE WHEN status_code >= 400 THEN 1 END) as error_count,
                COUNT(DISTINCT vendor) as vendors_used,
                COUNT(DISTINCT model) as models_used
            FROM cost_calculations 
            WHERE calculation_timestamp >= :start_time
        """
        
        usage_stats = await DatabaseUtils.execute_query(
            usage_query, 
            {'start_time': start_time}, 
            fetch_one=True
        )
        
        # Get hourly breakdown
        hourly_query = """
            SELECT 
                DATE_TRUNC('hour', calculation_timestamp) as hour,
                COUNT(*) as requests,
                SUM(total_cost) as cost,
                AVG(EXTRACT(EPOCH FROM (response_received_at - request_sent_at)) * 1000) as avg_response_time
            FROM cost_calculations 
            WHERE calculation_timestamp >= :start_time
            GROUP BY DATE_TRUNC('hour', calculation_timestamp)
            ORDER BY hour
        """
        
        hourly_data = await DatabaseUtils.execute_query(
            hourly_query, 
            {'start_time': start_time}, 
            fetch_all=True
        )
        
        # Get vendor breakdown
        vendor_query = """
            SELECT 
                vendor,
                COUNT(*) as requests,
                SUM(total_cost) as cost,
                COUNT(DISTINCT company_id) as companies
            FROM cost_calculations 
            WHERE calculation_timestamp >= :start_time
            GROUP BY vendor
            ORDER BY requests DESC
        """
        
        vendor_data = await DatabaseUtils.execute_query(
            vendor_query, 
            {'start_time': start_time}, 
            fetch_all=True
        )
        
        analytics_response = {
            'period': period,
            'start_time': start_time.isoformat(),
            'end_time': current_time.isoformat(),
            'summary': {
                'total_requests': usage_stats.get('total_requests', 0),
                'active_companies': usage_stats.get('active_companies', 0),
                'total_cost': float(usage_stats.get('total_cost', 0)),
                'avg_cost_per_request': float(usage_stats.get('avg_cost_per_request', 0)),
                'avg_response_time_ms': usage_stats.get('avg_response_time', 0),
                'error_count': usage_stats.get('error_count', 0),
                'error_rate_pct': (usage_stats.get('error_count', 0) / max(usage_stats.get('total_requests', 1), 1)) * 100,
                'vendors_used': usage_stats.get('vendors_used', 0),
                'models_used': usage_stats.get('models_used', 0)
            },
            'hourly_breakdown': [
                {
                    'hour': row['hour'].isoformat(),
                    'requests': row['requests'],
                    'cost': float(row['cost']),
                    'avg_response_time': row['avg_response_time'] or 0
                }
                for row in hourly_data
            ],
            'vendor_breakdown': [
                {
                    'vendor': row['vendor'],
                    'requests': row['requests'],
                    'cost': float(row['cost']),
                    'companies': row['companies'],
                    'avg_cost_per_request': float(row['cost']) / row['requests'] if row['requests'] > 0 else 0
                }
                for row in vendor_data
            ]
        }
        
        # Include company breakdown if requested
        if include_companies:
            company_query = """
                SELECT 
                    c.id,
                    c.name,
                    c.tier,
                    COUNT(cc.id) as requests,
                    SUM(cc.total_cost) as cost,
                    MAX(cc.calculation_timestamp) as last_request
                FROM companies c
                LEFT JOIN cost_calculations cc ON c.id = cc.company_id 
                    AND cc.calculation_timestamp >= :start_time
                WHERE c.is_active = true
                GROUP BY c.id, c.name, c.tier
                ORDER BY requests DESC NULLS LAST
                LIMIT 50
            """
            
            company_data = await DatabaseUtils.execute_query(
                company_query, 
                {'start_time': start_time}, 
                fetch_all=True
            )
            
            analytics_response['company_breakdown'] = [
                {
                    'company_id': row['id'],
                    'company_name': row['name'],
                    'tier': row['tier'],
                    'requests': row['requests'] or 0,
                    'cost': float(row['cost'] or 0),
                    'last_request': row['last_request'].isoformat() if row['last_request'] else None
                }
                for row in company_data
            ]
        
        return analytics_response
        
    except Exception as e:
        logger.error(f"Failed to get system analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system analytics")

# ============================================================================
# VENDOR PRICING MANAGEMENT ENDPOINTS
# ============================================================================

@admin_router.post("/pricing/update", status_code=200)
async def update_vendor_pricing(pricing_data: VendorPricingUpdateRequest):
    """
    Update vendor pricing configuration with validation and audit trail.
    Supports bulk updates and effective date management.
    """
    try:
        current_time = datetime.now(timezone.utc)
        pricing_id = str(uuid.uuid4())
        
        # Validate vendor and model
        if not pricing_data.vendor or not pricing_data.model:
            raise HTTPException(status_code=400, detail="Vendor and model are required")
        
        # Check if pricing already exists for this vendor/model
        existing_query = """
            SELECT id, input_price, output_price 
            FROM global_vendor_pricing 
            WHERE vendor = :vendor AND model = :model AND is_active = true
        """
        
        existing_pricing = await DatabaseUtils.execute_query(
            existing_query,
            {'vendor': pricing_data.vendor.lower(), 'model': pricing_data.model},
            fetch_one=True
        )
        
        if existing_pricing:
            # Deactivate existing pricing
            await DatabaseUtils.execute_query(
                "UPDATE global_vendor_pricing SET is_active = false, updated_at = :updated_at WHERE id = :id",
                {'id': existing_pricing['id'], 'updated_at': current_time}
            )
            
            # Log pricing change for audit
            logger.info(f"Updated pricing for {pricing_data.vendor}/{pricing_data.model}: "
                      f"${existing_pricing['input_price']} -> ${pricing_data.input_price} (input), "
                      f"${existing_pricing['output_price']} -> ${pricing_data.output_price} (output)")
        
        # Insert new pricing record
        pricing_query = """
            INSERT INTO global_vendor_pricing (
                id, vendor, model, pricing_model, input_price,
                output_price, currency, effective_date, is_active,
                batch_discount, volume_tiers, metadata, created_at, updated_at
            ) VALUES (
                :id, :vendor, :model, :pricing_model, :input_price,
                :output_price, :currency, :effective_date, :is_active,
                :batch_discount, :volume_tiers, :metadata, :created_at, :updated_at
            )
        """
        
        # Prepare metadata with additional pricing info
        pricing_metadata = {
            'minimum_charge': float(pricing_data.minimum_charge) if pricing_data.minimum_charge else None,
            'bulk_discount_threshold': pricing_data.bulk_discount_threshold,
            'bulk_discount_rate': float(pricing_data.bulk_discount_rate) if pricing_data.bulk_discount_rate else None,
            'pricing_tier': pricing_data.pricing_tier
        }
        
        await DatabaseUtils.execute_query(pricing_query, {
            'id': pricing_id,
            'vendor': pricing_data.vendor.lower(),
            'model': pricing_data.model,
            'pricing_model': pricing_data.pricing_model.replace('_based', ''),  # Convert to schema format
            'input_price': pricing_data.input_price,
            'output_price': pricing_data.output_price,
            'currency': pricing_data.currency,
            'effective_date': pricing_data.effective_date,
            'is_active': pricing_data.is_active,
            'batch_discount': pricing_data.bulk_discount_rate,
            'volume_tiers': None,  # Can be enhanced later
            'metadata': json.dumps(pricing_metadata),
            'created_at': current_time,
            'updated_at': current_time
        })
        
        # Clear pricing cache to ensure immediate effect
        from ..services.cache import invalidate_company_cache
        # Would typically clear pricing cache for all companies
        
        return {
            'message': 'Vendor pricing updated successfully',
            'pricing_id': pricing_id,
            'vendor': pricing_data.vendor,
            'model': pricing_data.model,
            'effective_date': pricing_data.effective_date.isoformat(),
            'previous_pricing_existed': existing_pricing is not None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update vendor pricing: {e}")
        raise HTTPException(status_code=500, detail="Failed to update vendor pricing")

@admin_router.get("/pricing/vendors")
async def get_vendor_pricing(
    vendor: Optional[str] = Query(None, description="Filter by vendor"),
    active_only: bool = Query(True, description="Return only active pricing")
):
    """
    Get current vendor pricing configuration with filtering options.
    """
    try:
        query = """
            SELECT 
                vendor, model, pricing_model, input_price,
                output_price, currency, effective_date,
                is_active, batch_discount, volume_tiers, metadata,
                created_at, updated_at
            FROM global_vendor_pricing
            WHERE 1=1
        """
        
        params = {}
        
        if vendor:
            query += " AND vendor = :vendor"
            params['vendor'] = vendor.lower()
        
        if active_only:
            query += " AND is_active = true"
        
        query += " ORDER BY vendor, model, effective_date DESC"
        
        pricing_data = await DatabaseUtils.execute_query(query, params, fetch_all=True)
        
        return {
            'pricing_count': len(pricing_data),
            'pricing_data': [
                {
                    'vendor': row['vendor'],
                    'model': row['model'],
                    'pricing_model': row['pricing_model'],
                    'input_price': float(row['input_price']),
                    'output_price': float(row['output_price']),
                    'currency': row['currency'],
                    'effective_date': row['effective_date'].isoformat(),
                    'is_active': row['is_active'],
                    'batch_discount': float(row['batch_discount']) if row['batch_discount'] else None,
                    'volume_tiers': row['volume_tiers'],
                    'metadata': row['metadata'],
                    'created_at': row['created_at'].isoformat(),
                    'updated_at': row['updated_at'].isoformat()
                }
                for row in pricing_data
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get vendor pricing: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve vendor pricing")

# ============================================================================
# SYSTEM CONFIGURATION ENDPOINTS
# ============================================================================

@admin_router.post("/config/update", status_code=200)
async def update_system_config(config_data: SystemConfigUpdateRequest):
    """
    Update system-wide configuration with validation and audit trail.
    """
    try:
        current_time = datetime.now(timezone.utc)
        
        # Validate configuration key
        if not config_data.config_key:
            raise HTTPException(status_code=400, detail="Configuration key is required")
        
        # Check if configuration exists
        existing_query = """
            SELECT id, value FROM system_config WHERE key = :config_key
        """
        
        existing_config = await DatabaseUtils.execute_query(
            existing_query,
            {'config_key': config_data.config_key},
            fetch_one=True
        )
        
        # Prepare configuration value as JSON
        config_value_json = json.dumps(config_data.config_value)
        
        if existing_config:
            # Update existing configuration
            update_query = """
                UPDATE system_config 
                SET value = :value, description = :description, updated_at = :updated_at
                WHERE key = :config_key
            """
            
            await DatabaseUtils.execute_query(update_query, {
                'config_key': config_data.config_key,
                'value': config_value_json,
                'description': config_data.description,
                'updated_at': current_time
            })
            
            logger.info(f"Updated system configuration: {config_data.config_key}")
        else:
            # Insert new configuration
            insert_query = """
                INSERT INTO system_config (key, value, description, created_at, updated_at)
                VALUES (:config_key, :value, :description, :created_at, :updated_at)
            """
            
            await DatabaseUtils.execute_query(insert_query, {
                'config_key': config_data.config_key,
                'value': config_value_json,
                'description': config_data.description,
                'created_at': current_time,
                'updated_at': current_time
            })
            
            logger.info(f"Created new system configuration: {config_data.config_key}")
        
        # Mask sensitive values in response
        display_value = "[REDACTED]" if config_data.is_sensitive else config_data.config_value
        
        return {
            'message': 'System configuration updated successfully',
            'config_key': config_data.config_key,
            'config_value': display_value,
            'updated_at': current_time.isoformat(),
            'is_sensitive': config_data.is_sensitive,
            'existed_before': existing_config is not None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update system config: {e}")
        raise HTTPException(status_code=500, detail="Failed to update system configuration")

@admin_router.get("/config")
async def get_system_config(
    config_key: Optional[str] = Query(None, description="Specific configuration key to retrieve"),
    include_sensitive: bool = Query(False, description="Include sensitive configuration values")
):
    """
    Get system configuration with optional filtering and sensitivity control.
    """
    try:
        if config_key:
            # Get specific configuration
            query = "SELECT * FROM system_config WHERE key = :config_key"
            config_data = await DatabaseUtils.execute_query(
                query, 
                {'config_key': config_key}, 
                fetch_one=True
            )
            
            if not config_data:
                raise HTTPException(status_code=404, detail="Configuration key not found")
            
            # Parse JSON value
            try:
                parsed_value = json.loads(config_data['value'])
            except json.JSONDecodeError:
                parsed_value = config_data['value']
            
            return {
                'config_key': config_data['key'],
                'config_value': parsed_value,
                'description': config_data['description'],
                'created_at': config_data['created_at'].isoformat(),
                'updated_at': config_data['updated_at'].isoformat()
            }
        else:
            # Get all configurations
            query = "SELECT * FROM system_config ORDER BY key"
            all_configs = await DatabaseUtils.execute_query(query, {}, fetch_all=True)
            
            configs_list = []
            for config in all_configs:
                try:
                    parsed_value = json.loads(config['value'])
                except json.JSONDecodeError:
                    parsed_value = config['value']
                
                # Mask sensitive values if needed
                if not include_sensitive and _is_sensitive_config(config['key']):
                    parsed_value = "[REDACTED]"
                
                configs_list.append({
                    'config_key': config['key'],
                    'config_value': parsed_value,
                    'description': config['description'],
                    'created_at': config['created_at'].isoformat(),
                    'updated_at': config['updated_at'].isoformat(),
                    'is_sensitive': _is_sensitive_config(config['key'])
                })
            
            return {
                'total_configs': len(configs_list),
                'configurations': configs_list
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get system config: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system configuration")

@admin_router.delete("/config/{config_key}", status_code=204)
async def delete_system_config(config_key: str):
    """
    Delete a system configuration key.
    """
    try:
        # Check if configuration exists
        existing_query = "SELECT id FROM system_config WHERE key = :config_key"
        existing_config = await DatabaseUtils.execute_query(
            existing_query,
            {'config_key': config_key},
            fetch_one=True
        )
        
        if not existing_config:
            raise HTTPException(status_code=404, detail="Configuration key not found")
        
        # Delete configuration
        delete_query = "DELETE FROM system_config WHERE key = :config_key"
        await DatabaseUtils.execute_query(delete_query, {'config_key': config_key})
        
        logger.info(f"Deleted system configuration: {config_key}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete system config: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete system configuration")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def _provision_company_schema(schema_name: str):
    """Provision company-specific database schema with required tables"""
    try:
        # Create vendor keys table in company schema
        vendor_keys_table = f"""
            CREATE TABLE {schema_name}.vendor_keys (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                vendor VARCHAR(50) NOT NULL,
                encrypted_key TEXT NOT NULL,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """
        await DatabaseUtils.execute_query(vendor_keys_table, {})
        
        # Create company-specific usage tracking table
        usage_tracking_table = f"""
            CREATE TABLE {schema_name}.usage_tracking (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                endpoint VARCHAR(255) NOT NULL,
                request_count INTEGER DEFAULT 0,
                total_cost DECIMAL(20,8) DEFAULT 0,
                last_request_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """
        await DatabaseUtils.execute_query(usage_tracking_table, {})
        
        logger.debug(f"Provisioned schema {schema_name} with required tables")
        
    except Exception as e:
        logger.error(f"Failed to provision company schema {schema_name}: {e}")
        raise

async def _get_company_details(company_id: str) -> Optional[CompanyResponse]:
    """Get comprehensive company details including usage statistics"""
    try:
        # Main company query with joins for current usage
        query = """
            SELECT 
                c.*,
                rlc.requests_per_minute, rlc.requests_per_hour, rlc.requests_per_day,
                qc.monthly_request_limit, qc.monthly_cost_limit,
                
                -- Current month usage
                COALESCE(usage.current_month_requests, 0) as current_month_requests,
                COALESCE(usage.current_month_cost, 0) as current_month_cost,
                COALESCE(usage.total_requests, 0) as total_requests,
                COALESCE(usage.total_cost, 0) as total_cost,
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
            return None
        
        # Parse custom settings
        custom_settings = {}
        if result.get('custom_settings'):
            try:
                custom_settings = json.loads(result['custom_settings'])
            except json.JSONDecodeError:
                custom_settings = {}
        
        return CompanyResponse(
            id=result['id'],
            name=result['name'],
            email=result['email'],
            tier=result['tier'],
            schema_name=result['schema_name'],
            is_active=result['is_active'],
            created_at=result['created_at'],
            updated_at=result['updated_at'],
            
            # Usage statistics
            total_requests=result['total_requests'],
            total_cost=Decimal(str(result['total_cost'])),
            last_request_at=result['last_request_at'],
            
            # Current quotas and limits
            monthly_request_limit=result['monthly_request_limit'] or 0,
            monthly_cost_limit=Decimal(str(result['monthly_cost_limit'] or 0)),
            current_month_requests=result['current_month_requests'],
            current_month_cost=Decimal(str(result['current_month_cost'])),
            
            # Settings
            enable_analytics=result['enable_analytics'],
            enable_monitoring=result['enable_monitoring'],
            custom_settings=custom_settings
        )
        
    except Exception as e:
        logger.error(f"Failed to get company details for {company_id}: {e}")
        return None

async def _get_critical_issues() -> List[str]:
    """Get list of current critical system issues"""
    try:
        issues = []
        
        # Check for critical system alerts
        alerts_query = """
            SELECT message, created_at
            FROM system_alerts 
            WHERE severity IN ('critical', 'emergency') 
                AND is_resolved = false
                AND created_at >= :since_time
            ORDER BY created_at DESC
            LIMIT 5
        """
        
        current_time = datetime.now(timezone.utc)
        alerts = await DatabaseUtils.execute_query(
            alerts_query,
            {'since_time': current_time - timedelta(hours=24)},
            fetch_all=True
        )
        
        for alert in alerts:
            issues.append(f"{alert['message']} (since {alert['created_at'].strftime('%H:%M')})")
        
        return issues
        
    except Exception as e:
        logger.error(f"Failed to get critical issues: {e}")
        return ["Failed to retrieve critical issues"]

def _is_sensitive_config(config_key: str) -> bool:
    """Determine if a configuration key contains sensitive information"""
    sensitive_patterns = [
        'key', 'secret', 'password', 'token', 'auth', 'credential',
        'api_key', 'private', 'cert', 'certificate', 'encryption'
    ]
    
    config_key_lower = config_key.lower()
    return any(pattern in config_key_lower for pattern in sensitive_patterns)