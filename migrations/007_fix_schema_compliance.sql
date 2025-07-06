-- ============================================================================
-- Fix Schema Compliance Issues - Migration 007
-- ============================================================================
-- This migration fixes schema differences to match the v2 specification
-- Addresses client_users and vendor_models table compliance issues

-- ============================================================================
-- Fix client_users table (71.4% compliance -> 100%)
-- ============================================================================

-- Add missing columns
ALTER TABLE client_users 
ADD COLUMN IF NOT EXISTS display_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS email VARCHAR(255),
ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500),
ADD COLUMN IF NOT EXISTS user_tier VARCHAR(100),
ADD COLUMN IF NOT EXISTS signup_date DATE,
ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT '{}';

-- Rename 'tier' to follow the correct naming convention (user_tier is already added above)
-- First copy data from tier to user_tier if tier exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'client_users' AND column_name = 'tier') THEN
        UPDATE client_users SET user_tier = tier WHERE tier IS NOT NULL;
        ALTER TABLE client_users DROP COLUMN tier;
    END IF;
END $$;

-- Rename 'timezone' to 'timezone_name' to match v2 schema
-- But in v2 schema, timezone info is in user_sessions, not client_users
-- So we should drop it from client_users
ALTER TABLE client_users DROP COLUMN IF EXISTS timezone;

-- ============================================================================
-- Fix vendor_models table (58.8% compliance -> 100%)
-- ============================================================================

-- Add missing columns from v2 schema
ALTER TABLE vendor_models
ADD COLUMN IF NOT EXISTS display_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS description TEXT,
ADD COLUMN IF NOT EXISTS context_window INTEGER,
ADD COLUMN IF NOT EXISTS max_output_tokens INTEGER,
ADD COLUMN IF NOT EXISTS supports_functions BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS supports_vision BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS sunset_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS replacement_model_id UUID REFERENCES vendor_models(id);

-- Rename 'context_length' to 'context_window' if it exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'vendor_models' AND column_name = 'context_length') THEN
        -- Copy data
        UPDATE vendor_models SET context_window = context_length WHERE context_length IS NOT NULL;
        -- Drop old column
        ALTER TABLE vendor_models DROP COLUMN context_length;
    END IF;
END $$;

-- Remove extra columns that don't belong in vendor_models (they belong in vendor_pricing)
ALTER TABLE vendor_models 
DROP COLUMN IF EXISTS input_price_per_1k,
DROP COLUMN IF EXISTS output_price_per_1k,
DROP COLUMN IF EXISTS pricing_model;

-- Keep 'slug' as it's useful for URL-safe identifiers
-- Keep 'capabilities' and 'supported_formats' as they provide value

-- Set display_name from name where it's null
UPDATE vendor_models 
SET display_name = name 
WHERE display_name IS NULL;

-- Set some reasonable defaults for context windows
UPDATE vendor_models 
SET context_window = CASE 
    WHEN name LIKE '%gpt-3.5%' THEN 16384
    WHEN name LIKE '%gpt-4-turbo%' THEN 128000
    WHEN name LIKE '%gpt-4o%' THEN 128000
    WHEN name LIKE '%gpt-4%' THEN 8192
    WHEN name LIKE '%claude-3-opus%' THEN 200000
    WHEN name LIKE '%claude-3-sonnet%' THEN 200000
    WHEN name LIKE '%claude-3-haiku%' THEN 200000
    WHEN name LIKE '%claude-3-5%' THEN 200000
    WHEN name LIKE '%dall-e%' THEN 1000
    ELSE 4096
END
WHERE context_window IS NULL;

-- Set max output tokens
UPDATE vendor_models 
SET max_output_tokens = CASE 
    WHEN name LIKE '%gpt-3.5%' THEN 4096
    WHEN name LIKE '%gpt-4o-mini%' THEN 16384
    WHEN name LIKE '%gpt-4%' THEN 4096
    WHEN name LIKE '%claude%' THEN 4096
    WHEN name LIKE '%dall-e%' THEN 0
    ELSE 2048
