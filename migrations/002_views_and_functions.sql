-- ============================================================================
-- Views and Functions for API Lens Schema
-- ============================================================================

-- ============================================================================
-- Optimized Views for Dashboard
-- ============================================================================

-- Real-time top users by cost (last 24 hours)
CREATE VIEW top_users_realtime AS
WITH user_costs AS (
    SELECT 
        r.company_id,
        r.client_user_id,
        cu.client_user_id as external_user_id,
        cu.display_name,
        cu.email,
        cu.user_tier,
        cu.metadata,
        SUM(r.total_cost) as total_cost,
        COUNT(*) as request_count,
        SUM(r.total_tokens) as total_tokens,
        AVG(r.total_latency_ms)::NUMERIC(8,2) as avg_latency_ms,
        COUNT(DISTINCT r.model_id) as models_used,
        COUNT(DISTINCT DATE_TRUNC('hour', r.timestamp_utc)) as active_hours
    FROM requests r
    JOIN client_users cu ON r.client_user_id = cu.id
    WHERE r.timestamp_utc >= NOW() - INTERVAL '24 hours'
    GROUP BY r.company_id, r.client_user_id, cu.client_user_id, 
             cu.display_name, cu.email, cu.user_tier, cu.metadata
)
SELECT 
    c.slug as company_slug,
    uc.*,
    RANK() OVER (PARTITION BY uc.company_id ORDER BY uc.total_cost DESC) as cost_rank
FROM user_costs uc
JOIN companies c ON uc.company_id = c.id
ORDER BY uc.company_id, uc.total_cost DESC;

-- User model preferences with cost breakdown
CREATE VIEW user_model_usage AS
SELECT 
    c.slug as company_slug,
    cu.client_user_id as external_user_id,
    cu.display_name,
    v.display_name as vendor_name,
    vm.display_name as model_name,
    COUNT(*) as usage_count,
    SUM(r.total_cost) as total_cost,
    SUM(r.total_tokens) as total_tokens,
    AVG(r.total_latency_ms)::NUMERIC(8,2) as avg_latency_ms,
    (COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY cu.id))::NUMERIC(5,2) as usage_percentage
FROM requests r
JOIN companies c ON r.company_id = c.id
JOIN client_users cu ON r.client_user_id = cu.id
JOIN vendors v ON r.vendor_id = v.id
JOIN vendor_models vm ON r.model_id = vm.id
WHERE r.timestamp_utc >= NOW() - INTERVAL '30 days'
GROUP BY c.slug, cu.client_user_id, cu.display_name, cu.id, v.display_name, vm.display_name
ORDER BY cu.id, total_cost DESC;

-- Company-wide user analytics summary
CREATE VIEW company_user_summary AS
SELECT 
    c.id as company_id,
    c.slug as company_slug,
    COUNT(DISTINCT cu.id) as total_users,
    COUNT(DISTINCT CASE WHEN cu.last_seen_at >= NOW() - INTERVAL '24 hours' THEN cu.id END) as daily_active_users,
    COUNT(DISTINCT CASE WHEN cu.last_seen_at >= NOW() - INTERVAL '7 days' THEN cu.id END) as weekly_active_users,
    COUNT(DISTINCT CASE WHEN cu.last_seen_at >= NOW() - INTERVAL '30 days' THEN cu.id END) as monthly_active_users,
    SUM(cu.total_cost_usd) as total_revenue,
    AVG(cu.total_cost_usd)::NUMERIC(12,2) as avg_revenue_per_user,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY cu.total_cost_usd)::NUMERIC(12,2) as median_revenue_per_user,
    MAX(cu.total_cost_usd) as max_user_cost,
    COUNT(DISTINCT CASE WHEN cu.total_cost_usd > 100 THEN cu.id END) as high_value_users
FROM companies c
LEFT JOIN client_users cu ON c.id = cu.company_id AND cu.is_active = true
GROUP BY c.id, c.slug;

-- ============================================================================
-- Helper Functions (Enhanced)
-- ============================================================================

-- Function to get or create vendor
CREATE OR REPLACE FUNCTION get_or_create_vendor(p_vendor_name VARCHAR)
RETURNS UUID AS $$
DECLARE
    v_vendor_id UUID;
