-- Migration: Quota Management System
-- Version: 002
-- Description: Adds quota management tables and enhanced quota tracking
-- Depends on: 001_cost_and_rate_limiting_migration

-- ============================================================================
-- MIGRATION SAFETY CHECKS
-- ============================================================================

DO $$
BEGIN
    -- Check if this migration has already been applied
    IF EXISTS (SELECT 1 FROM schema_migrations WHERE version = '002_quota_management') THEN
        RAISE NOTICE 'Migration 002_quota_management already applied, skipping...';
        RETURN;
    END IF;
    
    -- Check if prerequisite migration exists
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = '001_cost_and_rate_limiting') THEN
        RAISE EXCEPTION 'Prerequisite migration 001_cost_and_rate_limiting must be applied first';
    END IF;
    
    RAISE NOTICE 'Applying migration 002_quota_management...';
END
$$;

-- ============================================================================
-- CREATE QUOTA MANAGEMENT TABLES
-- ============================================================================

-- Enhanced quota configurations table
CREATE TABLE IF NOT EXISTS quota_configurations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE UNIQUE,
    monthly_request_limit INTEGER NOT NULL DEFAULT 10000,
    monthly_cost_limit DECIMAL(20,8) NOT NULL DEFAULT 100.00,
    daily_request_limit INTEGER,
    daily_cost_limit DECIMAL(20,8),
    warning_threshold DECIMAL(3,2) DEFAULT 0.75,
    critical_threshold DECIMAL(3,2) DEFAULT 0.90,
    danger_threshold DECIMAL(3,2) DEFAULT 0.95,
    is_active BOOLEAN DEFAULT true,
    auto_block BOOLEAN DEFAULT true,
    grace_period_hours INTEGER DEFAULT 24,
    reset_day INTEGER DEFAULT 1 CHECK (reset_day >= 1 AND reset_day <= 31),
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Quota alerts table
CREATE TABLE IF NOT EXISTS quota_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    alert_type VARCHAR(50) NOT NULL, -- 'requests', 'cost', 'combined'
    alert_level VARCHAR(50) NOT NULL, -- 'warning_75', 'critical_90', 'danger_95', 'exceeded', 'blocked'
    usage_percentage DECIMAL(8,4) NOT NULL,
    threshold_triggered DECIMAL(8,4) NOT NULL,
    alert_data JSONB DEFAULT '{}',
    is_resolved BOOLEAN DEFAULT false,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Quota resets table (audit trail)
CREATE TABLE IF NOT EXISTS quota_resets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    reset_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    reset_type VARCHAR(50) NOT NULL, -- 'monthly_auto', 'manual', 'admin_override'
    reset_by VARCHAR(255) NOT NULL,
    previous_usage_data JSONB DEFAULT '{}',
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Quota violations table (for analytics and compliance)
CREATE TABLE IF NOT EXISTS quota_violations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    violation_type VARCHAR(50) NOT NULL, -- 'request_quota', 'cost_quota'
    usage_at_violation DECIMAL(20,8) NOT NULL,
    limit_at_violation DECIMAL(20,8) NOT NULL,
    percentage_over DECIMAL(8,4) NOT NULL,
    action_taken VARCHAR(100) NOT NULL, -- 'blocked', 'warned', 'grace_period'
    violation_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_timestamp TIMESTAMP WITH TIME ZONE,
    resolution_method VARCHAR(100), -- 'auto_reset', 'manual_unblock', 'limit_increase'
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Usage analytics table (for reporting and insights)
CREATE TABLE IF NOT EXISTS usage_analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    analysis_date DATE NOT NULL,
    period_type VARCHAR(20) NOT NULL, -- 'daily', 'weekly', 'monthly'
    total_requests INTEGER DEFAULT 0,
    total_cost DECIMAL(20,8) DEFAULT 0,
    average_cost_per_request DECIMAL(20,8) DEFAULT 0,
    peak_hourly_requests INTEGER DEFAULT 0,
    peak_hour INTEGER, -- 0-23
    top_vendors JSONB DEFAULT '[]',
    top_models JSONB DEFAULT '[]',
    efficiency_score DECIMAL(5,2) DEFAULT 0, -- 0-100
    cost_optimization_potential DECIMAL(20,8) DEFAULT 0,
    predicted_monthly_cost DECIMAL(20,8) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, analysis_date, period_type)
);

-- ============================================================================
-- CREATE INDEXES
-- ============================================================================

-- Quota configurations indexes
CREATE INDEX IF NOT EXISTS idx_quota_configurations_company_id ON quota_configurations(company_id);
CREATE INDEX IF NOT EXISTS idx_quota_configurations_is_active ON quota_configurations(is_active);
CREATE INDEX IF NOT EXISTS idx_quota_configurations_reset_day ON quota_configurations(reset_day);

-- Quota alerts indexes
CREATE INDEX IF NOT EXISTS idx_quota_alerts_company_id ON quota_alerts(company_id);
CREATE INDEX IF NOT EXISTS idx_quota_alerts_alert_type ON quota_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_quota_alerts_alert_level ON quota_alerts(alert_level);
CREATE INDEX IF NOT EXISTS idx_quota_alerts_created_at ON quota_alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_quota_alerts_is_resolved ON quota_alerts(is_resolved);