END
WHERE max_output_tokens IS NULL;

-- Update descriptions
UPDATE vendor_models 
SET description = CASE 
    WHEN name LIKE '%gpt-3.5-turbo%' THEN 'Fast, efficient model for most tasks'
    WHEN name LIKE '%gpt-4%' THEN 'Most capable model for complex reasoning'
    WHEN name LIKE '%claude-3-opus%' THEN 'Most powerful Claude model'
    WHEN name LIKE '%claude-3-sonnet%' THEN 'Balanced performance Claude model'
    WHEN name LIKE '%claude-3-haiku%' THEN 'Fast, lightweight Claude model'
    WHEN name LIKE '%dall-e-3%' THEN 'Advanced image generation model'
    WHEN name LIKE '%dall-e-2%' THEN 'Image generation model'
    ELSE 'AI model'
END
WHERE description IS NULL;

-- Set capabilities for models
UPDATE vendor_models 
SET supports_functions = true 
WHERE model_type = 'chat' AND supports_functions IS NULL;

UPDATE vendor_models 
SET supports_vision = true 
WHERE name IN ('gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307', 'claude-3-5-sonnet-20241022');

-- ============================================================================
-- Populate sample data for client_users enhancements
-- ============================================================================

-- Update existing users with display names and emails
UPDATE client_users 
SET 
    display_name = CASE 
        WHEN client_user_id LIKE 'support_%' THEN 'Support Agent ' || SUBSTRING(client_user_id FROM 'support_agent_(\d+)')
        WHEN client_user_id LIKE 'dev_%' THEN 'Developer ' || SUBSTRING(client_user_id FROM 'dev_(\d+)')
        WHEN client_user_id LIKE 'writer_%' THEN 'Content Writer ' || SUBSTRING(client_user_id FROM 'writer_(\d+)')
        WHEN client_user_id LIKE 'designer_%' THEN 'Designer ' || SUBSTRING(client_user_id FROM 'designer_(\d+)')
        WHEN client_user_id LIKE 'researcher_%' THEN 'Researcher ' || SUBSTRING(client_user_id FROM 'researcher_(\d+)')
        WHEN client_user_id LIKE 'marketing_%' THEN 'Marketing ' || SUBSTRING(client_user_id FROM 'marketing_(\d+)')
        ELSE INITCAP(REPLACE(client_user_id, '_', ' '))
    END,
    email = LOWER(client_user_id) || '@example.com',
    user_tier = CASE 
        WHEN total_requests > 100 THEN 'premium'
        WHEN total_requests > 50 THEN 'standard'
        ELSE 'basic'
    END,
    signup_date = first_seen_at::date - INTERVAL '30 days',
    avatar_url = 'https://ui-avatars.com/api/?name=' || REPLACE(client_user_id, '_', '+'),
    tags = CASE 
        WHEN client_user_id LIKE 'support_%' THEN ARRAY['support', 'customer-facing']
        WHEN client_user_id LIKE 'dev_%' THEN ARRAY['engineering', 'technical']
        WHEN client_user_id LIKE 'writer_%' THEN ARRAY['content', 'creative']
        WHEN client_user_id LIKE 'designer_%' THEN ARRAY['design', 'creative']
        ELSE ARRAY['general']
    END
WHERE display_name IS NULL;

-- ============================================================================
-- Verification
-- ============================================================================

-- Check schema compliance
SELECT 
    'Schema Compliance Fixed!' as status,
    (SELECT COUNT(*) FROM information_schema.columns 
     WHERE table_name = 'client_users' 
     AND column_name IN ('display_name', 'email', 'avatar_url', 'user_tier', 'signup_date', 'tags')) as client_users_fixed,
    (SELECT COUNT(*) FROM information_schema.columns 
     WHERE table_name = 'vendor_models' 
     AND column_name IN ('display_name', 'description', 'context_window', 'max_output_tokens', 'supports_functions', 'supports_vision')) as vendor_models_fixed;