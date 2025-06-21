-- Migration: Admin System and Audit Logging
-- Version: 004
-- Description: Adds admin user management and audit logging tables
-- Depends on: 003_monitoring_system_migration

-- ============================================================================
-- MIGRATION SAFETY CHECKS
-- ============================================================================

DO $$
BEGIN
    -- Check if this migration has already been applied
    IF EXISTS (SELECT 1 FROM schema_migrations WHERE version = '004_admin_system') THEN
        RAISE NOTICE 'Migration 004_admin_system already applied, skipping...';
        RETURN;
    END IF;
    
    -- Check if prerequisite migration exists
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = '003_monitoring_system') THEN
        RAISE EXCEPTION 'Prerequisite migration 003_monitoring_system must be applied first';
    END IF;
    
    RAISE NOTICE 'Applying migration 004_admin_system...';
END
$$;

-- ============================================================================
-- CREATE ADMIN SYSTEM TABLES
-- ============================================================================

-- Admin users table
CREATE TABLE IF NOT EXISTS admin_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    
    -- Role and permissions
    role VARCHAR(50) NOT NULL CHECK (role IN ('super_admin', 'system_admin', 'support_admin', 'billing_admin')),
    is_active BOOLEAN DEFAULT true,
    
    -- Security tracking
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE,
    last_login_at TIMESTAMP WITH TIME ZONE,
    password_changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Two-factor authentication
    totp_secret VARCHAR(32), -- For TOTP 2FA
    backup_codes JSONB DEFAULT '[]', -- Emergency backup codes
    two_factor_enabled BOOLEAN DEFAULT false,
    
    -- Session management
    active_sessions JSONB DEFAULT '[]', -- Track active sessions
    max_concurrent_sessions INTEGER DEFAULT 3,
    
    -- Profile information
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(20),
    timezone VARCHAR(50) DEFAULT 'UTC',
    
    -- Audit fields
    created_by VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_password_change TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Admin audit log table
CREATE TABLE IF NOT EXISTS admin_audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    username VARCHAR(50), -- Store username for deleted users
    
    -- Action details
    action VARCHAR(100) NOT NULL, -- 'login_success', 'login_failed', 'company_created', etc.
    resource_type VARCHAR(50), -- 'company', 'user', 'system', 'pricing', etc.
    resource_id VARCHAR(255), -- ID of affected resource
    
    -- Request context
    ip_address INET,
    user_agent TEXT,
    session_id VARCHAR(255),
    request_id VARCHAR(255),
    
    -- Action details
    details JSONB DEFAULT '{}', -- Additional action-specific data
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    
    -- Risk assessment
    risk_level VARCHAR(20) DEFAULT 'low' CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    requires_approval BOOLEAN DEFAULT false,
    approved_by UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    approved_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Admin sessions table
CREATE TABLE IF NOT EXISTS admin_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES admin_users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    
    -- Session metadata
    ip_address INET,
    user_agent TEXT,
    device_fingerprint VARCHAR(255),
    location_info JSONB DEFAULT '{}', -- Country, city, etc.
    
    -- Session lifecycle
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active BOOLEAN DEFAULT true,
    
    -- Security flags
    is_suspicious BOOLEAN DEFAULT false,
    terminated_by VARCHAR(50), -- 'user', 'admin', 'system', 'timeout'
    terminated_at TIMESTAMP WITH TIME ZONE,
    termination_reason TEXT
);

-- System configuration table
CREATE TABLE IF NOT EXISTS system_configurations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value JSONB NOT NULL,
    data_type VARCHAR(20) NOT NULL CHECK (data_type IN ('string', 'number', 'boolean', 'object', 'array')),
    
    -- Metadata
    description TEXT,
    category VARCHAR(50) DEFAULT 'general', -- 'security', 'performance', 'features', etc.
    is_sensitive BOOLEAN DEFAULT false, -- Whether to mask in logs
    is_readonly BOOLEAN DEFAULT false, -- Whether value can be changed via API
    
    -- Validation
    validation_schema JSONB, -- JSON schema for validation
    allowed_values JSONB, -- Array of allowed values for enum-type configs
    min_value DECIMAL(20,8), -- For numeric configs
    max_value DECIMAL(20,8), -- For numeric configs
    
    -- Change tracking
    previous_value JSONB,
    changed_by UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    change_reason TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Admin permissions table (for granular permissions beyond roles)
