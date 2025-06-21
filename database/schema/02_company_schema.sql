-- Drop and recreate the function to ensure clean state
DROP FUNCTION IF EXISTS create_company_schema(TEXT);

CREATE OR REPLACE FUNCTION create_company_schema(company_id TEXT)
RETURNS void AS $$
DECLARE
    company_slug TEXT;
    schema_name TEXT;
BEGIN
    -- Get company slug from companies table
    SELECT c.slug INTO company_slug
    FROM companies c
    WHERE c.id::text = company_id;
    
    IF company_slug IS NULL THEN
        RAISE EXCEPTION 'Company with ID % not found', company_id;
    END IF;
    
    -- Create schema name from slug (replace hyphens with underscores)
    schema_name := 'company_' || replace(company_slug, '-', '_');
    
    -- Create schema if it doesn't exist
    EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', schema_name);
    
    -- Create api_logs table
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.api_logs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        api_key_id UUID REFERENCES public.api_keys(id) ON DELETE SET NULL,
        endpoint VARCHAR(255) NOT NULL,
        method VARCHAR(10) NOT NULL,
        status_code INTEGER,
        response_time INTEGER,
        request_size INTEGER,
        response_size INTEGER,
        ip_address VARCHAR(45),
        user_agent TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    )', schema_name);
    
    -- Create vendor_keys table
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.vendor_keys (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        vendor_name VARCHAR(255) NOT NULL,
        key_name VARCHAR(255) NOT NULL,
        key_value TEXT NOT NULL,
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(vendor_name, key_name)
    )', schema_name);
    
    -- Create usage_metrics table
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.usage_metrics (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        vendor_name VARCHAR(255) NOT NULL,
        service_name VARCHAR(255) NOT NULL,
        metric_name VARCHAR(255) NOT NULL,
        metric_value DECIMAL(20,4) NOT NULL,
        timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        metadata JSONB DEFAULT %L::jsonb
    )', schema_name, '{}');
    
    -- Create billing_data table
    EXECUTE format('
    CREATE TABLE IF NOT EXISTS %I.billing_data (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        vendor_name VARCHAR(255) NOT NULL,
        service_name VARCHAR(255) NOT NULL,
        amount DECIMAL(10,4) NOT NULL,
        currency VARCHAR(3) DEFAULT %L,
        billing_period_start TIMESTAMP WITH TIME ZONE NOT NULL,
        billing_period_end TIMESTAMP WITH TIME ZONE NOT NULL,
        status VARCHAR(50) DEFAULT %L CHECK (status IN (%L, %L, %L)),
        metadata JSONB DEFAULT %L::jsonb,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    )', schema_name, 'USD', 'pending', 'pending', 'processed', 'failed', '{}');
    
    -- Create indexes
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_api_logs_created_at ON %I.api_logs(created_at)', schema_name, schema_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_api_logs_api_key_id ON %I.api_logs(api_key_id)', schema_name, schema_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_vendor_keys_vendor ON %I.vendor_keys(vendor_name)', schema_name, schema_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_usage_metrics_timestamp ON %I.usage_metrics(timestamp)', schema_name, schema_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_usage_metrics_vendor_service ON %I.usage_metrics(vendor_name, service_name)', schema_name, schema_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_billing_data_period ON %I.billing_data(billing_period_start, billing_period_end)', schema_name, schema_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_billing_data_vendor_service ON %I.billing_data(vendor_name, service_name)', schema_name, schema_name);
    
    -- Enable RLS
    EXECUTE format('ALTER TABLE %I.api_logs ENABLE ROW LEVEL SECURITY', schema_name);
    EXECUTE format('ALTER TABLE %I.vendor_keys ENABLE ROW LEVEL SECURITY', schema_name);
    EXECUTE format('ALTER TABLE %I.usage_metrics ENABLE ROW LEVEL SECURITY', schema_name);
    EXECUTE format('ALTER TABLE %I.billing_data ENABLE ROW LEVEL SECURITY', schema_name);
    
    -- Drop and recreate policies
    EXECUTE format('DROP POLICY IF EXISTS company_isolation ON %I.api_logs', schema_name);
    EXECUTE format('CREATE POLICY company_isolation ON %I.api_logs FOR ALL USING (true)', schema_name);
    
    EXECUTE format('DROP POLICY IF EXISTS company_isolation ON %I.vendor_keys', schema_name);
    EXECUTE format('CREATE POLICY company_isolation ON %I.vendor_keys FOR ALL USING (true)', schema_name);
    
    EXECUTE format('DROP POLICY IF EXISTS company_isolation ON %I.usage_metrics', schema_name);
    EXECUTE format('CREATE POLICY company_isolation ON %I.usage_metrics FOR ALL USING (true)', schema_name);
    
    EXECUTE format('DROP POLICY IF EXISTS company_isolation ON %I.billing_data', schema_name);
    EXECUTE format('CREATE POLICY company_isolation ON %I.billing_data FOR ALL USING (true)', schema_name);
    
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;