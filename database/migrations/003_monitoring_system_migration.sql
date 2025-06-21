-- Migration: Monitoring and Anomaly Detection System
-- Version: 003
-- Description: Adds monitoring, analytics, and anomaly detection tables
-- Depends on: 002_quota_management_migration

-- ============================================================================
-- MIGRATION SAFETY CHECKS
-- ============================================================================

DO $$
BEGIN
    -- Check if this migration has already been applied
    IF EXISTS (SELECT 1 FROM schema_migrations WHERE version = '003_monitoring_system') THEN
        RAISE NOTICE 'Migration 003_monitoring_system already applied, skipping...';
        RETURN;
    END IF;
    
    -- Check if prerequisite migration exists
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = '002_quota_management') THEN
        RAISE EXCEPTION 'Prerequisite migration 002_quota_management must be applied first';
    END IF;
    
    RAISE NOTICE 'Applying migration 003_monitoring_system...';
END
$$;

-- ============================================================================
-- CREATE MONITORING TABLES
-- ============================================================================

-- System alerts table
CREATE TABLE IF NOT EXISTS system_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_type VARCHAR(50) NOT NULL, -- 'system_health', 'performance', 'error_rate'
    severity VARCHAR(20) NOT NULL, -- 'info', 'warning', 'critical', 'emergency'
    message TEXT NOT NULL,
    details JSONB DEFAULT '{}',
    is_resolved BOOLEAN DEFAULT false,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolved_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Usage anomalies table
CREATE TABLE IF NOT EXISTS usage_anomalies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    anomaly_id VARCHAR(50) UNIQUE NOT NULL,
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    anomaly_type VARCHAR(50) NOT NULL, -- 'sudden_spike', 'sudden_drop', 'unusual_pattern', 'cost_anomaly', 'error_surge'
    severity VARCHAR(20) NOT NULL, -- 'info', 'warning', 'critical', 'emergency'
    
    -- Detection details
    metric_name VARCHAR(100) NOT NULL,
    current_value DECIMAL(20,8) NOT NULL,
    expected_value DECIMAL(20,8) NOT NULL,
    deviation_percentage DECIMAL(8,4) NOT NULL,
    
    -- Analysis
    description TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    confidence_score DECIMAL(3,2) NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
    
    -- Timeline
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    affected_period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    affected_period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Status
    is_ongoing BOOLEAN DEFAULT true,
    is_resolved BOOLEAN DEFAULT false,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolved_by VARCHAR(255),
    resolution_notes TEXT,
    
    -- Impact
    impact_assessment TEXT,
    business_impact_score INTEGER DEFAULT 0 CHECK (business_impact_score >= 0 AND business_impact_score <= 100),
    
    -- Metadata
    detection_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Performance metrics table
CREATE TABLE IF NOT EXISTS performance_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- System health
    redis_status VARCHAR(20) DEFAULT 'unknown',
    database_status VARCHAR(20) DEFAULT 'unknown',
    cache_hit_rate DECIMAL(5,2) DEFAULT 0,
    
    -- Rate limiting performance
    avg_rate_limit_check_time_ms DECIMAL(8,3) DEFAULT 0,
    rate_limit_accuracy DECIMAL(5,2) DEFAULT 100,
    
    -- Throughput metrics
    requests_processed_per_second DECIMAL(10,2) DEFAULT 0,
    rate_limit_checks_per_second DECIMAL(10,2) DEFAULT 0,
    quota_checks_per_second DECIMAL(10,2) DEFAULT 0,
    
    -- Resource utilization
    redis_memory_usage JSONB DEFAULT '{}',
    database_connection_pool JSONB DEFAULT '{}',
    system_resource_usage JSONB DEFAULT '{}',
    
    -- Error tracking
    rate_limit_errors INTEGER DEFAULT 0,
    quota_calculation_errors INTEGER DEFAULT 0,
    cache_errors INTEGER DEFAULT 0,
    
    -- Additional metrics
    sliding_window_performance JSONB DEFAULT '{}',
    detailed_metrics JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Usage reports table