CREATE TABLE IF NOT EXISTS admin_permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES admin_users(id) ON DELETE CASCADE,
    permission VARCHAR(100) NOT NULL, -- Specific permission like 'view_company:company_123'
    granted_by UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE, -- For temporary permissions
    is_active BOOLEAN DEFAULT true,
    
    -- Context
    resource_type VARCHAR(50), -- 'company', 'system', etc.
    resource_id VARCHAR(255), -- Specific resource ID
    conditions JSONB DEFAULT '{}', -- Additional conditions for permission
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Admin notifications table
CREATE TABLE IF NOT EXISTS admin_notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES admin_users(id) ON DELETE CASCADE,
    
    -- Notification content
    type VARCHAR(50) NOT NULL, -- 'security_alert', 'system_alert', 'approval_request', etc.
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    priority VARCHAR(20) DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    
    -- Notification state
    is_read BOOLEAN DEFAULT false,
    read_at TIMESTAMP WITH TIME ZONE,
    is_dismissed BOOLEAN DEFAULT false,
    dismissed_at TIMESTAMP WITH TIME ZONE,
    
    -- Action tracking
    action_required BOOLEAN DEFAULT false,
    action_url TEXT, -- URL for action button
    action_completed BOOLEAN DEFAULT false,
    action_completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    source VARCHAR(100), -- Source system or component
    correlation_id VARCHAR(255), -- For grouping related notifications
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- CREATE INDEXES
-- ============================================================================

-- Admin users indexes
CREATE INDEX IF NOT EXISTS idx_admin_users_username ON admin_users(username);
CREATE INDEX IF NOT EXISTS idx_admin_users_email ON admin_users(email);
CREATE INDEX IF NOT EXISTS idx_admin_users_role ON admin_users(role);
CREATE INDEX IF NOT EXISTS idx_admin_users_is_active ON admin_users(is_active);
CREATE INDEX IF NOT EXISTS idx_admin_users_last_login ON admin_users(last_login_at);

-- Admin audit log indexes
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_user_id ON admin_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_action ON admin_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_resource_type ON admin_audit_log(resource_type);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_created_at ON admin_audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_risk_level ON admin_audit_log(risk_level);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_user_action ON admin_audit_log(user_id, action);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_resource ON admin_audit_log(resource_type, resource_id);

-- Admin sessions indexes
CREATE INDEX IF NOT EXISTS idx_admin_sessions_user_id ON admin_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_session_token ON admin_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_is_active ON admin_sessions(is_active);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_expires_at ON admin_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_last_activity ON admin_sessions(last_activity_at);

-- System configurations indexes
CREATE INDEX IF NOT EXISTS idx_system_configurations_config_key ON system_configurations(config_key);
CREATE INDEX IF NOT EXISTS idx_system_configurations_category ON system_configurations(category);
CREATE INDEX IF NOT EXISTS idx_system_configurations_is_sensitive ON system_configurations(is_sensitive);

-- Admin permissions indexes
CREATE INDEX IF NOT EXISTS idx_admin_permissions_user_id ON admin_permissions(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_permissions_permission ON admin_permissions(permission);
CREATE INDEX IF NOT EXISTS idx_admin_permissions_resource ON admin_permissions(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_admin_permissions_is_active ON admin_permissions(is_active);
CREATE INDEX IF NOT EXISTS idx_admin_permissions_expires_at ON admin_permissions(expires_at);

-- Admin notifications indexes
CREATE INDEX IF NOT EXISTS idx_admin_notifications_user_id ON admin_notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_notifications_type ON admin_notifications(type);
CREATE INDEX IF NOT EXISTS idx_admin_notifications_is_read ON admin_notifications(is_read);
CREATE INDEX IF NOT EXISTS idx_admin_notifications_priority ON admin_notifications(priority);
CREATE INDEX IF NOT EXISTS idx_admin_notifications_created_at ON admin_notifications(created_at);

-- ============================================================================
-- CREATE VIEWS
-- ============================================================================

-- Active admin sessions view
CREATE OR REPLACE VIEW active_admin_sessions AS
SELECT 
    s.*,
    u.username,
    u.email,
    u.role,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - s.last_activity_at))/60 as minutes_since_activity,
    EXTRACT(EPOCH FROM (s.expires_at - CURRENT_TIMESTAMP))/60 as minutes_until_expiry
