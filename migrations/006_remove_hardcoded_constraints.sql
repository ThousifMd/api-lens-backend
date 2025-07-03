-- Migration: Remove Hardcoded Database Constraints
-- Purpose: Convert hardcoded CHECK constraints and defaults to configurable values
-- This makes the system flexible and environment-agnostic

BEGIN;

-- ============================================================================
-- 1. DROP ALL HARDCODED CHECK CONSTRAINTS
-- ============================================================================

-- Drop company tier constraint
ALTER TABLE companies 
DROP CONSTRAINT IF EXISTS companies_tier_check;

-- Drop environment constraint
ALTER TABLE api_keys 
DROP CONSTRAINT IF EXISTS api_keys_environment_check;

-- Drop model type constraint  
ALTER TABLE vendor_models 
DROP CONSTRAINT IF EXISTS vendor_models_model_type_check;

-- Drop currency constraint (allow any currency)
ALTER TABLE vendor_pricing 
DROP CONSTRAINT IF EXISTS vendor_pricing_currency_check;

-- Drop any pricing tier constraints if they exist
ALTER TABLE vendor_pricing 
DROP CONSTRAINT IF EXISTS vendor_pricing_tier_check;

-- Drop HTTP method constraint
ALTER TABLE request_logs 
DROP CONSTRAINT IF EXISTS request_logs_method_check;

-- Drop alert type constraints
ALTER TABLE alerts 
DROP CONSTRAINT IF EXISTS alerts_alert_type_check,
DROP CONSTRAINT IF EXISTS alerts_severity_check;

-- Drop error type constraint
ALTER TABLE error_logs 
DROP CONSTRAINT IF EXISTS error_logs_error_type_check;

-- ============================================================================
-- 2. CREATE CONFIGURATION TABLES FOR DYNAMIC VALUES
-- ============================================================================

-- Configuration table for all system enums/constants
CREATE TABLE IF NOT EXISTS system_configuration (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category VARCHAR(100) NOT NULL,
    key VARCHAR(100) NOT NULL,
    value VARCHAR(500) NOT NULL,
    display_name VARCHAR(200),
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT system_configuration_category_key_unique UNIQUE (category, key)
);

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_system_configuration_category 
ON system_configuration (category, is_active);

-- ============================================================================
-- 3. POPULATE CONFIGURATION WITH CURRENT VALUES (MAKING THEM CONFIGURABLE)
-- ============================================================================

-- Company tiers
INSERT INTO system_configuration (category, key, value, display_name, description, sort_order) VALUES
('company_tier', 'free', 'free', 'Free Tier', 'Basic tier with limited usage', 1),
('company_tier', 'standard', 'standard', 'Standard', 'Standard tier for regular users', 2),
('company_tier', 'professional', 'professional', 'Professional', 'Professional tier with higher limits', 3),
('company_tier', 'enterprise', 'enterprise', 'Enterprise', 'Enterprise tier with custom limits', 4)
ON CONFLICT (category, key) DO UPDATE SET 
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    sort_order = EXCLUDED.sort_order,
    updated_at = NOW();

-- Environments
INSERT INTO system_configuration (category, key, value, display_name, description, sort_order) VALUES
('environment', 'development', 'development', 'Development', 'Development environment', 1),
('environment', 'staging', 'staging', 'Staging', 'Staging environment for testing', 2),
('environment', 'production', 'production', 'Production', 'Live production environment', 3),
('environment', 'test', 'test', 'Test', 'Automated testing environment', 4)
ON CONFLICT (category, key) DO UPDATE SET 
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    sort_order = EXCLUDED.sort_order,
    updated_at = NOW();

-- Model types
INSERT INTO system_configuration (category, key, value, display_name, description, sort_order) VALUES
('model_type', 'chat', 'chat', 'Chat/Conversation', 'Conversational AI models', 1),
('model_type', 'completion', 'completion', 'Text Completion', 'Text completion models', 2),
('model_type', 'embedding', 'embedding', 'Text Embedding', 'Text embedding models', 3),
('model_type', 'image', 'image', 'Image Generation', 'Image generation models', 4),
('model_type', 'audio', 'audio', 'Audio Processing', 'Audio transcription and synthesis', 5),
('model_type', 'video', 'video', 'Video Processing', 'Video analysis and generation', 6)
ON CONFLICT (category, key) DO UPDATE SET 
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    sort_order = EXCLUDED.sort_order,
    updated_at = NOW();