BEGIN
    -- Try to get existing vendor
    SELECT id INTO v_vendor_id FROM vendors WHERE name = p_vendor_name;
    
    -- Create if doesn't exist
    IF v_vendor_id IS NULL THEN
        INSERT INTO vendors (name, display_name) 
        VALUES (p_vendor_name, p_vendor_name) 
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
    -- Get or create vendor
    v_vendor_id := get_or_create_vendor(p_vendor_name);
    
    -- Try to get existing model
    SELECT id INTO v_model_id FROM vendor_models 
    WHERE vendor_id = v_vendor_id AND name = p_model_name;
    
    -- Create if doesn't exist
    IF v_model_id IS NULL THEN
        INSERT INTO vendor_models (vendor_id, name, display_name, model_type)
        VALUES (v_vendor_id, p_model_name, p_model_name, 'chat')
        RETURNING id INTO v_model_id;
    END IF;
    
    RETURN v_model_id;
END;
$$ LANGUAGE plpgsql;

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
    -- Try to get existing user
    SELECT id INTO v_user_id FROM client_users 
    WHERE company_id = p_company_id AND client_user_id = p_client_user_id;
    
    -- Create if doesn't exist
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

-- Function to handle request tracking with user ID validation
CREATE OR REPLACE FUNCTION track_request(
    p_request_id VARCHAR,
    p_api_key_hash VARCHAR,
    p_user_id_header VARCHAR,
    p_vendor_name VARCHAR,
    p_model_name VARCHAR,
    p_endpoint VARCHAR,
    p_method VARCHAR,
    p_status_code INTEGER,
    p_input_tokens INTEGER,
    p_output_tokens INTEGER,
    p_latency_ms INTEGER,
    p_vendor_latency_ms INTEGER,
    p_ip_address INET DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL,
    p_custom_headers JSONB DEFAULT '{}',
    p_error_message TEXT DEFAULT NULL,
    p_error_type VARCHAR DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_company_id UUID;
    v_api_key_id UUID;
    v_client_user_id UUID;
    v_vendor_id UUID;
    v_model_id UUID;
    v_input_cost NUMERIC(12, 8);
    v_output_cost NUMERIC(12, 8);
    v_request_id UUID;
    v_require_user_id BOOLEAN;
BEGIN
    -- Validate API key and get company
    SELECT ak.id, ak.company_id, c.require_user_id
    INTO v_api_key_id, v_company_id, v_require_user_id
    FROM api_keys ak
    JOIN companies c ON ak.company_id = c.id
    WHERE ak.key_hash = p_api_key_hash 
      AND ak.is_active = true 
      AND c.is_active = true;
    
    IF v_company_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or inactive API key';
    END IF;
    
    -- Validate user ID if required
    IF v_require_user_id AND (p_user_id_header IS NULL OR p_user_id_header = '') THEN
        RAISE EXCEPTION 'User ID header is required but not provided';
    END IF;
    
    -- Get or create user if user ID provided
    IF p_user_id_header IS NOT NULL AND p_user_id_header != '' THEN
        v_client_user_id := get_or_create_client_user(
            v_company_id, 
            p_user_id_header,
            NULL, -- display_name
            NULL, -- email
            p_custom_headers
        );
        
        -- Update user last seen
        UPDATE client_users 
        SET last_seen_at = NOW(),
            total_requests = total_requests + 1
        WHERE id = v_client_user_id;
    END IF;
    
    -- Get or create vendor and model
    v_model_id := get_or_create_vendor_model(p_vendor_name, p_model_name);
    v_vendor_id := get_or_create_vendor(p_vendor_name);
    
    -- Calculate costs
    SELECT 
        (p_input_tokens / 1000.0) * vp.input_cost_per_1k_tokens,
        (p_output_tokens / 1000.0) * vp.output_cost_per_1k_tokens
    INTO v_input_cost, v_output_cost
    FROM vendor_pricing vp
    WHERE vp.model_id = v_model_id 
      AND vp.is_active = true
    ORDER BY vp.effective_date DESC
    LIMIT 1;
    
    -- Insert request
    INSERT INTO requests (
        request_id, company_id, client_user_id, vendor_id, model_id,
        api_key_id, method, endpoint, user_id_header, custom_headers,
        status_code, input_tokens, output_tokens, input_cost, output_cost,
        total_latency_ms, vendor_latency_ms, ip_address, user_agent,
        error_message, error_type
    ) VALUES (
        p_request_id, v_company_id, v_client_user_id, v_vendor_id, v_model_id,
        v_api_key_id, p_method, p_endpoint, p_user_id_header, p_custom_headers,
        p_status_code, p_input_tokens, p_output_tokens, 
        COALESCE(v_input_cost, 0), COALESCE(v_output_cost, 0),
        p_latency_ms, p_vendor_latency_ms, p_ip_address, p_user_agent,
        p_error_message, p_error_type
    ) RETURNING id INTO v_request_id;
    
    -- Update user total cost if applicable
    IF v_client_user_id IS NOT NULL AND (v_input_cost + v_output_cost) > 0 THEN
        UPDATE client_users 
        SET total_cost_usd = total_cost_usd + (v_input_cost + v_output_cost)
        WHERE id = v_client_user_id;
    END IF;
    
    -- Update API key last used
    UPDATE api_keys SET last_used_at = NOW() WHERE id = v_api_key_id;
    
    RETURN v_request_id;
END;
$$ LANGUAGE plpgsql;

-- Function to check cost alerts
CREATE OR REPLACE FUNCTION check_cost_alerts()
RETURNS TABLE(alert_id UUID, alert_type VARCHAR, threshold_exceeded BOOLEAN, current_value NUMERIC) AS $$
BEGIN
    -- Check user daily alerts
    RETURN QUERY
    WITH user_daily_costs AS (
        SELECT 
            ca.id as alert_id,
            ca.alert_type,
            ca.threshold_usd,
            COALESCE(SUM(r.total_cost), 0) as current_cost
        FROM cost_alerts ca
        LEFT JOIN requests r ON r.client_user_id = ca.client_user_id
            AND r.timestamp_utc >= CURRENT_DATE
        WHERE ca.alert_type = 'user_daily'
          AND ca.is_active = true
        GROUP BY ca.id, ca.alert_type, ca.threshold_usd
    )
    SELECT 
        alert_id,
        alert_type,
        current_cost > threshold_usd as threshold_exceeded,
        current_cost as current_value
    FROM user_daily_costs
    WHERE current_cost > threshold_usd;
    
    -- Add other alert types as needed...
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Maintenance Functions
-- ============================================================================

-- Function to create next month's partition
CREATE OR REPLACE FUNCTION create_next_month_partition()
RETURNS void AS $$
DECLARE
    next_month_start date;
    next_month_end date;
    partition_name text;
BEGIN
    next_month_start := date_trunc('month', CURRENT_DATE + interval '1 month');
    next_month_end := next_month_start + interval '1 month';
    partition_name := 'requests_' || to_char(next_month_start, 'YYYY_MM');
    
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I PARTITION OF requests
        FOR VALUES FROM (%L) TO (%L)',
        partition_name, next_month_start, next_month_end
    );
    
    -- Create indexes
    EXECUTE format('
        CREATE INDEX IF NOT EXISTS idx_%I_company_time ON %I(company_id, timestamp_utc DESC);
        CREATE INDEX IF NOT EXISTS idx_%I_user_time ON %I(client_user_id, timestamp_utc DESC) WHERE client_user_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_%I_cost ON %I(company_id, total_cost DESC) WHERE total_cost > 0;',
        partition_name, partition_name,
        partition_name, partition_name,
        partition_name, partition_name
    );
