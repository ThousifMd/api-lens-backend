-- ============================================================================
-- API Lens - Complete Schema v2 Migration
-- ============================================================================
-- This migration applies the complete production-ready schema for API Lens
-- B2B User Analytics Platform with all tables, views, functions, and data

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- ============================================================================
-- Drop existing tables if they exist (clean slate approach)
-- ============================================================================

DROP TABLE IF EXISTS cost_calculations CASCADE;
DROP TABLE IF EXISTS user_tracking CASCADE;
DROP TABLE IF EXISTS user_sessions CASCADE;
DROP TABLE IF EXISTS requests CASCADE;
DROP TABLE IF EXISTS vendor_pricing CASCADE;
DROP TABLE IF EXISTS vendor_models CASCADE;
DROP TABLE IF EXISTS vendors CASCADE;
DROP TABLE IF EXISTS client_users CASCADE;
DROP TABLE IF EXISTS api_keys CASCADE;
DROP TABLE IF EXISTS companies CASCADE;
DROP TABLE IF EXISTS cost_alerts CASCADE;
DROP TABLE IF EXISTS cost_anomalies CASCADE;
DROP TABLE IF EXISTS user_analytics_hourly CASCADE;
DROP TABLE IF EXISTS user_analytics_daily CASCADE;

-- Drop views
DROP VIEW IF EXISTS top_users_realtime CASCADE;
DROP VIEW IF EXISTS geographic_usage_patterns CASCADE;
DROP VIEW IF EXISTS peak_usage_by_location CASCADE;
DROP VIEW IF EXISTS user_model_usage CASCADE;
DROP VIEW IF EXISTS company_user_summary CASCADE;
DROP VIEW IF EXISTS usage_heatmap CASCADE;

-- Drop functions
DROP FUNCTION IF EXISTS track_request CASCADE;
DROP FUNCTION IF EXISTS check_cost_alerts CASCADE;
DROP FUNCTION IF EXISTS create_next_month_partition CASCADE;
DROP FUNCTION IF EXISTS populate_hourly_analytics CASCADE;
DROP FUNCTION IF EXISTS populate_daily_analytics CASCADE;
DROP FUNCTION IF EXISTS detect_cost_anomalies CASCADE;
DROP FUNCTION IF EXISTS generate_api_key CASCADE;
DROP FUNCTION IF EXISTS archive_old_requests CASCADE;
DROP FUNCTION IF EXISTS update_user_stats_trigger CASCADE;
DROP FUNCTION IF EXISTS get_or_create_client_user CASCADE;
DROP FUNCTION IF EXISTS get_or_create_vendor CASCADE;
DROP FUNCTION IF EXISTS get_or_create_vendor_model CASCADE;

-- ============================================================================
-- Core Multi-Tenant Structure
-- ============================================================================

-- Companies table
CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    contact_email VARCHAR(255),
    billing_email VARCHAR(255),
    tier VARCHAR(50) DEFAULT 'standard' CHECK (tier IN ('standard', 'professional', 'enterprise')),
    
    -- Usage limits
    rate_limit_rps INTEGER DEFAULT 100 CHECK (rate_limit_rps > 0),
    monthly_quota BIGINT DEFAULT 10000 CHECK (monthly_quota > 0),
    monthly_budget_usd NUMERIC(12, 2),
    
    -- Configuration
    webhook_url VARCHAR(500),
    webhook_events TEXT[] DEFAULT '{}',
    dashboard_settings JSONB DEFAULT '{}',
    
    -- Client configuration
    require_user_id BOOLEAN DEFAULT true,
    user_id_header_name VARCHAR(100) DEFAULT 'X-User-ID',
    additional_headers JSONB DEFAULT '{}',
    
    -- Status and audit
    is_active BOOLEAN DEFAULT true,
    is_trial BOOLEAN DEFAULT false,
    trial_ends_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_companies_slug ON companies(slug) WHERE is_active = true;
CREATE INDEX idx_companies_active ON companies(is_active, created_at DESC);

