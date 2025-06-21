-- Migration: Cost Calculation and Rate Limiting System
-- Version: 001
-- Description: Adds all tables and structures needed for cost calculation, rate limiting, and analytics
-- Applied: Never (initial migration)

-- ============================================================================
-- MIGRATION SAFETY CHECKS
-- ============================================================================

-- Check if this migration has already been applied
DO $$
BEGIN
    -- Create migrations tracking table if it doesn't exist
    CREATE TABLE IF NOT EXISTS schema_migrations (
        id SERIAL PRIMARY KEY,
        version VARCHAR(50) UNIQUE NOT NULL,
        description TEXT,
        applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        rollback_sql TEXT
    );
    
    -- Check if this migration already exists
    IF EXISTS (SELECT 1 FROM schema_migrations WHERE version = '001_cost_and_rate_limiting') THEN
        RAISE NOTICE 'Migration 001_cost_and_rate_limiting already applied, skipping...';
        RETURN;
    END IF;
    
    RAISE NOTICE 'Applying migration 001_cost_and_rate_limiting...';
END
$$;

-- ============================================================================
-- BACKUP EXISTING DATA
-- ============================================================================

-- Create backup table for existing vendor_pricing data
CREATE TABLE IF NOT EXISTS vendor_pricing_backup_001 AS 
SELECT * FROM vendor_pricing WHERE 1=1;

-- ============================================================================
-- UPDATE EXISTING VENDOR_PRICING TABLE
-- ============================================================================

-- Step 1: Add new columns to existing vendor_pricing table
ALTER TABLE vendor_pricing 
ADD COLUMN IF NOT EXISTS model VARCHAR(255),
ADD COLUMN IF NOT EXISTS input_price DECIMAL(20,8),
ADD COLUMN IF NOT EXISTS output_price DECIMAL(20,8),
ADD COLUMN IF NOT EXISTS effective_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true,
ADD COLUMN IF NOT EXISTS batch_discount DECIMAL(5,2),
ADD COLUMN IF NOT EXISTS volume_tiers JSONB,
ADD COLUMN IF NOT EXISTS metadata_new JSONB DEFAULT '{}';

-- Step 2: Migrate existing data
UPDATE vendor_pricing SET 
    model = COALESCE(service_name, 'unknown'),
    input_price = COALESCE(base_price, 0.001),
    output_price = COALESCE(base_price * 1.5, 0.0015),
    is_active = true,
    metadata_new = COALESCE(config, '{}')
WHERE model IS NULL;

-- Step 3: Create new pricing_model_new column with updated enum
ALTER TABLE vendor_pricing 
ADD COLUMN IF NOT EXISTS pricing_model_new VARCHAR(50);

-- Map old pricing models to new ones
UPDATE vendor_pricing SET pricing_model_new = 
    CASE 
        WHEN pricing_model = 'per_request' THEN 'tokens'
        WHEN pricing_model = 'per_time' THEN 'characters'
        WHEN pricing_model = 'tiered' THEN 'requests'
        ELSE 'tokens'
    END
WHERE pricing_model_new IS NULL;

-- Step 4: Drop old constraints and columns
ALTER TABLE vendor_pricing 
DROP CONSTRAINT IF EXISTS vendor_pricing_pricing_model_check;

-- Step 5: Rename columns
ALTER TABLE vendor_pricing 
RENAME COLUMN vendor_name TO vendor;

-- Only rename service_name if model column wasn't already set
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'vendor_pricing' AND column_name = 'service_name') THEN
        EXECUTE 'ALTER TABLE vendor_pricing DROP COLUMN service_name';
    END IF;
END
$$;

-- Step 6: Replace old pricing_model and metadata columns
ALTER TABLE vendor_pricing 
DROP COLUMN IF EXISTS pricing_model,
DROP COLUMN IF EXISTS base_price,
DROP COLUMN IF EXISTS config;

ALTER TABLE vendor_pricing 
RENAME COLUMN pricing_model_new TO pricing_model;

ALTER TABLE vendor_pricing 
RENAME COLUMN metadata_new TO metadata;

-- Step 7: Add new constraints
ALTER TABLE vendor_pricing 
ADD CONSTRAINT vendor_pricing_pricing_model_check 
CHECK (pricing_model IN ('tokens', 'characters', 'requests', 'images', 'audio_seconds', 'video_seconds'));

-- Step 8: Update unique constraint
ALTER TABLE vendor_pricing 
DROP CONSTRAINT IF EXISTS vendor_pricing_company_id_vendor_name_service_name_key;

