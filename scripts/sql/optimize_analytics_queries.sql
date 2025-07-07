-- Analytics Query Optimization
-- Add indexes and optimize queries for better performance

-- 1. Create partitioned tables for high-volume data (requests table)
-- This helps with query performance on date ranges

-- Create partition function for requests table by month
CREATE OR REPLACE FUNCTION create_monthly_partition(table_name text, start_date date)
RETURNS void AS $$
DECLARE
    partition_name text;
    start_timestamp timestamp;
    end_timestamp timestamp;
BEGIN
    partition_name := table_name || '_' || to_char(start_date, 'YYYY_MM');
    start_timestamp := start_date::timestamp;
    end_timestamp := (start_date + interval '1 month')::timestamp;
    
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF %I 
                    FOR VALUES FROM (%L) TO (%L)',
                    partition_name, table_name, start_timestamp, end_timestamp);
END;
$$ LANGUAGE plpgsql;

-- 2. Create materialized views for expensive aggregations

-- Materialized view for hourly analytics summary
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_hourly_analytics_summary AS
SELECT 
    company_id,
    hour_bucket_utc,
    COUNT(DISTINCT client_user_id) as unique_users,
    COUNT(DISTINCT vendor_id) as unique_vendors,
    COUNT(DISTINCT model_id) as unique_models,
    SUM(request_count) as total_requests,
    SUM(success_count) as total_success,
    SUM(error_count) as total_errors,
    SUM(total_tokens) as total_tokens,
    SUM(total_cost) as total_cost,
    AVG(avg_latency_ms) as avg_latency
FROM user_analytics_hourly
GROUP BY company_id, hour_bucket_utc;

CREATE UNIQUE INDEX idx_mv_hourly_summary_unique 
ON mv_hourly_analytics_summary(company_id, hour_bucket_utc);

-- Materialized view for daily cost rankings
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_cost_rankings AS
WITH ranked_users AS (
    SELECT 
        company_id, 
        client_user_id, 
        date,
        total_cost,
        total_requests,
        ROW_NUMBER() OVER (PARTITION BY company_id, date ORDER BY total_cost DESC) as cost_rank,
        PERCENT_RANK() OVER (PARTITION BY company_id, date ORDER BY total_cost) as cost_percentile
    FROM user_analytics_daily
)
SELECT * FROM ranked_users;

CREATE UNIQUE INDEX idx_mv_daily_rankings_unique 
ON mv_daily_cost_rankings(company_id, client_user_id, date);

-- 3. Create indexes for session analytics queries

-- Index for session window calculations
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_requests_session_calc
ON requests(client_user_id, ip_address, timestamp_utc)
WHERE client_user_id IS NOT NULL AND ip_address IS NOT NULL;

-- Index for user activity patterns
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_requests_user_activity
ON requests(client_user_id, timestamp_utc DESC, total_cost)
WHERE client_user_id IS NOT NULL;

-- 4. Create function for optimized hourly analytics population
CREATE OR REPLACE FUNCTION populate_hourly_analytics_optimized(
    p_hour_start timestamp with time zone,
    p_hour_end timestamp with time zone
) RETURNS TABLE(processed_records bigint) AS $$
BEGIN
    -- Use UPSERT with better performance
    WITH aggregated_data AS (
        SELECT 
            r.company_id,
            r.client_user_id,
            r.vendor_id,
            r.model_id,
            date_trunc('hour', r.timestamp_utc) as hour_bucket_utc,
            COUNT(*) as request_count,
            COUNT(*) FILTER (WHERE r.status_code < 400) as success_count,
            COUNT(*) FILTER (WHERE r.status_code >= 400) as error_count,
            COALESCE(SUM(r.total_tokens), 0) as total_tokens,
            COALESCE(SUM(r.total_cost), 0) as total_cost,
            COALESCE(AVG(r.total_latency_ms), 0) as avg_latency_ms
        FROM requests r
        WHERE r.timestamp_utc >= p_hour_start 
          AND r.timestamp_utc < p_hour_end
          AND r.client_user_id IS NOT NULL
          AND r.vendor_id IS NOT NULL
          AND r.model_id IS NOT NULL
        GROUP BY 1, 2, 3, 4, 5
    )
    INSERT INTO user_analytics_hourly (
        company_id, client_user_id, vendor_id, model_id,
        hour_bucket_utc, hour_bucket_local, timezone_name,
        request_count, success_count, error_count,
        total_tokens, total_cost, avg_latency_ms
    )
    SELECT 
        company_id, client_user_id, vendor_id, model_id,
        hour_bucket_utc, hour_bucket_utc, 'UTC',
        request_count, success_count, error_count,
        total_tokens, total_cost, avg_latency_ms
    FROM aggregated_data
    ON CONFLICT (company_id, client_user_id, vendor_id, model_id, hour_bucket_utc) 
    DO UPDATE SET
        request_count = EXCLUDED.request_count,
        success_count = EXCLUDED.success_count,
        error_count = EXCLUDED.error_count,
        total_tokens = EXCLUDED.total_tokens,
        total_cost = EXCLUDED.total_cost,
        avg_latency_ms = EXCLUDED.avg_latency_ms,
        updated_at = NOW();
    
    RETURN QUERY SELECT COUNT(*)::bigint FROM aggregated_data;