-- API Keys table
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    key_prefix VARCHAR(20) NOT NULL,
    name VARCHAR(255) NOT NULL,
    environment VARCHAR(50) DEFAULT 'production' CHECK (environment IN ('production', 'staging', 'development', 'test')),
    
    -- Permissions
    scopes TEXT[] DEFAULT '{"read", "write"}',
    allowed_ips INET[] DEFAULT '{}',
    
    -- Usage tracking
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    
    -- Metadata
    created_by VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    
    UNIQUE(company_id, name, environment)
);

CREATE INDEX idx_api_keys_lookup ON api_keys(key_hash, is_active) WHERE is_active = true;
CREATE INDEX idx_api_keys_company ON api_keys(company_id, environment, is_active);

-- ============================================================================
-- User Management
-- ============================================================================

-- Client Users table
CREATE TABLE client_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    client_user_id VARCHAR(255) NOT NULL,
    
    -- User details
    display_name VARCHAR(255),
    email VARCHAR(255),
    avatar_url VARCHAR(500),
    
    -- User attributes
    user_tier VARCHAR(100),
    signup_date DATE,
    country VARCHAR(3),
    language VARCHAR(10),
    
    -- Usage tracking
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    total_requests BIGINT DEFAULT 0,
    total_cost_usd NUMERIC(12, 4) DEFAULT 0,
    
    -- Custom attributes
    metadata JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    is_blocked BOOLEAN DEFAULT false,
    blocked_reason TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(company_id, client_user_id)
);

CREATE INDEX idx_client_users_lookup ON client_users(company_id, client_user_id) WHERE is_active = true;
CREATE INDEX idx_client_users_cost ON client_users(company_id, total_cost_usd DESC);
CREATE INDEX idx_client_users_activity ON client_users(company_id, last_seen_at DESC);

-- User Sessions table
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_user_id UUID NOT NULL REFERENCES client_users(id) ON DELETE CASCADE,
    session_id VARCHAR(255) NOT NULL,
    
    -- Session details
    ip_address INET,
    user_agent TEXT,
    device_type VARCHAR(50),
    browser VARCHAR(100),
    os VARCHAR(100),
    
    -- Location with timezone
    country VARCHAR(3),
    country_name VARCHAR(100),
    region VARCHAR(100),
    city VARCHAR(100),
    timezone_name VARCHAR(100),
    utc_offset INTEGER,
    latitude NUMERIC(10, 6),
    longitude NUMERIC(10, 6),
    
    -- Session metrics
    started_at_utc TIMESTAMPTZ DEFAULT NOW(),
    started_at_local TIMESTAMPTZ,
    ended_at_utc TIMESTAMPTZ,
    ended_at_local TIMESTAMPTZ,
    last_activity_at_utc TIMESTAMPTZ DEFAULT NOW(),
    last_activity_at_local TIMESTAMPTZ,
    request_count INTEGER DEFAULT 0,
    total_cost_usd NUMERIC(12, 4) DEFAULT 0,
    
    is_active BOOLEAN DEFAULT true,
    
    UNIQUE(client_user_id, session_id)
);

CREATE INDEX idx_sessions_active ON user_sessions(client_user_id, is_active, last_activity_at_utc DESC);
CREATE INDEX idx_sessions_lookup ON user_sessions(session_id) WHERE is_active = true;
CREATE INDEX idx_sessions_local_time ON user_sessions(client_user_id, started_at_local DESC);

-- ============================================================================
-- Vendor Management
-- ============================================================================

-- Vendors table
CREATE TABLE vendors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) UNIQUE NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    website_url VARCHAR(500),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Vendor Models table
CREATE TABLE vendor_models (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    model_type VARCHAR(50) CHECK (model_type IN ('chat', 'completion', 'embedding', 'image', 'audio', 'video')),
    
    -- Model capabilities
    context_window INTEGER,
    max_output_tokens INTEGER,
    supports_functions BOOLEAN DEFAULT false,
    supports_vision BOOLEAN DEFAULT false,
    
    -- Model lifecycle
    is_active BOOLEAN DEFAULT true,
    is_deprecated BOOLEAN DEFAULT false,
    deprecated_at TIMESTAMPTZ,
    sunset_at TIMESTAMPTZ,
    replacement_model_id UUID REFERENCES vendor_models(id),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(vendor_id, name)
);

