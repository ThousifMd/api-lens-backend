import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
import re

from sqlalchemy import text
from ..database import DatabaseUtils
from ..config import get_settings
from ..utils.logger import get_logger
from models.company import Company, CompanyCreate, CompanyUpdate, CompanySettings

settings = get_settings()
logger = get_logger(__name__)

class DuplicateCompanyError(Exception):
    """Raised when attempting to create a company with a duplicate name"""
    pass

def _generate_schema_name(company_name: str) -> str:
    """Generate a valid schema name from company name"""
    # Convert to lowercase and replace spaces with underscores
    schema_name = company_name.lower().replace(' ', '_')
    # Remove any non-alphanumeric characters except underscores
    schema_name = re.sub(r'[^a-z0-9_]', '', schema_name)
    # Ensure it starts with a letter
    if not schema_name[0].isalpha():
        schema_name = 'c_' + schema_name
    # Add timestamp to ensure uniqueness
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    return f"{schema_name}_{timestamp}"

async def _create_company_schema(schema_name: str) -> None:
    """Create a new schema for a company"""
    try:
        # Create schema
        await DatabaseUtils.execute_query(
            f"CREATE SCHEMA IF NOT EXISTS {schema_name}",
            {},
            fetch_all=False
        )
        
        # Create necessary tables in the schema
        tables = [
            """
            CREATE TABLE IF NOT EXISTS {schema}.api_keys (
                id UUID PRIMARY KEY,
                company_id UUID NOT NULL,
                key_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP WITH TIME ZONE,
                UNIQUE(key_hash)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS {schema}.vendor_keys (
                id UUID PRIMARY KEY,
                vendor TEXT NOT NULL,
                encrypted_key TEXT NOT NULL,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(vendor)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS {schema}.usage_stats (
                id UUID PRIMARY KEY,
                endpoint TEXT NOT NULL,
                calls_count INTEGER DEFAULT 0,
                last_called_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]
        
        for table_sql in tables:
            await DatabaseUtils.execute_query(
                table_sql.format(schema=schema_name),
                {},
                fetch_all=False
            )
            
        logger.info(f"Created schema and tables for company: {schema_name}")
        
    except Exception as e:
        logger.error(f"Error creating company schema: {e}")
        raise

async def _drop_company_schema(schema_name: str) -> None:
    """Drop a company's schema and all its data"""
    try:
        await DatabaseUtils.execute_query(
            f"DROP SCHEMA IF EXISTS {schema_name} CASCADE",
            {},
            fetch_all=False
        )
        logger.info(f"Dropped schema for company: {schema_name}")
    except Exception as e:
        logger.error(f"Error dropping company schema: {e}")
        raise

async def create_company(company_data: CompanyCreate) -> Company:
    """Create a new company with schema provisioning"""
    try:
        # Check for duplicate company name
        existing_query = "SELECT id FROM companies WHERE name = $1"
        existing = await DatabaseUtils.execute_query(
            existing_query,
            {'name': company_data.name},
            fetch_all=False
        )
        
        if existing:
            raise DuplicateCompanyError(f"Company with name '{company_data.name}' already exists")
        
        # Generate schema name
        schema_name = _generate_schema_name(company_data.name)
        
        # Create company record
        company_id = uuid4()
        settings_obj = company_data.settings or CompanySettings()
        
        query = """
            INSERT INTO companies (
                id, name, schema_name, description, contact_email,
                billing_email, billing_address, vat_number,
                rate_limit_rps, monthly_quota, max_api_keys,
                allowed_ips, webhook_url, webhook_secret,
                created_at, updated_at, is_active
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, true
            ) RETURNING *
        """
        
        result = await DatabaseUtils.execute_query(
            query,
            {
                'id': company_id,
                'name': company_data.name,
                'schema_name': schema_name,
                'description': company_data.description,
                'contact_email': company_data.contact_email,
                'billing_email': company_data.billing_email,
                'billing_address': company_data.billing_address,
                'vat_number': company_data.vat_number,
                'rate_limit_rps': settings_obj.rate_limit_rps,
                'monthly_quota': settings_obj.monthly_quota,
                'max_api_keys': settings_obj.max_api_keys,
                'allowed_ips': settings_obj.allowed_ips,
                'webhook_url': settings_obj.webhook_url,
                'webhook_secret': settings_obj.webhook_secret
            },
            fetch_all=False
        )
        
        # Provision company schema
        await _create_company_schema(schema_name)
        
        # Create Company object from result
        company = Company(
            id=result['id'],
            name=result['name'],
            schema_name=result['schema_name'],
            settings=CompanySettings(
                rate_limit_rps=result['rate_limit_rps'],
                monthly_quota=result['monthly_quota'],
                max_api_keys=result['max_api_keys'],
                allowed_ips=result['allowed_ips'],
                webhook_url=result['webhook_url'],
                webhook_secret=result['webhook_secret']
            ),
            created_at=result['created_at'],
            updated_at=result['updated_at'],
            is_active=result['is_active'],
            description=result['description'],
            contact_email=result['contact_email'],
            billing_email=result['billing_email'],
            billing_address=result['billing_address'],
            vat_number=result['vat_number']
        )
        
        logger.info(f"Created new company: {company.name} (ID: {company.id})")
        return company
        
    except Exception as e:
        logger.error(f"Error creating company: {e}")
        raise

async def get_company(company_id: str) -> Optional[Company]:
    """Get company details"""
    try:
        query = "SELECT * FROM companies WHERE id = $1"
        
        result = await DatabaseUtils.execute_query(
            query,
            {'id': UUID(company_id)},
            fetch_all=False
        )
        
        if not result:
            return None
            
        return Company(
            id=result['id'],
            name=result['name'],
            schema_name=result['schema_name'],
            settings=CompanySettings(
                rate_limit_rps=result['rate_limit_rps'],
                monthly_quota=result['monthly_quota'],
                max_api_keys=result['max_api_keys'],
                allowed_ips=result['allowed_ips'],
                webhook_url=result['webhook_url'],
                webhook_secret=result['webhook_secret']
            ),
            created_at=result['created_at'],
            updated_at=result['updated_at'],
            is_active=result['is_active'],
            description=result['description'],
            contact_email=result['contact_email'],
            billing_email=result['billing_email'],
            billing_address=result['billing_address'],
            vat_number=result['vat_number']
        )
        
    except Exception as e:
        logger.error(f"Error getting company: {e}")
        raise

async def update_company(company_id: str, updates: CompanyUpdate) -> Optional[Company]:
    """Update company details"""
    try:
        # Build update query dynamically based on provided fields
        update_fields = []
        params = {'id': UUID(company_id)}
        
        for field, value in updates.dict(exclude_unset=True).items():
            if field == 'settings' and value:
                for setting, setting_value in value.dict(exclude_unset=True).items():
                    update_fields.append(f"{setting} = ${len(params) + 1}")
                    params[setting] = setting_value
            else:
                update_fields.append(f"{field} = ${len(params) + 1}")
                params[field] = value
        
        if not update_fields:
            return await get_company(company_id)
        
        query = f"""
            UPDATE companies
            SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
            RETURNING *
        """
        
        result = await DatabaseUtils.execute_query(
            query,
            params,
            fetch_all=False
        )
        
        if not result:
            return None
            
        return Company(
            id=result['id'],
            name=result['name'],
            schema_name=result['schema_name'],
            settings=CompanySettings(
                rate_limit_rps=result['rate_limit_rps'],
                monthly_quota=result['monthly_quota'],
                max_api_keys=result['max_api_keys'],
                allowed_ips=result['allowed_ips'],
                webhook_url=result['webhook_url'],
                webhook_secret=result['webhook_secret']
            ),
            created_at=result['created_at'],
            updated_at=result['updated_at'],
            is_active=result['is_active'],
            description=result['description'],
            contact_email=result['contact_email'],
            billing_email=result['billing_email'],
            billing_address=result['billing_address'],
            vat_number=result['vat_number']
        )
        
    except Exception as e:
        logger.error(f"Error updating company: {e}")
        raise

async def delete_company(company_id: str) -> bool:
    """Delete a company and all its data"""
    try:
        # Get company details first
        company = await get_company(company_id)
        if not company:
            return False
        
        # Drop company schema first
        await _drop_company_schema(company.schema_name)
        
        # Delete company record
        query = "DELETE FROM companies WHERE id = $1"
        await DatabaseUtils.execute_query(
            query,
            {'id': UUID(company_id)},
            fetch_all=False
        )
        
        logger.info(f"Deleted company: {company.name} (ID: {company_id})")
        return True
        
    except Exception as e:
        logger.error(f"Error deleting company: {e}")
        raise

async def provision_company_schema(company_id: str) -> bool:
    """Create database schema for a company"""
    try:
        # Get company details to get schema name
        company = await get_company(company_id)
        if not company:
            logger.error(f"Company not found: {company_id}")
            return False
        
        # Create the schema and tables
        await _create_company_schema(company.schema_name)
        
        logger.info(f"Successfully provisioned schema for company: {company.name}")
        return True
        
    except Exception as e:
        logger.error(f"Error provisioning schema for company {company_id}: {e}")
        return False