END;
$$ LANGUAGE plpgsql;

-- Function to populate hourly analytics
CREATE OR REPLACE FUNCTION populate_hourly_analytics(p_hour TIMESTAMPTZ DEFAULT date_trunc('hour', NOW() - INTERVAL '1 hour'))
RETURNS void AS $$
BEGIN
    INSERT INTO user_analytics_hourly (
        hour_bucket, company_id, client_user_id, vendor_id, model_id,
        request_count, success_count, error_count,
        total_tokens, total_cost,
        avg_latency_ms, p95_latency_ms, p99_latency_ms,
        unique_sessions, unique_ips
    )
    SELECT 
        p_hour,
        r.company_id,
        r.client_user_id,
        r.vendor_id,
        r.model_id,
        COUNT(*) as request_count,
        COUNT(*) FILTER (WHERE r.success = true) as success_count,
        COUNT(*) FILTER (WHERE r.success = false) as error_count,
        SUM(r.total_tokens) as total_tokens,
        SUM(r.total_cost) as total_cost,
        AVG(r.total_latency_ms)::NUMERIC(8,2) as avg_latency_ms,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY r.total_latency_ms)::INTEGER as p95_latency_ms,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY r.total_latency_ms)::INTEGER as p99_latency_ms,
        COUNT(DISTINCT r.user_session_id) as unique_sessions,
        COUNT(DISTINCT r.ip_address) as unique_ips
    FROM requests r
    WHERE r.timestamp_utc >= p_hour 
      AND r.timestamp_utc < p_hour + INTERVAL '1 hour'
      AND r.client_user_id IS NOT NULL
    GROUP BY r.company_id, r.client_user_id, r.vendor_id, r.model_id
    ON CONFLICT (hour_bucket, company_id, client_user_id, vendor_id, model_id) 
    DO UPDATE SET
        request_count = EXCLUDED.request_count,
        success_count = EXCLUDED.success_count,
        error_count = EXCLUDED.error_count,
        total_tokens = EXCLUDED.total_tokens,
        total_cost = EXCLUDED.total_cost,
        avg_latency_ms = EXCLUDED.avg_latency_ms,
        p95_latency_ms = EXCLUDED.p95_latency_ms,
        p99_latency_ms = EXCLUDED.p99_latency_ms,
        unique_sessions = EXCLUDED.unique_sessions,
        unique_ips = EXCLUDED.unique_ips,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- Function to populate daily analytics with ranking