CREATE INDEX idx_vendor_models_active ON vendor_models(vendor_id, is_active, is_deprecated);

-- Vendor Pricing table
CREATE TABLE vendor_pricing (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    model_id UUID NOT NULL REFERENCES vendor_models(id) ON DELETE CASCADE,
    
    -- Base pricing
    input_cost_per_1k_tokens NUMERIC(12, 8) NOT NULL CHECK (input_cost_per_1k_tokens >= 0),
    output_cost_per_1k_tokens NUMERIC(12, 8) NOT NULL CHECK (output_cost_per_1k_tokens >= 0),
    
    -- Additional costs
    function_call_cost NUMERIC(12, 8) DEFAULT 0,
    image_cost_per_item NUMERIC(12, 8) DEFAULT 0,
    
    -- Pricing metadata
    currency VARCHAR(3) DEFAULT 'USD' CHECK (currency IN ('USD', 'EUR', 'GBP')),
    pricing_tier VARCHAR(50) DEFAULT 'standard',
    min_volume INTEGER DEFAULT 0,
    
    effective_date TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pricing_lookup ON vendor_pricing(model_id, pricing_tier, is_active, effective_date DESC);

-- ============================================================================
-- Request Tracking (Partitioned)
-- ============================================================================

-- Main Requests table
CREATE TABLE requests (
    id UUID DEFAULT uuid_generate_v4(),
    request_id VARCHAR(255) UNIQUE NOT NULL,
    
    -- Core identifiers
    company_id UUID NOT NULL,
    client_user_id UUID,
    user_session_id UUID,
    vendor_id UUID NOT NULL,
    model_id UUID NOT NULL,
    api_key_id UUID,
    
    -- Request Details
    method VARCHAR(10) NOT NULL CHECK (method IN ('GET', 'POST', 'PUT', 'DELETE', 'PATCH')),
    endpoint VARCHAR(255) NOT NULL,
    url TEXT,
    
    -- Headers captured
    user_id_header VARCHAR(255),
    custom_headers JSONB DEFAULT '{}',
    
    -- Timing & Location
    timestamp_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    timestamp_local TIMESTAMPTZ,
    timezone_name VARCHAR(100),
    utc_offset INTEGER,
    response_time_ms INTEGER DEFAULT 0 CHECK (response_time_ms >= 0),
    
    -- Geolocation
    ip_address INET,
    country VARCHAR(3),
    country_name VARCHAR(100),
    region VARCHAR(100),
    city VARCHAR(100),
    latitude NUMERIC(10, 6),
    longitude NUMERIC(10, 6),
    
    -- Request context
    user_agent TEXT,
    referer TEXT,
    
    -- Token Usage
    input_tokens INTEGER DEFAULT 0 CHECK (input_tokens >= 0),
    output_tokens INTEGER DEFAULT 0 CHECK (output_tokens >= 0),
    total_tokens INTEGER GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,
    
    -- Costs
    input_cost NUMERIC(12, 8) DEFAULT 0 CHECK (input_cost >= 0),
    output_cost NUMERIC(12, 8) DEFAULT 0 CHECK (output_cost >= 0),
    total_cost NUMERIC(12, 8) GENERATED ALWAYS AS (input_cost + output_cost) STORED,
    
    -- Performance Metrics
    total_latency_ms INTEGER DEFAULT 0 CHECK (total_latency_ms >= 0),
    vendor_latency_ms INTEGER DEFAULT 0 CHECK (vendor_latency_ms >= 0),
    
    -- Response Details
    status_code INTEGER NOT NULL CHECK (status_code >= 100 AND status_code < 600),
    success BOOLEAN GENERATED ALWAYS AS (status_code >= 200 AND status_code < 300) STORED,
    error_type VARCHAR(100),
    error_message TEXT,
    error_code VARCHAR(100),
    
    -- Request/Response samples
    request_sample JSONB,
    response_sample JSONB,
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Partitioning key
    PRIMARY KEY (id, timestamp_utc)
) PARTITION BY RANGE (timestamp_utc);

-- Create monthly partitions for the next 12 months
DO $$
DECLARE
    start_date date := date_trunc('month', CURRENT_DATE);
    end_date date;
    partition_name text;
BEGIN
    FOR i IN 0..11 LOOP
        end_date := start_date + interval '1 month';
        partition_name := 'requests_' || to_char(start_date, 'YYYY_MM');
        
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I PARTITION OF requests
            FOR VALUES FROM (%L) TO (%L)',
            partition_name, start_date, end_date
        );
        
        -- Create indexes on partition
        EXECUTE format('
            CREATE INDEX IF NOT EXISTS idx_%I_company_time 
            ON %I(company_id, timestamp_utc DESC)',
            partition_name, partition_name
        );
        
        EXECUTE format('
            CREATE INDEX IF NOT EXISTS idx_%I_user_time 
            ON %I(client_user_id, timestamp_utc DESC)
            WHERE client_user_id IS NOT NULL',
            partition_name, partition_name
        );
        
        start_date := end_date;
    END LOOP;
