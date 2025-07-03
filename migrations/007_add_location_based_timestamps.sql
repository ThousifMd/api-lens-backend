-- Migration 007: Add Location-Based Timestamp Columns
-- Adds timezone-aware local timestamp columns based on IP geolocation
-- SAFE: Only adds new columns, doesn't modify existing ones

BEGIN;

-- Add location-based timezone information to requests table
-- This is the most critical table since it has IP addresses
ALTER TABLE requests 
ADD COLUMN IF NOT EXISTS detected_timezone VARCHAR(50),
ADD COLUMN IF NOT EXISTS detected_country_code CHAR(2),
ADD COLUMN IF NOT EXISTS timestamp_local_detected TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS created_at_local_detected TIMESTAMP WITH TIME ZONE;

-- Add comment to explain the new columns
COMMENT ON COLUMN requests.detected_timezone IS 'Timezone detected from IP geolocation (e.g. America/New_York)';
COMMENT ON COLUMN requests.detected_country_code IS 'ISO 3166-1 alpha-2 country code from IP geolocation';
COMMENT ON COLUMN requests.timestamp_local_detected IS 'Request timestamp converted to detected local timezone';
COMMENT ON COLUMN requests.created_at_local_detected IS 'Record creation time in detected local timezone';

-- Add location-based timezone information to user_sessions table
-- Since sessions track user activity and have IP data
ALTER TABLE user_sessions
ADD COLUMN IF NOT EXISTS detected_timezone VARCHAR(50),
ADD COLUMN IF NOT EXISTS detected_country_code CHAR(2),
ADD COLUMN IF NOT EXISTS started_at_local_detected TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS ended_at_local_detected TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS last_activity_local_detected TIMESTAMP WITH TIME ZONE;

-- Add comments
COMMENT ON COLUMN user_sessions.detected_timezone IS 'Timezone detected from session IP geolocation';
COMMENT ON COLUMN user_sessions.detected_country_code IS 'Country code from IP geolocation';
COMMENT ON COLUMN user_sessions.started_at_local_detected IS 'Session start time in detected local timezone';
COMMENT ON COLUMN user_sessions.ended_at_local_detected IS 'Session end time in detected local timezone';
COMMENT ON COLUMN user_sessions.last_activity_local_detected IS 'Last activity time in detected local timezone';

-- Add location-based timezone information to client_users table
-- To track when users were first/last seen in their local time
ALTER TABLE client_users
ADD COLUMN IF NOT EXISTS detected_timezone VARCHAR(50),
ADD COLUMN IF NOT EXISTS detected_country_code CHAR(2),
ADD COLUMN IF NOT EXISTS first_seen_local_detected TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS last_seen_local_detected TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS created_at_local_detected TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS updated_at_local_detected TIMESTAMP WITH TIME ZONE;

-- Add comments
COMMENT ON COLUMN client_users.detected_timezone IS 'Primary timezone detected for this user';
COMMENT ON COLUMN client_users.detected_country_code IS 'Primary country for this user';
COMMENT ON COLUMN client_users.first_seen_local_detected IS 'First seen time in user local timezone';
COMMENT ON COLUMN client_users.last_seen_local_detected IS 'Last seen time in user local timezone';
COMMENT ON COLUMN client_users.created_at_local_detected IS 'User creation time in local timezone';
COMMENT ON COLUMN client_users.updated_at_local_detected IS 'Last update time in local timezone';

-- Add location-based timezone information to analytics tables
-- For better reporting in user local times
ALTER TABLE user_analytics_hourly
ADD COLUMN IF NOT EXISTS user_timezone VARCHAR(50),
ADD COLUMN IF NOT EXISTS user_country_code CHAR(2),
ADD COLUMN IF NOT EXISTS hour_bucket_user_local TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS created_at_user_local TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS updated_at_user_local TIMESTAMP WITH TIME ZONE;

-- Add comments
COMMENT ON COLUMN user_analytics_hourly.user_timezone IS 'User timezone for this analytics record';
COMMENT ON COLUMN user_analytics_hourly.user_country_code IS 'User country for this analytics record';
COMMENT ON COLUMN user_analytics_hourly.hour_bucket_user_local IS 'Hour bucket in user local timezone';
COMMENT ON COLUMN user_analytics_hourly.created_at_user_local IS 'Record creation in user local timezone';
COMMENT ON COLUMN user_analytics_hourly.updated_at_user_local IS 'Record update in user local timezone';

ALTER TABLE user_analytics_daily
ADD COLUMN IF NOT EXISTS user_timezone VARCHAR(50),
ADD COLUMN IF NOT EXISTS user_country_code CHAR(2),
ADD COLUMN IF NOT EXISTS date_user_local DATE,
ADD COLUMN IF NOT EXISTS created_at_user_local TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS updated_at_user_local TIMESTAMP WITH TIME ZONE;

-- Add comments
COMMENT ON COLUMN user_analytics_daily.user_timezone IS 'User timezone for this analytics record';
COMMENT ON COLUMN user_analytics_daily.user_country_code IS 'User country for this analytics record';
COMMENT ON COLUMN user_analytics_daily.date_user_local IS 'Date in user local timezone';
COMMENT ON COLUMN user_analytics_daily.created_at_user_local IS 'Record creation in user local timezone';
COMMENT ON COLUMN user_analytics_daily.updated_at_user_local IS 'Record update in user local timezone';

-- Create indexes for better performance on timezone queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_requests_detected_timezone 
ON requests(detected_timezone) WHERE detected_timezone IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_requests_detected_country 
ON requests(detected_country_code) WHERE detected_country_code IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_requests_timestamp_local_detected 
ON requests(timestamp_local_detected) WHERE timestamp_local_detected IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_sessions_detected_timezone 
ON user_sessions(detected_timezone) WHERE detected_timezone IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_client_users_detected_timezone 
ON client_users(detected_timezone) WHERE detected_timezone IS NOT NULL;