-- Currencies (support major world currencies)
INSERT INTO system_configuration (category, key, value, display_name, description, sort_order) VALUES
('currency', 'USD', 'USD', 'US Dollar', 'United States Dollar', 1),
('currency', 'EUR', 'EUR', 'Euro', 'European Euro', 2),
('currency', 'GBP', 'GBP', 'British Pound', 'British Pound Sterling', 3),
('currency', 'CAD', 'CAD', 'Canadian Dollar', 'Canadian Dollar', 4),
('currency', 'JPY', 'JPY', 'Japanese Yen', 'Japanese Yen', 5),
('currency', 'AUD', 'AUD', 'Australian Dollar', 'Australian Dollar', 6),
('currency', 'CHF', 'CHF', 'Swiss Franc', 'Swiss Franc', 7),
('currency', 'CNY', 'CNY', 'Chinese Yuan', 'Chinese Yuan', 8),
('currency', 'INR', 'INR', 'Indian Rupee', 'Indian Rupee', 9),
('currency', 'KRW', 'KRW', 'South Korean Won', 'South Korean Won', 10),
('currency', 'BRL', 'BRL', 'Brazilian Real', 'Brazilian Real', 11),
('currency', 'SGD', 'SGD', 'Singapore Dollar', 'Singapore Dollar', 12)
ON CONFLICT (category, key) DO UPDATE SET 
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    sort_order = EXCLUDED.sort_order,
    updated_at = NOW();

-- Pricing tiers (flexible for different business models)
INSERT INTO system_configuration (category, key, value, display_name, description, sort_order) VALUES
('pricing_tier', 'free', 'free', 'Free', 'Free tier pricing', 1),
('pricing_tier', 'standard', 'standard', 'Standard', 'Standard pricing tier', 2),
('pricing_tier', 'premium', 'premium', 'Premium', 'Premium pricing tier', 3),
('pricing_tier', 'enterprise', 'enterprise', 'Enterprise', 'Custom enterprise pricing', 4),
('pricing_tier', 'volume', 'volume', 'Volume', 'High-volume discount pricing', 5),
('pricing_tier', 'academic', 'academic', 'Academic', 'Academic institution pricing', 6),
('pricing_tier', 'startup', 'startup', 'Startup', 'Startup discount pricing', 7)
ON CONFLICT (category, key) DO UPDATE SET 
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    sort_order = EXCLUDED.sort_order,
    updated_at = NOW();

-- HTTP methods
INSERT INTO system_configuration (category, key, value, display_name, description, sort_order) VALUES
('http_method', 'GET', 'GET', 'GET', 'HTTP GET method', 1),
('http_method', 'POST', 'POST', 'POST', 'HTTP POST method', 2),
('http_method', 'PUT', 'PUT', 'PUT', 'HTTP PUT method', 3),
('http_method', 'PATCH', 'PATCH', 'PATCH', 'HTTP PATCH method', 4),
('http_method', 'DELETE', 'DELETE', 'DELETE', 'HTTP DELETE method', 5),
('http_method', 'OPTIONS', 'OPTIONS', 'OPTIONS', 'HTTP OPTIONS method', 6),
('http_method', 'HEAD', 'HEAD', 'HEAD', 'HTTP HEAD method', 7)
ON CONFLICT (category, key) DO UPDATE SET 
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    sort_order = EXCLUDED.sort_order,
    updated_at = NOW();

-- Alert types
INSERT INTO system_configuration (category, key, value, display_name, description, sort_order) VALUES
('alert_type', 'cost_threshold', 'cost_threshold', 'Cost Threshold', 'Alert when cost exceeds threshold', 1),
('alert_type', 'usage_spike', 'usage_spike', 'Usage Spike', 'Alert on unusual usage patterns', 2),
('alert_type', 'error_rate', 'error_rate', 'Error Rate', 'Alert on high error rates', 3),
('alert_type', 'performance_degradation', 'performance_degradation', 'Performance Issues', 'Alert on performance problems', 4),
('alert_type', 'quota_exceeded', 'quota_exceeded', 'Quota Exceeded', 'Alert when quota limits reached', 5)
ON CONFLICT (category, key) DO UPDATE SET 
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    sort_order = EXCLUDED.sort_order,
    updated_at = NOW();

