-- Migration 005: Worker Logging System
-- Creates tables for storing logs from Cloudflare Workers proxy

-- Request logs table for Workers proxy
CREATE TABLE IF NOT EXISTS worker_request_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id VARCHAR(255) UNIQUE NOT NULL,
    company_id UUID NOT NULL,
    batch_id VARCHAR(255),
    
    -- Request metadata
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    method VARCHAR(10) NOT NULL,
    url TEXT NOT NULL,
    vendor VARCHAR(50) NOT NULL,
    model VARCHAR(100),
    endpoint VARCHAR(255),
    
    -- Response metadata
    status_code INTEGER NOT NULL,
    success BOOLEAN NOT NULL DEFAULT false,
    error_message TEXT,
    error_code VARCHAR(50),
    error_type VARCHAR(50),
    
    -- Performance metrics
    total_latency INTEGER NOT NULL DEFAULT 0, -- milliseconds
    vendor_latency INTEGER,
    processing_latency INTEGER,
    queue_time INTEGER,
    
    -- Usage tracking
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost DECIMAL(12,6) DEFAULT 0,
    
    -- Client information
    ip_address VARCHAR(45),
    country VARCHAR(10),
    region VARCHAR(50),
    city VARCHAR(100),
    user_agent TEXT,
    
    -- Cache information
    cache_hit BOOLEAN DEFAULT false,
    cache_key VARCHAR(255),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Performance metrics table for Workers proxy
CREATE TABLE IF NOT EXISTS worker_performance_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id VARCHAR(255) NOT NULL,
    company_id UUID NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Latency breakdown (in milliseconds)
    total_latency INTEGER NOT NULL DEFAULT 0,
    vendor_latency INTEGER DEFAULT 0,
    auth_latency INTEGER DEFAULT 0,
    ratelimit_latency INTEGER DEFAULT 0,
    cost_latency INTEGER DEFAULT 0,
    logging_latency INTEGER DEFAULT 0,
    
    -- Request outcome
    success BOOLEAN NOT NULL DEFAULT false,
    error_type VARCHAR(50),
    retry_count INTEGER DEFAULT 0,
    
    -- Resource usage
    memory_usage INTEGER, -- bytes
    cpu_time INTEGER, -- milliseconds
    bytes_in INTEGER DEFAULT 0,
    bytes_out INTEGER DEFAULT 0,
    connection_reused BOOLEAN,
    
    -- Cache metrics
    cache_hit_rate DECIMAL(5,2),
    cache_latency INTEGER,
    
    -- Rate limiting
    rate_limit_remaining INTEGER,
    rate_limit_reset TIMESTAMP WITH TIME ZONE,
    
    -- Queue metrics
    queue_depth INTEGER,
    queue_wait_time INTEGER,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- System events table for Workers proxy
CREATE TABLE IF NOT EXISTS worker_system_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id VARCHAR(255) NOT NULL,
    company_id UUID,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Event classification
    event_type VARCHAR(100) NOT NULL,
    success BOOLEAN,
    severity VARCHAR(20) DEFAULT 'info', -- debug, info, warn, error, critical
    
    -- Event details
    details JSONB DEFAULT '{}',
    error_message TEXT,
    stack_trace TEXT,
    
    -- Request context
    method VARCHAR(10),
    url TEXT,
    ip_address VARCHAR(45),
    user_agent TEXT,
    path VARCHAR(255),
    
    -- Component information
    component VARCHAR(100),
    function_name VARCHAR(100),
    vendor VARCHAR(50),
    model VARCHAR(100),
    
    -- Recovery information
    recovered BOOLEAN DEFAULT false,
    recovery_action TEXT,
    retry_attempt INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Request metadata table for detailed request information
