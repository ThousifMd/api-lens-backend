-- Migration: Add performance indexes for analytics and query optimization
-- This migration adds composite indexes to improve query performance

-- Analytics table indexes
-- Composite index for hourly analytics aggregation queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_analytics_hourly_composite 
ON user_analytics_hourly(company_id, time_bucket, vendor_id, model_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_analytics_hourly_time_company
ON user_analytics_hourly(time_bucket DESC, company_id);

-- Composite index for daily analytics aggregation queries  
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_analytics_daily_composite
ON user_analytics_daily(company_id, date, vendor_id, model_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_analytics_daily_date_company
ON user_analytics_daily(date DESC, company_id);

-- Session analytics indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_sessions_composite
ON user_sessions(company_id, user_id, session_start DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_sessions_time_window
ON user_sessions(session_start, session_end)
WHERE session_end IS NOT NULL;

-- Requests table indexes for common query patterns
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_requests_company_created
ON requests(company_id, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_requests_api_key_created
ON requests(api_key_id, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_requests_vendor_model_status
ON requests(vendor_id, model_id, status)
WHERE status IN ('success', 'error');

-- Cost monitoring indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cost_calculations_request_id
ON cost_calculations(request_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_requests_cost_monitoring
ON requests(company_id, created_at DESC)
WHERE total_cost > 0;

-- Vendor pricing lookup optimization
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_vendor_pricing_lookup
ON vendor_pricing(vendor_id, model_type, is_active)
WHERE is_active = true;

-- Client users lookup optimization
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_client_users_company_user
ON client_users(company_id, user_id);

-- API keys active lookup
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_api_keys_active
ON api_keys(company_id, is_active)
WHERE is_active = true;

-- Add partial indexes for common filtered queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_requests_recent_errors
ON requests(company_id, created_at DESC)
WHERE status = 'error' AND created_at > NOW() - INTERVAL '7 days';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_requests_high_latency
ON requests(company_id, latency_ms DESC)
WHERE latency_ms > 1000;

-- Create indexes for foreign key lookups (if not already present)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_requests_company_id 
ON requests(company_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_requests_vendor_id
ON requests(vendor_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_requests_model_id
ON requests(model_id);

-- Add comment to track migration
COMMENT ON INDEX idx_user_analytics_hourly_composite IS 'Composite index for analytics aggregation queries - Migration 009';
COMMENT ON INDEX idx_user_analytics_daily_composite IS 'Composite index for daily analytics queries - Migration 009';
COMMENT ON INDEX idx_requests_company_created IS 'Index for company request history queries - Migration 009';