-- Alert severity levels
INSERT INTO system_configuration (category, key, value, display_name, description, sort_order) VALUES
('alert_severity', 'info', 'info', 'Info', 'Informational alerts', 1),
('alert_severity', 'low', 'low', 'Low', 'Low priority alerts', 2),
('alert_severity', 'medium', 'medium', 'Medium', 'Medium priority alerts', 3),
('alert_severity', 'high', 'high', 'High', 'High priority alerts', 4),
('alert_severity', 'critical', 'critical', 'Critical', 'Critical alerts requiring immediate attention', 5)
ON CONFLICT (category, key) DO UPDATE SET 
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    sort_order = EXCLUDED.sort_order,
    updated_at = NOW();

-- Error types
INSERT INTO system_configuration (category, key, value, display_name, description, sort_order) VALUES
('error_type', 'api_error', 'api_error', 'API Error', 'External API errors', 1),
('error_type', 'timeout', 'timeout', 'Timeout', 'Request timeout errors', 2),
('error_type', 'rate_limit', 'rate_limit', 'Rate Limited', 'Rate limiting errors', 3),
('error_type', 'quota_exceeded', 'quota_exceeded', 'Quota Exceeded', 'Quota exceeded errors', 4),
('error_type', 'authentication', 'authentication', 'Authentication', 'Authentication failures', 5),
('error_type', 'validation', 'validation', 'Validation', 'Input validation errors', 6),
('error_type', 'network', 'network', 'Network', 'Network connectivity issues', 7),
('error_type', 'internal', 'internal', 'Internal Error', 'Internal server errors', 8)
ON CONFLICT (category, key) DO UPDATE SET 
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    sort_order = EXCLUDED.sort_order,
    updated_at = NOW();

-- ============================================================================
-- 4. CREATE VALIDATION FUNCTIONS (OPTIONAL - MORE FLEXIBLE THAN CHECK CONSTRAINTS)
-- ============================================================================

-- Function to validate values against configuration
CREATE OR REPLACE FUNCTION validate_config_value(
    p_category VARCHAR(100),
    p_value VARCHAR(500)
) RETURNS BOOLEAN AS $$
BEGIN
    -- Check if value exists in active configuration
    RETURN EXISTS (
        SELECT 1 
        FROM system_configuration 
        WHERE category = p_category 
        AND key = p_value 
        AND is_active = true
    );
END;
$$ LANGUAGE plpgsql;

-- Function to get valid values for a category
CREATE OR REPLACE FUNCTION get_valid_config_values(p_category VARCHAR(100))
RETURNS TABLE(key VARCHAR(100), display_name VARCHAR(200), description TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT sc.key, sc.display_name, sc.description
    FROM system_configuration sc
    WHERE sc.category = p_category
    AND sc.is_active = true
    ORDER BY sc.sort_order, sc.key;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 5. REMOVE HARDCODED DEFAULT VALUES (MAKE THEM CONFIGURABLE)
-- ============================================================================

-- Add configuration for default values
INSERT INTO system_configuration (category, key, value, display_name, description) VALUES
('defaults', 'company_tier', 'standard', 'Default Company Tier', 'Default tier assigned to new companies'),
('defaults', 'currency', 'USD', 'Default Currency', 'Default currency for pricing'),
('defaults', 'environment', 'production', 'Default Environment', 'Default environment for API keys'),
('defaults', 'timezone', 'UTC', 'Default Timezone', 'Default timezone when location cannot be determined'),
('defaults', 'rate_limit_rps', '100', 'Default Rate Limit (RPS)', 'Default requests per second limit'),
('defaults', 'monthly_quota', '10000', 'Default Monthly Quota', 'Default monthly request quota'),
('defaults', 'user_id_header', 'X-User-ID', 'Default User ID Header', 'Default header name for user identification')
ON CONFLICT (category, key) DO UPDATE SET 
    value = EXCLUDED.value,
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    updated_at = NOW();

-- ============================================================================
-- 6. CREATE INDEXES FOR PERFORMANCE
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_system_configuration_active 
ON system_configuration (category, is_active, sort_order);

-- ============================================================================
-- 7. GRANT PERMISSIONS
-- ============================================================================

-- Grant read access to application role (assuming it exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'api_lens_app') THEN
        GRANT SELECT ON system_configuration TO api_lens_app;
    END IF;
END $$;

-- ============================================================================
-- 8. ADD TRIGGER FOR UPDATED_AT
-- ============================================================================

CREATE OR REPLACE FUNCTION update_system_configuration_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS system_configuration_updated_at ON system_configuration;
CREATE TRIGGER system_configuration_updated_at
    BEFORE UPDATE ON system_configuration
    FOR EACH ROW
    EXECUTE FUNCTION update_system_configuration_timestamp();

COMMIT;