-- Core system tables
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    schema_name VARCHAR(255) NOT NULL UNIQUE,
    rate_limit_rps INTEGER NOT NULL DEFAULT 100,
    monthly_quota INTEGER NOT NULL DEFAULT 1000000,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(company_id, name)
);

CREATE TABLE IF NOT EXISTS vendor_pricing (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    pricing_tier VARCHAR(50) NOT NULL,
    cost_per_unit DECIMAL(10, 6) NOT NULL,
    unit_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(vendor, model, pricing_tier)
);

CREATE TABLE IF NOT EXISTS system_config (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_company_id ON api_keys(company_id);
CREATE INDEX IF NOT EXISTS idx_vendor_pricing_vendor_model ON vendor_pricing(vendor, model);

-- Function to create company schema
CREATE OR REPLACE FUNCTION create_company_schema(company_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    schema_name TEXT;
BEGIN
    -- Get company schema name
    SELECT c.schema_name INTO schema_name
    FROM companies c
    WHERE c.id = company_id;
    
    IF schema_name IS NULL THEN
        RETURN FALSE;
    END IF;
    
    -- Create schema
    EXECUTE 'CREATE SCHEMA IF NOT EXISTS ' || quote_ident(schema_name);
    
    -- Create company-specific tables
    EXECUTE '
        CREATE TABLE IF NOT EXISTS ' || quote_ident(schema_name) || '.api_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            api_key_id UUID NOT NULL,
            vendor VARCHAR(50) NOT NULL,
            model VARCHAR(100) NOT NULL,
            request_data JSONB NOT NULL,
            response_data JSONB NOT NULL,
            tokens_used INTEGER,
            cost DECIMAL(10, 6),
            latency INTEGER,
            status_code INTEGER,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    ';
    
    EXECUTE '
        CREATE TABLE IF NOT EXISTS ' || quote_ident(schema_name) || '.vendor_keys (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            vendor VARCHAR(50) NOT NULL,
            encrypted_key TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(vendor)
        )
    ';
    
    EXECUTE '
        CREATE TABLE IF NOT EXISTS ' || quote_ident(schema_name) || '.usage_metrics (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            date DATE NOT NULL,
            vendor VARCHAR(50) NOT NULL,
            model VARCHAR(100) NOT NULL,
            request_count INTEGER NOT NULL DEFAULT 0,
            token_count INTEGER NOT NULL DEFAULT 0,
            total_cost DECIMAL(10, 6) NOT NULL DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, vendor, model)
        )
    ';
    
    EXECUTE '
        CREATE TABLE IF NOT EXISTS ' || quote_ident(schema_name) || '.billing_data (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            total_requests INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            total_cost DECIMAL(10, 6) NOT NULL DEFAULT 0,
            status VARCHAR(50) NOT NULL DEFAULT ''pending'',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(period_start, period_end)
        )
    ';
    
    -- Create indexes for company tables
    EXECUTE '
        CREATE INDEX IF NOT EXISTS idx_' || schema_name || '_api_logs_api_key_id 
        ON ' || quote_ident(schema_name) || '.api_logs(api_key_id)
    ';
    
    EXECUTE '
        CREATE INDEX IF NOT EXISTS idx_' || schema_name || '_api_logs_created_at 
        ON ' || quote_ident(schema_name) || '.api_logs(created_at)
    ';
    
    EXECUTE '
        CREATE INDEX IF NOT EXISTS idx_' || schema_name || '_usage_metrics_date 
        ON ' || quote_ident(schema_name) || '.usage_metrics(date)
    ';
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql; 