CREATE OR REPLACE FUNCTION populate_daily_analytics(p_date DATE DEFAULT CURRENT_DATE - 1)
RETURNS void AS $$
BEGIN
    -- First, aggregate the data
    WITH daily_stats AS (
        SELECT 
            p_date as date,
            r.company_id,
            r.client_user_id,
            COUNT(*) as total_requests,
            SUM(r.total_tokens) as total_tokens,
            SUM(r.total_cost) as total_cost,
            AVG(r.total_latency_ms)::NUMERIC(8,2) as avg_latency_ms,
            (COUNT(*) FILTER (WHERE r.success = false)::FLOAT / NULLIF(COUNT(*), 0) * 100)::NUMERIC(5,2) as error_rate,
            COUNT(DISTINCT DATE_TRUNC('hour', r.timestamp_utc)) as active_hours,
            COUNT(DISTINCT r.user_session_id) as unique_sessions,
            ARRAY_AGG(DISTINCT r.country) FILTER (WHERE r.country IS NOT NULL) as countries,
            JSONB_OBJECT_AGG(
                r.model_id::TEXT,
                JSONB_BUILD_OBJECT(
                    'requests', COUNT(*),
                    'tokens', SUM(r.total_tokens),
                    'cost', SUM(r.total_cost)
                )
            ) as model_usage
        FROM requests r
        WHERE DATE(r.timestamp_utc) = p_date
          AND r.client_user_id IS NOT NULL
        GROUP BY r.company_id, r.client_user_id
    ),
    ranked_stats AS (
        SELECT 
            *,
            RANK() OVER (PARTITION BY company_id ORDER BY total_cost DESC) as cost_rank_in_company,
            PERCENT_RANK() OVER (PARTITION BY company_id ORDER BY total_cost) * 100 as cost_percentile
        FROM daily_stats
    )
    INSERT INTO user_analytics_daily (
        date, company_id, client_user_id,
        total_requests, total_tokens, total_cost,
        model_usage, avg_latency_ms, error_rate,
        active_hours, unique_sessions, countries,
        cost_rank_in_company, cost_percentile
    )
    SELECT * FROM ranked_stats
    ON CONFLICT (date, company_id, client_user_id) 
    DO UPDATE SET
        total_requests = EXCLUDED.total_requests,
        total_tokens = EXCLUDED.total_tokens,
        total_cost = EXCLUDED.total_cost,
        model_usage = EXCLUDED.model_usage,
        avg_latency_ms = EXCLUDED.avg_latency_ms,
        error_rate = EXCLUDED.error_rate,
        active_hours = EXCLUDED.active_hours,
        unique_sessions = EXCLUDED.unique_sessions,
        countries = EXCLUDED.countries,
        cost_rank_in_company = EXCLUDED.cost_rank_in_company,
        cost_percentile = EXCLUDED.cost_percentile,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- Function to detect cost anomalies
