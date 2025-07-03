-- ============================================================================
-- API Lens - B2B User Analytics Platform (Enhanced Schema v2)
-- ============================================================================
-- Complete schema replacement for production-ready user analytics platform
-- Features: Multi-tenancy, user tracking, cost analytics, alerting, audit trails

-- Drop existing tables if they exist (destructive migration)
DROP TABLE IF EXISTS cost_calculations CASCADE;
DROP TABLE IF EXISTS user_tracking CASCADE;
DROP TABLE IF EXISTS worker_request_logs CASCADE;
DROP TABLE IF EXISTS worker_performance CASCADE;
DROP TABLE IF EXISTS request_errors CASCADE;
DROP TABLE IF EXISTS requests CASCADE;
DROP TABLE IF EXISTS vendor_models CASCADE;
DROP TABLE IF EXISTS vendors CASCADE;
DROP TABLE IF EXISTS companies CASCADE;

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "btree_gist"; -- For exclusion constraints

-- ============================================================================
-- Core Multi-Tenant Structure (Enhanced)
-- ============================================================================

-- Companies table (Enhanced with billing and settings)
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
    monthly_budget_usd NUMERIC(12, 2), -- Optional spending limit
    
    -- Configuration
    webhook_url VARCHAR(500),
    webhook_events TEXT[] DEFAULT '{}', -- Events to send webhooks for
    dashboard_settings JSONB DEFAULT '{}',
    
    -- Client configuration
    require_user_id BOOLEAN DEFAULT true, -- Enforce user ID in headers
    user_id_header_name VARCHAR(100) DEFAULT 'X-User-ID', -- Configurable header name
    additional_headers JSONB DEFAULT '{}', -- Other headers to track
    
    -- Status and audit
    is_active BOOLEAN DEFAULT true,
    is_trial BOOLEAN DEFAULT false,
    trial_ends_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- API Keys table (Enhanced with scopes and metadata)
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    key_prefix VARCHAR(20) NOT NULL, -- First few chars for identification
    name VARCHAR(255) NOT NULL,
    environment VARCHAR(50) DEFAULT 'production' CHECK (environment IN ('production', 'staging', 'development', 'test')),
    
    -- Permissions
    scopes TEXT[] DEFAULT '{"read", "write"}',
    allowed_ips INET[] DEFAULT '{}', -- IP whitelist if needed
    
    -- Usage tracking
    is_active BOOLEAN DEFAULT true,
    last_used_at TIMESTAMPTZ,
    usage_count BIGINT DEFAULT 0,
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

-- ============================================================================
-- User Management System
-- ============================================================================

-- Client Users table (Core innovation for user analytics)
CREATE TABLE client_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    client_user_id VARCHAR(255) NOT NULL, -- Client's user ID from headers
    
    -- User attributes
    tier VARCHAR(50) DEFAULT 'standard',
    country VARCHAR(2),
    language VARCHAR(10),
    timezone VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    
    -- Usage tracking
    total_requests BIGINT DEFAULT 0,
    total_cost_usd NUMERIC(12, 6) DEFAULT 0,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    is_blocked BOOLEAN DEFAULT false,
    blocked_reason TEXT,
    
    -- Constraints
    UNIQUE(company_id, client_user_id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- User Sessions table (Geographic and device tracking)
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_user_id UUID NOT NULL REFERENCES client_users(id) ON DELETE CASCADE,
    
    -- Session info
    session_id VARCHAR(255) NOT NULL,
    ip_address INET,
    user_agent TEXT,
    country VARCHAR(2),
    region VARCHAR(100),
    city VARCHAR(100),
    
    -- Device info
    browser VARCHAR(100),
    os VARCHAR(100),
    device_type VARCHAR(50),
    
    -- Timing
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    
    -- Usage
    request_count INTEGER DEFAULT 0,
    total_cost_usd NUMERIC(12, 6) DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Vendor and Model Management
-- ============================================================================

-- Vendors table (Enhanced with metadata)
CREATE TABLE vendors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) UNIQUE NOT NULL,
    slug VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    website_url VARCHAR(500),
    api_documentation_url VARCHAR(500),
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    is_supported BOOLEAN DEFAULT true,
    
    -- Metadata
    features JSONB DEFAULT '{}',
    rate_limits JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Vendor Models table (Enhanced with pricing and capabilities)