CREATE TABLE IF NOT EXISTS usage_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_id VARCHAR(50) UNIQUE NOT NULL,
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    
    -- Report metadata
    report_type VARCHAR(50) DEFAULT 'comprehensive', -- 'summary', 'detailed', 'comprehensive'
    period_type VARCHAR(20) NOT NULL, -- 'hourly', 'daily', 'weekly', 'monthly', 'custom'
    period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Report content
    executive_summary JSONB DEFAULT '{}',
    key_metrics JSONB DEFAULT '{}',
    usage_analysis JSONB DEFAULT '{}',
    cost_analysis JSONB DEFAULT '{}',
    performance_analysis JSONB DEFAULT '{}',
    
    -- Insights
    anomalies_detected JSONB DEFAULT '[]',
    optimization_recommendations JSONB DEFAULT '[]',
    trend_analysis JSONB DEFAULT '{}',
    
    -- Comparisons
    period_comparison JSONB DEFAULT '{}',
    benchmark_comparison JSONB DEFAULT '{}',
    
    -- Status
    generation_status VARCHAR(20) DEFAULT 'completed', -- 'pending', 'processing', 'completed', 'failed'
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    generated_by VARCHAR(255),
    
    -- Access
    is_shared BOOLEAN DEFAULT false,
    shared_with JSONB DEFAULT '[]',
    expires_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Real-time metrics cache table (for backup/persistence)
CREATE TABLE IF NOT EXISTS real_time_metrics_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    metric_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Request metrics
    requests_per_minute INTEGER DEFAULT 0,
    requests_per_hour INTEGER DEFAULT 0,
    total_requests_today INTEGER DEFAULT 0,
    
    -- Cost metrics
    cost_per_minute DECIMAL(20,8) DEFAULT 0,
    cost_per_hour DECIMAL(20,8) DEFAULT 0,
    total_cost_today DECIMAL(20,8) DEFAULT 0,
    projected_monthly_cost DECIMAL(20,8) DEFAULT 0,
    
    -- Performance metrics
    avg_response_time_ms DECIMAL(8,3) DEFAULT 0,
    error_rate_percentage DECIMAL(5,2) DEFAULT 0,
    success_rate_percentage DECIMAL(5,2) DEFAULT 100,
    
    -- Quota status
    request_quota_used_percentage DECIMAL(5,2) DEFAULT 0,
    cost_quota_used_percentage DECIMAL(5,2) DEFAULT 0,
    quota_status VARCHAR(20) DEFAULT 'HEALTHY',
    
    -- Rate limiting
    rate_limit_hits_per_minute INTEGER DEFAULT 0,
    rate_limit_status VARCHAR(20) DEFAULT 'OK',
    
    -- Usage patterns
    top_vendors JSONB DEFAULT '[]',
    top_models JSONB DEFAULT '[]',
    top_endpoints JSONB DEFAULT '[]',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Monitoring configuration table
CREATE TABLE IF NOT EXISTS monitoring_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE UNIQUE,
    
    -- Anomaly detection settings
    anomaly_detection_enabled BOOLEAN DEFAULT true,
    anomaly_sensitivity VARCHAR(10) DEFAULT 'medium', -- 'low', 'medium', 'high'
    anomaly_notification_enabled BOOLEAN DEFAULT true,
    anomaly_notification_threshold VARCHAR(20) DEFAULT 'warning', -- 'info', 'warning', 'critical', 'emergency'
    
    -- Monitoring intervals
    real_time_monitoring_interval_seconds INTEGER DEFAULT 60,
    anomaly_check_interval_minutes INTEGER DEFAULT 15,
    report_generation_interval_hours INTEGER DEFAULT 24,
    
    -- Alert settings
    alert_email VARCHAR(255),
    alert_webhook_url TEXT,
    alert_slack_channel VARCHAR(100),
    
    -- Thresholds
    custom_thresholds JSONB DEFAULT '{}',
    baseline_period_days INTEGER DEFAULT 7,
    min_data_points INTEGER DEFAULT 20,
    
    -- Feature flags
    advanced_analytics_enabled BOOLEAN DEFAULT true,
    cost_optimization_suggestions BOOLEAN DEFAULT true,
    performance_monitoring_enabled BOOLEAN DEFAULT true,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- CREATE INDEXES
-- ============================================================================

-- System alerts indexes
CREATE INDEX IF NOT EXISTS idx_system_alerts_alert_type ON system_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_system_alerts_severity ON system_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_system_alerts_created_at ON system_alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_system_alerts_is_resolved ON system_alerts(is_resolved);

-- Usage anomalies indexes
CREATE INDEX IF NOT EXISTS idx_usage_anomalies_company_id ON usage_anomalies(company_id);
CREATE INDEX IF NOT EXISTS idx_usage_anomalies_anomaly_type ON usage_anomalies(anomaly_type);
CREATE INDEX IF NOT EXISTS idx_usage_anomalies_severity ON usage_anomalies(severity);
CREATE INDEX IF NOT EXISTS idx_usage_anomalies_detected_at ON usage_anomalies(detected_at);
CREATE INDEX IF NOT EXISTS idx_usage_anomalies_is_ongoing ON usage_anomalies(is_ongoing);
CREATE INDEX IF NOT EXISTS idx_usage_anomalies_is_resolved ON usage_anomalies(is_resolved);
CREATE INDEX IF NOT EXISTS idx_usage_anomalies_company_date ON usage_anomalies(company_id, detected_at);

