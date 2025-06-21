-- Company Schema Provisioning Function
CREATE OR REPLACE FUNCTION create_company_schema(company_id TEXT)
RETURNS VOID AS $$
DECLARE
    schema_name TEXT;
BEGIN
    -- Generate schema name
    schema_name := 'company_' || company_id;
    
    -- Create schema
    EXECUTE 'CREATE SCHEMA IF NOT EXISTS ' || quote_ident(schema_name);
    
    -- Create API Logs table
    EXECUTE '
    CREATE TABLE IF NOT EXISTS ' || quote_ident(schema_name) || '.api_logs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        api_key_id UUID NOT NULL,
        vendor VARCHAR(50) NOT NULL,
        model VARCHAR(100) NOT NULL,
        request_data JSONB NOT NULL,
        response_data JSONB NOT NULL,
        tokens_used INTEGER NOT NULL,
        cost DECIMAL(10, 6) NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )';
    
    -- Create Vendor Keys table
    EXECUTE '
    CREATE TABLE IF NOT EXISTS ' || quote_ident(schema_name) || '.vendor_keys (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        vendor VARCHAR(50) NOT NULL,
        encrypted_key TEXT NOT NULL,
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        CONSTRAINT unique_vendor_key UNIQUE (vendor, is_active)
    )';
    
    -- Create Usage Metrics table
    EXECUTE '
    CREATE TABLE IF NOT EXISTS ' || quote_ident(schema_name) || '.usage_metrics (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        date DATE NOT NULL,
        vendor VARCHAR(50) NOT NULL,
        model VARCHAR(100) NOT NULL,
        total_requests INTEGER NOT NULL DEFAULT 0,
        total_tokens INTEGER NOT NULL DEFAULT 0,
        total_cost DECIMAL(10, 6) NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        CONSTRAINT unique_metrics_per_day UNIQUE (date, vendor, model)
    )';
    
    -- Create Billing Data table
    EXECUTE '
    CREATE TABLE IF NOT EXISTS ' || quote_ident(schema_name) || '.billing_data (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        period_start DATE NOT NULL,
        period_end DATE NOT NULL,
        total_requests INTEGER NOT NULL DEFAULT 0,
        total_tokens INTEGER NOT NULL DEFAULT 0,
        total_cost DECIMAL(10, 6) NOT NULL DEFAULT 0,
        status VARCHAR(20) NOT NULL DEFAULT ''pending'',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        CONSTRAINT unique_billing_period UNIQUE (period_start, period_end)
    )';
    
    -- Create indexes for performance
    EXECUTE 'CREATE INDEX IF NOT EXISTS idx_' || schema_name || '_api_logs_api_key_id ON ' || 
            quote_ident(schema_name) || '.api_logs(api_key_id)';
    EXECUTE 'CREATE INDEX IF NOT EXISTS idx_' || schema_name || '_api_logs_created_at ON ' || 
            quote_ident(schema_name) || '.api_logs(created_at)';
    EXECUTE 'CREATE INDEX IF NOT EXISTS idx_' || schema_name || '_vendor_keys_vendor ON ' || 
            quote_ident(schema_name) || '.vendor_keys(vendor)';
    EXECUTE 'CREATE INDEX IF NOT EXISTS idx_' || schema_name || '_usage_metrics_date ON ' || 
            quote_ident(schema_name) || '.usage_metrics(date)';
    EXECUTE 'CREATE INDEX IF NOT EXISTS idx_' || schema_name || '_billing_data_period ON ' || 
            quote_ident(schema_name) || '.billing_data(period_start, period_end)';
    
    -- Add updated_at triggers
    EXECUTE '
    CREATE TRIGGER update_vendor_keys_updated_at
        BEFORE UPDATE ON ' || quote_ident(schema_name) || '.vendor_keys
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column()';
    
    EXECUTE '
    CREATE TRIGGER update_usage_metrics_updated_at
        BEFORE UPDATE ON ' || quote_ident(schema_name) || '.usage_metrics
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column()';
    
    EXECUTE '
    CREATE TRIGGER update_billing_data_updated_at
        BEFORE UPDATE ON ' || quote_ident(schema_name) || '.billing_data
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column()';
END;
$$ LANGUAGE plpgsql;

-- Function to drop company schema
CREATE OR REPLACE FUNCTION drop_company_schema(company_id TEXT)
RETURNS VOID AS $$
DECLARE
    schema_name TEXT;
BEGIN
    schema_name := 'company_' || company_id;
    EXECUTE 'DROP SCHEMA IF EXISTS ' || quote_ident(schema_name) || ' CASCADE';
END;
$$ LANGUAGE plpgsql; 