ALTER TABLE vendor_pricing 
ADD CONSTRAINT vendor_pricing_vendor_model_effective_date_key 
UNIQUE (company_id, vendor, model, effective_date);

-- ============================================================================
-- CREATE NEW TABLES
-- ============================================================================

-- Global vendor pricing table (system-wide pricing)
CREATE TABLE IF NOT EXISTS global_vendor_pricing (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor VARCHAR(255) NOT NULL,
    model VARCHAR(255) NOT NULL,
    pricing_model VARCHAR(50) NOT NULL CHECK (pricing_model IN ('tokens', 'characters', 'requests', 'images', 'audio_seconds', 'video_seconds')),
    input_price DECIMAL(20,8) NOT NULL,
    output_price DECIMAL(20,8) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    effective_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    batch_discount DECIMAL(5,2),
    volume_tiers JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(vendor, model, effective_date)
);

-- Cost calculations table
CREATE TABLE IF NOT EXISTS cost_calculations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    vendor VARCHAR(255) NOT NULL,
    model VARCHAR(255) NOT NULL,
    input_units INTEGER NOT NULL DEFAULT 0,
    output_units INTEGER NOT NULL DEFAULT 0,
    input_cost DECIMAL(20,8) NOT NULL DEFAULT 0,
    output_cost DECIMAL(20,8) NOT NULL DEFAULT 0,
    total_cost DECIMAL(20,8) NOT NULL DEFAULT 0,
    currency VARCHAR(3) DEFAULT 'USD',
    pricing_model VARCHAR(50) NOT NULL,
    calculation_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    accuracy_confidence DECIMAL(5,2) DEFAULT 95.0,
    request_id VARCHAR(255),
    api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Cost accuracy validations table
CREATE TABLE IF NOT EXISTS cost_accuracy_validations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor VARCHAR(255) NOT NULL,
    model VARCHAR(255) NOT NULL,
    calculated_cost DECIMAL(20,8) NOT NULL,
    actual_cost DECIMAL(20,8) NOT NULL,
    percentage_error DECIMAL(8,4) NOT NULL,
    accuracy_grade VARCHAR(5) NOT NULL,
    validation_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    validation_source VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Cost alerts table
CREATE TABLE IF NOT EXISTS cost_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_id VARCHAR(255) UNIQUE NOT NULL,
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    alert_type VARCHAR(100) NOT NULL,
    severity VARCHAR(50) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    message TEXT NOT NULL,
    threshold_value DECIMAL(20,8),
    actual_value DECIMAL(20,8),
    percentage_change DECIMAL(8,4),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_resolved BOOLEAN DEFAULT false,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Cost alerts log table
CREATE TABLE IF NOT EXISTS cost_alerts_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    alert_type VARCHAR(100) NOT NULL,
    alert_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Billing data table
CREATE TABLE IF NOT EXISTS billing_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    vendor VARCHAR(255) NOT NULL,
    model VARCHAR(255),
    total_cost DECIMAL(20,8) NOT NULL,
    total_requests INTEGER DEFAULT 0,
    total_tokens BIGINT DEFAULT 0,
    currency VARCHAR(3) DEFAULT 'USD',
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    billing_cycle VARCHAR(50) DEFAULT 'monthly',
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processed', 'failed', 'disputed')),
    vendor_invoice_id VARCHAR(255),
    imported_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Company quotas table
CREATE TABLE IF NOT EXISTS company_quotas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE UNIQUE,
    monthly_limit DECIMAL(20,8) NOT NULL,
    daily_limit DECIMAL(20,8),
    hourly_limit DECIMAL(20,8),
    warning_threshold DECIMAL(3,2) DEFAULT 0.80,
    critical_threshold DECIMAL(3,2) DEFAULT 0.95,
    is_active BOOLEAN DEFAULT true,
    auto_suspend BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Rate limit configurations table
CREATE TABLE IF NOT EXISTS rate_limit_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE UNIQUE,
    tier VARCHAR(50) NOT NULL DEFAULT 'basic' CHECK (tier IN ('free', 'basic', 'premium', 'enterprise', 'unlimited')),
    per_minute_limit INTEGER NOT NULL DEFAULT 50,
    per_hour_limit INTEGER NOT NULL DEFAULT 1000,
    per_day_limit INTEGER NOT NULL DEFAULT 10000,
    per_month_limit INTEGER,
    burst_limit INTEGER DEFAULT 100,
    burst_window_seconds INTEGER DEFAULT 60,
    is_bypassed BOOLEAN DEFAULT false,
    bypass_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Rate limit resets table