-- Performance metrics indexes
CREATE INDEX IF NOT EXISTS idx_performance_metrics_timestamp ON performance_metrics(metric_timestamp);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_redis_status ON performance_metrics(redis_status);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_database_status ON performance_metrics(database_status);

-- Usage reports indexes
CREATE INDEX IF NOT EXISTS idx_usage_reports_company_id ON usage_reports(company_id);
CREATE INDEX IF NOT EXISTS idx_usage_reports_period_type ON usage_reports(period_type);
CREATE INDEX IF NOT EXISTS idx_usage_reports_generated_at ON usage_reports(generated_at);
CREATE INDEX IF NOT EXISTS idx_usage_reports_period_range ON usage_reports(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_usage_reports_company_period ON usage_reports(company_id, period_start);

-- Real-time metrics indexes
CREATE INDEX IF NOT EXISTS idx_real_time_metrics_company_id ON real_time_metrics_history(company_id);
CREATE INDEX IF NOT EXISTS idx_real_time_metrics_timestamp ON real_time_metrics_history(metric_timestamp);
CREATE INDEX IF NOT EXISTS idx_real_time_metrics_company_time ON real_time_metrics_history(company_id, metric_timestamp);

-- Monitoring configs indexes
CREATE INDEX IF NOT EXISTS idx_monitoring_configs_company_id ON monitoring_configs(company_id);
CREATE INDEX IF NOT EXISTS idx_monitoring_configs_enabled ON monitoring_configs(anomaly_detection_enabled);

-- ============================================================================
-- CREATE VIEWS
-- ============================================================================

-- Active anomalies view
CREATE OR REPLACE VIEW active_anomalies AS
SELECT 
    ua.*,
    c.name as company_name,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - ua.detected_at))/3600 as hours_since_detection
FROM usage_anomalies ua
JOIN companies c ON ua.company_id = c.id
WHERE ua.is_ongoing = true 
    AND ua.is_resolved = false
    AND ua.detected_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
ORDER BY ua.severity DESC, ua.detected_at DESC;

-- System health overview
CREATE OR REPLACE VIEW system_health_overview AS
SELECT 
    metric_timestamp,
    redis_status,
    database_status,
    cache_hit_rate,
    avg_rate_limit_check_time_ms,
    requests_processed_per_second,
    rate_limit_errors + quota_calculation_errors + cache_errors as total_errors,
    CASE 
        WHEN redis_status = 'healthy' AND database_status = 'healthy' 
             AND cache_hit_rate >= 80 AND avg_rate_limit_check_time_ms < 10
        THEN 'healthy'
        WHEN redis_status = 'unhealthy' OR database_status = 'unhealthy'
        THEN 'critical'
        ELSE 'degraded'
    END as overall_health_status
FROM performance_metrics
WHERE metric_timestamp >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
ORDER BY metric_timestamp DESC;