END;
$$ LANGUAGE plpgsql;

-- 5. Create function for optimized session creation
CREATE OR REPLACE FUNCTION create_user_sessions_optimized(
    p_start_date timestamp with time zone DEFAULT NOW() - INTERVAL '7 days',
    p_end_date timestamp with time zone DEFAULT NOW()
) RETURNS TABLE(sessions_created bigint) AS $$
BEGIN
    -- More efficient session creation using window functions
    WITH session_windows AS (
        SELECT 
            company_id,
            client_user_id,
            ip_address,
            user_id_header,
            timestamp_utc,
            -- Calculate session boundaries using lag
            CASE 
                WHEN timestamp_utc - LAG(timestamp_utc) OVER (
                    PARTITION BY client_user_id, ip_address 
                    ORDER BY timestamp_utc
                ) > INTERVAL '30 minutes' 
                OR LAG(timestamp_utc) OVER (
                    PARTITION BY client_user_id, ip_address 
                    ORDER BY timestamp_utc
                ) IS NULL
                THEN 1 
                ELSE 0 
            END as new_session
        FROM requests
        WHERE timestamp_utc BETWEEN p_start_date AND p_end_date
          AND client_user_id IS NOT NULL
          AND ip_address IS NOT NULL
    ),
    session_groups AS (
        SELECT *,
            SUM(new_session) OVER (
                PARTITION BY client_user_id, ip_address 
                ORDER BY timestamp_utc
            ) as session_group
        FROM session_windows
    ),
    session_aggregates AS (
        SELECT 
            company_id,
            client_user_id,
            ip_address,
            user_id_header,
            session_group,
            MIN(timestamp_utc) as started_at,
            MAX(timestamp_utc) as ended_at,
            COUNT(*) as request_count,
            SUM(total_cost) as total_cost
        FROM session_groups sg
        JOIN requests r USING (client_user_id, ip_address, timestamp_utc)
        GROUP BY company_id, client_user_id, ip_address, user_id_header, session_group
    )
    INSERT INTO user_sessions (
        client_user_id, session_id, ip_address,
        started_at_utc, ended_at_utc, last_activity_at_utc,
        request_count, total_cost_usd
    )
    SELECT 
        client_user_id,
        'session_' || md5(client_user_id::text || ip_address::text || started_at::text)::text as session_id,
        ip_address,
        started_at,
        ended_at,
        ended_at,
        request_count,
        total_cost
    FROM session_aggregates
    ON CONFLICT (session_id) DO NOTHING;
    
    RETURN QUERY SELECT COUNT(*)::bigint FROM session_aggregates;
END;
$$ LANGUAGE plpgsql;

-- 6. Add refresh functions for materialized views
CREATE OR REPLACE FUNCTION refresh_analytics_materialized_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_hourly_analytics_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_cost_rankings;
END;
$$ LANGUAGE plpgsql;

-- 7. Create scheduled job to refresh materialized views (using pg_cron if available)
-- This would be run as: SELECT cron.schedule('refresh-analytics-views', '0 * * * *', 'SELECT refresh_analytics_materialized_views();');

COMMENT ON FUNCTION populate_hourly_analytics_optimized IS 'Optimized version of hourly analytics population using better aggregation';
COMMENT ON FUNCTION create_user_sessions_optimized IS 'Optimized session creation using window functions for better performance';
COMMENT ON MATERIALIZED VIEW mv_hourly_analytics_summary IS 'Pre-aggregated hourly analytics for faster dashboard queries';
COMMENT ON MATERIALIZED VIEW mv_daily_cost_rankings IS 'Pre-calculated daily cost rankings for faster user analytics';