-- Quota resets indexes
CREATE INDEX IF NOT EXISTS idx_quota_resets_company_id ON quota_resets(company_id);
CREATE INDEX IF NOT EXISTS idx_quota_resets_reset_timestamp ON quota_resets(reset_timestamp);
CREATE INDEX IF NOT EXISTS idx_quota_resets_reset_type ON quota_resets(reset_type);

-- Quota violations indexes
CREATE INDEX IF NOT EXISTS idx_quota_violations_company_id ON quota_violations(company_id);
CREATE INDEX IF NOT EXISTS idx_quota_violations_violation_type ON quota_violations(violation_type);
CREATE INDEX IF NOT EXISTS idx_quota_violations_violation_timestamp ON quota_violations(violation_timestamp);
CREATE INDEX IF NOT EXISTS idx_quota_violations_resolved ON quota_violations(resolved_timestamp);

-- Usage analytics indexes
CREATE INDEX IF NOT EXISTS idx_usage_analytics_company_id ON usage_analytics(company_id);
CREATE INDEX IF NOT EXISTS idx_usage_analytics_analysis_date ON usage_analytics(analysis_date);
CREATE INDEX IF NOT EXISTS idx_usage_analytics_period_type ON usage_analytics(period_type);
CREATE INDEX IF NOT EXISTS idx_usage_analytics_company_date ON usage_analytics(company_id, analysis_date);

-- ============================================================================
-- CREATE FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Function to update quota configuration timestamps
CREATE OR REPLACE FUNCTION update_quota_config_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically update quota config timestamps
DROP TRIGGER IF EXISTS quota_config_update_timestamp ON quota_configurations;
CREATE TRIGGER quota_config_update_timestamp
    BEFORE UPDATE ON quota_configurations
    FOR EACH ROW
    EXECUTE FUNCTION update_quota_config_timestamp();

-- Function to log quota violations
CREATE OR REPLACE FUNCTION log_quota_violation()
RETURNS TRIGGER AS $$
BEGIN
    -- This trigger could be attached to quota_alerts to auto-create violation records
    IF NEW.alert_level IN ('exceeded', 'blocked') AND NEW.is_resolved = false THEN
        INSERT INTO quota_violations (
            company_id, violation_type, usage_at_violation, 
            limit_at_violation, percentage_over, action_taken,
            violation_timestamp, metadata
        ) VALUES (
            NEW.company_id,
            NEW.alert_type || '_quota',
            NEW.usage_percentage,
            NEW.threshold_triggered,
            NEW.usage_percentage - NEW.threshold_triggered,
            CASE WHEN NEW.alert_level = 'blocked' THEN 'blocked' ELSE 'warned' END,
            NEW.created_at,
            NEW.alert_data
        ) ON CONFLICT DO NOTHING;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically log quota violations
DROP TRIGGER IF EXISTS quota_violation_logger ON quota_alerts;
CREATE TRIGGER quota_violation_logger
    AFTER INSERT ON quota_alerts
    FOR EACH ROW
    EXECUTE FUNCTION log_quota_violation();

-- ============================================================================
-- CREATE VIEWS
-- ============================================================================

-- View for quota status overview
CREATE OR REPLACE VIEW quota_status_overview AS
SELECT 
    c.id as company_id,
    c.name as company_name,
    qc.monthly_request_limit,
    qc.monthly_cost_limit,
    qc.warning_threshold,
    qc.critical_threshold,
    qc.danger_threshold,
    qc.is_active as quota_active,
    qc.auto_block,
    rlc.tier,
    -- Recent usage calculated from cost_calculations
    COALESCE(recent_usage.monthly_requests, 0) as current_month_requests,
    COALESCE(recent_usage.monthly_cost, 0) as current_month_cost,
    -- Calculate usage percentages
    CASE 
        WHEN qc.monthly_request_limit > 0 
        THEN ROUND((COALESCE(recent_usage.monthly_requests, 0)::decimal / qc.monthly_request_limit * 100), 2)
        ELSE 0 
    END as request_usage_percentage,
    CASE 
        WHEN qc.monthly_cost_limit > 0 
        THEN ROUND((COALESCE(recent_usage.monthly_cost, 0) / qc.monthly_cost_limit * 100), 2)
        ELSE 0 
    END as cost_usage_percentage,
    qc.updated_at as config_last_updated
FROM companies c
LEFT JOIN quota_configurations qc ON c.id = qc.company_id
LEFT JOIN rate_limit_configs rlc ON c.id = rlc.company_id
LEFT JOIN (
    -- Subquery to get current month usage
    SELECT 
        company_id,
        COUNT(*) as monthly_requests,
        SUM(total_cost) as monthly_cost
    FROM cost_calculations 
    WHERE calculation_timestamp >= DATE_TRUNC('month', CURRENT_TIMESTAMP)
    GROUP BY company_id
) recent_usage ON c.id = recent_usage.company_id
WHERE c.status = 'active';