-- Create a function to convert UTC timestamp to detected timezone
CREATE OR REPLACE FUNCTION convert_to_detected_timezone(
    utc_timestamp TIMESTAMP WITH TIME ZONE,
    timezone_name TEXT
) RETURNS TIMESTAMP WITH TIME ZONE AS $$
BEGIN
    -- If timezone is provided and valid, convert
    IF timezone_name IS NOT NULL AND timezone_name != '' THEN
        BEGIN
            RETURN utc_timestamp AT TIME ZONE timezone_name;
        EXCEPTION WHEN OTHERS THEN
            -- If timezone conversion fails, return UTC
            RETURN utc_timestamp;
        END;
    END IF;
    
    -- Default to UTC if no timezone provided
    RETURN utc_timestamp;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Create a function to detect timezone from country code (fallback)
CREATE OR REPLACE FUNCTION get_default_timezone_for_country(country_code TEXT) 
RETURNS TEXT AS $$
BEGIN
    -- Common timezone mappings for major countries
    CASE country_code
        WHEN 'US' THEN RETURN 'America/New_York';
        WHEN 'CA' THEN RETURN 'America/Toronto';
        WHEN 'GB' THEN RETURN 'Europe/London';
        WHEN 'DE' THEN RETURN 'Europe/Berlin';
        WHEN 'FR' THEN RETURN 'Europe/Paris';
        WHEN 'JP' THEN RETURN 'Asia/Tokyo';
        WHEN 'AU' THEN RETURN 'Australia/Sydney';
        WHEN 'IN' THEN RETURN 'Asia/Kolkata';
        WHEN 'CN' THEN RETURN 'Asia/Shanghai';
        WHEN 'BR' THEN RETURN 'America/Sao_Paulo';
        WHEN 'MX' THEN RETURN 'America/Mexico_City';
        WHEN 'RU' THEN RETURN 'Europe/Moscow';
        WHEN 'ZA' THEN RETURN 'Africa/Johannesburg';
        WHEN 'EG' THEN RETURN 'Africa/Cairo';
        WHEN 'NG' THEN RETURN 'Africa/Lagos';
        WHEN 'SG' THEN RETURN 'Asia/Singapore';
        WHEN 'KR' THEN RETURN 'Asia/Seoul';
        WHEN 'TH' THEN RETURN 'Asia/Bangkok';
        WHEN 'ID' THEN RETURN 'Asia/Jakarta';
        WHEN 'PH' THEN RETURN 'Asia/Manila';
        WHEN 'VN' THEN RETURN 'Asia/Ho_Chi_Minh';
        WHEN 'MY' THEN RETURN 'Asia/Kuala_Lumpur';
        WHEN 'NZ' THEN RETURN 'Pacific/Auckland';
        WHEN 'AR' THEN RETURN 'America/Argentina/Buenos_Aires';
        WHEN 'CL' THEN RETURN 'America/Santiago';
        WHEN 'CO' THEN RETURN 'America/Bogota';
        WHEN 'PE' THEN RETURN 'America/Lima';
        WHEN 'VE' THEN RETURN 'America/Caracas';
        WHEN 'AE' THEN RETURN 'Asia/Dubai';
        WHEN 'SA' THEN RETURN 'Asia/Riyadh';
        WHEN 'IL' THEN RETURN 'Asia/Jerusalem';
        WHEN 'TR' THEN RETURN 'Europe/Istanbul';
        WHEN 'IT' THEN RETURN 'Europe/Rome';
        WHEN 'ES' THEN RETURN 'Europe/Madrid';
        WHEN 'NL' THEN RETURN 'Europe/Amsterdam';
        WHEN 'CH' THEN RETURN 'Europe/Zurich';
        WHEN 'SE' THEN RETURN 'Europe/Stockholm';
        WHEN 'NO' THEN RETURN 'Europe/Oslo';
        WHEN 'DK' THEN RETURN 'Europe/Copenhagen';
        WHEN 'FI' THEN RETURN 'Europe/Helsinki';
        WHEN 'PL' THEN RETURN 'Europe/Warsaw';
        WHEN 'AT' THEN RETURN 'Europe/Vienna';
        WHEN 'BE' THEN RETURN 'Europe/Brussels';
        WHEN 'PT' THEN RETURN 'Europe/Lisbon';
        WHEN 'GR' THEN RETURN 'Europe/Athens';
        WHEN 'IE' THEN RETURN 'Europe/Dublin';
        ELSE RETURN 'UTC';
    END CASE;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Record migration
INSERT INTO schema_migrations (version, name, applied_at) 
VALUES ('007', 'add_location_based_timestamps', NOW())
ON CONFLICT (version) DO NOTHING;

COMMIT;

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✅ Migration 007 completed successfully!';
    RAISE NOTICE '📍 Added location-based timezone columns to tables:';
    RAISE NOTICE '   - requests (4 new columns)';
    RAISE NOTICE '   - user_sessions (5 new columns)';
    RAISE NOTICE '   - client_users (6 new columns)';
    RAISE NOTICE '   - user_analytics_hourly (5 new columns)';
    RAISE NOTICE '   - user_analytics_daily (5 new columns)';
    RAISE NOTICE '🔧 Added timezone conversion functions';
    RAISE NOTICE '⚡ Added performance indexes';
    RAISE NOTICE '🛡️  Migration is backwards compatible - existing functionality unchanged';
END $$;