-- Company monitoring summary
CREATE OR REPLACE VIEW company_monitoring_summary AS
SELECT 
    c.id as company_id,
    c.name as company_name,
    mc.anomaly_detection_enabled,
    mc.anomaly_sensitivity,
    
    -- Recent anomalies
    COUNT(ua.id) FILTER (WHERE ua.detected_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours') as anomalies_last_24h,
    COUNT(ua.id) FILTER (WHERE ua.is_ongoing = true) as ongoing_anomalies,
    MAX(ua.detected_at) as last_anomaly_detected,
    
    -- Recent reports
    COUNT(ur.id) FILTER (WHERE ur.generated_at >= CURRENT_TIMESTAMP - INTERVAL '7 days') as reports_last_week,
    MAX(ur.generated_at) as last_report_generated,
    
    mc.updated_at as config_last_updated
FROM companies c
LEFT JOIN monitoring_configs mc ON c.id = mc.company_id
LEFT JOIN usage_anomalies ua ON c.id = ua.company_id AND ua.detected_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
LEFT JOIN usage_reports ur ON c.id = ur.company_id AND ur.generated_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
WHERE c.status = 'active'
GROUP BY c.id, c.name, mc.anomaly_detection_enabled, mc.anomaly_sensitivity, mc.updated_at
ORDER BY anomalies_last_24h DESC, last_anomaly_detected DESC NULLS LAST;

-- ============================================================================
-- CREATE FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Function to update monitoring config timestamps
CREATE OR REPLACE FUNCTION update_monitoring_config_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for monitoring configs
DROP TRIGGER IF EXISTS monitoring_config_update_timestamp ON monitoring_configs;
CREATE TRIGGER monitoring_config_update_timestamp
    BEFORE UPDATE ON monitoring_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_monitoring_config_timestamp();

-- Function to update usage anomaly timestamps
CREATE OR REPLACE FUNCTION update_anomaly_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    
    -- Auto-resolve anomalies older than 24 hours if still marked as ongoing
    IF NEW.is_ongoing = true AND NEW.detected_at < CURRENT_TIMESTAMP - INTERVAL '24 hours' THEN
        NEW.is_ongoing = false;
        NEW.resolved_at = CURRENT_TIMESTAMP;
        NEW.resolved_by = 'system_auto';
        NEW.resolution_notes = 'Auto-resolved: anomaly older than 24 hours';
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for usage anomalies
DROP TRIGGER IF EXISTS anomaly_update_timestamp ON usage_anomalies;
CREATE TRIGGER anomaly_update_timestamp
    BEFORE UPDATE ON usage_anomalies
    FOR EACH ROW
    EXECUTE FUNCTION update_anomaly_timestamp();

-- ============================================================================
-- INSERT DEFAULT DATA
-- ============================================================================

-- Insert default monitoring configurations for existing companies
INSERT INTO monitoring_configs (
    company_id, anomaly_detection_enabled, anomaly_sensitivity,
    anomaly_notification_enabled, anomaly_notification_threshold,
    real_time_monitoring_interval_seconds, anomaly_check_interval_minutes
)
SELECT 
    c.id as company_id,
    true as anomaly_detection_enabled,
    CASE 
        WHEN rlc.tier = 'enterprise' THEN 'high'
        WHEN rlc.tier = 'premium' THEN 'medium'
        ELSE 'low'
    END as anomaly_sensitivity,
    true as anomaly_notification_enabled,
    CASE 
        WHEN rlc.tier IN ('enterprise', 'premium') THEN 'warning'
        ELSE 'critical'
    END as anomaly_notification_threshold,
    CASE 
        WHEN rlc.tier = 'enterprise' THEN 30
        WHEN rlc.tier = 'premium' THEN 60
        ELSE 300
    END as real_time_monitoring_interval_seconds,
    CASE 
        WHEN rlc.tier IN ('enterprise', 'premium') THEN 5
        ELSE 15
    END as anomaly_check_interval_minutes
FROM companies c
LEFT JOIN rate_limit_configs rlc ON c.id = rlc.company_id
WHERE c.id NOT IN (SELECT company_id FROM monitoring_configs WHERE company_id IS NOT NULL)
    AND c.status = 'active'
ON CONFLICT (company_id) DO NOTHING;

-- ============================================================================
-- ADD COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE system_alerts IS 'System-wide alerts for monitoring infrastructure health and performance';
COMMENT ON TABLE usage_anomalies IS 'Detected usage anomalies with statistical analysis and recommendations';
COMMENT ON TABLE performance_metrics IS 'System performance metrics collected over time';
COMMENT ON TABLE usage_reports IS 'Generated usage reports with analytics and insights';
COMMENT ON TABLE real_time_metrics_history IS 'Historical backup of real-time metrics for companies';
COMMENT ON TABLE monitoring_configs IS 'Company-specific monitoring and alerting configurations';

COMMENT ON VIEW active_anomalies IS 'Currently active and unresolved anomalies across all companies';
COMMENT ON VIEW system_health_overview IS 'Real-time system health status and performance indicators';
COMMENT ON VIEW company_monitoring_summary IS 'Monitoring summary for all companies including anomaly and report statistics';

-- ============================================================================
-- RECORD MIGRATION
-- ============================================================================

-- Record this migration as completed
INSERT INTO schema_migrations (version, description, rollback_sql) VALUES (
    '003_monitoring_system',
    'Added comprehensive monitoring, anomaly detection, and analytics system',
    '-- Rollback script for migration 003_monitoring_system
    DROP VIEW IF EXISTS company_monitoring_summary;
    DROP VIEW IF EXISTS system_health_overview;
    DROP VIEW IF EXISTS active_anomalies;
    DROP TRIGGER IF EXISTS anomaly_update_timestamp ON usage_anomalies;
    DROP TRIGGER IF EXISTS monitoring_config_update_timestamp ON monitoring_configs;
    DROP FUNCTION IF EXISTS update_anomaly_timestamp();
    DROP FUNCTION IF EXISTS update_monitoring_config_timestamp();
    DROP TABLE IF EXISTS monitoring_configs;
    DROP TABLE IF EXISTS real_time_metrics_history;
    DROP TABLE IF EXISTS usage_reports;
    DROP TABLE IF EXISTS performance_metrics;
    DROP TABLE IF EXISTS usage_anomalies;
    DROP TABLE IF EXISTS system_alerts;'
);

RAISE NOTICE 'Migration 003_monitoring_system completed successfully!';