CREATE TABLE vendor_models (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    
    -- Model info
    model_type VARCHAR(50) NOT NULL CHECK (model_type IN ('chat', 'completion', 'embedding', 'image', 'audio')),
    context_length INTEGER,
    max_output_tokens INTEGER,
    
    -- Pricing (per 1K tokens)
    input_price_per_1k NUMERIC(10, 6) NOT NULL,
    output_price_per_1k NUMERIC(10, 6) NOT NULL,
    pricing_model VARCHAR(50) DEFAULT 'pay-per-token',
    
    -- Capabilities
    capabilities JSONB DEFAULT '{}',
    supported_formats TEXT[] DEFAULT '{}',
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    is_deprecated BOOLEAN DEFAULT false,
    deprecated_at TIMESTAMPTZ,
    
    -- Constraints
    UNIQUE(vendor_id, name),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Request Tracking (Partitioned for Performance)
-- ============================================================================

-- Requests table (Monthly partitioned for scalability)
CREATE TABLE requests (
    id UUID DEFAULT uuid_generate_v4(),
    
    -- Core request info
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
    client_user_id UUID REFERENCES client_users(id) ON DELETE SET NULL,
    
    -- Vendor and model
    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    vendor_model_id UUID NOT NULL REFERENCES vendor_models(id) ON DELETE CASCADE,
    vendor VARCHAR(100) NOT NULL,
    model VARCHAR(255) NOT NULL,
    
    -- Request details
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    url TEXT NOT NULL,
    
    -- Token usage
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    
    -- Cost tracking
    input_cost_usd NUMERIC(12, 6) DEFAULT 0,
    output_cost_usd NUMERIC(12, 6) DEFAULT 0,
    total_cost_usd NUMERIC(12, 6) DEFAULT 0,
    
    -- Performance
    request_duration_ms INTEGER,
    response_size_bytes INTEGER,
    
    -- Status
    status_code INTEGER,
    is_success BOOLEAN DEFAULT true,
    error_message TEXT,
    
    -- Geographic and timing
    ip_address INET,
    country VARCHAR(2),
    region VARCHAR(100),
    city VARCHAR(100),
    
    -- Timestamps
    request_timestamp TIMESTAMPTZ DEFAULT NOW(),
    calculated_timestamp TEXT, -- Local timezone timestamp
    
    -- Metadata
    request_headers JSONB DEFAULT '{}',
    request_body JSONB,
    response_headers JSONB DEFAULT '{}',
    response_body JSONB,
    
    -- Partitioning
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_date DATE GENERATED ALWAYS AS (created_at::DATE) STORED,
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Create partitions for current and next 3 months
CREATE TABLE requests_2024_07 PARTITION OF requests
    FOR VALUES FROM ('2024-07-01') TO ('2024-08-01');
CREATE TABLE requests_2024_08 PARTITION OF requests
    FOR VALUES FROM ('2024-08-01') TO ('2024-09-01');
CREATE TABLE requests_2024_09 PARTITION OF requests
    FOR VALUES FROM ('2024-09-01') TO ('2024-10-01');
CREATE TABLE requests_2024_10 PARTITION OF requests
    FOR VALUES FROM ('2024-10-01') TO ('2024-11-01');

-- ============================================================================
-- Analytics Tables (Real-time and Historical)
-- ============================================================================

-- Hourly Analytics (Real-time insights)
CREATE TABLE hourly_analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    client_user_id UUID REFERENCES client_users(id) ON DELETE CASCADE,
    vendor_id UUID REFERENCES vendors(id) ON DELETE CASCADE,
    vendor_model_id UUID REFERENCES vendor_models(id) ON DELETE CASCADE,
    
    -- Time bucket
    hour_bucket TIMESTAMPTZ NOT NULL,
    
    -- Metrics
    request_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    
    -- Token usage
    total_input_tokens BIGINT DEFAULT 0,
    total_output_tokens BIGINT DEFAULT 0,
    total_tokens BIGINT DEFAULT 0,
    
    -- Costs
    total_cost_usd NUMERIC(12, 6) DEFAULT 0,
    avg_cost_per_request NUMERIC(12, 6) DEFAULT 0,
    
    -- Performance
    avg_response_time_ms NUMERIC(10, 2) DEFAULT 0,
    p95_response_time_ms NUMERIC(10, 2),
    p99_response_time_ms NUMERIC(10, 2),
    
    -- Constraints
    UNIQUE(company_id, client_user_id, vendor_id, vendor_model_id, hour_bucket),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Daily Analytics (Historical insights)
CREATE TABLE daily_analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    client_user_id UUID REFERENCES client_users(id) ON DELETE CASCADE,
    vendor_id UUID REFERENCES vendors(id) ON DELETE CASCADE,
    vendor_model_id UUID REFERENCES vendor_models(id) ON DELETE CASCADE,
    
    -- Time bucket
    date_bucket DATE NOT NULL,
    
    -- Metrics
    request_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    
    -- Token usage
    total_input_tokens BIGINT DEFAULT 0,
    total_output_tokens BIGINT DEFAULT 0,
    total_tokens BIGINT DEFAULT 0,
    
    -- Costs
    total_cost_usd NUMERIC(12, 6) DEFAULT 0,
    avg_cost_per_request NUMERIC(12, 6) DEFAULT 0,
    
    -- Performance
    avg_response_time_ms NUMERIC(10, 2) DEFAULT 0,
    p95_response_time_ms NUMERIC(10, 2),
    p99_response_time_ms NUMERIC(10, 2),
    
    -- Constraints
    UNIQUE(company_id, client_user_id, vendor_id, vendor_model_id, date_bucket),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Cost Tracking and Billing
-- ============================================================================

-- Cost Calculations table (Detailed cost breakdown)
CREATE TABLE cost_calculations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID NOT NULL,
    request_created_at TIMESTAMPTZ NOT NULL,
    
    -- Cost breakdown
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    
    input_cost_usd NUMERIC(12, 6) NOT NULL,
    output_cost_usd NUMERIC(12, 6) NOT NULL,
    total_cost_usd NUMERIC(12, 6) NOT NULL,
    
    -- Pricing info
    pricing_model VARCHAR(50) NOT NULL,
    input_price_per_1k NUMERIC(10, 6) NOT NULL,
    output_price_per_1k NUMERIC(10, 6) NOT NULL,
    
    -- Calculation metadata
    calculation_timestamp TIMESTAMPTZ DEFAULT NOW(),
    calculated_timestamp TEXT, -- Local timezone timestamp
    
    -- Constraints
    UNIQUE(request_id),
    FOREIGN KEY (request_id, request_created_at) REFERENCES requests(id, created_at) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Request Errors table (Error tracking with composite foreign key)
CREATE TABLE request_errors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID NOT NULL,
    request_created_at TIMESTAMPTZ NOT NULL,
    
    -- Error details
    error_message TEXT NOT NULL,
    error_code VARCHAR(100),
    error_type VARCHAR(50) NOT NULL CHECK (error_type IN ('api_error', 'timeout', 'rate_limit', 'quota_exceeded', 'authentication', 'validation')),
    
    -- Error context
    error_metadata JSONB DEFAULT '{}',
    stack_trace TEXT,
    
    -- Timing
    error_timestamp TIMESTAMPTZ DEFAULT NOW(),
    calculated_timestamp TEXT, -- Local timezone timestamp
    
    -- Constraints
    FOREIGN KEY (request_id, request_created_at) REFERENCES requests(id, created_at) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Billing Periods table (Monthly billing cycles)
CREATE TABLE billing_periods (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    
    -- Period info
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    period_month INTEGER NOT NULL,
    period_year INTEGER NOT NULL,
    
    -- Usage metrics
    total_requests BIGINT DEFAULT 0,
    total_cost_usd NUMERIC(12, 2) DEFAULT 0,
    total_tokens BIGINT DEFAULT 0,
    
    -- Billing status
    is_billed BOOLEAN DEFAULT false,
    billed_at TIMESTAMPTZ,
    invoice_id VARCHAR(255),
    
    -- Constraints
    UNIQUE(company_id, period_month, period_year),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Alerting and Anomaly Detection
-- ============================================================================

-- Alerts table (Cost and usage alerts)
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    
    -- Alert info
    alert_type VARCHAR(50) NOT NULL CHECK (alert_type IN ('cost_threshold', 'usage_spike', 'error_rate', 'performance_degradation')),
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    
    -- Thresholds
    threshold_value NUMERIC(12, 6),
    current_value NUMERIC(12, 6),
    
    -- Alert details
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    is_acknowledged BOOLEAN DEFAULT false,
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by VARCHAR(255),
    
    -- Timing
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Anomaly Detection table (Statistical anomalies)
CREATE TABLE anomalies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    client_user_id UUID REFERENCES client_users(id) ON DELETE CASCADE,
    
    -- Anomaly info
    anomaly_type VARCHAR(50) NOT NULL CHECK (anomaly_type IN ('cost_spike', 'usage_spike', 'error_spike', 'performance_drop')),
    confidence_score NUMERIC(5, 4) NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
    
    -- Values
    baseline_value NUMERIC(12, 6),
    actual_value NUMERIC(12, 6),
    deviation_percentage NUMERIC(8, 4),
    
    -- Time window
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    
    -- Status
    is_investigated BOOLEAN DEFAULT false,
    investigation_notes TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Audit and Compliance
-- ============================================================================

-- Audit Logs table (Comprehensive audit trail)
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE SET NULL,
    api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
    
    -- Action info
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID,
    
    -- User context
    user_id VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    
    -- Changes
    old_values JSONB,
    new_values JSONB,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Data Retention Policies table (GDPR compliance)
CREATE TABLE retention_policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    
    -- Policy info
    table_name VARCHAR(100) NOT NULL,
    retention_days INTEGER NOT NULL,
    retention_type VARCHAR(50) NOT NULL CHECK (retention_type IN ('delete', 'archive', 'anonymize')),
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    last_cleanup_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

-- Companies indexes
CREATE INDEX idx_companies_slug ON companies(slug) WHERE is_active = true;
CREATE INDEX idx_companies_active ON companies(is_active, created_at DESC);

-- API Keys indexes
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash) WHERE is_active = true;
CREATE INDEX idx_api_keys_company ON api_keys(company_id, is_active);
CREATE INDEX idx_api_keys_last_used ON api_keys(last_used_at DESC);

-- Client Users indexes
CREATE INDEX idx_client_users_company ON client_users(company_id, is_active);
CREATE INDEX idx_client_users_client_id ON client_users(client_user_id);
CREATE INDEX idx_client_users_last_seen ON client_users(last_seen_at DESC);
CREATE INDEX idx_client_users_cost ON client_users(total_cost_usd DESC);

-- User Sessions indexes
CREATE INDEX idx_user_sessions_client_user ON user_sessions(client_user_id, started_at DESC);
CREATE INDEX idx_user_sessions_ip ON user_sessions(ip_address);
CREATE INDEX idx_user_sessions_country ON user_sessions(country);

-- Vendors indexes
CREATE INDEX idx_vendors_slug ON vendors(slug) WHERE is_active = true;
CREATE INDEX idx_vendors_active ON vendors(is_active);

-- Vendor Models indexes
CREATE INDEX idx_vendor_models_vendor ON vendor_models(vendor_id, is_active);
CREATE INDEX idx_vendor_models_type ON vendor_models(model_type, is_active);
CREATE INDEX idx_vendor_models_pricing ON vendor_models(input_price_per_1k, output_price_per_1k);

-- Requests indexes (partitioned)
CREATE INDEX idx_requests_company ON requests(company_id, created_at DESC);
CREATE INDEX idx_requests_client_user ON requests(client_user_id, created_at DESC);
CREATE INDEX idx_requests_vendor_model ON requests(vendor_id, vendor_model_id, created_at DESC);
CREATE INDEX idx_requests_timestamp ON requests(request_timestamp DESC);
CREATE INDEX idx_requests_cost ON requests(total_cost_usd DESC);
CREATE INDEX idx_requests_success ON requests(is_success, created_at DESC);

-- Analytics indexes
CREATE INDEX idx_hourly_analytics_company ON hourly_analytics(company_id, hour_bucket DESC);
CREATE INDEX idx_hourly_analytics_user ON hourly_analytics(client_user_id, hour_bucket DESC);
CREATE INDEX idx_daily_analytics_company ON daily_analytics(company_id, date_bucket DESC);
CREATE INDEX idx_daily_analytics_user ON daily_analytics(client_user_id, date_bucket DESC);

-- Cost indexes
CREATE INDEX idx_cost_calculations_request ON cost_calculations(request_id);
CREATE INDEX idx_cost_calculations_timestamp ON cost_calculations(calculation_timestamp DESC);
CREATE INDEX idx_billing_periods_company ON billing_periods(company_id, period_year DESC, period_month DESC);

-- Request Errors indexes
CREATE INDEX idx_request_errors_request ON request_errors(request_id, request_created_at);
CREATE INDEX idx_request_errors_timestamp ON request_errors(error_timestamp DESC);
CREATE INDEX idx_request_errors_type ON request_errors(error_type, error_timestamp DESC);

-- Alert indexes
CREATE INDEX idx_alerts_company ON alerts(company_id, triggered_at DESC);
CREATE INDEX idx_alerts_active ON alerts(is_active, severity);
CREATE INDEX idx_anomalies_company ON anomalies(company_id, created_at DESC);

-- Audit indexes
CREATE INDEX idx_audit_logs_company ON audit_logs(company_id, created_at DESC);
CREATE INDEX idx_audit_logs_action ON audit_logs(action, created_at DESC);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);

-- ============================================================================
-- Views for Analytics
-- ============================================================================

-- User Analytics View (Top users by cost)
CREATE VIEW user_analytics AS
SELECT 
    cu.id,
    cu.company_id,
    c.name as company_name,
    cu.client_user_id,
    cu.tier,
    cu.country,
    cu.total_requests,
    cu.total_cost_usd,
    cu.first_seen_at,
    cu.last_seen_at,
    EXTRACT(EPOCH FROM (cu.last_seen_at - cu.first_seen_at)) / 86400 as days_active,
    CASE 
        WHEN cu.total_requests > 0 THEN cu.total_cost_usd / cu.total_requests 
        ELSE 0 
    END as avg_cost_per_request
FROM client_users cu
JOIN companies c ON cu.company_id = c.id
WHERE cu.is_active = true;

-- Model Usage Analytics View
CREATE VIEW model_usage_analytics AS
SELECT 
    vm.id,
    vm.name as model_name,
    v.name as vendor_name,
    vm.model_type,
    COUNT(r.id) as total_requests,
    SUM(r.total_cost_usd) as total_cost_usd,
    AVG(r.total_cost_usd) as avg_cost_per_request,
    AVG(r.request_duration_ms) as avg_response_time_ms,
    SUM(r.total_tokens) as total_tokens,
    COUNT(CASE WHEN r.is_success = true THEN 1 END) as success_count,
    COUNT(CASE WHEN r.is_success = false THEN 1 END) as error_count,
    CASE 
        WHEN COUNT(r.id) > 0 THEN 
            COUNT(CASE WHEN r.is_success = true THEN 1 END)::NUMERIC / COUNT(r.id) * 100 
        ELSE 0 
    END as success_rate
FROM vendor_models vm
JOIN vendors v ON vm.vendor_id = v.id
LEFT JOIN requests r ON vm.id = r.vendor_model_id
WHERE vm.is_active = true
GROUP BY vm.id, vm.name, v.name, vm.model_type;

-- Cost Analytics View (Daily trends)
CREATE VIEW cost_analytics AS
SELECT 
    da.date_bucket,
    c.name as company_name,
    cu.client_user_id,
    v.name as vendor_name,
    vm.name as model_name,
    da.request_count,
    da.total_cost_usd,
    da.avg_cost_per_request,
    da.total_tokens,
    da.success_count,
    da.error_count,
    CASE 
        WHEN da.request_count > 0 THEN 
            da.success_count::NUMERIC / da.request_count * 100 
        ELSE 0 
    END as success_rate
FROM daily_analytics da
JOIN companies c ON da.company_id = c.id
LEFT JOIN client_users cu ON da.client_user_id = cu.id
LEFT JOIN vendors v ON da.vendor_id = v.id
LEFT JOIN vendor_models vm ON da.vendor_model_id = vm.id
ORDER BY da.date_bucket DESC;

-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Function to get timezone from country/region
CREATE OR REPLACE FUNCTION get_timezone_from_location(
    country_code VARCHAR(2),
    region_name VARCHAR(100) DEFAULT NULL
) RETURNS VARCHAR(50) AS $$
BEGIN
    -- Default timezone mapping
    RETURN CASE 
        WHEN country_code = 'US' THEN
            CASE region_name
                WHEN 'California' THEN 'America/Los_Angeles'
                WHEN 'New York' THEN 'America/New_York'
                WHEN 'Texas' THEN 'America/Chicago'
                WHEN 'Florida' THEN 'America/New_York'
                WHEN 'Illinois' THEN 'America/Chicago'
                ELSE 'America/New_York'
            END
        WHEN country_code = 'CA' THEN 'America/Toronto'
        WHEN country_code = 'GB' THEN 'Europe/London'
        WHEN country_code = 'DE' THEN 'Europe/Berlin'
        WHEN country_code = 'FR' THEN 'Europe/Paris'
        WHEN country_code = 'IN' THEN 'Asia/Kolkata'
        WHEN country_code = 'JP' THEN 'Asia/Tokyo'
        WHEN country_code = 'AU' THEN 'Australia/Sydney'
        WHEN country_code = 'BR' THEN 'America/Sao_Paulo'
        WHEN country_code = 'MX' THEN 'America/Mexico_City'
        ELSE 'UTC'
    END;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to calculate local timestamp
CREATE OR REPLACE FUNCTION calculate_local_timestamp(
    utc_timestamp TIMESTAMPTZ,
    country_code VARCHAR(2),
    region_name VARCHAR(100) DEFAULT NULL
) RETURNS TEXT AS $$
DECLARE
    timezone_name VARCHAR(50);
    local_time TIMESTAMPTZ;
BEGIN
    timezone_name := get_timezone_from_location(country_code, region_name);
    local_time := utc_timestamp AT TIME ZONE timezone_name;
    RETURN to_char(local_time, 'YYYY-MM-DD HH24:MI:SS TZ');
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to update user analytics
CREATE OR REPLACE FUNCTION update_user_analytics() RETURNS TRIGGER AS $$
BEGIN
    -- Update client_users table
    INSERT INTO client_users (company_id, client_user_id, total_requests, total_cost_usd, last_seen_at)
    VALUES (NEW.company_id, NEW.client_user_id, 1, NEW.total_cost_usd, NEW.request_timestamp)
    ON CONFLICT (company_id, client_user_id) 
    DO UPDATE SET
        total_requests = client_users.total_requests + 1,
        total_cost_usd = client_users.total_cost_usd + NEW.total_cost_usd,
        last_seen_at = NEW.request_timestamp;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update user analytics on request insert
CREATE TRIGGER trigger_update_user_analytics
    AFTER INSERT ON requests
    FOR EACH ROW
    WHEN (NEW.client_user_id IS NOT NULL)
    EXECUTE FUNCTION update_user_analytics();

-- ============================================================================
-- Security and Permissions
-- ============================================================================

-- Create roles
CREATE ROLE readonly_role;
CREATE ROLE api_role;
CREATE ROLE admin_role;

-- Grant permissions
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_role;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO api_role;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO admin_role;

-- Grant sequence permissions
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO api_role;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO admin_role;

-- ============================================================================
-- Initial Data
-- ============================================================================

-- Insert default vendors
INSERT INTO vendors (name, slug, description, website_url) VALUES
('OpenAI', 'openai', 'Leading AI research company', 'https://openai.com'),
('Anthropic', 'anthropic', 'AI safety and research', 'https://anthropic.com'),
('Google', 'google', 'Google AI services', 'https://ai.google'),
('Meta', 'meta', 'Meta AI research', 'https://ai.meta.com'),
('Cohere', 'cohere', 'Enterprise AI platform', 'https://cohere.ai');

-- Insert default models
INSERT INTO vendor_models (vendor_id, name, slug, model_type, context_length, input_price_per_1k, output_price_per_1k) 
SELECT 
    v.id,
    'GPT-4',
    'gpt-4',
    'chat',
    8192,
    0.03,
    0.06
FROM vendors v WHERE v.slug = 'openai';

INSERT INTO vendor_models (vendor_id, name, slug, model_type, context_length, input_price_per_1k, output_price_per_1k) 
SELECT 
    v.id,
    'GPT-3.5 Turbo',
    'gpt-3.5-turbo',
    'chat',
    4096,
    0.0015,
    0.002
FROM vendors v WHERE v.slug = 'openai';

INSERT INTO vendor_models (vendor_id, name, slug, model_type, context_length, input_price_per_1k, output_price_per_1k) 
SELECT 
    v.id,
    'Claude-3 Opus',
    'claude-3-opus',
    'chat',
    200000,
    0.015,
    0.075
FROM vendors v WHERE v.slug = 'anthropic';

INSERT INTO vendor_models (vendor_id, name, slug, model_type, context_length, input_price_per_1k, output_price_per_1k) 
SELECT 
    v.id,
    'Claude-3 Sonnet',
    'claude-3-sonnet',
    'chat',
    200000,
    0.003,
    0.015
FROM vendors v WHERE v.slug = 'anthropic';

INSERT INTO vendor_models (vendor_id, name, slug, model_type, context_length, input_price_per_1k, output_price_per_1k) 
SELECT 
    v.id,
    'Claude-3 Haiku',
    'claude-3-haiku',
    'chat',
    200000,
    0.00025,
    0.00125
FROM vendors v WHERE v.slug = 'anthropic';

INSERT INTO vendor_models (vendor_id, name, slug, model_type, context_length, input_price_per_1k, output_price_per_1k) 
SELECT 
    v.id,
    'Gemini 1.5 Pro',
    'gemini-1.5-pro',
    'chat',
    1000000,
    0.0035,
    0.0105
FROM vendors v WHERE v.slug = 'google';

-- Insert sample company
INSERT INTO companies (name, slug, contact_email, tier) VALUES
('Sample Company', 'sample-company', 'admin@samplecompany.com', 'enterprise');

-- Insert sample API key
INSERT INTO api_keys (company_id, key_hash, key_prefix, name, environment)
SELECT 
    c.id,
    'sample_hash_123456789',
    'sk-sample',
    'Production API Key',
    'production'
FROM companies c WHERE c.slug = 'sample-company';

-- ============================================================================
-- Migration Complete
-- ============================================================================

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'Enhanced schema migration completed successfully!';
    RAISE NOTICE 'Features enabled: Multi-tenancy, User Analytics, Cost Tracking, Alerting, Audit Trails';
    RAISE NOTICE 'Tables created: %', (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public');
    RAISE NOTICE 'Indexes created: %', (SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public');
    RAISE NOTICE 'Views created: %', (SELECT COUNT(*) FROM information_schema.views WHERE table_schema = 'public');
END $$;