FROM admin_sessions s
JOIN admin_users u ON s.user_id = u.id
WHERE s.is_active = true 
    AND s.expires_at > CURRENT_TIMESTAMP
ORDER BY s.last_activity_at DESC;

-- Admin audit summary view
CREATE OR REPLACE VIEW admin_audit_summary AS
SELECT 
    u.username,
    u.email,
    u.role,
    COUNT(al.*) as total_actions,
    COUNT(CASE WHEN al.created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours' THEN 1 END) as actions_last_24h,
    COUNT(CASE WHEN al.created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days' THEN 1 END) as actions_last_7d,
    COUNT(CASE WHEN al.success = false THEN 1 END) as failed_actions,
    MAX(al.created_at) as last_action_at,
    COUNT(CASE WHEN al.risk_level IN ('high', 'critical') THEN 1 END) as high_risk_actions
FROM admin_users u
LEFT JOIN admin_audit_log al ON u.id = al.user_id
WHERE u.is_active = true
GROUP BY u.id, u.username, u.email, u.role
ORDER BY actions_last_24h DESC;

-- Security alerts view
CREATE OR REPLACE VIEW security_alerts AS
SELECT 
    al.*,
    u.username,
    u.email,
    u.role
FROM admin_audit_log al
LEFT JOIN admin_users u ON al.user_id = u.id
WHERE al.risk_level IN ('high', 'critical')
    OR al.action IN ('login_failed', 'suspicious_activity', 'permission_denied')
    OR al.success = false
ORDER BY al.created_at DESC;

-- ============================================================================
-- CREATE FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Function to update admin user timestamps
CREATE OR REPLACE FUNCTION update_admin_user_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    
    -- Track password changes
    IF OLD.password_hash IS DISTINCT FROM NEW.password_hash THEN
        NEW.password_changed_at = CURRENT_TIMESTAMP;
        NEW.last_password_change = CURRENT_TIMESTAMP;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for admin users
DROP TRIGGER IF EXISTS admin_user_update_timestamp ON admin_users;
CREATE TRIGGER admin_user_update_timestamp
    BEFORE UPDATE ON admin_users
    FOR EACH ROW
    EXECUTE FUNCTION update_admin_user_timestamp();

-- Function to update system config timestamps
CREATE OR REPLACE FUNCTION update_system_config_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    NEW.previous_value = OLD.config_value;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for system configurations
DROP TRIGGER IF EXISTS system_config_update_timestamp ON system_configurations;
CREATE TRIGGER system_config_update_timestamp
    BEFORE UPDATE ON system_configurations
    FOR EACH ROW
    EXECUTE FUNCTION update_system_config_timestamp();

-- Function to cleanup expired sessions
CREATE OR REPLACE FUNCTION cleanup_expired_admin_sessions()
RETURNS INTEGER AS $$
DECLARE
    cleanup_count INTEGER;
BEGIN
    UPDATE admin_sessions 
    SET is_active = false,
        terminated_by = 'system',
        terminated_at = CURRENT_TIMESTAMP,
        termination_reason = 'Session expired'
    WHERE is_active = true 
        AND expires_at < CURRENT_TIMESTAMP;
    
    GET DIAGNOSTICS cleanup_count = ROW_COUNT;
    
    RETURN cleanup_count;
END;
$$ LANGUAGE plpgsql;

-- Function to auto-resolve old notifications
CREATE OR REPLACE FUNCTION cleanup_old_admin_notifications()
RETURNS INTEGER AS $$
DECLARE
    cleanup_count INTEGER;
BEGIN
    UPDATE admin_notifications 
    SET is_dismissed = true,
        dismissed_at = CURRENT_TIMESTAMP
    WHERE is_dismissed = false 
        AND created_at < CURRENT_TIMESTAMP - INTERVAL '30 days'
        AND priority = 'low';
    
    GET DIAGNOSTICS cleanup_count = ROW_COUNT;
    
    RETURN cleanup_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- INSERT DEFAULT SYSTEM CONFIGURATIONS
-- ============================================================================

-- Insert default system configurations
INSERT INTO system_configurations (config_key, config_value, data_type, description, category) VALUES
-- Security settings
('admin_session_timeout_hours', '24', 'number', 'Admin session timeout in hours', 'security'),
('max_failed_login_attempts', '5', 'number', 'Maximum failed login attempts before account lock', 'security'),
('account_lockout_duration_minutes', '60', 'number', 'Account lockout duration in minutes', 'security'),
('password_min_length', '8', 'number', 'Minimum password length for admin users', 'security'),
('require_2fa_for_admin', 'false', 'boolean', 'Require two-factor authentication for admin users', 'security'),

-- System settings
('maintenance_mode', 'false', 'boolean', 'Enable maintenance mode', 'system'),
('audit_log_retention_days', '365', 'number', 'Number of days to retain audit logs', 'system'),
('max_concurrent_admin_sessions', '3', 'number', 'Maximum concurrent sessions per admin user', 'system'),
('system_timezone', '"UTC"', 'string', 'Default system timezone', 'system'),

-- Performance settings
('cache_default_ttl_seconds', '3600', 'number', 'Default cache TTL in seconds', 'performance'),
('rate_limit_default_requests_per_minute', '100', 'number', 'Default rate limit requests per minute', 'performance'),
('monitoring_data_retention_days', '90', 'number', 'Number of days to retain monitoring data', 'performance'),

-- Feature flags
('anomaly_detection_enabled', 'true', 'boolean', 'Enable anomaly detection system', 'features'),
('cost_optimization_suggestions', 'true', 'boolean', 'Enable cost optimization suggestions', 'features'),
('advanced_analytics_enabled', 'true', 'boolean', 'Enable advanced analytics features', 'features'),
('real_time_monitoring_enabled', 'true', 'boolean', 'Enable real-time monitoring', 'features')

ON CONFLICT (config_key) DO NOTHING;

-- ============================================================================
-- ADD COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE admin_users IS 'Administrative users with role-based access control';
COMMENT ON TABLE admin_audit_log IS 'Comprehensive audit log for all admin actions';
COMMENT ON TABLE admin_sessions IS 'Active admin user sessions with security tracking';
COMMENT ON TABLE system_configurations IS 'System-wide configuration settings';
COMMENT ON TABLE admin_permissions IS 'Granular permissions beyond role-based access';
COMMENT ON TABLE admin_notifications IS 'Admin notifications and alerts system';

COMMENT ON VIEW active_admin_sessions IS 'Currently active admin sessions with user details';
COMMENT ON VIEW admin_audit_summary IS 'Summary of admin user activity and audit statistics';
COMMENT ON VIEW security_alerts IS 'Security-related events requiring attention';

-- ============================================================================
-- RECORD MIGRATION
-- ============================================================================

-- Record this migration as completed
INSERT INTO schema_migrations (version, description, rollback_sql) VALUES (
    '004_admin_system',
    'Added comprehensive admin system with authentication, audit logging, and configuration management',
    '-- Rollback script for migration 004_admin_system
    DROP VIEW IF EXISTS security_alerts;
    DROP VIEW IF EXISTS admin_audit_summary;
    DROP VIEW IF EXISTS active_admin_sessions;
    DROP FUNCTION IF EXISTS cleanup_old_admin_notifications();
    DROP FUNCTION IF EXISTS cleanup_expired_admin_sessions();
    DROP TRIGGER IF EXISTS system_config_update_timestamp ON system_configurations;
    DROP TRIGGER IF EXISTS admin_user_update_timestamp ON admin_users;
    DROP FUNCTION IF EXISTS update_system_config_timestamp();
    DROP FUNCTION IF EXISTS update_admin_user_timestamp();
    DROP TABLE IF EXISTS admin_notifications;
    DROP TABLE IF EXISTS admin_permissions;
    DROP TABLE IF EXISTS system_configurations;
    DROP TABLE IF EXISTS admin_sessions;
    DROP TABLE IF EXISTS admin_audit_log;
    DROP TABLE IF EXISTS admin_users;'
);

RAISE NOTICE 'Migration 004_admin_system completed successfully!';