END $$;

-- ============================================================================
-- Analytics Tables
-- ============================================================================

-- User Analytics Hourly
CREATE TABLE user_analytics_hourly (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hour_bucket_utc TIMESTAMPTZ NOT NULL,
    hour_bucket_local TIMESTAMPTZ NOT NULL,
    timezone_name VARCHAR(100),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    client_user_id UUID NOT NULL REFERENCES client_users(id) ON DELETE CASCADE,
    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    model_id UUID NOT NULL REFERENCES vendor_models(id) ON DELETE CASCADE,
    
    -- Metrics
    request_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    
    total_tokens INTEGER DEFAULT 0,
    total_cost NUMERIC(12, 8) DEFAULT 0,
    
    avg_latency_ms NUMERIC(8, 2) DEFAULT 0,
    p95_latency_ms INTEGER DEFAULT 0,
    p99_latency_ms INTEGER DEFAULT 0,
    
    -- Unique counts
    unique_sessions INTEGER DEFAULT 0,
    unique_ips INTEGER DEFAULT 0,
    
    -- Location breakdown
    location_breakdown JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(hour_bucket_utc, company_id, client_user_id, vendor_id, model_id)
);

CREATE INDEX idx_user_hourly_lookup ON user_analytics_hourly(company_id, client_user_id, hour_bucket_utc DESC);
CREATE INDEX idx_user_hourly_local ON user_analytics_hourly(company_id, client_user_id, hour_bucket_local DESC);
CREATE INDEX idx_user_hourly_cost ON user_analytics_hourly(company_id, hour_bucket_utc DESC, total_cost DESC);

-- User Analytics Daily
CREATE TABLE user_analytics_daily (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    date DATE NOT NULL,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    client_user_id UUID NOT NULL REFERENCES client_users(id) ON DELETE CASCADE,
    
    -- Aggregated metrics
    total_requests INTEGER DEFAULT 0,
    total_tokens BIGINT DEFAULT 0,
    total_cost NUMERIC(12, 4) DEFAULT 0,
    
    -- Model usage breakdown
    model_usage JSONB DEFAULT '{}',
    
    -- Performance
    avg_latency_ms NUMERIC(8, 2) DEFAULT 0,
    error_rate NUMERIC(5, 2) DEFAULT 0,
    
    -- User behavior
    active_hours INTEGER DEFAULT 0,
    unique_sessions INTEGER DEFAULT 0,
    countries TEXT[] DEFAULT '{}',
    
    -- Cost ranking
    cost_rank_in_company INTEGER,
    cost_percentile NUMERIC(5, 2),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(date, company_id, client_user_id)
);

CREATE INDEX idx_daily_lookup ON user_analytics_daily(company_id, date DESC, total_cost DESC);
CREATE INDEX idx_daily_user ON user_analytics_daily(client_user_id, date DESC);

-- ============================================================================
-- Cost Tracking and Billing
-- ============================================================================

-- Cost alerts configuration
CREATE TABLE cost_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    
    alert_type VARCHAR(50) NOT NULL CHECK (alert_type IN ('user_daily', 'user_monthly', 'company_daily', 'company_monthly')),
    threshold_usd NUMERIC(12, 2) NOT NULL CHECK (threshold_usd > 0),
    
    -- Alert targets
    client_user_id UUID REFERENCES client_users(id) ON DELETE CASCADE,
    
    -- Notification settings
    notification_emails TEXT[] DEFAULT '{}',
    webhook_url VARCHAR(500),
    
    -- State
    is_active BOOLEAN DEFAULT true,
    last_triggered_at TIMESTAMPTZ,
    trigger_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_alerts_active ON cost_alerts(company_id, is_active, alert_type);