CREATE TABLE IF NOT EXISTS rate_limit_resets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    reset_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    reset_reason TEXT NOT NULL,
    reset_by VARCHAR(255) NOT NULL,
    affected_limits TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- CREATE INDEXES
-- ============================================================================

-- Cost calculations indexes
CREATE INDEX IF NOT EXISTS idx_cost_calculations_company_id ON cost_calculations(company_id);
CREATE INDEX IF NOT EXISTS idx_cost_calculations_timestamp ON cost_calculations(calculation_timestamp);
CREATE INDEX IF NOT EXISTS idx_cost_calculations_vendor_model ON cost_calculations(vendor, model);
CREATE INDEX IF NOT EXISTS idx_cost_calculations_company_timestamp ON cost_calculations(company_id, calculation_timestamp);
CREATE INDEX IF NOT EXISTS idx_cost_calculations_total_cost ON cost_calculations(total_cost);

-- Cost accuracy validations indexes
CREATE INDEX IF NOT EXISTS idx_cost_accuracy_vendor_model ON cost_accuracy_validations(vendor, model);
CREATE INDEX IF NOT EXISTS idx_cost_accuracy_validation_date ON cost_accuracy_validations(validation_date);

-- Cost alerts indexes
CREATE INDEX IF NOT EXISTS idx_cost_alerts_company_id ON cost_alerts(company_id);
CREATE INDEX IF NOT EXISTS idx_cost_alerts_alert_type ON cost_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_cost_alerts_timestamp ON cost_alerts(timestamp);
CREATE INDEX IF NOT EXISTS idx_cost_alerts_is_resolved ON cost_alerts(is_resolved);

-- Cost alerts log indexes
CREATE INDEX IF NOT EXISTS idx_cost_alerts_log_company_id ON cost_alerts_log(company_id);
CREATE INDEX IF NOT EXISTS idx_cost_alerts_log_created_at ON cost_alerts_log(created_at);