CREATE OR REPLACE FUNCTION detect_cost_anomalies(p_company_id UUID DEFAULT NULL)
RETURNS void AS $$
BEGIN
    -- Detect hourly spikes (>3x normal)
    INSERT INTO cost_anomalies (
        company_id, client_user_id, anomaly_type,
        expected_value, actual_value, deviation_percentage,
        time_window, details
    )
    WITH hourly_baseline AS (
        SELECT 
            company_id,
            client_user_id,
            AVG(total_cost) as avg_hourly_cost,
            STDDEV(total_cost) as stddev_cost
        FROM user_analytics_hourly
        WHERE hour_bucket >= NOW() - INTERVAL '7 days'
          AND hour_bucket < NOW() - INTERVAL '1 hour'
          AND (p_company_id IS NULL OR company_id = p_company_id)
        GROUP BY company_id, client_user_id
        HAVING COUNT(*) >= 24 -- At least 24 hours of data
    ),
    recent_hour AS (
        SELECT 
            company_id,
            client_user_id,
            total_cost,
            request_count
        FROM user_analytics_hourly
        WHERE hour_bucket = date_trunc('hour', NOW() - INTERVAL '1 hour')
          AND (p_company_id IS NULL OR company_id = p_company_id)
    )
    SELECT 
        rh.company_id,
        rh.client_user_id,
        'spike',
        hb.avg_hourly_cost,
        rh.total_cost,
        ((rh.total_cost - hb.avg_hourly_cost) / NULLIF(hb.avg_hourly_cost, 0) * 100)::NUMERIC(8,2),
        'hourly',
        JSONB_BUILD_OBJECT(
            'request_count', rh.request_count,
            'baseline_avg', hb.avg_hourly_cost,
            'baseline_stddev', hb.stddev_cost
        )
    FROM recent_hour rh
    JOIN hourly_baseline hb ON rh.company_id = hb.company_id 
        AND rh.client_user_id = hb.client_user_id
    WHERE rh.total_cost > hb.avg_hourly_cost + (3 * COALESCE(hb.stddev_cost, hb.avg_hourly_cost))
    ON CONFLICT DO NOTHING;
END;
$$ LANGUAGE plpgsql;

-- Function to generate secure API key
CREATE OR REPLACE FUNCTION generate_api_key(
    p_company_id UUID,
    p_name VARCHAR,
    p_environment VARCHAR DEFAULT 'production',
    p_created_by VARCHAR DEFAULT NULL
)
RETURNS TABLE(key_id UUID, api_key TEXT) AS $$
DECLARE
    v_key_id UUID;
    v_api_key TEXT;
    v_key_prefix TEXT;
    v_key_hash TEXT;
BEGIN
    -- Generate a secure random key
    v_api_key := 'sk_' || p_environment || '_' || encode(gen_random_bytes(32), 'hex');
    v_key_prefix := substring(v_api_key, 1, 12) || '...';
    v_key_hash := encode(digest(v_api_key, 'sha256'), 'hex');
    
    -- Insert the key
    INSERT INTO api_keys (
        company_id, key_hash, key_prefix, name, 
        environment, created_by
    ) VALUES (
        p_company_id, v_key_hash, v_key_prefix, p_name,
        p_environment, p_created_by
    ) RETURNING id INTO v_key_id;
    
    RETURN QUERY SELECT v_key_id, v_api_key;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Performance Optimization Triggers
-- ============================================================================

-- Trigger to update user stats on request insert
CREATE OR REPLACE FUNCTION update_user_stats_trigger()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.client_user_id IS NOT NULL THEN
        UPDATE client_users
        SET 
            last_seen_at = NEW.timestamp_utc,
            total_requests = total_requests + 1,
            total_cost_usd = total_cost_usd + NEW.total_cost
        WHERE id = NEW.client_user_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_user_stats
AFTER INSERT ON requests
FOR EACH ROW
EXECUTE FUNCTION update_user_stats_trigger();