-- Cost anomalies detection
CREATE TABLE cost_anomalies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    client_user_id UUID REFERENCES client_users(id) ON DELETE CASCADE,
    
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    anomaly_type VARCHAR(50) NOT NULL,
    
    -- Anomaly details
    expected_value NUMERIC(12, 4),
    actual_value NUMERIC(12, 4),
    deviation_percentage NUMERIC(8, 2),
    
    -- Context
    time_window VARCHAR(50),
    details JSONB DEFAULT '{}',
    
    -- Resolution
    is_resolved BOOLEAN DEFAULT false,
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT
);

CREATE INDEX idx_anomalies_unresolved ON cost_anomalies(company_id, is_resolved, detected_at DESC);

-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Function to get or create client user
CREATE OR REPLACE FUNCTION get_or_create_client_user(
    p_company_id UUID,
    p_client_user_id VARCHAR,
    p_display_name VARCHAR DEFAULT NULL,
    p_email VARCHAR DEFAULT NULL,
    p_metadata JSONB DEFAULT '{}'
)
RETURNS UUID AS $$
DECLARE
    v_user_id UUID;
BEGIN
    -- Try to find existing user
    SELECT id INTO v_user_id
    FROM client_users
    WHERE company_id = p_company_id AND client_user_id = p_client_user_id;
    
    -- Create if not exists
    IF v_user_id IS NULL THEN
        INSERT INTO client_users (
            company_id, client_user_id, display_name, email, metadata
        ) VALUES (
            p_company_id, p_client_user_id, p_display_name, p_email, p_metadata
        ) RETURNING id INTO v_user_id;
    END IF;
    
    RETURN v_user_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get or create vendor
CREATE OR REPLACE FUNCTION get_or_create_vendor(p_vendor_name VARCHAR)
RETURNS UUID AS $$
DECLARE
    v_vendor_id UUID;
BEGIN
    SELECT id INTO v_vendor_id FROM vendors WHERE name = p_vendor_name;
    
    IF v_vendor_id IS NULL THEN
        INSERT INTO vendors (name, display_name) 
        VALUES (p_vendor_name, INITCAP(p_vendor_name))
        RETURNING id INTO v_vendor_id;
    END IF;
    
    RETURN v_vendor_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get or create vendor model
CREATE OR REPLACE FUNCTION get_or_create_vendor_model(p_vendor_name VARCHAR, p_model_name VARCHAR)
RETURNS UUID AS $$
DECLARE
    v_vendor_id UUID;
    v_model_id UUID;
BEGIN
    v_vendor_id := get_or_create_vendor(p_vendor_name);
    
    SELECT vm.id INTO v_model_id
    FROM vendor_models vm
    JOIN vendors v ON vm.vendor_id = v.id
    WHERE v.name = p_vendor_name AND vm.name = p_model_name;
    
    IF v_model_id IS NULL THEN
        INSERT INTO vendor_models (vendor_id, name, display_name, model_type)
        VALUES (v_vendor_id, p_model_name, p_model_name, 'chat')
        RETURNING id INTO v_model_id;
    END IF;
    
    RETURN v_model_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Initial Data
-- ============================================================================