-- View for quota violations summary
CREATE OR REPLACE VIEW quota_violations_summary AS
SELECT 
    c.id as company_id,
    c.name as company_name,
    COUNT(qv.*) as total_violations,
    COUNT(CASE WHEN qv.violation_type = 'request_quota' THEN 1 END) as request_violations,
    COUNT(CASE WHEN qv.violation_type = 'cost_quota' THEN 1 END) as cost_violations,
    COUNT(CASE WHEN qv.resolved_timestamp IS NULL THEN 1 END) as unresolved_violations,
    MAX(qv.violation_timestamp) as last_violation,
    AVG(qv.percentage_over) as avg_overage_percentage
FROM companies c
LEFT JOIN quota_violations qv ON c.id = qv.company_id
WHERE qv.violation_timestamp >= CURRENT_TIMESTAMP - INTERVAL '30 days'
GROUP BY c.id, c.name
HAVING COUNT(qv.*) > 0
ORDER BY total_violations DESC;

-- ============================================================================
-- INSERT DEFAULT DATA
-- ============================================================================

-- Insert default quota configurations for existing companies
INSERT INTO quota_configurations (
    company_id, monthly_request_limit, monthly_cost_limit, 
    daily_request_limit, daily_cost_limit
)
SELECT 
    c.id as company_id,
    CASE 
        WHEN rlc.tier = 'free' THEN 1000
        WHEN rlc.tier = 'basic' THEN 10000
        WHEN rlc.tier = 'premium' THEN 100000
        WHEN rlc.tier = 'enterprise' THEN 1000000
        WHEN rlc.tier = 'unlimited' THEN 999999999
        ELSE 10000
    END as monthly_request_limit,
    CASE 
        WHEN rlc.tier = 'free' THEN 10.00
        WHEN rlc.tier = 'basic' THEN 100.00
        WHEN rlc.tier = 'premium' THEN 1000.00
        WHEN rlc.tier = 'enterprise' THEN 10000.00
        WHEN rlc.tier = 'unlimited' THEN 999999.00
        ELSE 100.00
    END as monthly_cost_limit,
    CASE 
        WHEN rlc.tier = 'free' THEN 100
        WHEN rlc.tier = 'basic' THEN 1000
        WHEN rlc.tier = 'premium' THEN 10000
        WHEN rlc.tier = 'enterprise' THEN 50000
        WHEN rlc.tier = 'unlimited' THEN 99999999
        ELSE 1000
    END as daily_request_limit,
    CASE 
        WHEN rlc.tier = 'free' THEN 1.00
        WHEN rlc.tier = 'basic' THEN 10.00
        WHEN rlc.tier = 'premium' THEN 100.00
        WHEN rlc.tier = 'enterprise' THEN 500.00
        WHEN rlc.tier = 'unlimited' THEN 99999.00
        ELSE 10.00
    END as daily_cost_limit
FROM companies c
LEFT JOIN rate_limit_configs rlc ON c.id = rlc.company_id
WHERE c.id NOT IN (SELECT company_id FROM quota_configurations WHERE company_id IS NOT NULL)
ON CONFLICT (company_id) DO NOTHING;

-- ============================================================================
-- ADD COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE quota_configurations IS 'Company-specific quota limits and settings for request and cost management';
COMMENT ON TABLE quota_alerts IS 'Quota alert history and notifications with threshold tracking';
COMMENT ON TABLE quota_resets IS 'Audit trail for quota resets and administrative modifications';
COMMENT ON TABLE quota_violations IS 'Record of quota violations for compliance and analytics';
COMMENT ON TABLE usage_analytics IS 'Aggregated usage analytics for reporting and business insights';

COMMENT ON VIEW quota_status_overview IS 'Real-time overview of quota status for all active companies';
COMMENT ON VIEW quota_violations_summary IS 'Summary of quota violations in the last 30 days for monitoring';

-- ============================================================================
-- RECORD MIGRATION
-- ============================================================================

-- Record this migration as completed
INSERT INTO schema_migrations (version, description, rollback_sql) VALUES (
    '002_quota_management',
    'Added comprehensive quota management system with alerts, violations tracking, and analytics',
    '-- Rollback script for migration 002_quota_management
    DROP VIEW IF EXISTS quota_status_overview;
    DROP VIEW IF EXISTS quota_violations_summary;
    DROP TRIGGER IF EXISTS quota_config_update_timestamp ON quota_configurations;
    DROP TRIGGER IF EXISTS quota_violation_logger ON quota_alerts;
    DROP FUNCTION IF EXISTS update_quota_config_timestamp();
    DROP FUNCTION IF EXISTS log_quota_violation();
    DROP TABLE IF EXISTS usage_analytics;
    DROP TABLE IF EXISTS quota_violations;
    DROP TABLE IF EXISTS quota_resets;
    DROP TABLE IF EXISTS quota_alerts;
    DROP TABLE IF EXISTS quota_configurations;'
);

RAISE NOTICE 'Migration 002_quota_management completed successfully!';