CREATE TABLE IF NOT EXISTS worker_request_metadata (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id VARCHAR(255) NOT NULL,
    
    -- Request details
    headers JSONB DEFAULT '{}',
    request_body_hash VARCHAR(64),
    request_body_size INTEGER DEFAULT 0,
    content_type VARCHAR(100),
    
    -- Response details
    response_headers JSONB DEFAULT '{}',
    response_body_hash VARCHAR(64),
    response_body_size INTEGER DEFAULT 0,
    response_content_type VARCHAR(100),
    
    -- Geographical data
    timezone VARCHAR(50),
    
    -- Additional metadata
    origin VARCHAR(255),
    referer TEXT,
    api_key_id VARCHAR(255),
    user_id VARCHAR(255),
    features JSONB DEFAULT '[]',
    experiments JSONB DEFAULT '{}',
    custom_metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_worker_request_logs_company_id ON worker_request_logs(company_id);
CREATE INDEX IF NOT EXISTS idx_worker_request_logs_timestamp ON worker_request_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_worker_request_logs_vendor ON worker_request_logs(vendor);
CREATE INDEX IF NOT EXISTS idx_worker_request_logs_success ON worker_request_logs(success);
CREATE INDEX IF NOT EXISTS idx_worker_request_logs_request_id ON worker_request_logs(request_id);
CREATE INDEX IF NOT EXISTS idx_worker_request_logs_batch_id ON worker_request_logs(batch_id);

CREATE INDEX IF NOT EXISTS idx_worker_performance_metrics_company_id ON worker_performance_metrics(company_id);
CREATE INDEX IF NOT EXISTS idx_worker_performance_metrics_timestamp ON worker_performance_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_worker_performance_metrics_success ON worker_performance_metrics(success);
CREATE INDEX IF NOT EXISTS idx_worker_performance_metrics_request_id ON worker_performance_metrics(request_id);

CREATE INDEX IF NOT EXISTS idx_worker_system_events_company_id ON worker_system_events(company_id);
CREATE INDEX IF NOT EXISTS idx_worker_system_events_timestamp ON worker_system_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_worker_system_events_event_type ON worker_system_events(event_type);
CREATE INDEX IF NOT EXISTS idx_worker_system_events_severity ON worker_system_events(severity);
CREATE INDEX IF NOT EXISTS idx_worker_system_events_request_id ON worker_system_events(request_id);

CREATE INDEX IF NOT EXISTS idx_worker_request_metadata_request_id ON worker_request_metadata(request_id);

-- Create composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_worker_request_logs_company_timestamp ON worker_request_logs(company_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_worker_request_logs_vendor_timestamp ON worker_request_logs(vendor, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_worker_request_logs_success_timestamp ON worker_request_logs(success, timestamp DESC);

-- Create trigger to update updated_at column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_worker_request_logs_updated_at 
    BEFORE UPDATE ON worker_request_logs 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_worker_performance_metrics_updated_at 
    BEFORE UPDATE ON worker_performance_metrics 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE worker_request_logs IS 'Stores request logs from Cloudflare Workers proxy';
COMMENT ON TABLE worker_performance_metrics IS 'Stores performance metrics for Workers proxy requests';
COMMENT ON TABLE worker_system_events IS 'Stores system events and errors from Workers proxy';
COMMENT ON TABLE worker_request_metadata IS 'Stores detailed metadata for requests processed by Workers proxy';

COMMENT ON COLUMN worker_request_logs.request_id IS 'Unique identifier for the request generated by Workers';
COMMENT ON COLUMN worker_request_logs.batch_id IS 'Batch identifier for bulk logging operations';
COMMENT ON COLUMN worker_request_logs.total_latency IS 'Total request processing time in milliseconds';
COMMENT ON COLUMN worker_request_logs.vendor_latency IS 'Time spent waiting for vendor API response in milliseconds';
COMMENT ON COLUMN worker_request_logs.cost IS 'Calculated cost for the request in USD';

COMMENT ON COLUMN worker_performance_metrics.queue_depth IS 'Number of requests in processing queue';
COMMENT ON COLUMN worker_performance_metrics.cache_hit_rate IS 'Cache hit rate as percentage (0-100)';

COMMENT ON COLUMN worker_system_events.event_type IS 'Type of system event (auth_failure, rate_limit_exceeded, etc.)';
COMMENT ON COLUMN worker_system_events.severity IS 'Event severity level (debug, info, warn, error, critical)';