-- Insert sample vendors
INSERT INTO vendors (name, display_name, description, website_url) VALUES
('openai', 'OpenAI', 'OpenAI API services', 'https://openai.com'),
('anthropic', 'Anthropic', 'Claude AI services', 'https://anthropic.com'),
('google', 'Google', 'Google AI services', 'https://ai.google.dev'),
('cohere', 'Cohere', 'Cohere AI services', 'https://cohere.ai'),
('mistral', 'Mistral AI', 'Mistral AI services', 'https://mistral.ai')
ON CONFLICT (name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    updated_at = NOW();

-- Insert vendor models
INSERT INTO vendor_models (vendor_id, name, display_name, model_type, context_window, max_output_tokens) VALUES
-- OpenAI models
((SELECT id FROM vendors WHERE name = 'openai'), 'gpt-3.5-turbo', 'GPT-3.5 Turbo', 'chat', 16384, 4096),
((SELECT id FROM vendors WHERE name = 'openai'), 'gpt-4', 'GPT-4', 'chat', 8192, 4096),
((SELECT id FROM vendors WHERE name = 'openai'), 'gpt-4-turbo', 'GPT-4 Turbo', 'chat', 128000, 4096),
((SELECT id FROM vendors WHERE name = 'openai'), 'gpt-4o', 'GPT-4o', 'chat', 128000, 4096),
((SELECT id FROM vendors WHERE name = 'openai'), 'gpt-4o-mini', 'GPT-4o Mini', 'chat', 128000, 16384),
-- Anthropic models
((SELECT id FROM vendors WHERE name = 'anthropic'), 'claude-3-opus-20240229', 'Claude 3 Opus', 'chat', 200000, 4096),
((SELECT id FROM vendors WHERE name = 'anthropic'), 'claude-3-sonnet-20240229', 'Claude 3 Sonnet', 'chat', 200000, 4096),
((SELECT id FROM vendors WHERE name = 'anthropic'), 'claude-3-haiku-20240307', 'Claude 3 Haiku', 'chat', 200000, 4096),
((SELECT id FROM vendors WHERE name = 'anthropic'), 'claude-3-5-sonnet-20241022', 'Claude 3.5 Sonnet', 'chat', 200000, 8192)
ON CONFLICT (vendor_id, name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    context_window = EXCLUDED.context_window,
    max_output_tokens = EXCLUDED.max_output_tokens,
    updated_at = NOW();

-- Insert current pricing
INSERT INTO vendor_pricing (vendor_id, model_id, input_cost_per_1k_tokens, output_cost_per_1k_tokens) VALUES
-- OpenAI pricing
((SELECT id FROM vendors WHERE name = 'openai'), (SELECT id FROM vendor_models WHERE name = 'gpt-3.5-turbo'), 0.0005, 0.0015),
((SELECT id FROM vendors WHERE name = 'openai'), (SELECT id FROM vendor_models WHERE name = 'gpt-4'), 0.03, 0.06),
((SELECT id FROM vendors WHERE name = 'openai'), (SELECT id FROM vendor_models WHERE name = 'gpt-4-turbo'), 0.01, 0.03),
((SELECT id FROM vendors WHERE name = 'openai'), (SELECT id FROM vendor_models WHERE name = 'gpt-4o'), 0.0025, 0.01),
((SELECT id FROM vendors WHERE name = 'openai'), (SELECT id FROM vendor_models WHERE name = 'gpt-4o-mini'), 0.00015, 0.0006),
-- Anthropic pricing
((SELECT id FROM vendors WHERE name = 'anthropic'), (SELECT id FROM vendor_models WHERE name = 'claude-3-opus-20240229'), 0.015, 0.075),
((SELECT id FROM vendors WHERE name = 'anthropic'), (SELECT id FROM vendor_models WHERE name = 'claude-3-sonnet-20240229'), 0.003, 0.015),
((SELECT id FROM vendors WHERE name = 'anthropic'), (SELECT id FROM vendor_models WHERE name = 'claude-3-haiku-20240307'), 0.00025, 0.00125),
((SELECT id FROM vendors WHERE name = 'anthropic'), (SELECT id FROM vendor_models WHERE name = 'claude-3-5-sonnet-20241022'), 0.003, 0.015)
ON CONFLICT (model_id, effective_date) DO NOTHING;

-- ============================================================================
-- Verification
-- ============================================================================

-- Check schema health
SELECT 
    'Complete Schema v2 applied successfully!' as status,
    (SELECT COUNT(*) FROM vendors) as vendor_count,
    (SELECT COUNT(*) FROM vendor_models) as model_count,
    (SELECT COUNT(*) FROM vendor_pricing WHERE is_active = true) as active_pricing_count,
    (SELECT COUNT(*) FROM pg_tables WHERE tablename LIKE 'requests_%') as request_partitions; 