-- Billing data indexes
CREATE INDEX IF NOT EXISTS idx_billing_data_company_id ON billing_data(company_id);
CREATE INDEX IF NOT EXISTS idx_billing_data_period ON billing_data(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_billing_data_vendor ON billing_data(vendor);

-- Company quotas indexes
CREATE INDEX IF NOT EXISTS idx_company_quotas_company_id ON company_quotas(company_id);
CREATE INDEX IF NOT EXISTS idx_company_quotas_is_active ON company_quotas(is_active);

-- Rate limit configs indexes
CREATE INDEX IF NOT EXISTS idx_rate_limit_configs_company_id ON rate_limit_configs(company_id);
CREATE INDEX IF NOT EXISTS idx_rate_limit_configs_tier ON rate_limit_configs(tier);

-- Rate limit resets indexes
CREATE INDEX IF NOT EXISTS idx_rate_limit_resets_company_id ON rate_limit_resets(company_id);
CREATE INDEX IF NOT EXISTS idx_rate_limit_resets_timestamp ON rate_limit_resets(reset_timestamp);

-- Global vendor pricing indexes
CREATE INDEX IF NOT EXISTS idx_global_vendor_pricing_vendor_model ON global_vendor_pricing(vendor, model);
CREATE INDEX IF NOT EXISTS idx_global_vendor_pricing_effective_date ON global_vendor_pricing(effective_date);
CREATE INDEX IF NOT EXISTS idx_global_vendor_pricing_is_active ON global_vendor_pricing(is_active);

-- Update existing vendor_pricing indexes
DROP INDEX IF EXISTS idx_vendor_pricing_vendor_service;
CREATE INDEX IF NOT EXISTS idx_vendor_pricing_vendor_model ON vendor_pricing(vendor, model);

-- ============================================================================
-- INSERT DEFAULT DATA
-- ============================================================================

-- Insert default global vendor pricing
INSERT INTO global_vendor_pricing (vendor, model, pricing_model, input_price, output_price, currency, is_active) VALUES
-- OpenAI Pricing (as of 2024)
('openai', 'gpt-4', 'tokens', 0.00003, 0.00006, 'USD', true),
('openai', 'gpt-4-turbo', 'tokens', 0.00001, 0.00003, 'USD', true),
('openai', 'gpt-4-32k', 'tokens', 0.00006, 0.00012, 'USD', true),
('openai', 'gpt-3.5-turbo', 'tokens', 0.0000015, 0.000002, 'USD', true),
('openai', 'gpt-3.5-turbo-16k', 'tokens', 0.000003, 0.000004, 'USD', true),
('openai', 'text-embedding-ada-002', 'tokens', 0.0000001, 0.0000001, 'USD', true),
('openai', 'text-embedding-3-small', 'tokens', 0.00000002, 0.00000002, 'USD', true),
('openai', 'text-embedding-3-large', 'tokens', 0.00000013, 0.00000013, 'USD', true),

-- Anthropic Pricing (as of 2024)
('anthropic', 'claude-3-opus', 'tokens', 0.000015, 0.000075, 'USD', true),
('anthropic', 'claude-3-sonnet', 'tokens', 0.000003, 0.000015, 'USD', true),
('anthropic', 'claude-3-haiku', 'tokens', 0.00000025, 0.00000125, 'USD', true),
('anthropic', 'claude-2.1', 'tokens', 0.000008, 0.000024, 'USD', true),
('anthropic', 'claude-2', 'tokens', 0.000008, 0.000024, 'USD', true),
('anthropic', 'claude-instant-1.2', 'tokens', 0.0000008, 0.0000024, 'USD', true),

-- Google Pricing (as of 2024)
('google', 'gemini-pro', 'tokens', 0.0000005, 0.0000015, 'USD', true),
('google', 'gemini-pro-vision', 'tokens', 0.0000005, 0.0000015, 'USD', true),
('google', 'gemini-1.5-pro', 'tokens', 0.0000035, 0.0000105, 'USD', true),
('google', 'gemini-1.5-flash', 'tokens', 0.00000035, 0.00000105, 'USD', true),
('google', 'text-bison', 'characters', 0.000001, 0.000001, 'USD', true),
('google', 'chat-bison', 'characters', 0.000001, 0.000001, 'USD', true),

-- Cohere Pricing (as of 2024)
('cohere', 'command', 'tokens', 0.000015, 0.000015, 'USD', true),
('cohere', 'command-light', 'tokens', 0.000003, 0.000006, 'USD', true),
('cohere', 'embed-english-v2.0', 'tokens', 0.0000001, 0.0000001, 'USD', true)

ON CONFLICT (vendor, model, effective_date) DO NOTHING;

-- Insert default rate limit configurations for existing companies
INSERT INTO rate_limit_configs (company_id, tier, per_minute_limit, per_hour_limit, per_day_limit, per_month_limit, burst_limit)
SELECT 
    id as company_id,
    'basic' as tier,
    50 as per_minute_limit,
    1000 as per_hour_limit,
    10000 as per_day_limit,
    100000 as per_month_limit,
    100 as burst_limit
FROM companies
WHERE id NOT IN (SELECT company_id FROM rate_limit_configs WHERE company_id IS NOT NULL)
ON CONFLICT (company_id) DO NOTHING;

-- Insert default quota configurations for existing companies
INSERT INTO company_quotas (company_id, monthly_limit, daily_limit, hourly_limit)
SELECT 
    id as company_id,
    1000.00 as monthly_limit,
    50.00 as daily_limit,
    10.00 as hourly_limit
FROM companies
WHERE id NOT IN (SELECT company_id FROM company_quotas WHERE company_id IS NOT NULL)
ON CONFLICT (company_id) DO NOTHING;

-- ============================================================================
-- RECORD MIGRATION
-- ============================================================================

-- Record this migration as completed
INSERT INTO schema_migrations (version, description, rollback_sql) VALUES (
    '001_cost_and_rate_limiting',
    'Added cost calculation, rate limiting, and analytics tables with comprehensive pricing and quota system',
    '-- Rollback script for migration 001_cost_and_rate_limiting
    DROP TABLE IF EXISTS cost_calculations;
    DROP TABLE IF EXISTS cost_accuracy_validations;
    DROP TABLE IF EXISTS cost_alerts;
    DROP TABLE IF EXISTS cost_alerts_log;
    DROP TABLE IF EXISTS billing_data;
    DROP TABLE IF EXISTS company_quotas;
    DROP TABLE IF EXISTS rate_limit_configs;
    DROP TABLE IF EXISTS rate_limit_resets;
    DROP TABLE IF EXISTS global_vendor_pricing;
    -- Restore original vendor_pricing table structure from backup
    DROP TABLE IF EXISTS vendor_pricing;
    ALTER TABLE vendor_pricing_backup_001 RENAME TO vendor_pricing;'
);

RAISE NOTICE 'Migration 001_cost_and_rate_limiting completed successfully!';